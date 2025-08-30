from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from typing import Any, List
import logging
from database import get_db
from portfolio_service import PortfolioService
from portfolio_blender import create_blended_portfolio, process_individual_portfolios
from plotting import create_plots, create_correlation_heatmap, create_monte_carlo_simulation
from models import PortfolioMarginData
from sqlalchemy import func
import gc
import pandas as pd
import os

router = APIRouter()
logger = logging.getLogger(__name__)

def calculate_starting_capital_from_margins(db: Session, portfolio_ids: List[int], portfolio_weights: List[float] = None) -> float:
    """
    Calculate starting capital based on the maximum daily margin requirements
    for the selected portfolios. Returns the sum of maximum daily margins.
    Applies portfolio weights/multipliers if provided.
    """
    try:
        if not portfolio_ids:
            logger.warning("[MARGIN CAPITAL] No portfolio IDs provided, using default starting capital")
            return 1000000.0
        
        # Default to 1x multiplier for all portfolios if no weights provided
        if portfolio_weights is None:
            portfolio_weights = [1.0] * len(portfolio_ids)
        
        logger.info(f"[MARGIN CAPITAL] Calculating margin-based starting capital for portfolios: {portfolio_ids}")
        logger.info(f"[MARGIN CAPITAL] Using portfolio multipliers: {[f'{w:.2f}x' for w in portfolio_weights]}")
        
        total_max_margin = 0.0
        
        for i, portfolio_id in enumerate(portfolio_ids):
            # Get the maximum daily total margin requirement for this portfolio
            # First aggregate by date to get daily totals, then find the maximum
            daily_totals_subquery = db.query(
                PortfolioMarginData.date,
                func.sum(PortfolioMarginData.margin_requirement).label('daily_total')
            ).filter(
                PortfolioMarginData.portfolio_id == portfolio_id
            ).group_by(PortfolioMarginData.date).subquery()
            
            max_daily_total = db.query(
                func.max(daily_totals_subquery.c.daily_total)
            ).scalar()
            
            if max_daily_total:
                max_daily_margin = float(max_daily_total)
                weight = portfolio_weights[i] if i < len(portfolio_weights) else 1.0
                weighted_margin = max_daily_margin * weight
                total_max_margin += weighted_margin
                logger.info(f"[MARGIN CAPITAL] Portfolio {portfolio_id} max daily margin: ${max_daily_margin:,.2f} x {weight:.2f} = ${weighted_margin:,.2f}")
            else:
                logger.warning(f"[MARGIN CAPITAL] No margin data found for portfolio {portfolio_id}")
        
        if total_max_margin > 0:
            logger.info(f"[MARGIN CAPITAL] Total margin-based starting capital: ${total_max_margin:,.2f}")
            return total_max_margin
        else:
            logger.warning("[MARGIN CAPITAL] No margin data found for any portfolio, using default starting capital")
            return 1000000.0
            
    except Exception as e:
        logger.error(f"[MARGIN CAPITAL] Error calculating margin-based starting capital: {e}")
        return 1000000.0

# Add a helper function to check for a matching AnalysisResult for a portfolio and parameters.
def get_cached_analysis_result(db, portfolio_id, rf_rate, sma_window, use_trading_filter, starting_capital):
    from sqlalchemy import and_
    from models import AnalysisResult
    return db.query(AnalysisResult).filter(
        AnalysisResult.portfolio_id == portfolio_id,
        AnalysisResult.rf_rate == rf_rate,
        AnalysisResult.sma_window == sma_window,
        AnalysisResult.use_trading_filter == use_trading_filter,
        AnalysisResult.starting_capital == starting_capital
    ).order_by(AnalysisResult.created_at.desc()).first()

@router.post("/analyze-portfolios-weighted")
async def analyze_selected_portfolios_weighted(request: Request, db: Session = Depends(get_db)):
    try:
        gc.collect()
        body = await request.json()
        portfolio_ids = body.get("portfolio_ids", [])
        weighting_method = body.get("weighting_method", "equal")
        weights = body.get("weights", None)
        user_starting_capital = body.get("starting_capital", 1000000.0)
        if not portfolio_ids:
            return {"success": False, "error": "No portfolio IDs provided"}
        if user_starting_capital <= 0:
            return {"success": False, "error": "Starting capital must be greater than 0"}
        if len(portfolio_ids) > 20:
            return {"success": False, "error": "Maximum 20 portfolios allowed for analysis to prevent memory issues"}
        
        # Calculate starting capital based on maximum daily margin requirements
        # For weighted analysis, we need to determine the weights first to calculate proper margin requirements
        if weighting_method == "custom" and weights:
            portfolio_weights = weights
        elif weighting_method == "equal":
            portfolio_weights = [1.0] * len(portfolio_ids)
        elif weights:
            portfolio_weights = weights
        else:
            portfolio_weights = [1.0] * len(portfolio_ids)
        
        starting_capital = calculate_starting_capital_from_margins(db, portfolio_ids, portfolio_weights)
        
        logger.info(f"[Weighted Analysis] Analyzing portfolios: {portfolio_ids}")
        logger.info(f"[Weighted Analysis] Weighting method: {weighting_method}")
        logger.info(f"[Weighted Analysis] Weights: {weights}")
        logger.info(f"[Weighted Analysis] User provided starting capital: ${user_starting_capital:,.2f}")
        logger.info(f"[Weighted Analysis] Margin-based starting capital: ${starting_capital:,.2f}")
        
        # Re-determine portfolio_weights for the actual analysis (this logic was duplicated)
        portfolio_weights = None
        if len(portfolio_ids) > 1:
            if weighting_method == "custom" and weights:
                if len(weights) != len(portfolio_ids):
                    return {"success": False, "error": f"Number of weights ({len(weights)}) must match number of portfolios ({len(portfolio_ids)})"}
                for i, multiplier in enumerate(weights):
                    if multiplier <= 0:
                        return {"success": False, "error": f"All multipliers must be positive numbers (e.g., 1.0, 1.5, 2.0). Multiplier {i+1}: {multiplier}"}
                portfolio_weights = weights
            elif weighting_method == "equal":
                portfolio_weights = [1.0] * len(portfolio_ids)  # Each portfolio at 1x
            elif weights:
                portfolio_weights = weights
            else:
                portfolio_weights = [1.0] * len(portfolio_ids)  # Default to 1x for each portfolio
            
            # Log total portfolio scale
            total_scale = sum(portfolio_weights)
            logger.info(f"[Weighted Analysis] Using portfolio multipliers: {[f'{w:.2f}x' for w in portfolio_weights]} (total scale: {total_scale:.2f}x)")
        portfolios_data = []
        for portfolio_id in portfolio_ids:
            portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
            if not portfolio:
                logger.warning(f"Portfolio {portfolio_id} not found")
                continue
            df = PortfolioService.get_portfolio_dataframe(db, portfolio_id, columns=["Date", "P/L", "Daily_Return"])
            if df.empty:
                logger.warning(f"No data found for portfolio {portfolio_id}")
                continue
            logger.info(f"[Weighted Analysis] Retrieved {len(df)} rows for portfolio {portfolio_id} ({portfolio.name})")
            portfolios_data.append((portfolio.name, df))
        if not portfolios_data:
            return {"success": False, "error": "No valid portfolio data found"}
        logger.info(f"[Weighted Analysis] Processing {len(portfolios_data)} portfolios")
        individual_results = []
        for i, (name, df) in enumerate(portfolios_data):
            cached = get_cached_analysis_result(db, portfolio_ids[i], 0.05, 20, True, starting_capital)
            if cached:
                import json
                metrics = json.loads(cached.metrics_json) if cached.metrics_json else {}
                df = PortfolioService.get_portfolio_dataframe(db, portfolio_ids[i], columns=["Date", "P/L", "Daily_Return"])
                # Check for missing/zero metrics
                if not metrics or any(metrics.get(k, 0) == 0 for k in ["sharpe_ratio", "total_return", "final_account_value"]):
                    result = process_individual_portfolios([(name, df)], rf_rate=0.05, sma_window=20, use_trading_filter=True, starting_capital=starting_capital)[0]
                    logger.error(f"[ROUTER:optimization] About to call store_analysis_result for portfolio_id={portfolio_ids[i]}, metrics={result['metrics']}")
                    PortfolioService.store_analysis_result(db, portfolio_ids[i], "individual", result['metrics'], {"rf_rate": 0.05, "sma_window": 20, "use_trading_filter": True, "starting_capital": starting_capital})
                    metrics = result['metrics']
                    clean_df = result['clean_df']
                else:
                    clean_df = df
                individual_results.append({
                    'filename': name,
                    'metrics': metrics,
                    'type': 'file',
                    'plots': [],
                    'clean_df': clean_df
                })
            else:
                # Run process_individual_portfolios for this portfolio only
                result = process_individual_portfolios([(name, df)], rf_rate=0.05, sma_window=20, use_trading_filter=True, starting_capital=starting_capital)[0]
                logger.error(f"[ROUTER:optimization] About to call store_analysis_result for portfolio_id={portfolio_ids[i]}, metrics={result['metrics']}")
                PortfolioService.store_analysis_result(db, portfolio_ids[i], "individual", result['metrics'], {"rf_rate": 0.05, "sma_window": 20, "use_trading_filter": True, "starting_capital": starting_capital})
                individual_results.append(result)
        simplified_individual_results = []
        for i, result in enumerate(individual_results):
            if 'metrics' in result:
                plots_list = []
                logger.info(f"[Weighted Analysis] Processing result {i+1}, keys: {list(result.keys())}")
                if 'clean_df' in result:
                    try:
                        logger.info(f"[Weighted Analysis] Creating plots for portfolio {i+1}")
                        plot_paths = create_plots(
                            result['clean_df'], 
                            result['metrics'], 
                            filename_prefix=f"weighted_analysis_portfolio_{i}_{portfolio_ids[i] if i < len(portfolio_ids) else 'unknown'}", 
                            sma_window=20
                        )
                        if 'clean_df' in result:
                            del result['clean_df']
                        gc.collect()
                        logger.info(f"[Weighted Analysis] create_plots returned: {plot_paths}")
                        for plot_path in plot_paths:
                            filename = os.path.basename(plot_path)
                            plot_url = f"/uploads/plots/{filename}".replace("\\", "/")
                            plots_list.append({
                                'filename': filename,
                                'url': plot_url
                            })
                        logger.info(f"[Weighted Analysis] Created {len(plot_paths)} plots for portfolio {i+1}")
                    except Exception as plot_error:
                        logger.error(f"[Weighted Analysis] Error creating plots for portfolio {i+1}: {str(plot_error)}")
                else:
                    logger.warning(f"[Weighted Analysis] No 'clean_df' key found in result {i+1}")
                simplified_result = {
                    'filename': result.get('filename', 'Unknown'),
                    'type': result.get('type', 'file'),
                    'plots': plots_list,
                    'metrics': {
                        'sharpe_ratio': float(result['metrics'].get('sharpe_ratio', 0)),
                        'sortino_ratio': float(result['metrics'].get('sortino_ratio', 0)),
                        'ulcer_index': float(result['metrics'].get('ulcer_index', 0)),
                        'upi': float(result['metrics'].get('upi', 0)),
                        'kelly_criterion': float(result['metrics'].get('kelly_criterion', 0)),
                        'total_return': float(result['metrics'].get('total_return', 0)),
                        'total_pl': float(result['metrics'].get('total_pl', 0)),
                        'final_account_value': float(result['metrics'].get('final_account_value', 100000)),
                        'max_drawdown': float(result['metrics'].get('max_drawdown', 0)),
                        'max_drawdown_percent': float(result['metrics'].get('max_drawdown_percent', 0)),
                        'max_drawdown_date': result['metrics'].get('max_drawdown_date', ''),
                        'cagr': float(result['metrics'].get('cagr', 0)),
                        'annual_volatility': float(result['metrics'].get('annual_volatility', 0)),
                        'mar_ratio': float(result['metrics'].get('mar_ratio', 0)),
                        'time_period_years': float(result['metrics'].get('time_period_years', 0)),
                        'number_of_trading_days': int(result['metrics'].get('number_of_trading_days', 0))
                    }
                }
                simplified_individual_results.append(simplified_result)
        simplified_blended_result = None
        heatmap_url = None
        monte_carlo_url = None
        portfolio_composition = {}
        if len(portfolios_data) > 1:
            try:
                logger.info("[Weighted Analysis] Creating weighted blended portfolio analysis")
                blended_df, blended_metrics = create_blended_portfolio(
                    db=db,
                    portfolio_ids=portfolio_ids,
                    weights=portfolio_weights,
                    name=f"Weighted Blended Portfolio ({len(portfolios_data)} strategies)",
                    description=f"Weighted blend of {len(portfolios_data)} portfolios"
                )
                if blended_df is not None and blended_metrics is not None:
                    blended_plots_list = []
                    try:
                        logger.info("[Weighted Analysis] Creating plots for weighted blended portfolio")
                        portfolio_ids_str = "_".join(str(pid) for pid in portfolio_ids)
                        unique_prefix = f"weighted_blended_{len(portfolio_ids)}portfolios_{portfolio_ids_str}"
                        blended_plot_paths = create_plots(
                            blended_df, 
                            blended_metrics, 
                            filename_prefix=unique_prefix, 
                            sma_window=20
                        )
                        for plot_path in blended_plot_paths:
                            filename = os.path.basename(plot_path)
                            plot_url = f"/uploads/plots/{filename}".replace("\\", "/")
                            blended_plots_list.append({
                                'filename': filename,
                                'url': plot_url
                            })
                        logger.info(f"[Weighted Analysis] Created {len(blended_plot_paths)} plots for weighted blended portfolio")
                    except Exception as plot_error:
                        logger.error(f"[Weighted Analysis] Error creating plots for weighted blended portfolio: {str(plot_error)}")
                    try:
                        logger.info("[Weighted Analysis] Creating correlation heatmap")
                        # Create correlation data from individual portfolios only
                        correlation_data = pd.DataFrame()
                        portfolio_names = []
                        
                        # Only use individual portfolio data for correlation
                        for i, (name, df) in enumerate(portfolios_data):
                            # Calculate daily returns for each portfolio
                            df['Daily Return'] = df['P/L'] / starting_capital
                            correlation_data[name] = df['Daily Return']
                            portfolio_names.append(name)
                        
                        if not correlation_data.empty and len(correlation_data.columns) >= 2:
                            logger.info(f"[Weighted Analysis] Creating correlation heatmap with {len(portfolio_names)} portfolios")
                            heatmap_path = create_correlation_heatmap(correlation_data, portfolio_names)
                            if heatmap_path:
                                heatmap_filename = os.path.basename(heatmap_path)
                                heatmap_url = f"/uploads/plots/{heatmap_filename}".replace("\\", "/")
                                logger.info(f"[Weighted Analysis] Correlation heatmap created: {heatmap_url}")
                        else:
                            logger.warning("[Weighted Analysis] No correlation data available for heatmap")
                    except Exception as heatmap_error:
                        logger.error(f"[Weighted Analysis] Error creating correlation heatmap: {str(heatmap_error)}")
                    if len(portfolios_data) <= 20:
                        try:
                            logger.info(f"[Weighted Analysis] Creating Monte Carlo simulation for {len(portfolios_data)} portfolios")
                            mc_path = create_monte_carlo_simulation(blended_df, blended_metrics)
                            if mc_path:
                                mc_filename = os.path.basename(mc_path)
                                monte_carlo_url = f"/uploads/plots/{mc_filename}".replace("\\", "/")
                                logger.info(f"[Weighted Analysis] Monte Carlo simulation created: {monte_carlo_url}")
                            else:
                                logger.warning("[Weighted Analysis] Monte Carlo simulation returned None")
                        except Exception as mc_error:
                            logger.error(f"[Weighted Analysis] Error creating Monte Carlo simulation: {str(mc_error)}")
                    else:
                        logger.info(f"[Weighted Analysis] Skipping Monte Carlo simulation for {len(portfolios_data)} portfolios to save memory")
                    del blended_df
                    gc.collect()
                    portfolio_composition = {}
                    if portfolio_weights:
                        for i, (name, _) in enumerate(portfolios_data):
                            if i < len(portfolio_weights):
                                portfolio_composition[name] = portfolio_weights[i]
                    simplified_blended_result = {
                        'filename': f'Weighted Blended Portfolio ({len(portfolios_data)} strategies)',
                        'type': 'blended',
                        'plots': blended_plots_list,
                        'weighting_method': weighting_method,
                        'portfolio_composition': portfolio_composition,
                        'metrics': {
                            'sharpe_ratio': float(blended_metrics.get('sharpe_ratio', 0)),
                            'sortino_ratio': float(blended_metrics.get('sortino_ratio', 0)),
                            'ulcer_index': float(blended_metrics.get('ulcer_index', 0)),
                            'upi': float(blended_metrics.get('upi', 0)),
                            'kelly_criterion': float(blended_metrics.get('kelly_criterion', 0)),
                            'total_return': float(blended_metrics.get('total_return', 0)),
                            'total_pl': float(blended_metrics.get('total_pl', 0)),
                            'final_account_value': float(blended_metrics.get('final_account_value', 100000)),
                            'max_drawdown': float(blended_metrics.get('max_drawdown', 0)),
                            'max_drawdown_percent': float(blended_metrics.get('max_drawdown_percent', 0)),
                            'max_drawdown_date': blended_metrics.get('max_drawdown_date', ''),
                            'cagr': float(blended_metrics.get('cagr', 0)),
                            'annual_volatility': float(blended_metrics.get('annual_volatility', 0)),
                            'mar_ratio': float(blended_metrics.get('mar_ratio', 0)),
                            'time_period_years': float(blended_metrics.get('time_period_years', 0)),
                            'number_of_trading_days': int(blended_metrics.get('number_of_trading_days', 0))
                        }
                    }
                    logger.info("[Weighted Analysis] Weighted blended portfolio created successfully")
                    for result in individual_results:
                        if 'clean_df' in result:
                            del result['clean_df']
                    gc.collect()
                else:
                    logger.warning("[Weighted Analysis] Weighted blended portfolio creation failed")
            except Exception as e:
                logger.error(f"[Weighted Analysis] Weighted blended portfolio creation error: {str(e)}")
                simplified_blended_result = None
        logger.info(f"[Weighted Analysis] Analysis completed successfully for {len(portfolio_ids)} portfolios")
        gc.collect()
        return {
            "success": True,
            "message": f"Successfully analyzed {len(portfolio_ids)} portfolios with {weighting_method} weighting",
            "individual_results": simplified_individual_results,
            "blended_result": simplified_blended_result,
            "multiple_portfolios": len(portfolios_data) > 1,
            "weighting_method": weighting_method,
            "portfolio_weights": portfolio_composition,
            "advanced_plots": {
                "correlation_heatmap": heatmap_url,
                "monte_carlo_simulation": monte_carlo_url
            },
            "starting_capital_used": starting_capital,
            "user_starting_capital": user_starting_capital,
            "margin_based_calculation": True
        }
    except Exception as e:
        logger.error(f"[Weighted Analysis] Error analyzing portfolios: {str(e)}", exc_info=True)
        gc.collect()
        return {"success": False, "error": f"Weighted analysis failed: {str(e)}"}

@router.post("/optimize-weights")
async def optimize_portfolio_weights(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
        portfolio_ids = body.get("portfolio_ids", [])
        method = body.get("method", "differential_evolution")
        if not portfolio_ids:
            return {"success": False, "error": "No portfolio IDs provided"}
        if len(portfolio_ids) < 2:
            return {"success": False, "error": "Need at least 2 portfolios for weight optimization"}
        if len(portfolio_ids) > 20:
            return {"success": False, "error": "Maximum 20 portfolios allowed for optimization to prevent performance issues"}
        logger.info(f"[Weight Optimization] Optimizing weights for portfolios: {portfolio_ids}")
        logger.info(f"[Weight Optimization] Using optimization method: {method}")
        try:
            from portfolio_optimizer import PortfolioOptimizer, OptimizationObjective
        except ImportError as e:
            return {
                "success": False,
                "error": "Portfolio optimization requires scipy. Please install scipy>=1.10.0",
                "details": str(e)
            }
        optimizer = PortfolioOptimizer(
            objective=OptimizationObjective(),
            rf_rate=0.043,
            sma_window=20,
            use_trading_filter=True,
            starting_capital=1000000.0
        )
        result = optimizer.optimize_weights_from_ids(db, portfolio_ids, method)
        if not result.success:
            return {
                "success": False,
                "error": result.message,
                "explored_combinations": len(result.explored_combinations)
            }
        portfolio_names = []
        for portfolio_id in portfolio_ids:
            portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
            if portfolio:
                portfolio_names.append(portfolio.name)
        weight_mapping = dict(zip(portfolio_names, result.optimal_weights))
        logger.info(f"[Weight Optimization] Optimization completed successfully")
        logger.info(f"[Weight Optimization] Optimal weights: {weight_mapping}")
        logger.info(f"[Weight Optimization] CAGR: {result.optimal_cagr:.4f}, Max Drawdown: {result.optimal_max_drawdown:.4f}")
        logger.info(f"[Weight Optimization] Return/Drawdown Ratio: {result.optimal_return_drawdown_ratio:.4f}")
        # Create ratio mapping
        ratio_mapping = dict(zip(portfolio_names, result.optimal_ratios))
        
        return {
            "success": True,
            "message": f"Weight optimization completed using {result.optimization_method}",
            "optimal_weights": weight_mapping,
            "optimal_weights_array": result.optimal_weights,
            "optimal_ratios": ratio_mapping,
            "optimal_ratios_array": result.optimal_ratios,
            "metrics": {
                "cagr": result.optimal_cagr,
                "max_drawdown_percent": result.optimal_max_drawdown,
                "return_drawdown_ratio": result.optimal_return_drawdown_ratio,
                "sharpe_ratio": result.optimal_sharpe_ratio
            },
            "optimization_details": {
                "method": result.optimization_method,
                "iterations": result.iterations,
                "combinations_explored": len(result.explored_combinations)
            },
            "portfolio_names": portfolio_names,
            "portfolio_ids": portfolio_ids
        }
    except Exception as e:
        logger.error(f"[Weight Optimization] Error optimizing weights: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Weight optimization failed: {str(e)}"}

@router.post("/calculate-margin-capital")
async def calculate_margin_based_capital(request: Request, db: Session = Depends(get_db)):
    """
    Preview the margin-based starting capital calculation for selected portfolios
    """
    try:
        body = await request.json()
        portfolio_ids = body.get("portfolio_ids", [])
        portfolio_weights = body.get("portfolio_weights", None)
        
        if not portfolio_ids:
            return {"success": False, "error": "No portfolio IDs provided"}
        
        # Use equal weights if not provided
        if portfolio_weights is None:
            portfolio_weights = [1.0] * len(portfolio_ids)
        
        # Calculate starting capital based on maximum daily margin requirements
        margin_capital = calculate_starting_capital_from_margins(db, portfolio_ids, portfolio_weights)
        
        # Get individual portfolio margin details
        portfolio_details = []
        for i, portfolio_id in enumerate(portfolio_ids):
            portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
            if not portfolio:
                continue
                
            # Get the maximum daily total margin requirement for this portfolio
            daily_totals_subquery = db.query(
                PortfolioMarginData.date,
                func.sum(PortfolioMarginData.margin_requirement).label('daily_total')
            ).filter(
                PortfolioMarginData.portfolio_id == portfolio_id
            ).group_by(PortfolioMarginData.date).subquery()
            
            max_daily_total = db.query(
                func.max(daily_totals_subquery.c.daily_total)
            ).scalar()
            
            max_margin = float(max_daily_total) if max_daily_total else 0.0
            weight = portfolio_weights[i] if i < len(portfolio_weights) else 1.0
            weighted_margin = max_margin * weight
            
            portfolio_details.append({
                "portfolio_id": portfolio_id,
                "portfolio_name": portfolio.name,
                "max_daily_margin": max_margin,
                "weight": weight,
                "weighted_margin": weighted_margin
            })
        
        return {
            "success": True,
            "total_margin_capital": margin_capital,
            "portfolio_details": portfolio_details,
            "portfolio_count": len(portfolio_details)
        }
        
    except Exception as e:
        logger.error(f"[MARGIN PREVIEW] Error calculating margin capital: {e}")
        return {"success": False, "error": f"Failed to calculate margin capital: {str(e)}"}

@router.post("/analyze-portfolios")
async def analyze_selected_portfolios(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
        portfolio_ids = body.get("portfolio_ids", [])
        user_starting_capital = body.get("starting_capital", 1000000.0)
        if not portfolio_ids:
            return {"success": False, "error": "No portfolio IDs provided"}
        if user_starting_capital <= 0:
            return {"success": False, "error": "Starting capital must be greater than 0"}
        
        # Calculate starting capital based on maximum daily margin requirements (equal weights for basic analysis)
        equal_weights = [1.0] * len(portfolio_ids)
        starting_capital = calculate_starting_capital_from_margins(db, portfolio_ids, equal_weights)
        
        logger.info(f"[Analyze Portfolios] Analyzing portfolios: {portfolio_ids}")
        logger.info(f"[Analyze Portfolios] User provided starting capital: ${user_starting_capital:,.2f}")
        logger.info(f"[Analyze Portfolios] Margin-based starting capital: ${starting_capital:,.2f}")
        portfolios_data = []
        for portfolio_id in portfolio_ids:
            portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
            if not portfolio:
                logger.warning(f"Portfolio {portfolio_id} not found")
                continue
            df = PortfolioService.get_portfolio_dataframe(db, portfolio_id, columns=["Date", "P/L", "Daily_Return"])
            if df.empty:
                logger.warning(f"No data found for portfolio {portfolio_id}")
                continue
            logger.info(f"[Analyze Portfolios] Retrieved {len(df)} rows for portfolio {portfolio_id} ({portfolio.name})")
            portfolios_data.append((portfolio.name, df))
        if not portfolios_data:
            return {"success": False, "error": "No valid portfolio data found"}
        logger.info(f"[Analyze Portfolios] Processing {len(portfolios_data)} portfolios")
        individual_results = []
        for i, (name, df) in enumerate(portfolios_data):
            cached = get_cached_analysis_result(db, portfolio_ids[i], 0.05, 20, True, starting_capital)
            if cached:
                import json
                metrics = json.loads(cached.metrics_json) if cached.metrics_json else {}
                df = PortfolioService.get_portfolio_dataframe(db, portfolio_ids[i], columns=["Date", "P/L", "Daily_Return"])
                # Check for missing/zero metrics
                if not metrics or any(metrics.get(k, 0) == 0 for k in ["sharpe_ratio", "total_return", "final_account_value"]):
                    result = process_individual_portfolios([(name, df)], rf_rate=0.05, sma_window=20, use_trading_filter=True, starting_capital=starting_capital)[0]
                    logger.error(f"[ROUTER:optimization] About to call store_analysis_result for portfolio_id={portfolio_ids[i]}, metrics={result['metrics']}")
                    PortfolioService.store_analysis_result(db, portfolio_ids[i], "individual", result['metrics'], {"rf_rate": 0.05, "sma_window": 20, "use_trading_filter": True, "starting_capital": starting_capital})
                    metrics = result['metrics']
                    clean_df = result['clean_df']
                else:
                    clean_df = df
                individual_results.append({
                    'filename': name,
                    'metrics': metrics,
                    'type': 'file',
                    'plots': [],
                    'clean_df': clean_df
                })
            else:
                # Run process_individual_portfolios for this portfolio only
                result = process_individual_portfolios([(name, df)], rf_rate=0.05, sma_window=20, use_trading_filter=True, starting_capital=starting_capital)[0]
                logger.error(f"[ROUTER:optimization] About to call store_analysis_result for portfolio_id={portfolio_ids[i]}, metrics={result['metrics']}")
                PortfolioService.store_analysis_result(db, portfolio_ids[i], "individual", result['metrics'], {"rf_rate": 0.05, "sma_window": 20, "use_trading_filter": True, "starting_capital": starting_capital})
                individual_results.append(result)
        simplified_individual_results = []
        for i, result in enumerate(individual_results):
            if 'metrics' in result:
                plots_list = []
                logger.info(f"[Analyze Portfolios] Processing result {i+1}, keys: {list(result.keys())}")
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
                        'sortino_ratio': float(result['metrics'].get('sortino_ratio', 0)),
                        'ulcer_index': float(result['metrics'].get('ulcer_index', 0)),
                        'upi': float(result['metrics'].get('upi', 0)),
                        'kelly_criterion': float(result['metrics'].get('kelly_criterion', 0)),
                        'total_return': float(result['metrics'].get('total_return', 0)),
                        'total_pl': float(result['metrics'].get('total_pl', 0)),
                        'final_account_value': float(result['metrics'].get('final_account_value', 100000)),
                        'max_drawdown': float(result['metrics'].get('max_drawdown', 0)),
                        'max_drawdown_percent': float(result['metrics'].get('max_drawdown_percent', 0)),
                        'max_drawdown_date': result['metrics'].get('max_drawdown_date', ''),
                        'cagr': float(result['metrics'].get('cagr', 0)),
                        'annual_volatility': float(result['metrics'].get('annual_volatility', 0)),
                        'mar_ratio': float(result['metrics'].get('mar_ratio', 0)),
                        'time_period_years': float(result['metrics'].get('time_period_years', 0)),
                        'number_of_trading_days': int(result['metrics'].get('number_of_trading_days', 0))
                    }
                }
                simplified_individual_results.append(simplified_result)
        simplified_blended_result = None
        heatmap_url = None
        monte_carlo_url = None
        if len(portfolios_data) > 1:
            try:
                logger.info("[Analyze Portfolios] Creating blended portfolio analysis")
                # Use 1x multiplier for each portfolio
                equal_weights = [1.0] * len(portfolio_ids)
                logger.info(f"[Analyze Portfolios] Using equal weights (1x each): {equal_weights}")
                
                blended_df, blended_metrics = create_blended_portfolio(
                    db=db,
                    portfolio_ids=portfolio_ids,
                    weights=equal_weights,
                    name=f"Equal-Weight Blended Portfolio ({len(portfolios_data)} strategies)",
                    description=f"Equal-weight blend of {len(portfolios_data)} portfolios"
                )
                if blended_df is not None and blended_metrics is not None:
                    blended_plots_list = []
                    try:
                        logger.info("[Analyze Portfolios] Creating plots for blended portfolio")
                        portfolio_ids_str = "_".join(str(pid) for pid in portfolio_ids)
                        unique_prefix = f"analysis_blended_{len(portfolio_ids)}portfolios_{portfolio_ids_str}"
                        blended_plot_paths = create_plots(
                            blended_df, 
                            blended_metrics, 
                            filename_prefix=unique_prefix, 
                            sma_window=20
                        )
                        for plot_path in blended_plot_paths:
                            filename = os.path.basename(plot_path)
                            plot_url = f"/uploads/plots/{filename}".replace("\\", "/")
                            blended_plots_list.append({
                                'filename': filename,
                                'url': plot_url
                            })
                        logger.info(f"[Analyze Portfolios] Created {len(blended_plot_paths)} plots for blended portfolio")
                    except Exception as plot_error:
                        logger.error(f"[Analyze Portfolios] Error creating plots for blended portfolio: {str(plot_error)}")
                    try:
                        logger.info("[Analyze Portfolios] Creating correlation heatmap")
                        correlation_data = pd.DataFrame()
                        portfolio_names = []
                        for i, (name, _) in enumerate(portfolios_data):
                            if i < len(individual_results) and 'clean_df' in individual_results[i]:
                                df = individual_results[i]['clean_df']
                                if 'Daily Return' in df.columns:
                                    correlation_data[name] = df['Daily Return']
                                    portfolio_names.append(name)
                        if len(correlation_data.columns) >= 2:
                            heatmap_path = create_correlation_heatmap(correlation_data, portfolio_names)
                            if heatmap_path:
                                heatmap_filename = os.path.basename(heatmap_path)
                                heatmap_url = f"/uploads/plots/{heatmap_filename}".replace("\\", "/")
                                logger.info(f"[Analyze Portfolios] Correlation heatmap created: {heatmap_url}")
                    except Exception as heatmap_error:
                        logger.error(f"[Analyze Portfolios] Error creating correlation heatmap: {str(heatmap_error)}")
                    try:
                        logger.info("[Analyze Portfolios] Creating Monte Carlo simulation")
                        mc_path = create_monte_carlo_simulation(blended_df, blended_metrics)
                        if mc_path:
                            mc_filename = os.path.basename(mc_path)
                            monte_carlo_url = f"/uploads/plots/{mc_filename}".replace("\\", "/")
                            logger.info(f"[Analyze Portfolios] Monte Carlo simulation created: {monte_carlo_url}")
                    except Exception as mc_error:
                        logger.error(f"[Analyze Portfolios] Error creating Monte Carlo simulation: {str(mc_error)}")
                    simplified_blended_result = {
                        'filename': f'Blended Portfolio ({len(portfolios_data)} strategies)',
                        'type': 'blended',
                        'plots': blended_plots_list,
                        'metrics': {
                            'sharpe_ratio': float(blended_metrics.get('sharpe_ratio', 0)),
                            'sortino_ratio': float(blended_metrics.get('sortino_ratio', 0)),
                            'ulcer_index': float(blended_metrics.get('ulcer_index', 0)),
                            'upi': float(blended_metrics.get('upi', 0)),
                            'kelly_criterion': float(blended_metrics.get('kelly_criterion', 0)),
                            'total_return': float(blended_metrics.get('total_return', 0)),
                            'total_pl': float(blended_metrics.get('total_pl', 0)),
                            'final_account_value': float(blended_metrics.get('final_account_value', 100000)),
                            'max_drawdown': float(blended_metrics.get('max_drawdown', 0)),
                            'max_drawdown_percent': float(blended_metrics.get('max_drawdown_percent', 0)),
                            'max_drawdown_date': blended_metrics.get('max_drawdown_date', ''),
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
            "multiple_portfolios": len(portfolios_data) > 1,
            "advanced_plots": {
                "correlation_heatmap": heatmap_url,
                "monte_carlo_simulation": monte_carlo_url
            },
            "starting_capital_used": starting_capital,
            "user_starting_capital": user_starting_capital,
            "margin_based_calculation": True
        }
    except Exception as e:
        logger.error(f"[Analyze Portfolios] Error analyzing portfolios: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Analysis failed: {str(e)}"} 