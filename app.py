import os
import pandas as pd
import gc  # Add garbage collection for memory management
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Request, Form, Depends
from fastapi.responses import HTMLResponse, FileResponse
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
from routers.portfolio import router as portfolio_router
from routers.strategies import router as strategies_router
from routers.upload import router as upload_router
from routers.optimization import router as optimization_router
from routers.regime import router as regime_router
from routers.auth import router as auth_router
from routers.margin import router as margin_router
from routers.robustness import router as robustness_router
from routers.profit_optimization import router as profit_optimization_router
from routers.favorites import router as favorites_router
from routers.tear_sheet import router as tear_sheet_router

# Set up logging
logger = logging.getLogger(__name__)

# Configure yfinance cache location to avoid permission errors
try:
    import yfinance as yf
    cache_dir = os.path.join(os.path.dirname(__file__), '.cache', 'yfinance')
    os.makedirs(cache_dir, exist_ok=True)
    yf.set_tz_cache_location(cache_dir)
    logger.info(f"yfinance cache configured: {cache_dir}")
except Exception as e:
    logger.warning(f"Could not configure yfinance cache: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI startup and shutdown events"""
    # Startup
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
    
    yield
    
    # Shutdown (if needed)
    # Add cleanup code here if necessary

# FastAPI app setup
app = FastAPI(
    title="Cotton's Portfolio Analyzer", 
    version="1.0.0",
    lifespan=lifespan
)

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
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://closet.local:5173",
    "http://closet.local:8000",
    # VPS domains
    "https://hornillo.cloud",
    "http://hornillo.cloud",
    "https://cottonmike.com",
    "http://cottonmike.com",
    "https://portfolio.cottonmike.com",
    "http://portfolio.cottonmike.com"
]

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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(portfolio_router, prefix="/api/portfolio")
app.include_router(strategies_router, prefix="/api/strategies")
app.include_router(upload_router, prefix="/api/upload")
app.include_router(optimization_router, prefix="/api")
app.include_router(regime_router)
app.include_router(margin_router, prefix="/api/margin")
app.include_router(robustness_router, prefix="/api/robustness")
app.include_router(profit_optimization_router, prefix="/api/profit-optimization")
app.include_router(favorites_router)
app.include_router(tear_sheet_router, prefix="/api")

# Legacy upload endpoint for backward compatibility
@app.post("/upload")
async def legacy_upload(
    files: List[UploadFile] = File(...),
    rf_rate: float = Form(DEFAULT_RF_RATE),
    daily_rf_rate: float = Form(DEFAULT_DAILY_RF_RATE),
    sma_window: int = Form(DEFAULT_SMA_WINDOW),
    use_trading_filter: bool = Form(True),
    starting_capital: float = Form(DEFAULT_STARTING_CAPITAL),
    weighting_method: str = Form("equal"),
    weights: str = Form(None),
    db: Session = Depends(get_db)
):
    """Legacy upload endpoint - redirects to the upload router"""
    from routers.upload import upload_files_api
    
    return await upload_files_api(
        files=files,
        rf_rate=rf_rate,
        daily_rf_rate=daily_rf_rate,
        sma_window=sma_window,
        use_trading_filter=use_trading_filter,
        starting_capital=starting_capital,
        weighting_method=weighting_method,
        weights=weights,
        db=db
    )

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


@app.get("/api/portfolios")
async def get_portfolios(db: Session = Depends(get_db)):
    """
    Get all portfolios from the database
    
    Returns:
        JSON response with list of portfolios and their metadata
    """
    try:
        logger.info("[API Portfolios] Fetching all portfolios")
        portfolios = PortfolioService.get_all_portfolios(db)
        
        result = []
        for portfolio in portfolios:
            # Get the latest analysis result for this portfolio
            latest_analysis = PortfolioService.get_latest_analysis_result(db, portfolio.id)
            
            portfolio_data = {
                "id": portfolio.id,
                "name": portfolio.name,
                "filename": portfolio.filename,
                "upload_date": portfolio.upload_date.isoformat() if portfolio.upload_date else None,
                "data_count": portfolio.row_count,
                "file_size": portfolio.file_size,
                "date_range_start": portfolio.date_range_start.isoformat() if portfolio.date_range_start else None,
                "date_range_end": portfolio.date_range_end.isoformat() if portfolio.date_range_end else None,
                "strategy": portfolio.strategy
            }
            
            if latest_analysis:
                import json
                # Parse metrics_json if it exists
                metrics_data = None
                if latest_analysis.metrics_json:
                    try:
                        metrics_data = json.loads(latest_analysis.metrics_json)
                    except json.JSONDecodeError:
                        metrics_data = latest_analysis.metrics_json
                
                portfolio_data["latest_analysis"] = {
                    "id": latest_analysis.id,
                    "analysis_type": latest_analysis.analysis_type,
                    "created_at": latest_analysis.created_at.isoformat() if latest_analysis.created_at else None,
                    "metrics": metrics_data
                }
            
            result.append(portfolio_data)
        
        logger.info(f"[API Portfolios] Returning {len(result)} portfolios")
        return {
            "success": True,
            "portfolios": result
        }
        
    except Exception as e:
        logger.error(f"[API Portfolios] Error fetching portfolios: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


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


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
