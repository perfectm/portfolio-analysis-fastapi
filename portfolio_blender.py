"""
Portfolio blending utilities for combining multiple portfolios
"""
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any, Tuple

from portfolio_processor import process_portfolio_data, _convert_numpy_types

logger = logging.getLogger(__name__)


def create_blended_portfolio(
    files_data: List[Tuple[str, pd.DataFrame]], 
    rf_rate: float = 0.043,
    sma_window: int = 20,
    use_trading_filter: bool = True,
    starting_capital: float = 100000.0,
    weights: List[float] = None
) -> Tuple[pd.DataFrame, Dict[str, Any], pd.DataFrame]:
    """
    Create a blended portfolio from multiple portfolio files
    
    Args:
        files_data: List of (filename, dataframe) tuples
        rf_rate: Annual risk-free rate
        sma_window: SMA window
        use_trading_filter: Whether to use trading filter
        starting_capital: Starting capital
        weights: List of weights for each portfolio (must sum to 1.0)
        
    Returns:
        Tuple of (blended_df, blended_metrics, correlation_data)
    """
    blended_trades = pd.DataFrame()
    correlation_data = pd.DataFrame()
    portfolio_names = []
    
    # Validate and set up weights
    if weights is None:
        # Equal weighting if no weights provided
        weights = [1.0 / len(files_data)] * len(files_data)
        logger.info(f"Using equal weighting: {weights}")
    else:
        # Validate weights
        if len(weights) != len(files_data):
            raise ValueError(f"Number of weights ({len(weights)}) must match number of files ({len(files_data)})")
        
        # Normalize weights to sum to 1.0 if they don't already
        weight_sum = sum(weights)
        if abs(weight_sum - 1.0) > 0.001:  # Allow small floating point errors
            weights = [w / weight_sum for w in weights]
            logger.info(f"Normalized weights to sum to 1.0: {weights}")
        else:
            logger.info(f"Using provided weights: {weights}")
    
    # Store individual portfolio P/L data for weighted blending
    individual_portfolios_pl = []
    
    successfully_processed_portfolios = []
    
    for i, (filename, df) in enumerate(files_data):
        try:
            logger.info(f"Processing file for blended portfolio: {filename} (weight: {weights[i]:.3f})")
            logger.info(f"Input DataFrame shape for {filename}: {df.shape}")
            
            # Process individual file to get clean trade data
            clean_df, individual_metrics = process_portfolio_data(
                df,
                rf_rate=rf_rate,
                sma_window=sma_window,
                use_trading_filter=use_trading_filter,
                starting_capital=starting_capital
            )
            
            logger.info(f"Processed DataFrame shape for {filename}: {clean_df.shape}")
            
            # Store daily returns for correlation analysis
            portfolio_name = filename.replace('.csv', '')
            portfolio_names.append(portfolio_name)
            successfully_processed_portfolios.append((filename, portfolio_name, i))
            
            # Get daily account returns for correlation
            daily_returns = clean_df.set_index('Date')['Daily Return'].fillna(0)
            logger.info(f"Daily returns shape for {filename}: {daily_returns.shape}")
            
            if correlation_data.empty:
                correlation_data = daily_returns.to_frame(portfolio_name)
                logger.info(f"Initialized correlation_data with {portfolio_name}: shape {correlation_data.shape}")
            else:
                correlation_data = correlation_data.join(daily_returns.to_frame(portfolio_name), how='outer')
                logger.info(f"Added {portfolio_name} to correlation_data: shape {correlation_data.shape}, columns: {list(correlation_data.columns)}")
            
            # Store individual portfolio P/L data with weighting
            # Group by date to get daily P/L and apply weight
            daily_pl = clean_df.groupby('Date')['P/L'].sum().reset_index()
            daily_pl['P/L'] = daily_pl['P/L'] * weights[i]  # Apply weight to P/L
            individual_portfolios_pl.append(daily_pl)
            
            logger.info(f"Successfully processed {filename} for blended portfolio")
            
        except Exception as e:
            logger.error(f"Error processing {filename} for blended portfolio: {str(e)}", exc_info=True)
            logger.warning(f"Skipping {filename} - will not be included in correlation analysis or blended portfolio")
            continue
    
    logger.info(f"Successfully processed {len(successfully_processed_portfolios)} out of {len(files_data)} portfolios")
    logger.info(f"Final correlation_data shape: {correlation_data.shape}, columns: {list(correlation_data.columns)}")
    logger.info(f"Successfully processed portfolios: {[name for _, name, _ in successfully_processed_portfolios]}")
    
    # Combine all weighted portfolios
    if individual_portfolios_pl:
        # Start with the first portfolio
        blended_trades = individual_portfolios_pl[0].copy()
        
        # Add subsequent portfolios
        for daily_pl in individual_portfolios_pl[1:]:
            blended_trades = pd.merge(blended_trades, daily_pl, on='Date', how='outer', suffixes=('', '_new'))
            # Sum P/L columns, treating NaN as 0
            blended_trades['P/L'] = blended_trades['P/L'].fillna(0) + blended_trades['P/L_new'].fillna(0)
            blended_trades = blended_trades.drop('P/L_new', axis=1)
    
    # Process blended portfolio if we have data
    if not blended_trades.empty and len(files_data) > 1:
        try:
            logger.info("Processing weighted blended portfolio")
            logger.info(f"Portfolio weights: {dict(zip(portfolio_names, weights))}")
            logger.info(f"Initial total P/L in blended trades: {blended_trades['P/L'].sum():.2f}")
            
            # Ensure Date is datetime type and normalize to midnight
            blended_trades['Date'] = pd.to_datetime(blended_trades['Date']).dt.normalize()
            
            # Sort by date (no need to group since we've already done daily aggregation)
            blended_trades = blended_trades.sort_values('Date').reset_index(drop=True)
            
            logger.info(f"Total P/L after processing: {blended_trades['P/L'].sum():.2f}")
            
            # Process the blended portfolio using the existing function
            blended_df, blended_metrics = process_portfolio_data(
                blended_trades,
                rf_rate=rf_rate,
                sma_window=sma_window,
                use_trading_filter=use_trading_filter,
                starting_capital=starting_capital,
                is_blended=True  # Important flag to indicate this is a blended portfolio
            )
            
            # Add weighting information to metrics
            blended_metrics['Portfolio_Weights'] = dict(zip(portfolio_names, weights))
            blended_metrics['Weighting_Method'] = 'Custom' if any(w != weights[0] for w in weights) else 'Equal'
            
            # Convert numpy types to Python native types for JSON serialization
            blended_metrics = _convert_numpy_types(blended_metrics)
            
            return blended_df, blended_metrics, correlation_data
            
        except Exception as e:
            logger.error(f"Error processing blended portfolio: {str(e)}")
            return None, None, correlation_data
    
    return None, None, correlation_data


def process_individual_portfolios(
    files_data: List[Tuple[str, pd.DataFrame]],
    rf_rate: float = 0.043,
    sma_window: int = 20,
    use_trading_filter: bool = True,
    starting_capital: float = 100000.0
) -> List[Dict[str, Any]]:
    """
    Process individual portfolio files
    
    Args:
        files_data: List of (filename, dataframe) tuples
        rf_rate: Annual risk-free rate
        sma_window: SMA window
        use_trading_filter: Whether to use trading filter
        starting_capital: Starting capital
        
    Returns:
        List of individual portfolio results
    """
    results = []
    
    for i, (filename, df) in enumerate(files_data):
        try:
            logger.info(f"Processing individual portfolio: {filename}")
            
            # Process individual file
            clean_df, individual_metrics = process_portfolio_data(
                df,
                rf_rate=rf_rate,
                sma_window=sma_window,
                use_trading_filter=use_trading_filter,
                starting_capital=starting_capital
            )
            
            # Create individual portfolio result
            individual_result = {
                'filename': filename,
                'metrics': individual_metrics,
                'type': 'file',
                'plots': [],
                'clean_df': clean_df  # Store for plotting
            }
            
            results.append(individual_result)
            
        except Exception as e:
            logger.error(f"Error processing individual portfolio {filename}: {str(e)}", exc_info=True)
            continue
    
    return results
