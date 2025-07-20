import os
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Request, Form, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from typing import List
import logging
import warnings

# Suppress matplotlib warnings about Axes3D
warnings.filterwarnings('ignore', message='Unable to import Axes3D')
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib.projections')

# Import our modular components
from config import (
    UPLOAD_FOLDER, SESSION_SECRET_KEY, DEFAULT_RF_RATE, 
    DEFAULT_DAILY_RF_RATE, DEFAULT_SMA_WINDOW, DEFAULT_STARTING_CAPITAL
)
from portfolio_blender import create_blended_portfolio, process_individual_portfolios
from plotting import create_plots, create_correlation_heatmap, create_monte_carlo_simulation

# Import database components
from database import get_db, create_tables
from portfolio_service import PortfolioService

# Set up logging
logger = logging.getLogger(__name__)

# FastAPI app setup
app = FastAPI(title="Portfolio Analysis API", version="1.0.0")
templates = Jinja2Templates(directory="templates")

# Mount static files for uploads
app.mount("/uploads", StaticFiles(directory=UPLOAD_FOLDER), name="uploads")

# Mount React frontend static files (only if directory exists)
import os
frontend_dist_path = "frontend/dist"
if os.path.exists(frontend_dist_path) and os.path.exists(f"{frontend_dist_path}/assets"):
    app.mount("/assets", StaticFiles(directory=f"{frontend_dist_path}/assets"), name="react-assets")

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

# Add CORS middleware to allow React frontend to communicate with API
# Configure CORS based on environment
allowed_origins = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"]

# In production (Render), allow the deployed domain
if os.getenv('RENDER'):
    # Add your Render domain here - replace with your actual domain
    render_domain = os.getenv('RENDER_EXTERNAL_URL', '')
    if render_domain:
        allowed_origins.append(render_domain)
        allowed_origins.append(render_domain.replace('http://', 'https://'))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database tables on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database tables on application startup"""
    try:
        create_tables()
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        # Continue running even if database fails (graceful degradation)

@app.get("/", response_class=HTMLResponse)
async def main(request: Request):
    """Serve React frontend"""
    frontend_index_path = 'frontend/dist/index.html'
    if os.path.exists(frontend_index_path):
        return FileResponse(frontend_index_path)
    else:
        # Fallback to a simple HTML page if React build doesn't exist
        return HTMLResponse("""
        <html>
            <head><title>Portfolio Analysis API</title></head>
            <body>
                <h1>Portfolio Analysis API</h1>
                <p>The React frontend is not available. Please build the frontend first.</p>
                <p>API documentation is available at <a href="/docs">/docs</a></p>
            </body>
        </html>
        """)

# Catch-all route for React Router (must be at the end)
@app.get("/{path:path}", response_class=HTMLResponse)
async def catch_all(path: str):
    """Serve React app for any route not handled by API"""
    # Only serve React app for non-API routes
    if not path.startswith("api/") and not path.startswith("uploads/"):
        frontend_index_path = 'frontend/dist/index.html'
        if os.path.exists(frontend_index_path):
            return FileResponse(frontend_index_path)
        else:
            # Fallback for missing React build
            return HTMLResponse("""
            <html>
                <head><title>Portfolio Analysis API</title></head>
                <body>
                    <h1>Portfolio Analysis API</h1>
                    <p>The React frontend is not available.</p>
                    <p>API documentation is available at <a href="/docs">/docs</a></p>
                </body>
            </html>
            """)
    # For API routes that don't exist, return 404
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Not Found")


@app.get("/portfolios", response_class=HTMLResponse)
async def list_portfolios(request: Request, db: Session = Depends(get_db)):
    """List all stored portfolios"""
    try:
        portfolios = PortfolioService.get_portfolios(db)
        return templates.TemplateResponse(
            "portfolios.html", 
            {"request": request, "portfolios": portfolios}
        )
    except Exception as e:
        logger.error(f"Error fetching portfolios: {e}")
        return templates.TemplateResponse(
            "portfolios.html", 
            {"request": request, "portfolios": [], "error": str(e)}
        )


@app.get("/portfolio/{portfolio_id}")
async def get_portfolio_data(portfolio_id: int, db: Session = Depends(get_db)):
    """Get portfolio data as JSON"""
    try:
        portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
        if not portfolio:
            return {"error": "Portfolio not found"}
        
        data = PortfolioService.get_portfolio_data(db, portfolio_id, limit=1000)
        return {
            "portfolio": {
                "id": portfolio.id,
                "name": portfolio.name,
                "filename": portfolio.filename,
                "upload_date": portfolio.upload_date.isoformat(),
                "row_count": portfolio.row_count,
                "date_range_start": portfolio.date_range_start.isoformat() if portfolio.date_range_start else None,
                "date_range_end": portfolio.date_range_end.isoformat() if portfolio.date_range_end else None,
            },
            "data": [
                {
                    "date": item.date.isoformat(),
                    "pl": item.pl,
                    "cumulative_pl": item.cumulative_pl,
                    "account_value": item.account_value,
                    "daily_return": item.daily_return
                }
                for item in data
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching portfolio data: {e}")
        return {"error": str(e)}


@app.delete("/api/portfolio/{portfolio_id}")
async def delete_portfolio(portfolio_id: int, db: Session = Depends(get_db)):
    """
    Delete a portfolio and all associated data
    """
    try:
        # Check if portfolio exists
        portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
        if not portfolio:
            return {"success": False, "error": f"Portfolio with ID {portfolio_id} not found"}
        
        # Delete the portfolio (cascade will handle related data)
        success = PortfolioService.delete_portfolio(db, portfolio_id)
        
        if success:
            logger.info(f"Portfolio {portfolio_id} ({portfolio.name}) deleted successfully")
            return {
                "success": True, 
                "message": f"Portfolio '{portfolio.name}' deleted successfully",
                "portfolio_id": portfolio_id
            }
        else:
            return {"success": False, "error": "Failed to delete portfolio"}
            
    except Exception as e:
        logger.error(f"Error deleting portfolio {portfolio_id}: {e}")
        return {"success": False, "error": str(e)}


@app.put("/api/portfolio/{portfolio_id}/name")
async def update_portfolio_name(portfolio_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Update portfolio name
    """
    try:
        # Get the new name from the request body
        body = await request.json()
        new_name = body.get("name", "").strip()
        
        if not new_name:
            return {"success": False, "error": "Portfolio name cannot be empty"}
        
        if len(new_name) > 255:
            return {"success": False, "error": "Portfolio name too long (max 255 characters)"}
        
        # Check if portfolio exists
        portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
        if not portfolio:
            return {"success": False, "error": f"Portfolio with ID {portfolio_id} not found"}
        
        old_name = portfolio.name
        
        # Update the portfolio name
        success = PortfolioService.update_portfolio_name(db, portfolio_id, new_name)
        
        if success:
            logger.info(f"Portfolio {portfolio_id} name updated from '{old_name}' to '{new_name}'")
            return {
                "success": True, 
                "message": f"Portfolio name updated from '{old_name}' to '{new_name}'",
                "portfolio_id": portfolio_id,
                "old_name": old_name,
                "new_name": new_name
            }
        else:
            return {"success": False, "error": "Failed to update portfolio name"}
            
    except Exception as e:
        logger.error(f"Error updating portfolio {portfolio_id} name: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/strategies")
async def get_strategies(
    limit: int = 100,
    include_summary: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get all existing strategies (portfolios) from the database
    
    Args:
        limit: Maximum number of strategies to return (default: 100)
        include_summary: Whether to include analysis summary data (default: True)
        
    Returns:
        JSON response with strategies list and metadata
    """
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
                "file_hash": portfolio.file_hash[:16] + "..." if portfolio.file_hash else None  # Truncated for security
            }
            
            # Include analysis summary if requested
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
                        "mar_ratio": analysis.mar_ratio,
                        "cagr": analysis.cagr,
                        "annual_volatility": analysis.annual_volatility,
                        "total_return": analysis.total_return,
                        "max_drawdown": analysis.max_drawdown,
                        "max_drawdown_percent": analysis.max_drawdown_percent,
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


@app.get("/api/strategies/list")
async def get_strategies_list(db: Session = Depends(get_db)):
    """
    Get a lightweight list of strategy names and IDs
    
    Returns:
        Simple JSON list of strategies with minimal data
    """
    try:
        portfolios = PortfolioService.get_portfolios(db, limit=1000)
        
        strategies_list = [
            {
                "id": portfolio.id,
                "name": portfolio.name,
                "filename": portfolio.filename,
                "upload_date": portfolio.upload_date.isoformat(),
                "row_count": portfolio.row_count
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


@app.get("/api/strategies/{strategy_id}/analysis")
async def get_strategy_analysis(
    strategy_id: int,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Get analysis history for a specific strategy
    
    Args:
        strategy_id: ID of the strategy/portfolio
        limit: Maximum number of analysis results to return
        
    Returns:
        JSON response with analysis history
    """
    try:
        # Check if strategy exists
        portfolio = PortfolioService.get_portfolio_by_id(db, strategy_id)
        if not portfolio:
            return {
                "success": False,
                "error": f"Strategy with ID {strategy_id} not found",
                "analysis_results": []
            }
        
        # Get analysis results
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
            
            # Add plots information if available
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


@app.get("/api/debug/database")
async def debug_database_connection(db: Session = Depends(get_db)):
    """
    Debug endpoint to check database connection and environment
    """
    import os
    from database import engine, DATABASE_URL, postgresql_success
    import traceback
    
    try:
        # Get environment info
        database_url = os.getenv('DATABASE_URL', 'NOT SET')
        db_host = os.getenv('DB_HOST', 'NOT SET')
        render_env = os.getenv('RENDER', 'NOT SET')
        
        # Test database connection directly
        portfolios = PortfolioService.get_portfolios(db, limit=10)
        
        # Get database engine info
        engine_url = str(engine.url)
        
        # Try direct PostgreSQL connection test
        connection_test_result = "Not tested"
        connection_error = "None"
        
        if database_url != 'NOT SET' and database_url.startswith('postgresql://'):
            try:
                from sqlalchemy import create_engine as test_engine, text
                test_conn = test_engine(database_url, connect_args={"connect_timeout": 10})
                with test_conn.connect() as conn:
                    conn.execute(text("SELECT 1"))
                connection_test_result = "SUCCESS"
            except Exception as e:
                connection_test_result = "FAILED"
                connection_error = str(e)
        
        return {
            "success": True,
            "environment": {
                "DATABASE_URL": "SET" if database_url != 'NOT SET' else "NOT SET",
                "DATABASE_URL_preview": database_url[:30] + "..." if database_url != 'NOT SET' else "NOT SET",
                "DATABASE_URL_full_length": len(database_url) if database_url != 'NOT SET' else 0,
                "DB_HOST": db_host,
                "RENDER": render_env,
                "ENGINE_URL": engine_url,
                "POSTGRESQL_SUCCESS": postgresql_success
            },
            "database": {
                "portfolios_count": len(portfolios),
                "portfolios": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "upload_date": p.upload_date.isoformat() if p.upload_date else None
                    } for p in portfolios
                ]
            },
            "connection_test": {
                "result": connection_test_result,
                "error": connection_error
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "environment": {
                "DATABASE_URL": "SET" if os.getenv('DATABASE_URL') else "NOT SET",
                "DB_HOST": os.getenv('DB_HOST', 'NOT SET'),
                "RENDER": os.getenv('RENDER', 'NOT SET'),
                "ENGINE_URL": str(engine.url) if 'engine' in globals() else "NOT INITIALIZED"
            }
        }


@app.post("/upload")
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    rf_rate: float = Form(DEFAULT_RF_RATE),
    daily_rf_rate: float = Form(DEFAULT_DAILY_RF_RATE),
    sma_window: int = Form(DEFAULT_SMA_WINDOW),
    use_trading_filter: bool = Form(True),
    starting_capital: float = Form(DEFAULT_STARTING_CAPITAL),
    weighting_method: str = Form("equal"),
    rebalance_weighting_method: str = Form(None),
    weights: List[float] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload and process portfolio files
    
    Args:
        request: FastAPI request object
        files: List of uploaded CSV files
        rf_rate: Annual risk-free rate
        daily_rf_rate: Daily risk-free rate
        sma_window: SMA window for trading filter
        use_trading_filter: Whether to apply SMA trading filter
        starting_capital: Starting capital amount
        weighting_method: 'equal' or 'custom' weighting method
        weights: List of custom weights (only used if weighting_method='custom')
        
    Returns:
        Rendered results template
    """
    logger.info(f"Received {len(files)} files for processing")
    logger.info(f"Parameters: rf_rate={rf_rate}, sma_window={sma_window}, "
                f"use_trading_filter={use_trading_filter}, starting_capital={starting_capital}")
    
    # Handle both initial and rebalance weighting method
    effective_weighting_method = rebalance_weighting_method if rebalance_weighting_method else weighting_method
    logger.info(f"Weighting method: {effective_weighting_method}, weights: {weights}")
    
    # Process weighting
    portfolio_weights = None
    if len(files) > 1:
        if effective_weighting_method == "custom" and weights is not None:
            # Validate custom weights
            if len(weights) != len(files):
                return templates.TemplateResponse(
                    "results.html",
                    {
                        "request": request,
                        "results": [],
                        "blended_result": None,
                        "multiple_portfolios": False,
                        "heatmap_url": None,
                        "monte_carlo_url": None,
                        "error": f"Number of weights ({len(weights)}) must match number of files ({len(files)})"
                    }
                )
            
            # Check if weights sum to approximately 1.0
            weight_sum = sum(weights)
            if abs(weight_sum - 1.0) > 0.001:
                return templates.TemplateResponse(
                    "results.html",
                    {
                        "request": request,
                        "results": [],
                        "blended_result": None,
                        "multiple_portfolios": False,
                        "heatmap_url": None,
                        "monte_carlo_url": None,
                        "error": f"Weights must sum to 1.0. Current sum: {weight_sum:.3f}"
                    }
                )
            
            portfolio_weights = weights
            logger.info(f"Using custom weights: {portfolio_weights}")
        else:
            # Equal weighting (default)
            portfolio_weights = [1.0 / len(files)] * len(files)
            logger.info(f"Using equal weights: {portfolio_weights}")
    
    # Read all files into memory and store in database
    files_data = []
    portfolio_ids = []
    
    for file in files:
        try:
            contents = await file.read()
            df = pd.read_csv(pd.io.common.BytesIO(contents))
            
            # Store portfolio and data in database
            try:
                # Create portfolio record
                portfolio_name = file.filename.replace('.csv', '').replace('_', ' ').title()
                portfolio = PortfolioService.create_portfolio(
                    db, portfolio_name, file.filename, contents, df
                )
                
                # Store raw data
                PortfolioService.store_portfolio_data(db, portfolio.id, df)
                
                # Add to processing list
                files_data.append((file.filename, df))
                portfolio_ids.append(portfolio.id)
                
                logger.info(f"Stored portfolio {portfolio.name} with ID {portfolio.id}")
                
            except Exception as db_error:
                logger.error(f"Database error for file {file.filename}: {str(db_error)}")
                # Continue processing even if database storage fails
                files_data.append((file.filename, df))
                portfolio_ids.append(None)
                
        except Exception as e:
            logger.error(f"Error reading file {file.filename}: {str(e)}")
            continue
    
    if not files_data:
        logger.error("No valid files to process")
        return templates.TemplateResponse(
            "results.html",
            {
                "request": request,
                "results": [],
                "blended_result": None,
                "multiple_portfolios": False,
                "heatmap_url": None,
                "monte_carlo_url": None,
                "error": "No valid files were uploaded"
            }
        )
    
    # Process individual portfolios
    individual_results = process_individual_portfolios(
        files_data, rf_rate, sma_window, use_trading_filter, starting_capital
    )
    
    # Store analysis results in database
    analysis_params = {
        'rf_rate': rf_rate,
        'daily_rf_rate': daily_rf_rate,
        'sma_window': sma_window,
        'use_trading_filter': use_trading_filter,
        'starting_capital': starting_capital
    }
    
    # Create plots for individual portfolios and store analysis results
    for i, result in enumerate(individual_results):
        if 'clean_df' in result:
            plot_paths = create_plots(
                result['clean_df'], 
                result['metrics'], 
                filename_prefix=f"portfolio_{i}", 
                sma_window=sma_window
            )
            
            # Add plot paths to the results
            for plot_path in plot_paths:
                filename = os.path.basename(plot_path)
                plot_url = f"/uploads/plots/{filename}"
                result['plots'].append({
                    'filename': filename,
                    'url': plot_url
                })
            
            # Store analysis result in database if we have a portfolio ID
            if i < len(portfolio_ids) and portfolio_ids[i] is not None:
                try:
                    analysis_result = PortfolioService.store_analysis_result(
                        db, portfolio_ids[i], "individual", result['metrics'], analysis_params
                    )
                    
                    # Store plot information
                    for plot_info in result['plots']:
                        PortfolioService.store_analysis_plot(
                            db, analysis_result.id, "combined_analysis",
                            plot_info['url'], plot_info['url']
                        )
                    
                    logger.info(f"Stored analysis result for portfolio {portfolio_ids[i]}")
                except Exception as db_error:
                    logger.error(f"Error storing analysis result: {str(db_error)}")
            
            # Remove clean_df from result as it's no longer needed
            del result['clean_df']
    
    # Create blended portfolio if multiple files
    blended_result = None
    correlation_data = None
    
    if len(files_data) > 1:
        blended_df, blended_metrics, correlation_data = create_blended_portfolio(
            files_data, rf_rate, sma_window, use_trading_filter, starting_capital, portfolio_weights
        )
        
        if blended_df is not None and blended_metrics is not None:
            blended_result = {
                'filename': 'Blended Portfolio',
                'metrics': blended_metrics,
                'type': 'file',
                'plots': []
            }
            
            # Create plots for blended portfolio
            plot_paths = create_plots(
                blended_df, 
                blended_metrics, 
                filename_prefix="blended_portfolio", 
                sma_window=sma_window
            )
            
            # Add plot paths to the results
            for plot_path in plot_paths:
                filename = os.path.basename(plot_path)
                plot_url = f"/uploads/plots/{filename}"
                blended_result['plots'].append({
                    'filename': filename,
                    'url': plot_url
                })
    
    # Create correlation analysis if we have multiple portfolios
    heatmap_url = None
    if len(files_data) > 1 and correlation_data is not None and not correlation_data.empty:
        try:
            logger.info("Creating correlation analysis for multiple portfolios")
            portfolio_names = [name for name, _ in files_data]
            heatmap_path = create_correlation_heatmap(correlation_data, portfolio_names)
            if heatmap_path:
                heatmap_filename = os.path.basename(heatmap_path)
                heatmap_url = f"/uploads/plots/{heatmap_filename}"
                logger.info(f"Correlation heatmap created: {heatmap_url}")
        except Exception as e:
            logger.error(f"Error creating correlation analysis: {str(e)}")
    
    # Create Monte Carlo simulation for blended portfolio if we have one
    monte_carlo_url = None
    if blended_result is not None and blended_df is not None:
        try:
            logger.info("Creating Monte Carlo simulation for blended portfolio")
            mc_path = create_monte_carlo_simulation(blended_df, blended_result['metrics'])
            if mc_path:
                mc_filename = os.path.basename(mc_path)
                monte_carlo_url = f"/uploads/plots/{mc_filename}"
                logger.info(f"Monte Carlo simulation created: {monte_carlo_url}")
        except Exception as e:
            logger.error(f"Error creating Monte Carlo simulation: {str(e)}")
    
    # Return the results
    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "results": individual_results,
            "blended_result": blended_result,
            "multiple_portfolios": len(files_data) > 1,
            "heatmap_url": heatmap_url,
            "monte_carlo_url": monte_carlo_url,
            "analysis_params": analysis_params
        }
    )


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
