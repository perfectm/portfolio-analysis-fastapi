from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Any, List
import logging
from database import get_db
from portfolio_service import PortfolioService
from portfolio_blender import create_blended_portfolio, process_individual_portfolios
from plotting import create_plots, create_correlation_heatmap, create_monte_carlo_simulation
from correlation_utils import create_correlation_data_for_plotting, calculate_correlation_matrix_from_dataframe
from models import PortfolioMarginData
from sqlalchemy import func
import gc
import pandas as pd
import numpy as np
import os
import io
from config import UPLOAD_FOLDER

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
        rf_rate = body.get("rf_rate", 0.043)  # Default to 4.3% if not provided
        sma_window = body.get("sma_window", 20)  # Default to 20 if not provided
        use_trading_filter = body.get("use_trading_filter", True)  # Default to True if not provided
        date_range_start = body.get("date_range_start", None)
        date_range_end = body.get("date_range_end", None)
        if not portfolio_ids:
            return {"success": False, "error": "No portfolio IDs provided"}
        if user_starting_capital <= 0:
            return {"success": False, "error": "Starting capital must be greater than 0"}
        
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
        
        # Use user-provided starting capital if available, otherwise calculate from margins
        margin_based_capital = calculate_starting_capital_from_margins(db, portfolio_ids, portfolio_weights)
        starting_capital = user_starting_capital if user_starting_capital and user_starting_capital > 0 else margin_based_capital
        
        logger.info(f"[Weighted Analysis] Analyzing portfolios: {portfolio_ids}")
        logger.info(f"[Weighted Analysis] Weighting method: {weighting_method}")
        logger.info(f"[Weighted Analysis] Weights: {weights}")
        logger.info(f"[Weighted Analysis] User provided starting capital: ${user_starting_capital:,.2f}")
        logger.info(f"[Weighted Analysis] Margin-based starting capital: ${margin_based_capital:,.2f}")
        logger.info(f"[Weighted Analysis] Using starting capital: ${starting_capital:,.2f}")
        logger.info(f"[Weighted Analysis] RF Rate: {rf_rate:.4f}, SMA Window: {sma_window}, Trading Filter: {use_trading_filter}")
        
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

        # Validate portfolios first and filter out non-existent ones
        valid_portfolio_ids = []
        invalid_ids = []
        for portfolio_id in portfolio_ids:
            portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
            if portfolio:
                valid_portfolio_ids.append(portfolio_id)
            else:
                invalid_ids.append(portfolio_id)

        # Log once if there were invalid IDs
        if invalid_ids:
            logger.info(f"[Weighted Analysis] Filtered out {len(invalid_ids)} non-existent portfolio(s): {invalid_ids}")

        if not valid_portfolio_ids:
            return {"success": False, "error": "None of the selected portfolios exist in the database"}

        # Now fetch data only for valid portfolios
        portfolios_data = []
        for portfolio_id in valid_portfolio_ids:
            portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
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
            cached = get_cached_analysis_result(db, valid_portfolio_ids[i], 0.05, 20, True, starting_capital)
            if cached:
                import json
                metrics = json.loads(cached.metrics_json) if cached.metrics_json else {}
                df = PortfolioService.get_portfolio_dataframe(db, valid_portfolio_ids[i], columns=["Date", "P/L", "Daily_Return"])
                # Check for missing/zero metrics
                if not metrics or any(metrics.get(k, 0) == 0 for k in ["sharpe_ratio", "total_return", "final_account_value"]):
                    result = process_individual_portfolios([(name, df)], rf_rate=rf_rate, sma_window=sma_window, use_trading_filter=use_trading_filter, starting_capital=starting_capital, date_range_start=date_range_start, date_range_end=date_range_end)[0]
                    logger.error(f"[ROUTER:optimization] About to call store_analysis_result for portfolio_id={valid_portfolio_ids[i]}, metrics={result['metrics']}")
                    PortfolioService.store_analysis_result(db, valid_portfolio_ids[i], "individual", result['metrics'], {"rf_rate": rf_rate, "sma_window": sma_window, "use_trading_filter": use_trading_filter, "starting_capital": starting_capital})
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
                result = process_individual_portfolios([(name, df)], rf_rate=rf_rate, sma_window=sma_window, use_trading_filter=use_trading_filter, starting_capital=starting_capital, date_range_start=date_range_start, date_range_end=date_range_end)[0]
                logger.error(f"[ROUTER:optimization] About to call store_analysis_result for portfolio_id={valid_portfolio_ids[i]}, metrics={result['metrics']}")
                PortfolioService.store_analysis_result(db, valid_portfolio_ids[i], "individual", result['metrics'], {"rf_rate": rf_rate, "sma_window": sma_window, "use_trading_filter": use_trading_filter, "starting_capital": starting_capital})
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
                            filename_prefix=f"weighted_analysis_portfolio_{i}_{valid_portfolio_ids[i] if i < len(portfolio_ids) else 'unknown'}", 
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
                        'cvar': float(result['metrics'].get('cvar', 0)),
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
                        'number_of_trading_days': int(result['metrics'].get('number_of_trading_days', 0)),
                        'worst_pl_day': float(result['metrics'].get('worst_pl_day', 0)),
                        'worst_pl_date': result['metrics'].get('worst_pl_date', ''),
                        'best_pl_day': float(result['metrics'].get('best_pl_day', 0)),
                        'best_pl_date': result['metrics'].get('best_pl_date', ''),
                        'days_in_drawdown': int(result['metrics'].get('days_in_drawdown', 0)),
                        'avg_drawdown_length': float(result['metrics'].get('avg_drawdown_length', 0)),
                        'num_drawdown_periods': int(result['metrics'].get('num_drawdown_periods', 0)),
                        'days_loss_over_half_pct': int(result['metrics'].get('days_loss_over_half_pct', 0)),
                        'days_loss_over_three_quarters_pct': int(result['metrics'].get('days_loss_over_three_quarters_pct', 0)),
                        'days_loss_over_one_pct': int(result['metrics'].get('days_loss_over_one_pct', 0)),
                        'days_gain_over_half_pct': int(result['metrics'].get('days_gain_over_half_pct', 0)),
                        'days_gain_over_three_quarters_pct': int(result['metrics'].get('days_gain_over_three_quarters_pct', 0)),
                        'days_gain_over_one_pct': int(result['metrics'].get('days_gain_over_one_pct', 0)),
                        'days_loss_over_half_pct_starting_cap': int(result['metrics'].get('days_loss_over_half_pct_starting_cap', 0)),
                        'days_loss_over_three_quarters_pct_starting_cap': int(result['metrics'].get('days_loss_over_three_quarters_pct_starting_cap', 0)),
                        'days_loss_over_one_pct_starting_cap': int(result['metrics'].get('days_loss_over_one_pct_starting_cap', 0)),
                        'days_gain_over_half_pct_starting_cap': int(result['metrics'].get('days_gain_over_half_pct_starting_cap', 0)),
                        'days_gain_over_three_quarters_pct_starting_cap': int(result['metrics'].get('days_gain_over_three_quarters_pct_starting_cap', 0)),
                        'days_gain_over_one_pct_starting_cap': int(result['metrics'].get('days_gain_over_one_pct_starting_cap', 0)),
                        'largest_profit_day': float(result['metrics'].get('largest_profit_day', 0)),
                        'largest_profit_date': result['metrics'].get('largest_profit_date', '')
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
                blended_df, blended_metrics, _ = create_blended_portfolio(
                    db=db,
                    portfolio_ids=valid_portfolio_ids,
                    weights=portfolio_weights,
                    name=f"Weighted Blended Portfolio ({len(portfolios_data)} strategies)",
                    description=f"Weighted blend of {len(portfolios_data)} portfolios",
                    date_range_start=date_range_start,
                    date_range_end=date_range_end,
                    starting_capital=starting_capital,
                    rf_rate=rf_rate,
                    sma_window=sma_window,
                    use_trading_filter=use_trading_filter
                )
                if blended_df is not None and blended_metrics is not None:
                    blended_plots_list = []
                    try:
                        logger.info("[Weighted Analysis] Creating plots for weighted blended portfolio")
                        portfolio_ids_str = "_".join(str(pid) for pid in valid_portfolio_ids)
                        unique_prefix = f"weighted_blended_{len(valid_portfolio_ids)}portfolios_{portfolio_ids_str}"
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
                        # Create correlation data from individual portfolios using proper correlation approach
                        correlation_data = pd.DataFrame()
                        portfolio_names = []
                        
                        # Prepare portfolio data for correlation calculation
                        for i, (name, df) in enumerate(portfolios_data):
                            # Sum P/L by date first (handle multiple trades per day)
                            if 'Date' in df.columns:
                                df_copy = df.copy()
                                df_copy['Date'] = pd.to_datetime(df_copy['Date'])
                                # Group by date and sum P/L values
                                daily_pnl_sum = df_copy.groupby('Date')['P/L'].sum()
                                daily_pnl_sum.name = name
                                
                                # Join with correlation_data using outer join to align dates
                                if correlation_data.empty:
                                    correlation_data = daily_pnl_sum.to_frame()
                                else:
                                    correlation_data = correlation_data.join(daily_pnl_sum, how='outer')
                                
                                portfolio_names.append(name)
                            else:
                                # Fallback if no Date column - assume data is already daily
                                daily_pnl_sum = df['P/L'].fillna(0)
                                daily_pnl_sum.name = name
                                
                                if correlation_data.empty:
                                    correlation_data = daily_pnl_sum.to_frame()
                                else:
                                    correlation_data = correlation_data.join(daily_pnl_sum, how='outer')
                                
                                portfolio_names.append(name)
                        
                        # Fill NaN values with 0 for days where portfolios don't have trades
                        correlation_data = correlation_data.fillna(0)
                        
                        if not correlation_data.empty and len(correlation_data.columns) >= 2:
                            # Save correlation data to CSV for debugging
                            debug_csv_path = os.path.join(UPLOAD_FOLDER, 'plots', 'correlation_debug_data.csv')
                            correlation_data.to_csv(debug_csv_path, index=True)
                            logger.info(f"[Weighted Analysis] Correlation debug data saved to: {debug_csv_path}")
                            logger.info(f"[Weighted Analysis] Correlation data shape: {correlation_data.shape}")
                            # Calculate preview using new correlation method
                            value_columns = list(correlation_data.columns)
                            correlation_matrix_preview = calculate_correlation_matrix_from_dataframe(correlation_data, value_columns)
                            logger.info(f"[Weighted Analysis] Correlation matrix preview:\n{correlation_matrix_preview}")
                            
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

                    # Extract daily time series data (Date and Account Value) BEFORE deleting blended_df
                    daily_data = []
                    if blended_df is not None and 'Date' in blended_df.columns and 'Account Value' in blended_df.columns:
                        # Calculate daily P/L changes for validation
                        blended_df['Daily_PL_Change'] = blended_df['Account Value'].diff()

                        for _, row in blended_df[['Date', 'Account Value', 'P/L']].iterrows():
                            daily_data.append({
                                'date': row['Date'].strftime('%Y-%m-%d') if hasattr(row['Date'], 'strftime') else str(row['Date']),
                                'account_value': float(row['Account Value']),
                                'daily_pl': float(row['P/L']) if 'P/L' in row else 0
                            })

                        # Log validation data
                        worst_drop = blended_df['Daily_PL_Change'].min()
                        worst_drop_date = blended_df.loc[blended_df['Daily_PL_Change'].idxmin(), 'Date']
                        worst_pl_single_day = blended_df['P/L'].min()
                        worst_pl_date = blended_df.loc[blended_df['P/L'].idxmin(), 'Date']

                        logger.info(f"[Weighted Analysis] Extracted {len(daily_data)} daily data points for chart")
                        logger.info(f"[Weighted Analysis] Worst Account Value drop (day-to-day): ${worst_drop:.2f} on {worst_drop_date}")
                        logger.info(f"[Weighted Analysis] Worst P/L single day: ${worst_pl_single_day:.2f} on {worst_pl_date}")
                        logger.info(f"[Weighted Analysis] Account Value range: ${blended_df['Account Value'].min():.2f} to ${blended_df['Account Value'].max():.2f}")

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
                        'daily_data': daily_data,
                        'metrics': {
                            'sharpe_ratio': float(blended_metrics.get('sharpe_ratio', 0)),
                            'sortino_ratio': float(blended_metrics.get('sortino_ratio', 0)),
                            'ulcer_index': float(blended_metrics.get('ulcer_index', 0)),
                            'upi': float(blended_metrics.get('upi', 0)),
                            'kelly_criterion': float(blended_metrics.get('kelly_criterion', 0)),
                            'cvar': float(blended_metrics.get('cvar', 0)),
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
                            'number_of_trading_days': int(blended_metrics.get('number_of_trading_days', 0)),
                            'beta': float(blended_metrics.get('beta', 0)),
                            'alpha': float(blended_metrics.get('alpha', 0)),
                            'r_squared': float(blended_metrics.get('r_squared', 0)),
                            'beta_observation_count': int(blended_metrics.get('beta_observation_count', 0)),
                            'worst_pl_day': float(blended_metrics.get('worst_pl_day', 0)),
                            'worst_pl_date': blended_metrics.get('worst_pl_date', ''),
                            'best_pl_day': float(blended_metrics.get('best_pl_day', 0)),
                            'best_pl_date': blended_metrics.get('best_pl_date', ''),
                            'days_in_drawdown': int(blended_metrics.get('days_in_drawdown', 0)),
                            'avg_drawdown_length': float(blended_metrics.get('avg_drawdown_length', 0)),
                            'num_drawdown_periods': int(blended_metrics.get('num_drawdown_periods', 0)),
                            'days_loss_over_half_pct': int(blended_metrics.get('days_loss_over_half_pct', 0)),
                            'days_loss_over_three_quarters_pct': int(blended_metrics.get('days_loss_over_three_quarters_pct', 0)),
                            'days_loss_over_one_pct': int(blended_metrics.get('days_loss_over_one_pct', 0)),
                            'days_gain_over_half_pct': int(blended_metrics.get('days_gain_over_half_pct', 0)),
                            'days_gain_over_three_quarters_pct': int(blended_metrics.get('days_gain_over_three_quarters_pct', 0)),
                            'days_gain_over_one_pct': int(blended_metrics.get('days_gain_over_one_pct', 0)),
                            'days_loss_over_half_pct_starting_cap': int(blended_metrics.get('days_loss_over_half_pct_starting_cap', 0)),
                            'days_loss_over_three_quarters_pct_starting_cap': int(blended_metrics.get('days_loss_over_three_quarters_pct_starting_cap', 0)),
                            'days_loss_over_one_pct_starting_cap': int(blended_metrics.get('days_loss_over_one_pct_starting_cap', 0)),
                            'days_gain_over_half_pct_starting_cap': int(blended_metrics.get('days_gain_over_half_pct_starting_cap', 0)),
                            'days_gain_over_three_quarters_pct_starting_cap': int(blended_metrics.get('days_gain_over_three_quarters_pct_starting_cap', 0)),
                            'days_gain_over_one_pct_starting_cap': int(blended_metrics.get('days_gain_over_one_pct_starting_cap', 0)),
                            'largest_profit_day': float(blended_metrics.get('largest_profit_day', 0)),
                            'largest_profit_date': blended_metrics.get('largest_profit_date', '')
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
            "margin_based_calculation": starting_capital == margin_based_capital
        }
    except Exception as e:
        logger.error(f"[Weighted Analysis] Error analyzing portfolios: {str(e)}", exc_info=True)
        gc.collect()
        return {"success": False, "error": f"Weighted analysis failed: {str(e)}"}

@router.post("/optimize-weights-progressive")
async def optimize_portfolio_weights_progressive(request: Request, db: Session = Depends(get_db)):
    """
    Progressive optimization that returns partial results on timeout and supports continuation
    """
    try:
        body = await request.json()
        portfolio_ids = body.get("portfolio_ids", [])
        method = body.get("method", "differential_evolution")
        max_time_seconds = body.get("max_time_seconds", None)
        resume_from_weights = body.get("resume_from_weights", None)
        
        # Debug logging
        logger.info(f"[DEBUG] Received optimization request: portfolio_ids={portfolio_ids}, method={method}, max_time_seconds={max_time_seconds}")
        logger.info(f"[DEBUG] Request body type checks: portfolio_ids type={type(portfolio_ids)}, method type={type(method)}")
        
        # Validate data types
        if not isinstance(portfolio_ids, list):
            return {"success": False, "error": f"portfolio_ids must be a list, received {type(portfolio_ids)}"}
        if not isinstance(method, str):
            return {"success": False, "error": f"method must be a string, received {type(method)}"}
        if max_time_seconds is not None and not isinstance(max_time_seconds, (int, float)):
            return {"success": False, "error": f"max_time_seconds must be a number, received {type(max_time_seconds)}"}
        
        if not portfolio_ids:
            return {"success": False, "error": "No portfolio IDs provided"}
        if len(portfolio_ids) < 2:
            return {"success": False, "error": "Need at least 2 portfolios for weight optimization"}

        logger.info(f"[Progressive Optimization] Optimizing weights for portfolios: {portfolio_ids}")
        logger.info(f"[Progressive Optimization] Method: {method}, timeout: {max_time_seconds}s")
        if resume_from_weights:
            logger.info(f"[Progressive Optimization] Resuming from previous weights: {resume_from_weights}")
        
        # Validate portfolios exist and have data
        for portfolio_id in portfolio_ids:
            portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
            if not portfolio:
                return {"success": False, "error": f"Portfolio {portfolio_id} not found"}
            df = PortfolioService.get_portfolio_dataframe(db, portfolio_id)
            if df.empty:
                return {"success": False, "error": f"No data found for portfolio {portfolio_id}"}
        
        try:
            from portfolio_optimizer import PortfolioOptimizer, OptimizationObjective
        except ImportError as e:
            return {
                "success": False,
                "error": "Portfolio optimization requires scipy. Please install scipy>=1.10.0",
                "details": str(e)
            }
        
        # Create optimizer with timeout support
        optimizer = PortfolioOptimizer(
            objective=OptimizationObjective(),
            rf_rate=0.043,
            sma_window=20,
            use_trading_filter=True,
            starting_capital=1000000.0,
            portfolio_count=len(portfolio_ids),
            max_time_seconds=max_time_seconds
        )
        
        # Run optimization with optional resume weights
        result = optimizer.optimize_weights_from_ids(db, portfolio_ids, method, resume_from_weights)
        
        # Get portfolio names for response
        portfolio_names = []
        for portfolio_id in portfolio_ids:
            portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
            if portfolio:
                portfolio_names.append(portfolio.name)
        
        weight_mapping = dict(zip(portfolio_names, result.optimal_weights))
        ratio_mapping = dict(zip(portfolio_names, result.optimal_ratios))
        
        # Build response with progressive optimization fields
        response_data = {
            "success": result.success or result.is_partial_result,  # Partial results are still "successful"
            "message": result.message,
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
            "portfolio_ids": portfolio_ids,
            # Progressive optimization fields
            "is_partial_result": result.is_partial_result,
            "progress_percentage": result.progress_percentage,
            "remaining_iterations": result.remaining_iterations,
            "execution_time_seconds": result.execution_time_seconds,
            "can_continue": result.can_continue
        }
        
        if result.is_partial_result:
            logger.info(f"[Progressive Optimization] Returning partial result: {result.progress_percentage:.1f}% complete")
        else:
            logger.info(f"[Progressive Optimization] Optimization completed successfully in {result.execution_time_seconds:.1f}s")
            
        return response_data
        
    except Exception as e:
        logger.error(f"[Progressive Optimization] Error: {str(e)}", exc_info=True)
        
        # Debug pattern-related errors
        if "pattern" in str(e).lower():
            logger.error(f"[DEBUG] Pattern-related error detected: {str(e)}")
            logger.error(f"[DEBUG] Exception type: {type(e)}")
            logger.error(f"[DEBUG] Exception args: {e.args if hasattr(e, 'args') else 'No args'}")
        
        return {"success": False, "error": f"Progressive optimization failed: {str(e)}"}

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
        logger.info(f"[Weight Optimization] Optimizing weights for portfolios: {portfolio_ids}")
        logger.info(f"[Weight Optimization] Using optimization method: {method}")
        
        # Validate portfolios exist and have data
        for portfolio_id in portfolio_ids:
            portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
            if not portfolio:
                return {"success": False, "error": f"Portfolio {portfolio_id} not found"}
            df = PortfolioService.get_portfolio_dataframe(db, portfolio_id)
            if df.empty:
                return {"success": False, "error": f"No data found for portfolio {portfolio_id}"}
        
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
            starting_capital=1000000.0,
            portfolio_count=len(portfolio_ids)
        )
        # Add timeout to prevent hanging
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Optimization timed out after 300 seconds")
        
        # Set timeout for 300 seconds (5 minutes)
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(300)
        
        try:
            result = optimizer.optimize_weights_from_ids(db, portfolio_ids, method)
            signal.alarm(0)  # Cancel timeout
        except TimeoutError as e:
            logger.warning(f"[Weight Optimization] Optimization timed out after 5 minutes, falling back to equal weights")
            # Fallback to equal weights
            num_portfolios = len(portfolio_ids)
            equal_weights = [1.0 / num_portfolios] * num_portfolios
            equal_ratios = [1.0] * num_portfolios
            
            portfolio_names = []
            for portfolio_id in portfolio_ids:
                portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
                if portfolio:
                    portfolio_names.append(portfolio.name)
            
            weight_mapping = dict(zip(portfolio_names, equal_weights))
            ratio_mapping = dict(zip(portfolio_names, equal_ratios))
            
            return {
                "success": True,
                "message": "Optimization timed out, using equal weights as fallback",
                "optimal_weights": weight_mapping,
                "optimal_weights_array": equal_weights,
                "optimal_ratios": ratio_mapping,
                "optimal_ratios_array": equal_ratios,
                "metrics": {
                    "cagr": 0.0,
                    "max_drawdown_percent": 0.0,
                    "return_drawdown_ratio": 0.0,
                    "sharpe_ratio": 0.0
                },
                "optimization_details": {
                    "method": "equal_weight_fallback",
                    "iterations": 0,
                    "combinations_explored": 0
                },
                "portfolio_names": portfolio_names,
                "portfolio_ids": portfolio_ids,
                "fallback": True,
                "timeout": True
            }
        except Exception as opt_error:
            signal.alarm(0)  # Cancel timeout
            logger.error(f"[Weight Optimization] Optimization error: {str(opt_error)}")
            # Also fallback to equal weights on other errors
            try:
                num_portfolios = len(portfolio_ids)
                equal_weights = [1.0 / num_portfolios] * num_portfolios
                equal_ratios = [1.0] * num_portfolios
                
                portfolio_names = []
                for portfolio_id in portfolio_ids:
                    portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
                    if portfolio:
                        portfolio_names.append(portfolio.name)
                
                weight_mapping = dict(zip(portfolio_names, equal_weights))
                ratio_mapping = dict(zip(portfolio_names, equal_ratios))
                
                return {
                    "success": True,
                    "message": f"Optimization failed ({str(opt_error)}), using equal weights as fallback",
                    "optimal_weights": weight_mapping,
                    "optimal_weights_array": equal_weights,
                    "optimal_ratios": ratio_mapping,
                    "optimal_ratios_array": equal_ratios,
                    "metrics": {
                        "cagr": 0.0,
                        "max_drawdown_percent": 0.0,
                        "return_drawdown_ratio": 0.0,
                        "sharpe_ratio": 0.0
                    },
                    "optimization_details": {
                        "method": "equal_weight_fallback",
                        "iterations": 0,
                        "combinations_explored": 0
                    },
                    "portfolio_names": portfolio_names,
                    "portfolio_ids": portfolio_ids,
                    "fallback": True,
                    "error": str(opt_error)
                }
            except Exception as fallback_error:
                raise opt_error  # Raise original error if fallback also fails
            
        if not result.success:
            return {
                "success": False,
                "error": result.message,
                "explored_combinations": len(result.explored_combinations) if hasattr(result, 'explored_combinations') else 0
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

@router.post("/clear-optimization-cache")
async def clear_optimization_cache(db: Session = Depends(get_db)):
    """
    Clear all cached optimization results.
    Use this when optimization logic has been updated to remove stale results.
    """
    try:
        from models import OptimizationCache
        
        # Count existing cache entries
        cache_count = db.query(OptimizationCache).count()
        
        if cache_count == 0:
            return {
                "success": True,
                "message": "Optimization cache was already empty",
                "cleared_entries": 0
            }
        
        # Clear all cache entries
        db.query(OptimizationCache).delete()
        db.commit()
        
        logger.info(f"[OPTIMIZATION CACHE] Cleared {cache_count} cached optimization results")
        
        return {
            "success": True,
            "message": f"Successfully cleared optimization cache",
            "cleared_entries": cache_count
        }
        
    except Exception as e:
        logger.error(f"[OPTIMIZATION CACHE] Error clearing cache: {str(e)}")
        db.rollback()
        return {
            "success": False,
            "error": f"Failed to clear optimization cache: {str(e)}"
        }

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
        rf_rate = body.get("rf_rate", 0.043)  # Default to 4.3% if not provided
        sma_window = body.get("sma_window", 20)  # Default to 20 if not provided
        use_trading_filter = body.get("use_trading_filter", True)  # Default to True if not provided
        date_range_start = body.get("date_range_start", None)
        date_range_end = body.get("date_range_end", None)
        if not portfolio_ids:
            return {"success": False, "error": "No portfolio IDs provided"}
        if user_starting_capital <= 0:
            return {"success": False, "error": "Starting capital must be greater than 0"}
        
        # Use user-provided starting capital if available, otherwise calculate from margins (equal weights for basic analysis)
        equal_weights = [1.0] * len(portfolio_ids)
        margin_based_capital = calculate_starting_capital_from_margins(db, portfolio_ids, equal_weights)
        starting_capital = user_starting_capital if user_starting_capital and user_starting_capital > 0 else margin_based_capital
        
        logger.info(f"[Analyze Portfolios] Analyzing portfolios: {portfolio_ids}")
        logger.info(f"[Analyze Portfolios] User provided starting capital: ${user_starting_capital:,.2f}")
        logger.info(f"[Analyze Portfolios] Margin-based starting capital: ${margin_based_capital:,.2f}")
        logger.info(f"[Analyze Portfolios] Using starting capital: ${starting_capital:,.2f}")

        # Validate portfolios first and filter out non-existent ones
        valid_portfolio_ids = []
        invalid_ids = []
        for portfolio_id in portfolio_ids:
            portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
            if portfolio:
                valid_portfolio_ids.append(portfolio_id)
            else:
                invalid_ids.append(portfolio_id)

        # Log once if there were invalid IDs
        if invalid_ids:
            logger.info(f"[Analyze Portfolios] Filtered out {len(invalid_ids)} non-existent portfolio(s): {invalid_ids}")

        if not valid_portfolio_ids:
            return {"success": False, "error": "None of the selected portfolios exist in the database"}

        # Now fetch data only for valid portfolios
        portfolios_data = []
        for portfolio_id in valid_portfolio_ids:
            portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
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
            cached = get_cached_analysis_result(db, valid_portfolio_ids[i], 0.05, 20, True, starting_capital)
            if cached:
                import json
                metrics = json.loads(cached.metrics_json) if cached.metrics_json else {}
                df = PortfolioService.get_portfolio_dataframe(db, valid_portfolio_ids[i], columns=["Date", "P/L", "Daily_Return"])
                # Check for missing/zero metrics
                if not metrics or any(metrics.get(k, 0) == 0 for k in ["sharpe_ratio", "total_return", "final_account_value"]):
                    result = process_individual_portfolios([(name, df)], rf_rate=rf_rate, sma_window=sma_window, use_trading_filter=use_trading_filter, starting_capital=starting_capital, date_range_start=date_range_start, date_range_end=date_range_end)[0]
                    logger.error(f"[ROUTER:optimization] About to call store_analysis_result for portfolio_id={valid_portfolio_ids[i]}, metrics={result['metrics']}")
                    PortfolioService.store_analysis_result(db, valid_portfolio_ids[i], "individual", result['metrics'], {"rf_rate": rf_rate, "sma_window": sma_window, "use_trading_filter": use_trading_filter, "starting_capital": starting_capital})
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
                result = process_individual_portfolios([(name, df)], rf_rate=rf_rate, sma_window=sma_window, use_trading_filter=use_trading_filter, starting_capital=starting_capital, date_range_start=date_range_start, date_range_end=date_range_end)[0]
                logger.error(f"[ROUTER:optimization] About to call store_analysis_result for portfolio_id={valid_portfolio_ids[i]}, metrics={result['metrics']}")
                PortfolioService.store_analysis_result(db, valid_portfolio_ids[i], "individual", result['metrics'], {"rf_rate": rf_rate, "sma_window": sma_window, "use_trading_filter": use_trading_filter, "starting_capital": starting_capital})
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
                            filename_prefix=f"analysis_portfolio_{i}_{valid_portfolio_ids[i] if i < len(valid_portfolio_ids) else 'unknown'}", 
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
                        'cvar': float(result['metrics'].get('cvar', 0)),
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
                        'number_of_trading_days': int(result['metrics'].get('number_of_trading_days', 0)),
                        'worst_pl_day': float(result['metrics'].get('worst_pl_day', 0)),
                        'worst_pl_date': result['metrics'].get('worst_pl_date', ''),
                        'best_pl_day': float(result['metrics'].get('best_pl_day', 0)),
                        'best_pl_date': result['metrics'].get('best_pl_date', ''),
                        'days_in_drawdown': int(result['metrics'].get('days_in_drawdown', 0)),
                        'avg_drawdown_length': float(result['metrics'].get('avg_drawdown_length', 0)),
                        'num_drawdown_periods': int(result['metrics'].get('num_drawdown_periods', 0)),
                        'days_loss_over_half_pct': int(result['metrics'].get('days_loss_over_half_pct', 0)),
                        'days_loss_over_three_quarters_pct': int(result['metrics'].get('days_loss_over_three_quarters_pct', 0)),
                        'days_loss_over_one_pct': int(result['metrics'].get('days_loss_over_one_pct', 0)),
                        'days_gain_over_half_pct': int(result['metrics'].get('days_gain_over_half_pct', 0)),
                        'days_gain_over_three_quarters_pct': int(result['metrics'].get('days_gain_over_three_quarters_pct', 0)),
                        'days_gain_over_one_pct': int(result['metrics'].get('days_gain_over_one_pct', 0)),
                        'days_loss_over_half_pct_starting_cap': int(result['metrics'].get('days_loss_over_half_pct_starting_cap', 0)),
                        'days_loss_over_three_quarters_pct_starting_cap': int(result['metrics'].get('days_loss_over_three_quarters_pct_starting_cap', 0)),
                        'days_loss_over_one_pct_starting_cap': int(result['metrics'].get('days_loss_over_one_pct_starting_cap', 0)),
                        'days_gain_over_half_pct_starting_cap': int(result['metrics'].get('days_gain_over_half_pct_starting_cap', 0)),
                        'days_gain_over_three_quarters_pct_starting_cap': int(result['metrics'].get('days_gain_over_three_quarters_pct_starting_cap', 0)),
                        'days_gain_over_one_pct_starting_cap': int(result['metrics'].get('days_gain_over_one_pct_starting_cap', 0)),
                        'largest_profit_day': float(result['metrics'].get('largest_profit_day', 0)),
                        'largest_profit_date': result['metrics'].get('largest_profit_date', '')
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
                equal_weights = [1.0] * len(valid_portfolio_ids)
                logger.info(f"[Analyze Portfolios] Using equal weights (1x each): {equal_weights}")

                blended_df, blended_metrics, _ = create_blended_portfolio(
                    db=db,
                    portfolio_ids=valid_portfolio_ids,
                    weights=equal_weights,
                    name=f"Equal-Weight Blended Portfolio ({len(portfolios_data)} strategies)",
                    description=f"Equal-weight blend of {len(portfolios_data)} portfolios",
                    date_range_start=date_range_start,
                    date_range_end=date_range_end,
                    starting_capital=starting_capital,
                    rf_rate=rf_rate,
                    sma_window=sma_window,
                    use_trading_filter=use_trading_filter
                )
                if blended_df is not None and blended_metrics is not None:
                    blended_plots_list = []
                    try:
                        logger.info("[Analyze Portfolios] Creating plots for blended portfolio")
                        portfolio_ids_str = "_".join(str(pid) for pid in valid_portfolio_ids)
                        unique_prefix = f"analysis_blended_{len(valid_portfolio_ids)}portfolios_{portfolio_ids_str}"
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
                        # Create correlation data using proper correlation approach
                        correlation_data = pd.DataFrame()
                        portfolio_names = []
                        for i, (name, orig_df) in enumerate(portfolios_data):
                            if i < len(individual_results) and 'clean_df' in individual_results[i]:
                                # Sum P/L by date first (handle multiple trades per day)
                                if 'Date' in orig_df.columns:
                                    df_copy = orig_df.copy()
                                    df_copy['Date'] = pd.to_datetime(df_copy['Date'])
                                    # Group by date and sum P/L values
                                    daily_pnl_sum = df_copy.groupby('Date')['P/L'].sum()
                                    daily_pnl_sum.name = name
                                    
                                    # Join with correlation_data using outer join to align dates
                                    if correlation_data.empty:
                                        correlation_data = daily_pnl_sum.to_frame()
                                    else:
                                        correlation_data = correlation_data.join(daily_pnl_sum, how='outer')
                                    
                                    portfolio_names.append(name)
                                else:
                                    # Fallback if no Date column - assume data is already daily
                                    daily_pnl_sum = orig_df['P/L'].fillna(0)
                                    daily_pnl_sum.name = name
                                    
                                    if correlation_data.empty:
                                        correlation_data = daily_pnl_sum.to_frame()
                                    else:
                                        correlation_data = correlation_data.join(daily_pnl_sum, how='outer')
                                    
                                    portfolio_names.append(name)
                        
                        # Fill NaN values with 0 for days where portfolios don't have trades
                        correlation_data = correlation_data.fillna(0)
                        if len(correlation_data.columns) >= 2:
                            # Save correlation data to CSV for debugging
                            debug_csv_path = os.path.join(UPLOAD_FOLDER, 'plots', 'correlation_debug_data_equal_weighted.csv')
                            correlation_data.to_csv(debug_csv_path, index=True)
                            logger.info(f"[Analyze Portfolios] Correlation debug data saved to: {debug_csv_path}")
                            logger.info(f"[Analyze Portfolios] Correlation data shape: {correlation_data.shape}")
                            # Calculate preview using new correlation method
                            value_columns = list(correlation_data.columns)
                            correlation_matrix_preview = calculate_correlation_matrix_from_dataframe(correlation_data, value_columns)
                            logger.info(f"[Analyze Portfolios] Correlation matrix preview:\n{correlation_matrix_preview}")
                            
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

                    # Extract daily time series data (Date and Account Value) for chart
                    daily_data = []
                    if blended_df is not None and 'Date' in blended_df.columns and 'Account Value' in blended_df.columns:
                        # Calculate daily P/L changes for validation
                        blended_df['Daily_PL_Change'] = blended_df['Account Value'].diff()

                        for _, row in blended_df[['Date', 'Account Value', 'P/L']].iterrows():
                            daily_data.append({
                                'date': row['Date'].strftime('%Y-%m-%d') if hasattr(row['Date'], 'strftime') else str(row['Date']),
                                'account_value': float(row['Account Value']),
                                'daily_pl': float(row['P/L']) if 'P/L' in row else 0
                            })

                        # Log validation data
                        worst_drop = blended_df['Daily_PL_Change'].min()
                        worst_drop_date = blended_df.loc[blended_df['Daily_PL_Change'].idxmin(), 'Date']
                        worst_pl_single_day = blended_df['P/L'].min()
                        worst_pl_date = blended_df.loc[blended_df['P/L'].idxmin(), 'Date']

                        logger.info(f"[Analyze Portfolios] Extracted {len(daily_data)} daily data points for chart")
                        logger.info(f"[Analyze Portfolios] Worst Account Value drop (day-to-day): ${worst_drop:.2f} on {worst_drop_date}")
                        logger.info(f"[Analyze Portfolios] Worst P/L single day: ${worst_pl_single_day:.2f} on {worst_pl_date}")
                        logger.info(f"[Analyze Portfolios] Account Value range: ${blended_df['Account Value'].min():.2f} to ${blended_df['Account Value'].max():.2f}")

                    simplified_blended_result = {
                        'filename': f'Blended Portfolio ({len(portfolios_data)} strategies)',
                        'type': 'blended',
                        'plots': blended_plots_list,
                        'daily_data': daily_data,
                        'metrics': {
                            'sharpe_ratio': float(blended_metrics.get('sharpe_ratio', 0)),
                            'sortino_ratio': float(blended_metrics.get('sortino_ratio', 0)),
                            'ulcer_index': float(blended_metrics.get('ulcer_index', 0)),
                            'upi': float(blended_metrics.get('upi', 0)),
                            'kelly_criterion': float(blended_metrics.get('kelly_criterion', 0)),
                            'cvar': float(blended_metrics.get('cvar', 0)),
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
                            'number_of_trading_days': int(blended_metrics.get('number_of_trading_days', 0)),
                            'beta': float(blended_metrics.get('beta', 0)),
                            'alpha': float(blended_metrics.get('alpha', 0)),
                            'r_squared': float(blended_metrics.get('r_squared', 0)),
                            'beta_observation_count': int(blended_metrics.get('beta_observation_count', 0)),
                            'worst_pl_day': float(blended_metrics.get('worst_pl_day', 0)),
                            'worst_pl_date': blended_metrics.get('worst_pl_date', ''),
                            'best_pl_day': float(blended_metrics.get('best_pl_day', 0)),
                            'best_pl_date': blended_metrics.get('best_pl_date', ''),
                            'days_in_drawdown': int(blended_metrics.get('days_in_drawdown', 0)),
                            'avg_drawdown_length': float(blended_metrics.get('avg_drawdown_length', 0)),
                            'num_drawdown_periods': int(blended_metrics.get('num_drawdown_periods', 0)),
                            'days_loss_over_half_pct': int(blended_metrics.get('days_loss_over_half_pct', 0)),
                            'days_loss_over_three_quarters_pct': int(blended_metrics.get('days_loss_over_three_quarters_pct', 0)),
                            'days_loss_over_one_pct': int(blended_metrics.get('days_loss_over_one_pct', 0)),
                            'days_gain_over_half_pct': int(blended_metrics.get('days_gain_over_half_pct', 0)),
                            'days_gain_over_three_quarters_pct': int(blended_metrics.get('days_gain_over_three_quarters_pct', 0)),
                            'days_gain_over_one_pct': int(blended_metrics.get('days_gain_over_one_pct', 0)),
                            'days_loss_over_half_pct_starting_cap': int(blended_metrics.get('days_loss_over_half_pct_starting_cap', 0)),
                            'days_loss_over_three_quarters_pct_starting_cap': int(blended_metrics.get('days_loss_over_three_quarters_pct_starting_cap', 0)),
                            'days_loss_over_one_pct_starting_cap': int(blended_metrics.get('days_loss_over_one_pct_starting_cap', 0)),
                            'days_gain_over_half_pct_starting_cap': int(blended_metrics.get('days_gain_over_half_pct_starting_cap', 0)),
                            'days_gain_over_three_quarters_pct_starting_cap': int(blended_metrics.get('days_gain_over_three_quarters_pct_starting_cap', 0)),
                            'days_gain_over_one_pct_starting_cap': int(blended_metrics.get('days_gain_over_one_pct_starting_cap', 0)),
                            'largest_profit_day': float(blended_metrics.get('largest_profit_day', 0)),
                            'largest_profit_date': blended_metrics.get('largest_profit_date', '')
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
            "margin_based_calculation": starting_capital == margin_based_capital
        }
    except Exception as e:
        logger.error(f"[Analyze Portfolios] Error analyzing portfolios: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Analysis failed: {str(e)}"}

@router.delete("/optimization-cache")
async def clear_optimization_cache(db: Session = Depends(get_db)):
    """
    Clear the optimization cache to force fresh optimization runs
    """
    try:
        from models import OptimizationCache
        
        # Count existing cache entries
        cache_count = db.query(OptimizationCache).count()
        
        # Clear all cache entries
        deleted_count = db.query(OptimizationCache).delete()
        db.commit()
        
        logger.info(f"[Cache Clear] Cleared {deleted_count} optimization cache entries")
        
        return {
            "success": True,
            "message": f"Optimization cache cleared successfully",
            "entries_deleted": deleted_count,
            "previous_count": cache_count
        }
        
    except Exception as e:
        logger.error(f"[Cache Clear] Error clearing optimization cache: {str(e)}")
        db.rollback()
        return {
            "success": False,
            "error": f"Failed to clear optimization cache: {str(e)}"
        }

@router.get("/cached-results")
async def get_cached_optimization_results(
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
    order_by: str = "created_at",
    order_direction: str = "desc"
):
    """
    Get cached portfolio optimization results for browsing

    Args:
        limit: Maximum number of results to return (default 50)
        offset: Number of results to skip (default 0)
        order_by: Field to order by (created_at, portfolio_count, optimal_cagr, optimal_max_drawdown, optimal_return_drawdown_ratio)
        order_direction: Order direction (asc or desc)

    Returns:
        JSON response with cached optimization results and portfolio names
    """
    try:
        from models import OptimizationCache
        import json

        logger.info(f"[Cached Results] Fetching cached optimization results (limit={limit}, offset={offset})")

        # Build query with ordering
        query = db.query(OptimizationCache).filter(OptimizationCache.success == True)

        # Apply ordering
        if order_by == "created_at":
            order_field = OptimizationCache.created_at
        elif order_by == "portfolio_count":
            order_field = OptimizationCache.portfolio_count
        elif order_by == "optimal_cagr":
            order_field = OptimizationCache.optimal_cagr
        elif order_by == "optimal_max_drawdown":
            order_field = OptimizationCache.optimal_max_drawdown
        elif order_by == "optimal_return_drawdown_ratio":
            order_field = OptimizationCache.optimal_return_drawdown_ratio
        elif order_by == "access_count":
            order_field = OptimizationCache.access_count
        else:
            order_field = OptimizationCache.created_at

        if order_direction.lower() == "asc":
            query = query.order_by(order_field.asc())
        else:
            query = query.order_by(order_field.desc())

        # Apply pagination
        cached_results = query.offset(offset).limit(limit).all()
        total_count = query.count()

        # Build response with portfolio names
        results = []
        for cache_entry in cached_results:
            try:
                # Parse portfolio IDs
                portfolio_ids = [int(pid) for pid in cache_entry.portfolio_ids.split(',')]

                # Get portfolio names
                portfolio_names = []
                for pid in portfolio_ids:
                    portfolio = PortfolioService.get_portfolio_by_id(db, pid)
                    if portfolio:
                        portfolio_names.append(portfolio.name)
                    else:
                        portfolio_names.append(f"Portfolio {pid} (deleted)")

                # Parse JSON fields
                optimal_weights = json.loads(cache_entry.optimal_weights)
                optimal_ratios = json.loads(cache_entry.optimal_ratios)

                result = {
                    "id": cache_entry.id,
                    "name": cache_entry.name,
                    "portfolio_ids": portfolio_ids,
                    "portfolio_names": portfolio_names,
                    "portfolio_count": cache_entry.portfolio_count,
                    "optimization_method": cache_entry.optimization_method,
                    "optimal_weights": optimal_weights,
                    "optimal_ratios": optimal_ratios,
                    "metrics": {
                        "cagr": cache_entry.optimal_cagr,
                        "max_drawdown": cache_entry.optimal_max_drawdown,
                        "return_drawdown_ratio": cache_entry.optimal_return_drawdown_ratio,
                        "sharpe_ratio": cache_entry.optimal_sharpe_ratio
                    },
                    "parameters": {
                        "rf_rate": cache_entry.rf_rate,
                        "sma_window": cache_entry.sma_window,
                        "use_trading_filter": cache_entry.use_trading_filter,
                        "starting_capital": cache_entry.starting_capital,
                        "min_weight": cache_entry.min_weight,
                        "max_weight": cache_entry.max_weight
                    },
                    "execution_info": {
                        "iterations": cache_entry.iterations,
                        "execution_time_seconds": cache_entry.execution_time_seconds,
                        "explored_combinations_count": cache_entry.explored_combinations_count,
                        "access_count": cache_entry.access_count
                    },
                    "timestamps": {
                        "created_at": cache_entry.created_at.isoformat() if cache_entry.created_at else None,
                        "last_accessed_at": cache_entry.last_accessed_at.isoformat() if cache_entry.last_accessed_at else None
                    }
                }
                results.append(result)

            except Exception as e:
                logger.warning(f"[Cached Results] Error processing cache entry {cache_entry.id}: {str(e)}")
                continue

        logger.info(f"[Cached Results] Returning {len(results)} cached optimization results")

        return {
            "success": True,
            "results": results,
            "pagination": {
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count
            }
        }

    except Exception as e:
        logger.error(f"[Cached Results] Error fetching cached optimization results: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to fetch cached optimization results: {str(e)}"
        }

@router.put("/cached-results/{optimization_id}/name")
async def update_optimization_name(
    optimization_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Update the name of an optimization result

    Args:
        optimization_id: ID of the optimization to update
        request: Request body containing the new name

    Returns:
        JSON response indicating success or failure
    """
    try:
        from models import OptimizationCache

        # Parse request body
        body = await request.json()
        new_name = body.get('name', '').strip()

        if not new_name:
            return {
                "success": False,
                "error": "Name cannot be empty"
            }

        if len(new_name) > 200:
            return {
                "success": False,
                "error": "Name must be 200 characters or less"
            }

        logger.info(f"[Update Name] Updating optimization {optimization_id} name to: {new_name}")

        # Find the optimization entry
        optimization = db.query(OptimizationCache).filter(
            OptimizationCache.id == optimization_id
        ).first()

        if not optimization:
            return {
                "success": False,
                "error": f"Optimization {optimization_id} not found"
            }

        # Update the name
        old_name = optimization.name
        optimization.name = new_name
        db.commit()

        logger.info(f"[Update Name] Successfully updated optimization {optimization_id} name from '{old_name}' to '{new_name}'")

        return {
            "success": True,
            "message": f"Optimization name updated to '{new_name}'",
            "old_name": old_name,
            "new_name": new_name
        }

    except Exception as e:
        logger.error(f"[Update Name] Error updating optimization name: {str(e)}")
        db.rollback()
        return {
            "success": False,
            "error": f"Failed to update optimization name: {str(e)}"
        }

@router.delete("/cached-results/{optimization_id}")
async def delete_optimization_result(
    optimization_id: int,
    db: Session = Depends(get_db)
):
    """Delete a cached optimization result"""
    try:
        from models import OptimizationCache

        # Find the optimization cache entry
        cache_entry = db.query(OptimizationCache).filter(
            OptimizationCache.id == optimization_id
        ).first()

        if not cache_entry:
            return {"success": False, "error": "Optimization result not found"}

        # Log the deletion
        logger.info(f"[Delete Optimization] Deleting optimization {optimization_id}: {cache_entry.name or f'Optimization #{optimization_id}'}")

        # Delete the entry
        db.delete(cache_entry)
        db.commit()

        logger.info(f"[Delete Optimization] Successfully deleted optimization cache entry {optimization_id}")
        return {"success": True, "message": "Optimization result deleted successfully"}

    except Exception as e:
        logger.error(f"[Delete Optimization] Error deleting optimization result {optimization_id}: {str(e)}")
        db.rollback()
        return {"success": False, "error": f"Failed to delete optimization result: {str(e)}"}


@router.post("/export-blended-csv")
async def export_blended_portfolio_csv(request: Request, db: Session = Depends(get_db)):
    """
    Export blended portfolio data as CSV with columns:
    date, net liquidity, daily P/L $, daily P/L %, current drawdown %
    """
    try:
        data = await request.json()
        portfolio_ids = data.get('portfolio_ids', [])
        portfolio_weights = data.get('portfolio_weights', [])
        starting_capital = data.get('starting_capital', 1000000.0)
        rf_rate = data.get('rf_rate', 0.043)
        sma_window = data.get('sma_window', 20)
        use_trading_filter = data.get('use_trading_filter', True)
        date_range_start = data.get('date_range_start')
        date_range_end = data.get('date_range_end')

        logger.info(f"[Export CSV] Generating blended portfolio CSV for {len(portfolio_ids)} portfolios")

        # Create blended portfolio
        blended_df, blended_metrics, _ = create_blended_portfolio(
            db=db,
            portfolio_ids=portfolio_ids,
            weights=portfolio_weights,
            name="Blended Portfolio Export",
            starting_capital=starting_capital,
            rf_rate=rf_rate,
            sma_window=sma_window,
            use_trading_filter=use_trading_filter,
            date_range_start=date_range_start,
            date_range_end=date_range_end
        )

        if blended_df is None or blended_df.empty:
            logger.error("[Export CSV] Failed to generate blended portfolio data")
            return {"success": False, "error": "Failed to generate blended portfolio data"}

        # Select and rename columns for export
        export_df = pd.DataFrame({
            'Date': blended_df['Date'].dt.strftime('%Y-%m-%d'),
            'Net Liquidity': blended_df['Account Value'].round(2),
            'Daily P/L $': blended_df['P/L'].round(2),
            'Daily P/L %': (blended_df['Daily Return'] * 100).round(4),
            'Current Drawdown %': (blended_df['Drawdown Pct'] * 100).round(4)
        })

        # Convert to CSV
        csv_buffer = io.StringIO()
        export_df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)

        # Generate filename
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"blended_portfolio_{timestamp}.csv"

        logger.info(f"[Export CSV] Successfully generated CSV with {len(export_df)} rows")

        # Return as streaming response
        return StreamingResponse(
            iter([csv_buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"[Export CSV] Error generating CSV: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Failed to generate CSV: {str(e)}"} 