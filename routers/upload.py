from fastapi import APIRouter, UploadFile, File, Form, Depends, Request
from sqlalchemy.orm import Session
from fastapi.responses import HTMLResponse
from typing import List
import logging
from config import DEFAULT_RF_RATE, DEFAULT_DAILY_RF_RATE, DEFAULT_SMA_WINDOW, DEFAULT_STARTING_CAPITAL
from database import get_db
from portfolio_service import PortfolioService
from portfolio_blender import create_blended_portfolio, process_individual_portfolios
from plotting import create_plots, create_correlation_heatmap, create_monte_carlo_simulation
import pandas as pd
import os

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("")
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
    import json
    try:
        logger.info(f"[API Upload] Received request with {len(files)} files")
        logger.info(f"[API Upload] File details: {[{'name': f.filename, 'size': f.size, 'content_type': f.content_type} for f in files]}")
        logger.info(f"[API Upload] Parameters: rf_rate={rf_rate}, sma_window={sma_window}, "
                    f"use_trading_filter={use_trading_filter}, starting_capital={starting_capital}, "
                    f"weighting_method={weighting_method}")
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
                    for i, multiplier in enumerate(weight_list):
                        if multiplier <= 0:
                            error_msg = f"All multipliers must be positive. Multiplier {i+1}: {multiplier}"
                            logger.error(f"[API Upload] Multiplier validation failed: {error_msg}")
                            return {"success": False, "error": error_msg}
                    portfolio_weights = weight_list
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid weights format: {str(e)}"
                    logger.error(f"[API Upload] JSON decode error: {error_msg}")
                    return {"success": False, "error": error_msg}
            else:
                portfolio_weights = [1.0 / len(files)] * len(files)
                logger.info(f"[API Upload] Using equal weights: {portfolio_weights}")
        files_data = []
        portfolio_ids = []
        for i, file in enumerate(files):
            try:
                logger.info(f"[API Upload] Processing file {i+1}/{len(files)}: {file.filename}")
                contents = await file.read()
                logger.info(f"[API Upload] Read {len(contents)} bytes from {file.filename}")
                df = pd.read_csv(pd.io.common.BytesIO(contents))
                logger.info(f"[API Upload] Parsed CSV with shape {df.shape} for {file.filename}")
                portfolio_name = file.filename.replace('.csv', '').replace('_', ' ').title()
                logger.info(f"[API Upload] Creating portfolio record: {portfolio_name}")
                portfolio = PortfolioService.create_portfolio(
                    db, portfolio_name, file.filename, contents, df
                )
                logger.info(f"[API Upload] Created portfolio with ID {portfolio.id}")
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
        individual_results = process_individual_portfolios(
            files_data, rf_rate, sma_window, use_trading_filter, starting_capital
        )
        logger.info(f"[API Upload] Individual analysis completed for {len(individual_results)} portfolios")
        analysis_params = {
            'rf_rate': rf_rate,
            'daily_rf_rate': daily_rf_rate,
            'sma_window': sma_window,
            'use_trading_filter': use_trading_filter,
            'starting_capital': starting_capital
        }
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
                if i < len(portfolio_ids) and portfolio_ids[i] is not None:
                    try:
                        logger.debug(f"[ROUTER:upload] Storing analysis result for portfolio_id={portfolio_ids[i]}")
                        analysis_result = PortfolioService.store_analysis_result(
                            db, portfolio_ids[i], "individual", result['metrics'], analysis_params
                        )
                        logger.info(f"[API Upload] Stored analysis result ID {analysis_result.id} for portfolio {portfolio_ids[i]}")
                    except Exception as db_error:
                        logger.error(f"[API Upload] Error storing analysis result: {str(db_error)}", exc_info=True)
                del result['clean_df']
        blended_result = None
        if len(files_data) > 1 and len(portfolio_ids) > 1:
            logger.info(f"[API Upload] Creating blended portfolio from {len(files_data)} files")
            try:
                blended_portfolio = create_blended_portfolio(
                    db=db,
                    portfolio_ids=portfolio_ids,
                    weights=portfolio_weights,
                    name=f"Blended Portfolio ({len(portfolio_ids)} strategies)",
                    description=f"Blended portfolio from {len(portfolio_ids)} uploaded strategies"
                )
                logger.info(f"[API Upload] Blended portfolio created with ID {blended_portfolio.id}")
                
                # For compatibility with the existing response format, create a dummy result
                blended_metrics = {
                    'total_return': 0.0,  # Would need to calculate from actual blended data
                    'sharpe_ratio': 0.0,
                    'total_pl': 0.0,
                    'final_account_value': starting_capital,
                    'max_drawdown': 0.0,
                    'max_drawdown_percent': 0.0,
                    'cagr': 0.0,
                    'annual_volatility': 0.0
                }
                
                blended_df = None  # Not used in current response format
                correlation_data = None
            except Exception as blend_error:
                logger.error(f"[API Upload] Error creating blended portfolio: {str(blend_error)}", exc_info=True)
                blended_df, blended_metrics, correlation_data = None, None, None
            if blended_df is not None and blended_metrics is not None:
                logger.info("[API Upload] Blended portfolio created successfully")
                blended_result = {
                    'filename': 'Blended Portfolio',
                    'metrics': blended_metrics,
                    'type': 'file',
                    'plots': []
                }
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

@router.post("/deprecated")
async def upload_files_deprecated():
    return {"error": "This endpoint has been deprecated. Please use /api/upload instead.", "success": False} 