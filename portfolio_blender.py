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
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def create_blended_portfolio(
    db: Session,
    portfolio_ids: List[int],
    weights: List[float],
    name: str = None,
    description: str = None
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
        
        # Aggregate P/L by date in case of duplicates
        df = df.groupby('Date')['P/L'].sum().reset_index()
        
        # Scale P/L by weight (multiplier)
        df['P/L'] = df['P/L'] * weight
        
        # Get portfolio name for reference
        portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        portfolio_name = f"{portfolio.name} ({weight}x)"
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
        rf_rate=0.05,
        sma_window=20,
        use_trading_filter=True,
        starting_capital=100000.0,
        is_blended=True
    )
    
    # Create blended portfolio record
    if name is None:
        name = f"Blended Portfolio ({', '.join(portfolio_names)})"
        
    blended_portfolio = BlendedPortfolio(
        name=name,
        weighting_method='custom',
        weights_json=json.dumps(dict(zip(portfolio_names, weights))),
        rf_rate=0.05,
        daily_rf_rate=0.000171,
        sma_window=20,
        use_trading_filter=True,
        starting_capital=100000.0
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
