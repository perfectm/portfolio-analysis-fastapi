from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Annotated
import logging
import pandas as pd
from database import get_db
from margin_service import MarginService
from auth_middleware import get_current_user
from models import User
from config import DEFAULT_STARTING_CAPITAL

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/bulk-upload")
async def bulk_upload_margin_files(
    files: List[UploadFile] = File(...),
    starting_capital: float = Form(DEFAULT_STARTING_CAPITAL),
    max_margin_percent: float = Form(0.85),
    db: Annotated[Session, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None
):
    """
    Bulk upload margin requirement files for existing portfolios
    """
    try:
        logger.info(f"[MARGIN UPLOAD] Received {len(files)} margin files from user {current_user.username}")
        logger.info(f"[MARGIN UPLOAD] Parameters: starting_capital=${starting_capital:,.2f}, max_margin_percent={max_margin_percent*100}%")
        
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        # Initialize default validation rules if needed
        MarginService.initialize_default_validation_rules(db)
        
        processed_files = []
        failed_files = []
        matched_portfolios = []
        
        for file in files:
            try:
                logger.info(f"[MARGIN UPLOAD] Processing file: {file.filename}")
                
                # Read the file contents
                contents = await file.read()
                df = pd.read_csv(pd.io.common.BytesIO(contents))
                logger.info(f"[MARGIN UPLOAD] Read CSV with shape {df.shape} for {file.filename}")
                
                # Try to match this margin file to an existing portfolio
                portfolio = MarginService.match_portfolio_by_filename(db, file.filename)
                
                if not portfolio:
                    failed_files.append({
                        "filename": file.filename,
                        "error": "Could not match to any existing portfolio"
                    })
                    logger.warning(f"[MARGIN UPLOAD] Could not match {file.filename} to any portfolio")
                    continue
                
                # Clean the margin data
                try:
                    clean_margin_df = MarginService._clean_margin_data(df)
                    logger.info(f"[MARGIN UPLOAD] Cleaned margin data for {file.filename}: {len(clean_margin_df)} records")
                except Exception as clean_error:
                    failed_files.append({
                        "filename": file.filename,
                        "error": f"Error cleaning margin data: {str(clean_error)}"
                    })
                    logger.error(f"[MARGIN UPLOAD] Error cleaning margin data for {file.filename}: {clean_error}")
                    continue
                
                # Store margin data
                success = MarginService.store_margin_data(db, portfolio.id, clean_margin_df)
                
                if success:
                    # Calculate daily aggregated statistics
                    daily_totals = clean_margin_df.groupby('Date')['Margin Requirement'].sum()
                    
                    processed_files.append({
                        "filename": file.filename,
                        "portfolio_id": portfolio.id,
                        "portfolio_name": portfolio.name,
                        "margin_records": len(clean_margin_df),
                        "date_range": {
                            "start": clean_margin_df['Date'].min().isoformat(),
                            "end": clean_margin_df['Date'].max().isoformat()
                        },
                        "margin_range": {
                            "min": float(daily_totals.min()),
                            "max": float(daily_totals.max()),
                            "average": float(daily_totals.mean())
                        },
                        "daily_stats": {
                            "total_trading_days": len(daily_totals),
                            "records_per_day": len(clean_margin_df) / len(daily_totals)
                        }
                    })
                    matched_portfolios.append(portfolio.id)
                    logger.info(f"[MARGIN UPLOAD] Successfully processed {file.filename} for portfolio {portfolio.name}")
                else:
                    failed_files.append({
                        "filename": file.filename,
                        "error": "Failed to store margin data in database"
                    })
                
            except Exception as e:
                failed_files.append({
                    "filename": file.filename,
                    "error": f"Error processing file: {str(e)}"
                })
                logger.error(f"[MARGIN UPLOAD] Error processing {file.filename}: {e}")
        
        # Calculate daily margin aggregates if any files were processed
        aggregation_result = None
        if processed_files:
            logger.info(f"[MARGIN UPLOAD] Calculating daily margin aggregates for {len(processed_files)} processed files")
            aggregation_result = MarginService.calculate_daily_margin_aggregates(
                db, starting_capital, max_margin_percent
            )
        
        response = {
            "success": True,
            "message": f"Processed {len(processed_files)} of {len(files)} margin files",
            "processed_files": len(processed_files),
            "failed_files": len(failed_files),
            "files_detail": {
                "processed": processed_files,
                "failed": failed_files
            },
            "aggregation_result": aggregation_result
        }
        
        logger.info(f"[MARGIN UPLOAD] Bulk upload complete: {len(processed_files)} successful, {len(failed_files)} failed")
        return response
        
    except Exception as e:
        logger.error(f"[MARGIN UPLOAD] Unexpected error in bulk upload: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing margin files: {str(e)}")

@router.get("/summary")
async def get_margin_summary(
    db: Annotated[Session, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None
):
    """
    Get margin requirements summary and statistics
    """
    try:
        summary_stats = MarginService.get_margin_summary_stats(db)
        violations = MarginService.get_margin_violations(db, limit=10)
        
        return {
            "success": True,
            "summary": summary_stats,
            "recent_violations": violations
        }
        
    except Exception as e:
        logger.error(f"[MARGIN] Error getting margin summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting margin summary: {str(e)}")

@router.get("/daily-aggregates")
async def get_daily_margin_aggregates(
    db: Annotated[Session, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    limit: int = 100,
    valid_only: bool = False
):
    """
    Get daily margin aggregates with optional filtering
    """
    try:
        from models import DailyMarginAggregate
        
        query = db.query(DailyMarginAggregate).order_by(DailyMarginAggregate.date.desc())
        
        if valid_only:
            query = query.filter(DailyMarginAggregate.is_valid == True)
        
        if limit:
            query = query.limit(limit)
        
        aggregates = query.all()
        
        return {
            "success": True,
            "count": len(aggregates),
            "aggregates": [
                {
                    "date": agg.date.isoformat(),
                    "total_margin_required": agg.total_margin_required,
                    "portfolio_count": agg.portfolio_count,
                    "starting_capital": agg.starting_capital,
                    "margin_utilization_percent": agg.margin_utilization_percent,
                    "is_valid": agg.is_valid,
                    "validation_message": agg.validation_message
                }
                for agg in aggregates
            ]
        }
        
    except Exception as e:
        logger.error(f"[MARGIN] Error getting daily aggregates: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting daily aggregates: {str(e)}")

@router.get("/portfolio/{portfolio_id}")
async def get_portfolio_margin_data(
    portfolio_id: int,
    db: Annotated[Session, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    limit: int = 1000
):
    """
    Get margin data for a specific portfolio
    """
    try:
        margin_data = MarginService.get_portfolio_margin_data(db, portfolio_id, limit)
        
        if not margin_data:
            return {
                "success": True,
                "message": "No margin data found for this portfolio",
                "portfolio_id": portfolio_id,
                "margin_data": []
            }
        
        return {
            "success": True,
            "portfolio_id": portfolio_id,
            "count": len(margin_data),
            "margin_data": [
                {
                    "date": data.date.isoformat(),
                    "margin_requirement": data.margin_requirement,
                    "margin_type": data.margin_type
                }
                for data in margin_data
            ]
        }
        
    except Exception as e:
        logger.error(f"[MARGIN] Error getting portfolio margin data: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting portfolio margin data: {str(e)}")

@router.get("/supported-formats")
async def get_supported_margin_formats(
    current_user: Annotated[User, Depends(get_current_user)] = None
):
    """
    Get information about supported margin file formats and column names
    """
    from margin_service import MARGIN_COLUMNS
    from config import DATE_COLUMNS
    
    return {
        "success": True,
        "supported_date_columns": DATE_COLUMNS,
        "supported_margin_columns": MARGIN_COLUMNS[:15],  # Show first 15 for readability
        "example_format": {
            "csv_structure": "Date,Margin Requirement,Margin Type",
            "sample_data": [
                "2024-01-01,15000,initial",
                "2024-01-02,18500,initial", 
                "2024-01-03,22000,initial"
            ]
        },
        "tips": [
            "Date columns can be: Date, Date Opened, Trade Date, Entry Date, etc.",
            "Margin columns can be: Margin, Margin Requirement, Initial Margin, etc.",
            "The system supports case-insensitive matching",
            "Files will be automatically matched to portfolios by filename"
        ]
    }

@router.get("/strategies-overview")
async def get_strategies_margin_overview(
    db: Annotated[Session, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None
):
    """
    Get all strategies with their margin data overview
    """
    try:
        from models import Portfolio, PortfolioMarginData
        from sqlalchemy import func
        
        # Get all portfolios with their strategies and margin statistics
        query = db.query(
            Portfolio.id,
            Portfolio.name,
            Portfolio.strategy,
            Portfolio.filename,
            Portfolio.upload_date,
            func.count(PortfolioMarginData.id).label('margin_records_count'),
            func.min(PortfolioMarginData.date).label('margin_date_start'),
            func.max(PortfolioMarginData.date).label('margin_date_end'),
            func.min(PortfolioMarginData.margin_requirement).label('min_margin'),
            func.max(PortfolioMarginData.margin_requirement).label('max_margin'),
            func.avg(PortfolioMarginData.margin_requirement).label('avg_margin')
        ).outerjoin(
            PortfolioMarginData, Portfolio.id == PortfolioMarginData.portfolio_id
        ).group_by(
            Portfolio.id, Portfolio.name, Portfolio.strategy, Portfolio.filename, Portfolio.upload_date
        ).order_by(
            Portfolio.strategy.nullslast(), Portfolio.name
        ).all()
        
        # Group by strategy
        strategies = {}
        total_portfolios = 0
        total_with_margin = 0
        
        for row in query:
            strategy = row.strategy or "No Strategy Set"
            if strategy not in strategies:
                strategies[strategy] = {
                    "strategy_name": strategy,
                    "portfolios": [],
                    "total_portfolios": 0,
                    "portfolios_with_margin": 0,
                    "total_margin_records": 0,
                    "strategy_margin_range": {
                        "min": None,
                        "max": None,
                        "avg": None
                    }
                }
            
            portfolio_data = {
                "id": row.id,
                "name": row.name,
                "filename": row.filename,
                "upload_date": row.upload_date.isoformat() if row.upload_date else None,
                "margin_data": {
                    "has_margin_data": row.margin_records_count > 0,
                    "records_count": row.margin_records_count or 0,
                    "date_range": {
                        "start": row.margin_date_start.isoformat() if row.margin_date_start else None,
                        "end": row.margin_date_end.isoformat() if row.margin_date_end else None
                    },
                    "margin_range": {
                        "min": float(row.min_margin) if row.min_margin else None,
                        "max": float(row.max_margin) if row.max_margin else None,
                        "avg": float(row.avg_margin) if row.avg_margin else None
                    }
                }
            }
            
            strategies[strategy]["portfolios"].append(portfolio_data)
            strategies[strategy]["total_portfolios"] += 1
            total_portfolios += 1
            
            if row.margin_records_count > 0:
                strategies[strategy]["portfolios_with_margin"] += 1
                strategies[strategy]["total_margin_records"] += row.margin_records_count
                total_with_margin += 1
                
                # Update strategy-level margin range
                if strategies[strategy]["strategy_margin_range"]["min"] is None or row.min_margin < strategies[strategy]["strategy_margin_range"]["min"]:
                    strategies[strategy]["strategy_margin_range"]["min"] = float(row.min_margin) if row.min_margin else None
                if strategies[strategy]["strategy_margin_range"]["max"] is None or row.max_margin > strategies[strategy]["strategy_margin_range"]["max"]:
                    strategies[strategy]["strategy_margin_range"]["max"] = float(row.max_margin) if row.max_margin else None
        
        # Calculate strategy-level averages
        for strategy_data in strategies.values():
            if strategy_data["portfolios_with_margin"] > 0:
                avg_values = [p["margin_data"]["margin_range"]["avg"] for p in strategy_data["portfolios"] 
                             if p["margin_data"]["margin_range"]["avg"] is not None]
                if avg_values:
                    strategy_data["strategy_margin_range"]["avg"] = sum(avg_values) / len(avg_values)
        
        return {
            "success": True,
            "summary": {
                "total_portfolios": total_portfolios,
                "portfolios_with_margin": total_with_margin,
                "strategies_count": len(strategies),
                "coverage_percentage": (total_with_margin / total_portfolios * 100) if total_portfolios > 0 else 0
            },
            "strategies": list(strategies.values())
        }
        
    except Exception as e:
        logger.error(f"[MARGIN] Error getting strategies overview: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting strategies overview: {str(e)}")

@router.post("/recalculate-aggregates") 
async def recalculate_margin_aggregates(
    starting_capital: float = Form(DEFAULT_STARTING_CAPITAL),
    max_margin_percent: float = Form(0.85),
    db: Annotated[Session, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None
):
    """
    Manually recalculate daily margin aggregates with new parameters
    """
    try:
        logger.info(f"[MARGIN] Manually recalculating aggregates with starting_capital=${starting_capital:,.2f}")
        
        result = MarginService.calculate_daily_margin_aggregates(
            db, starting_capital, max_margin_percent
        )
        
        return result
        
    except Exception as e:
        logger.error(f"[MARGIN] Error recalculating aggregates: {e}")
        raise HTTPException(status_code=500, detail=f"Error recalculating aggregates: {str(e)}")