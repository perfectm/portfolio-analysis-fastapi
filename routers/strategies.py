from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from typing import Any, Annotated
import logging
from database import get_db
from portfolio_service import PortfolioService
from auth_middleware import get_current_user
from models import User
import pandas as pd

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("")
async def get_strategies(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 100,
    include_summary: bool = True
):
    try:
        portfolios = PortfolioService.get_portfolios(db, limit=limit)
        strategies = []
        for portfolio in portfolios:
            strategy_data = {
                "id": portfolio.id,
                "name": portfolio.name,
                "filename": portfolio.filename,
                "upload_date": portfolio.upload_date.isoformat(),
                "file_size": portfolio.file_size,
                "row_count": portfolio.row_count,
                "date_range_start": portfolio.date_range_start.isoformat() if portfolio.date_range_start else None,
                "date_range_end": portfolio.date_range_end.isoformat() if portfolio.date_range_end else None,
                "file_hash": portfolio.file_hash[:16] + "..." if portfolio.file_hash else None,
                "strategy": portfolio.strategy
            }
            if include_summary:
                recent_analysis = PortfolioService.get_recent_analysis_results(
                    db, portfolio_id=portfolio.id, limit=1
                )
                if recent_analysis:
                    analysis = recent_analysis[0]
                    strategy_data["latest_analysis"] = {
                        "analysis_type": analysis.analysis_type,
                        "created_at": analysis.created_at.isoformat(),
                        "sharpe_ratio": analysis.sharpe_ratio,
                        "sortino_ratio": analysis.sortino_ratio,
                        "ulcer_index": analysis.ulcer_index,
                        "upi": analysis.upi,
                        "kelly_criterion": analysis.kelly_criterion,
                        "mar_ratio": analysis.mar_ratio,
                        "cagr": analysis.cagr,
                        "annual_volatility": analysis.annual_volatility,
                        "total_return": analysis.total_return,
                        "max_drawdown": analysis.max_drawdown,
                        "max_drawdown_percent": analysis.max_drawdown_percent,
                        "max_drawdown_date": analysis.max_drawdown_date,
                        "final_account_value": analysis.final_account_value
                    }
                else:
                    strategy_data["latest_analysis"] = None
            strategies.append(strategy_data)
        return {
            "success": True,
            "count": len(strategies),
            "total_available": len(portfolios),
            "strategies": strategies,
            "metadata": {
                "limit_applied": limit,
                "include_summary": include_summary,
                "generated_at": pd.Timestamp.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error fetching strategies: {e}")
        return {
            "success": False,
            "error": str(e),
            "strategies": [],
            "count": 0
        }

@router.get("/list")
async def get_strategies_list(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    try:
        portfolios = PortfolioService.get_portfolios(db, limit=1000)
        strategies_list = [
            {
                "id": portfolio.id,
                "name": portfolio.name,
                "filename": portfolio.filename,
                "upload_date": portfolio.upload_date.isoformat(),
                "row_count": portfolio.row_count,
                "strategy": portfolio.strategy
            }
            for portfolio in portfolios
        ]
        return {
            "success": True,
            "count": len(strategies_list),
            "strategies": strategies_list
        }
    except Exception as e:
        logger.error(f"Error fetching strategies list: {e}")
        return {
            "success": False,
            "error": str(e),
            "strategies": [],
            "count": 0
        }

@router.get("/{strategy_id}/analysis")
async def get_strategy_analysis(
    strategy_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 10
):
    try:
        portfolio = PortfolioService.get_portfolio_by_id(db, strategy_id)
        if not portfolio:
            return {
                "success": False,
                "error": f"Strategy with ID {strategy_id} not found",
                "analysis_results": []
            }
        analysis_results = PortfolioService.get_recent_analysis_results(
            db, portfolio_id=strategy_id, limit=limit
        )
        analysis_data = []
        for analysis in analysis_results:
            analysis_item = {
                "id": analysis.id,
                "analysis_type": analysis.analysis_type,
                "created_at": analysis.created_at.isoformat(),
                "parameters": {
                    "rf_rate": analysis.rf_rate,
                    "daily_rf_rate": analysis.daily_rf_rate,
                    "sma_window": analysis.sma_window,
                    "use_trading_filter": analysis.use_trading_filter,
                    "starting_capital": analysis.starting_capital
                },
                "metrics": {
                    "sharpe_ratio": analysis.sharpe_ratio,
                    "mar_ratio": analysis.mar_ratio,
                    "cagr": analysis.cagr,
                    "annual_volatility": analysis.annual_volatility,
                    "total_return": analysis.total_return,
                    "total_pl": analysis.total_pl,
                    "final_account_value": analysis.final_account_value,
                    "max_drawdown": analysis.max_drawdown,
                    "max_drawdown_percent": analysis.max_drawdown_percent
                }
            }
            if hasattr(analysis, 'plots') and analysis.plots:
                analysis_item["plots"] = [
                    {
                        "plot_type": plot.plot_type,
                        "file_url": plot.file_url,
                        "file_size": plot.file_size,
                        "created_at": plot.created_at.isoformat()
                    }
                    for plot in analysis.plots
                ]
            analysis_data.append(analysis_item)
        return {
            "success": True,
            "strategy": {
                "id": portfolio.id,
                "name": portfolio.name,
                "filename": portfolio.filename
            },
            "analysis_count": len(analysis_data),
            "analysis_results": analysis_data
        }
    except Exception as e:
        logger.error(f"Error fetching strategy analysis: {e}")
        return {
            "success": False,
            "error": str(e),
            "analysis_results": []
        } 