"""
Portfolio blending utilities for combining multiple portfolios
"""
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any, Tuple
import json

from models import Portfolio, BlendedPortfolio, BlendedPortfolioMapping
from portfolio_service import PortfolioService
from portfolio_processor import process_portfolio_data, _convert_numpy_types
from beta_calculator import calculate_blended_portfolio_beta
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def create_blended_portfolio(
    db: Session,
    portfolio_ids: List[int],
    weights: List[float],
    name: str = None,
    description: str = None,
    date_range_start: str = None,
    date_range_end: str = None,
    starting_capital: float = 1000000.0,
    rf_rate: float = 0.043,
    sma_window: int = 20,
    use_trading_filter: bool = True
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Create a blended portfolio with memory optimization"""
    import psutil
    process = psutil.Process()
    logger.info(f"[MEMORY] Start blending - RSS: {process.memory_info().rss / 1024 / 1024:.2f} MB")
    
    if len(portfolio_ids) != len(weights):
        raise ValueError("Number of portfolios must match number of weights")
        
    # Validate that all weights are positive
    if any(w <= 0 for w in weights):
        raise ValueError("All weights must be positive numbers")
    
    individual_portfolios_pl = []
    portfolio_names = []
    
    # Process each portfolio with minimal memory footprint
    for idx, (portfolio_id, weight) in enumerate(zip(portfolio_ids, weights)):
        logger.info(f"Processing portfolio {portfolio_id} with weight {weight}x")
        
        # Load only necessary columns
        df = PortfolioService.get_portfolio_dataframe(
            db, 
            portfolio_id,
            columns=['Date', 'P/L']
        )
        
        if df.empty:
            logger.warning(f"No data found for portfolio {portfolio_id}")
            continue
            
        # Ensure Date is datetime and normalize to midnight
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        
        # Apply date filtering if specified
        if date_range_start:
            start_date = pd.to_datetime(date_range_start).normalize()
            df = df[df['Date'] >= start_date]
            logger.info(f"Portfolio {portfolio_id}: Filtered to dates >= {start_date.date()}")
            
        if date_range_end:
            end_date = pd.to_datetime(date_range_end).normalize()
            df = df[df['Date'] <= end_date]
            logger.info(f"Portfolio {portfolio_id}: Filtered to dates <= {end_date.date()}")
        
        if df.empty:
            logger.warning(f"Portfolio {portfolio_id}: No data remaining after date filtering")
            continue
        
        # Aggregate P/L by date in case of duplicates
        df = df.groupby('Date')['P/L'].sum().reset_index()
        
        # Scale P/L by weight (multiplier)
        df['P/L'] = df['P/L'] * weight
        
        # Get portfolio name for reference
        portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        portfolio_name = f"{portfolio.name} ({weight:.2f}x)"
        portfolio_names.append(portfolio_name)
        
        # Set unique column name for this portfolio's P/L
        df = df.rename(columns={'P/L': f'P/L_{portfolio_id}'})
        individual_portfolios_pl.append(df)
        
        logger.info(f"[MEMORY] After portfolio {idx+1} - RSS: {process.memory_info().rss / 1024 / 1024:.2f} MB")
    
    if not individual_portfolios_pl:
        raise ValueError("No valid portfolios to blend")
    
    # Combine all weighted portfolios efficiently
    logger.info("Combining portfolios...")
    
    # Set index to Date for all DataFrames
    for idx in range(len(individual_portfolios_pl)):
        individual_portfolios_pl[idx] = individual_portfolios_pl[idx].set_index('Date')
    
    # Concatenate all on columns, fill NaN with 0, then sum across columns
    blended_trades = pd.concat(individual_portfolios_pl, axis=1).fillna(0)
    
    # Sum across all P/L columns to get total P/L per day
    pl_columns = [col for col in blended_trades.columns if col.startswith('P/L_')]
    blended_trades['P/L'] = blended_trades[pl_columns].sum(axis=1)
    
    # Keep only the total P/L and reset index
    blended_trades = blended_trades[['P/L']].reset_index()
    
    # Sort by date
    blended_trades = blended_trades.sort_values('Date')
    
    # Free memory from individual portfolio DataFrames
    del individual_portfolios_pl
    
    logger.info(f"[MEMORY] After combining - RSS: {process.memory_info().rss / 1024 / 1024:.2f} MB")
    
    # Process the blended portfolio
    processed_df, metrics = process_portfolio_data(
        blended_trades,
        rf_rate=rf_rate,
        sma_window=sma_window,
        use_trading_filter=use_trading_filter,
        starting_capital=starting_capital,
        is_blended=True
    )
    
    # Create blended portfolio record
    if name is None:
        name = f"Blended Portfolio ({', '.join(portfolio_names)})"
        
    blended_portfolio = BlendedPortfolio(
        name=name,
        weighting_method='custom',
        weights_json=json.dumps(dict(zip(portfolio_names, weights))),
        rf_rate=rf_rate,
        daily_rf_rate=rf_rate / 252,  # Convert annual to daily
        sma_window=sma_window,
        use_trading_filter=use_trading_filter,
        starting_capital=starting_capital
    )
    
    db.add(blended_portfolio)
    db.commit()
    db.refresh(blended_portfolio)
    
    # Create mappings
    for portfolio_id, weight in zip(portfolio_ids, weights):
        mapping = BlendedPortfolioMapping(
            blended_portfolio_id=blended_portfolio.id,
            portfolio_id=portfolio_id,
            weight=weight
        )
        db.add(mapping)
    
    db.commit()
    
    logger.info(f"[MEMORY] End blending - RSS: {process.memory_info().rss / 1024 / 1024:.2f} MB")
    return processed_df, metrics


def create_blended_portfolio_from_files(
    files_data: List[Tuple[str, pd.DataFrame]],
    rf_rate: float = 0.043,
    sma_window: int = 20,
    use_trading_filter: bool = True,
    starting_capital: float = 1000000.0,
    weights: List[float] = None,
    use_capital_allocation: bool = False,
    date_range_start: str = None,
    date_range_end: str = None
) -> Tuple[pd.DataFrame, Dict[str, Any], Dict[str, Any]]:
    """
    Create a blended portfolio from file data (for optimization)
    
    Args:
        files_data: List of (filename, dataframe) tuples
        rf_rate: Annual risk-free rate
        sma_window: SMA window
        use_trading_filter: Whether to use trading filter
        starting_capital: Starting capital
        weights: Portfolio weights (defaults to equal weights)
        use_capital_allocation: Whether to use capital allocation
        
    Returns:
        Tuple of (blended_df, blended_metrics, correlation_data)
    """
    if not files_data:
        return None, None, None
        
    if weights is None:
        weights = [1.0 / len(files_data)] * len(files_data)
    
    if len(weights) != len(files_data):
        return None, None, None
        
    # Process each portfolio individually
    individual_results = process_individual_portfolios(
        files_data, float(rf_rate), int(sma_window), bool(use_trading_filter), float(starting_capital)
    )
    
    if not individual_results:
        return None, None, None
        
    # Create combined P/L by weighting each portfolio
    combined_data = []
    for i, (result, weight) in enumerate(zip(individual_results, weights)):
        if 'clean_df' in result and result['clean_df'] is not None:
            df = result['clean_df'].copy()
            df['Weighted_PL'] = df['P/L'] * weight
            df['Portfolio'] = f"Portfolio_{i}"
            combined_data.append(df[['Date', 'Weighted_PL', 'Portfolio']])
    
    if not combined_data:
        return None, None, None
        
    # Merge all portfolios by date
    blended_df = combined_data[0].copy()
    blended_df = blended_df.rename(columns={'Weighted_PL': 'P/L'})
    blended_df = blended_df.drop('Portfolio', axis=1)
    
    for df in combined_data[1:]:
        blended_df = pd.merge(blended_df, df[['Date', 'Weighted_PL']], on='Date', how='outer')
        blended_df['P/L'] = blended_df['P/L'].fillna(0) + blended_df['Weighted_PL'].fillna(0)
        blended_df = blended_df.drop('Weighted_PL', axis=1)
    
    blended_df = blended_df.sort_values('Date').reset_index(drop=True)
    
    # Apply date filtering if specified
    if date_range_start:
        start_date = pd.to_datetime(date_range_start).normalize()
        blended_df = blended_df[blended_df['Date'] >= start_date]
        logger.info(f"Blended portfolio: Filtered to dates >= {start_date.date()}")
        
    if date_range_end:
        end_date = pd.to_datetime(date_range_end).normalize()
        blended_df = blended_df[blended_df['Date'] <= end_date]
        logger.info(f"Blended portfolio: Filtered to dates <= {end_date.date()}")
    
    if blended_df.empty:
        logger.warning("Blended portfolio: No data remaining after date filtering")
        return None, None, None
    
    blended_df = blended_df.reset_index(drop=True)
    
    # Process the blended portfolio to get metrics
    try:
        processed_df, blended_metrics = process_portfolio_data(
            blended_df, float(rf_rate), int(sma_window), bool(use_trading_filter), float(starting_capital)
        )
        
        # Create correlation data (simplified)
        correlation_data = {"correlation_matrix": {}}
        
        return processed_df, blended_metrics, correlation_data
        
    except Exception as e:
        logger.error(f"Error processing blended portfolio: {e}")
        return None, None, None

def process_individual_portfolios(
    files_data: List[Tuple[str, pd.DataFrame]],
    rf_rate: float = 0.043,
    sma_window: int = 20,
    use_trading_filter: bool = True,
    starting_capital: float = 1000000.0
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
