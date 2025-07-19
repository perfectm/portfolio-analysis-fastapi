import os
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from typing import List
import logging

# Import our modular components
from config import (
    UPLOAD_FOLDER, SESSION_SECRET_KEY, DEFAULT_RF_RATE, 
    DEFAULT_DAILY_RF_RATE, DEFAULT_SMA_WINDOW, DEFAULT_STARTING_CAPITAL
)
from portfolio_blender import create_blended_portfolio, process_individual_portfolios
from plotting import create_plots, create_correlation_heatmap, create_monte_carlo_simulation

# Set up logging
logger = logging.getLogger(__name__)

# FastAPI app setup
app = FastAPI(title="Portfolio Analysis API", version="1.0.0")
templates = Jinja2Templates(directory="templates")
app.mount("/uploads", StaticFiles(directory=UPLOAD_FOLDER), name="uploads")

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)


@app.get("/", response_class=HTMLResponse)
async def main(request: Request):
    """Main page endpoint"""
    return templates.TemplateResponse("upload.html", {"request": request})


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
    weights: List[float] = Form(None)
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
    logger.info(f"Weighting method: {weighting_method}, weights: {weights}")
    
    # Process weighting
    portfolio_weights = None
    if len(files) > 1:
        if weighting_method == "custom" and weights is not None:
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
    
    # Read all files into memory
    files_data = []
    for file in files:
        try:
            contents = await file.read()
            df = pd.read_csv(pd.io.common.BytesIO(contents))
            files_data.append((file.filename, df))
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
    
    # Create plots for individual portfolios
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
            "monte_carlo_url": monte_carlo_url
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
