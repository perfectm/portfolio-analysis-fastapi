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
app = FastAPI(title="Cotton's Portfolio Analyzer", version="1.0.0")
templates = Jinja2Templates(directory="templates")

# Mount static files for uploads
app.mount("/uploads", StaticFiles(directory=UPLOAD_FOLDER), name="uploads")

# Mount React frontend static files (only if directory exists)
frontend_dist_path = "frontend/dist"
frontend_assets_path = f"{frontend_dist_path}/assets"
if os.path.exists(frontend_dist_path):
    # Mount React assets directory
    if os.path.exists(frontend_assets_path):
        app.mount("/assets", StaticFiles(directory=frontend_assets_path), name="react-assets")
        logger.info(f"Mounted React assets from {frontend_assets_path}")
    else:
        logger.warning(f"React assets directory not found at {frontend_assets_path}")
else:
    logger.warning(f"React dist directory not found at {frontend_dist_path}, skipping mount")

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
        # Ensure required directories exist
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        os.makedirs("uploads/plots", exist_ok=True)
        os.makedirs("frontend/dist/assets", exist_ok=True)
        
        # Create minimal index.html if it doesn't exist
        frontend_index_path = "frontend/dist/index.html"
        if not os.path.exists(frontend_index_path):
            with open(frontend_index_path, 'w') as f:
                f.write("""
                <html>
                    <head><title>Cotton's Portfolio Analyzer</title></head>
                    <body>
                        <h1>Cotton's Portfolio Analyzer</h1>
                        <p>The React frontend is not available.</p>
                        <p>API documentation is available at <a href="/docs">/docs</a></p>
                    </body>
                </html>
                """)
        
        create_tables()
        logger.info("Database tables initialized successfully")
        logger.info("Required directories ensured")
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
            <head><title>Cotton's Portfolio Analyzer</title></head>
            <body>
                <h1>Cotton's Portfolio Analyzer</h1>
                <p>The React frontend is not available. Please build the frontend first.</p>
                <p>API documentation is available at <a href="/docs">/docs</a></p>
            </body>
        </html>
        """)

@app.get("/vite.svg")
async def serve_vite_svg():
    """Serve vite.svg from frontend dist"""
    vite_svg_path = 'frontend/dist/vite.svg'
    if os.path.exists(vite_svg_path):
        return FileResponse(vite_svg_path, media_type="image/svg+xml")
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Vite SVG not found")


# Removed conflicting /portfolios route to allow React frontend to handle it
# The portfolios page is now handled by the React frontend with checkboxes
# Backend data is available via /api/strategies/list endpoint

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


@app.get("/api/test")
async def test_endpoint():
    """Simple test endpoint"""
    return {"status": "working", "message": "API test endpoint is functional"}


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


@app.post("/api/upload")
async def upload_files_api(
    files: List[UploadFile] = File(...),
    rf_rate: float = Form(DEFAULT_RF_RATE),
    daily_rf_rate: float = Form(DEFAULT_DAILY_RF_RATE),
    sma_window: int = Form(DEFAULT_SMA_WINDOW),
    use_trading_filter: bool = Form(True),
    starting_capital: float = Form(DEFAULT_STARTING_CAPITAL),
    weighting_method: str = Form("equal"),
    weights: str = Form(None),  # JSON string of weights array
    db: Session = Depends(get_db)
):
    """
    API endpoint for uploading and processing portfolio files (returns JSON)
    
    Args:
        files: List of uploaded CSV files
        rf_rate: Annual risk-free rate
        daily_rf_rate: Daily risk-free rate
        sma_window: SMA window for trading filter
        use_trading_filter: Whether to apply SMA trading filter
        starting_capital: Starting capital amount
        weighting_method: 'equal' or 'custom' weighting method
        weights: JSON string of custom weights array
        
    Returns:
        JSON response with analysis results
    """
    import json
    
    try:
        logger.info(f"[API Upload] Received request with {len(files)} files")
        logger.info(f"[API Upload] File details: {[{'name': f.filename, 'size': f.size, 'content_type': f.content_type} for f in files]}")
        logger.info(f"[API Upload] Parameters: rf_rate={rf_rate}, sma_window={sma_window}, "
                    f"use_trading_filter={use_trading_filter}, starting_capital={starting_capital}, "
                    f"weighting_method={weighting_method}")
        
        # Parse weights if provided
        portfolio_weights = None
        if len(files) > 1:
            if weighting_method == "custom" and weights:
                try:
                    weight_list = json.loads(weights)
                    logger.info(f"[API Upload] Parsed custom weights: {weight_list}")
                    if len(weight_list) != len(files):
                        error_msg = f"Number of weights ({len(weight_list)}) must match number of files ({len(files)})"
                        logger.error(f"[API Upload] Weight validation failed: {error_msg}")
                        return {"success": False, "error": error_msg}
                    
                    weight_sum = sum(weight_list)
                    if abs(weight_sum - 1.0) > 0.001:
                        error_msg = f"Weights must sum to 1.0. Current sum: {weight_sum:.3f}"
                        logger.error(f"[API Upload] Weight sum validation failed: {error_msg}")
                        return {"success": False, "error": error_msg}
                    
                    portfolio_weights = weight_list
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid weights format: {str(e)}"
                    logger.error(f"[API Upload] JSON decode error: {error_msg}")
                    return {"success": False, "error": error_msg}
            else:
                # Equal weighting
                portfolio_weights = [1.0 / len(files)] * len(files)
                logger.info(f"[API Upload] Using equal weights: {portfolio_weights}")
        
        # Read all files and store in database
        files_data = []
        portfolio_ids = []
        
        for i, file in enumerate(files):
            try:
                logger.info(f"[API Upload] Processing file {i+1}/{len(files)}: {file.filename}")
                contents = await file.read()
                logger.info(f"[API Upload] Read {len(contents)} bytes from {file.filename}")
                
                df = pd.read_csv(pd.io.common.BytesIO(contents))
                logger.info(f"[API Upload] Parsed CSV with shape {df.shape} for {file.filename}")
                
                # Store portfolio and data in database
                portfolio_name = file.filename.replace('.csv', '').replace('_', ' ').title()
                logger.info(f"[API Upload] Creating portfolio record: {portfolio_name}")
                
                portfolio = PortfolioService.create_portfolio(
                    db, portfolio_name, file.filename, contents, df
                )
                logger.info(f"[API Upload] Created portfolio with ID {portfolio.id}")
                
                # Store raw data
                PortfolioService.store_portfolio_data(db, portfolio.id, df)
                logger.info(f"[API Upload] Stored {len(df)} data rows for portfolio {portfolio.id}")
                
                files_data.append((file.filename, df))
                portfolio_ids.append(portfolio.id)
                
            except Exception as e:
                error_msg = f"Error processing file {file.filename}: {str(e)}"
                logger.error(f"[API Upload] {error_msg}", exc_info=True)
                return {"success": False, "error": error_msg}
        
        if not files_data:
            logger.error("[API Upload] No valid files were processed")
            return {"success": False, "error": "No valid files were processed"}
        
        logger.info(f"[API Upload] Successfully processed {len(files_data)} files, starting analysis")
        
        # Process individual portfolios
        individual_results = process_individual_portfolios(
            files_data, rf_rate, sma_window, use_trading_filter, starting_capital
        )
        logger.info(f"[API Upload] Individual analysis completed for {len(individual_results)} portfolios")
        
        # Store analysis results
        analysis_params = {
            'rf_rate': rf_rate,
            'daily_rf_rate': daily_rf_rate,
            'sma_window': sma_window,
            'use_trading_filter': use_trading_filter,
            'starting_capital': starting_capital
        }
        
        # Process plots and store analysis results
        for i, result in enumerate(individual_results):
            if 'clean_df' in result:
                logger.info(f"[API Upload] Creating plots for portfolio {i+1}")
                plot_paths = create_plots(
                    result['clean_df'], 
                    result['metrics'], 
                    filename_prefix=f"portfolio_{i}", 
                    sma_window=sma_window
                )
                
                for plot_path in plot_paths:
                    filename = os.path.basename(plot_path)
                    plot_url = f"/uploads/plots/{filename}"
                    result['plots'].append({
                        'filename': filename,
                        'url': plot_url
                    })
                logger.info(f"[API Upload] Created {len(plot_paths)} plots for portfolio {i+1}")
                
                # Store analysis result in database
                if i < len(portfolio_ids) and portfolio_ids[i] is not None:
                    try:
                        analysis_result = PortfolioService.store_analysis_result(
                            db, portfolio_ids[i], "individual", result['metrics'], analysis_params
                        )
                        logger.info(f"[API Upload] Stored analysis result ID {analysis_result.id} for portfolio {portfolio_ids[i]}")
                    except Exception as db_error:
                        logger.error(f"[API Upload] Error storing analysis result: {str(db_error)}", exc_info=True)
                
                # Remove clean_df from result
                del result['clean_df']
        
        # Create blended portfolio if multiple files
        blended_result = None
        if len(files_data) > 1:
            logger.info(f"[API Upload] Creating blended portfolio from {len(files_data)} files")
            blended_df, blended_metrics, correlation_data = create_blended_portfolio(
                files_data, rf_rate, sma_window, use_trading_filter, starting_capital, portfolio_weights
            )
            
            if blended_df is not None and blended_metrics is not None:
                logger.info("[API Upload] Blended portfolio created successfully")
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
                
                for plot_path in plot_paths:
                    filename = os.path.basename(plot_path)
                    plot_url = f"/uploads/plots/{filename}"
                    blended_result['plots'].append({
                        'filename': filename,
                        'url': plot_url
                    })
                logger.info(f"[API Upload] Created {len(plot_paths)} plots for blended portfolio")
            else:
                logger.warning("[API Upload] Blended portfolio creation failed")
        
        logger.info(f"[API Upload] Upload and analysis completed successfully for {len(files)} files")
        return {
            "success": True,
            "message": f"Successfully processed {len(files)} files",
            "portfolio_ids": portfolio_ids,
            "individual_results": individual_results,
            "blended_result": blended_result,
            "multiple_portfolios": len(files_data) > 1
        }
        
    except Exception as e:
        error_msg = f"Unexpected error in upload_files_api: {str(e)}"
        logger.error(f"[API Upload] {error_msg}", exc_info=True)
        return {"success": False, "error": error_msg}


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
    logger.info(f"[Main Upload] Received {len(files)} files for processing")
    logger.info(f"[Main Upload] File details: {[{'name': f.filename, 'size': f.size, 'content_type': f.content_type} for f in files]}")
    logger.info(f"[Main Upload] Parameters: rf_rate={rf_rate}, sma_window={sma_window}, "
                f"use_trading_filter={use_trading_filter}, starting_capital={starting_capital}")
    
    # Handle both initial and rebalance weighting method
    effective_weighting_method = rebalance_weighting_method if rebalance_weighting_method else weighting_method
    logger.info(f"[Main Upload] Weighting method: {effective_weighting_method}, weights: {weights}")
    
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


# Catch-all route for React Router (must be at the end)
@app.get("/{path:path}", response_class=HTMLResponse)
async def catch_all(path: str):
    """Serve React app for any route not handled by API"""
    # For API routes that don't exist, return 404
    if path.startswith("api/"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not Found")
    
    # For uploads routes that don't exist, return 404  
    if path.startswith("uploads/"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not Found")
    
    # For all other routes, serve React app
    frontend_index_path = 'frontend/dist/index.html'
    if os.path.exists(frontend_index_path):
        return FileResponse(frontend_index_path)
    else:
        # Fallback for missing React build
        return HTMLResponse("""
        <html>
            <head><title>Cotton's Portfolio Analyzer</title></head>
            <body>
                <h1>Cotton's Portfolio Analyzer</h1>
                <p>The React frontend is not available.</p>
                <p>API documentation is available at <a href="/docs">/docs</a></p>
            </body>
        </html>
        """)


@app.post("/api/analyze-portfolios")
async def analyze_selected_portfolios(request: Request, db: Session = Depends(get_db)):
    """
    Analyze selected portfolios by their IDs
    """
    try:
        # Get the portfolio IDs from the request
        body = await request.json()
        portfolio_ids = body.get("portfolio_ids", [])
        
        if not portfolio_ids:
            return {"success": False, "error": "No portfolio IDs provided"}
        
        logger.info(f"[Analyze Portfolios] Analyzing portfolios: {portfolio_ids}")
        
        # Get portfolio data from database
        portfolios_data = []
        for portfolio_id in portfolio_ids:
            portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
            if not portfolio:
                logger.warning(f"Portfolio {portfolio_id} not found")
                continue
                
            # Get the portfolio data using the correct method
            df = PortfolioService.get_portfolio_dataframe(db, portfolio_id)
            if df.empty:
                logger.warning(f"No data found for portfolio {portfolio_id}")
                continue
                
            logger.info(f"[Analyze Portfolios] Retrieved {len(df)} rows for portfolio {portfolio_id} ({portfolio.name})")
            portfolios_data.append((portfolio.name, df))
        
        if not portfolios_data:
            return {"success": False, "error": "No valid portfolio data found"}
        
        logger.info(f"[Analyze Portfolios] Processing {len(portfolios_data)} portfolios")
        
        # Process individual portfolios
        individual_results = process_individual_portfolios(
            portfolios_data,
            rf_rate=0.05,
            sma_window=20,
            use_trading_filter=True,
            starting_capital=100000.0
        )
        
        logger.info(f"[Analyze Portfolios] Individual analysis completed for {len(individual_results)} portfolios")
        
        # Create plots and simplify individual results for JSON serialization
        simplified_individual_results = []
        for i, result in enumerate(individual_results):
            if 'metrics' in result:
                plots_list = []
                
                logger.info(f"[Analyze Portfolios] Processing result {i+1}, keys: {list(result.keys())}")
                
                # Create plots if we have the clean_df
                if 'clean_df' in result:
                    try:
                        logger.info(f"[Analyze Portfolios] Creating plots for portfolio {i+1}")
                        plot_paths = create_plots(
                            result['clean_df'], 
                            result['metrics'], 
                            filename_prefix=f"analysis_portfolio_{i}_{portfolio_ids[i] if i < len(portfolio_ids) else 'unknown'}", 
                            sma_window=20
                        )
                        
                        logger.info(f"[Analyze Portfolios] create_plots returned: {plot_paths}")
                        
                        for plot_path in plot_paths:
                            filename = os.path.basename(plot_path)
                            # Ensure URL uses forward slashes for web compatibility
                            plot_url = f"/uploads/plots/{filename}".replace("\\", "/")
                            plots_list.append({
                                'filename': filename,
                                'url': plot_url
                            })
                        logger.info(f"[Analyze Portfolios] Created {len(plot_paths)} plots for portfolio {i+1}")
                    except Exception as plot_error:
                        logger.error(f"[Analyze Portfolios] Error creating plots for portfolio {i+1}: {str(plot_error)}")
                else:
                    logger.warning(f"[Analyze Portfolios] No 'clean_df' key found in result {i+1}")
                
                simplified_result = {
                    'filename': result.get('filename', 'Unknown'),
                    'type': result.get('type', 'file'),
                    'plots': plots_list,
                    'metrics': {
                        'sharpe_ratio': float(result['metrics'].get('sharpe_ratio', 0)),
                        'total_return': float(result['metrics'].get('total_return', 0)),
                        'total_pl': float(result['metrics'].get('total_pl', 0)),
                        'final_account_value': float(result['metrics'].get('final_account_value', 100000)),
                        'max_drawdown': float(result['metrics'].get('max_drawdown', 0)),
                        'max_drawdown_percent': float(result['metrics'].get('max_drawdown_percent', 0)),
                        'cagr': float(result['metrics'].get('cagr', 0)),
                        'annual_volatility': float(result['metrics'].get('annual_volatility', 0)),
                        'mar_ratio': float(result['metrics'].get('mar_ratio', 0)),
                        'time_period_years': float(result['metrics'].get('time_period_years', 0)),
                        'number_of_trading_days': int(result['metrics'].get('number_of_trading_days', 0))
                    }
                }
                simplified_individual_results.append(simplified_result)
        
        # Create blended portfolio if multiple portfolios
        simplified_blended_result = None
        if len(portfolios_data) > 1:
            try:
                logger.info("[Analyze Portfolios] Creating blended portfolio analysis")
                blended_df, blended_metrics, _ = create_blended_portfolio(
                    portfolios_data,
                    rf_rate=0.05,
                    sma_window=20,
                    use_trading_filter=True,
                    starting_capital=100000.0
                )
                
                if blended_df is not None and blended_metrics is not None:
                    # Create plots for blended portfolio
                    blended_plots_list = []
                    try:
                        logger.info("[Analyze Portfolios] Creating plots for blended portfolio")
                        blended_plot_paths = create_plots(
                            blended_df, 
                            blended_metrics, 
                            filename_prefix="analysis_blended_portfolio", 
                            sma_window=20
                        )
                        
                        for plot_path in blended_plot_paths:
                            filename = os.path.basename(plot_path)
                            # Ensure URL uses forward slashes for web compatibility
                            plot_url = f"/uploads/plots/{filename}".replace("\\", "/")
                            blended_plots_list.append({
                                'filename': filename,
                                'url': plot_url
                            })
                        logger.info(f"[Analyze Portfolios] Created {len(blended_plot_paths)} plots for blended portfolio")
                    except Exception as plot_error:
                        logger.error(f"[Analyze Portfolios] Error creating plots for blended portfolio: {str(plot_error)}")
                    
                    simplified_blended_result = {
                        'filename': f'Blended Portfolio ({len(portfolios_data)} strategies)',
                        'type': 'blended',
                        'plots': blended_plots_list,
                        'metrics': {
                            'sharpe_ratio': float(blended_metrics.get('sharpe_ratio', 0)),
                            'total_return': float(blended_metrics.get('total_return', 0)),
                            'total_pl': float(blended_metrics.get('total_pl', 0)),
                            'final_account_value': float(blended_metrics.get('final_account_value', 100000)),
                            'max_drawdown': float(blended_metrics.get('max_drawdown', 0)),
                            'max_drawdown_percent': float(blended_metrics.get('max_drawdown_percent', 0)),
                            'cagr': float(blended_metrics.get('cagr', 0)),
                            'annual_volatility': float(blended_metrics.get('annual_volatility', 0)),
                            'mar_ratio': float(blended_metrics.get('mar_ratio', 0)),
                            'time_period_years': float(blended_metrics.get('time_period_years', 0)),
                            'number_of_trading_days': int(blended_metrics.get('number_of_trading_days', 0))
                        }
                    }
                    logger.info("[Analyze Portfolios] Blended portfolio created successfully")
                else:
                    logger.warning("[Analyze Portfolios] Blended portfolio creation failed")
            except Exception as e:
                logger.error(f"[Analyze Portfolios] Blended portfolio creation error: {str(e)}")
                simplified_blended_result = None
        
        logger.info(f"[Analyze Portfolios] Analysis completed successfully for {len(portfolio_ids)} portfolios")
        return {
            "success": True,
            "message": f"Successfully analyzed {len(portfolio_ids)} portfolios",
            "individual_results": simplified_individual_results,
            "blended_result": simplified_blended_result,
            "multiple_portfolios": len(portfolios_data) > 1
        }
        
    except Exception as e:
        logger.error(f"[Analyze Portfolios] Error analyzing portfolios: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Analysis failed: {str(e)}"}


# Catch-all route for React frontend routing (must be last)
@app.get("/{path:path}", response_class=HTMLResponse)
async def serve_react_app(path: str = None):
    """Catch-all route to serve React frontend for client-side routing"""
    frontend_index_path = 'frontend/dist/index.html'
    if os.path.exists(frontend_index_path):
        return FileResponse(frontend_index_path)
    else:
        return HTMLResponse("""
        <html>
            <head><title>Cotton's Portfolio Analyzer</title></head>
            <body>
                <h1>Cotton's Portfolio Analyzer</h1>
                <p>The React frontend is not available. Please build the frontend first.</p>
                <p>API documentation is available at <a href="/docs">/docs</a></p>
            </body>
        </html>
        """)


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
