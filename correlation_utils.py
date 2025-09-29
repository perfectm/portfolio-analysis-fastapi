"""
Correlation utilities for portfolio analysis that exclude zero values.

This module provides proper correlation calculation methods that exclude 
zero P&L values from correlation calculations, as recommended for financial
time series analysis.
"""
import numpy as np
import pandas as pd
from typing import Optional, Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


def calculate_correlation_excluding_zeros(x: np.ndarray, y: np.ndarray) -> Optional[float]:
    """
    Calculate Pearson correlation between two arrays, excluding pairs where either value is zero.
    
    This is essential for financial P&L data where zero values represent non-trading days
    and should not be included in correlation calculations.
    
    Args:
        x, y: arrays of equal length containing P&L values
    
    Returns:
        correlation coefficient (float) or None if insufficient data
    """
    # Convert to numpy arrays for easier handling
    x = np.array(x)
    y = np.array(y)
    
    # Create mask for valid pairs (both non-zero and not NaN)
    valid_mask = (x != 0) & (y != 0) & (~np.isnan(x)) & (~np.isnan(y))
    
    # Filter to only valid pairs
    x_valid = x[valid_mask]
    y_valid = y[valid_mask]
    
    # Need at least 2 data points for correlation
    if len(x_valid) < 2:
        logger.warning(f"Insufficient valid data points for correlation: {len(x_valid)} pairs")
        return None
    
    # Calculate means
    mean_x = np.mean(x_valid)
    mean_y = np.mean(y_valid)
    
    # Calculate numerator and denominators
    numerator = np.sum((x_valid - mean_x) * (y_valid - mean_y))
    denominator_x = np.sum((x_valid - mean_x) ** 2)
    denominator_y = np.sum((y_valid - mean_y) ** 2)
    
    # Check for zero variance (would cause division by zero)
    if denominator_x == 0 or denominator_y == 0:
        logger.warning("Zero variance detected in correlation calculation")
        return 0.0
    
    # Calculate correlation
    correlation = numerator / np.sqrt(denominator_x * denominator_y)
    
    return correlation


def build_correlation_matrix(data_dict: Dict[str, np.ndarray]) -> Tuple[np.ndarray, List[str]]:
    """
    Build correlation matrix for multiple strategies excluding zero values.
    
    Args:
        data_dict: dictionary where keys are strategy names and values are P&L arrays
    
    Returns:
        Tuple of (correlation matrix as 2D numpy array, list of strategy names)
    """
    strategy_names = list(data_dict.keys())
    n_strategies = len(strategy_names)
    
    # Initialize correlation matrix
    correlation_matrix = np.zeros((n_strategies, n_strategies))
    
    # Calculate correlations for all pairs
    for i, strategy1 in enumerate(strategy_names):
        for j, strategy2 in enumerate(strategy_names):
            if i == j:
                # Correlation of strategy with itself is always 1
                correlation_matrix[i, j] = 1.0
            else:
                # Calculate correlation between different strategies
                corr = calculate_correlation_excluding_zeros(
                    data_dict[strategy1], 
                    data_dict[strategy2]
                )
                correlation_matrix[i, j] = corr if corr is not None else np.nan
    
    return correlation_matrix, strategy_names


def calculate_correlation_matrix_from_dataframe(
    df: pd.DataFrame, 
    value_columns: List[str]
) -> pd.DataFrame:
    """
    Calculate correlation matrix directly from pandas DataFrame excluding zeros.
    
    Args:
        df: DataFrame containing P&L data
        value_columns: List of column names to calculate correlations for
    
    Returns:
        DataFrame containing correlation matrix with proper column/index names
    """
    n_strategies = len(value_columns)
    correlation_matrix = np.zeros((n_strategies, n_strategies))
    
    for i, col1 in enumerate(value_columns):
        for j, col2 in enumerate(value_columns):
            if i == j:
                correlation_matrix[i, j] = 1.0
            else:
                # Get the data arrays
                x = df[col1].values
                y = df[col2].values
                
                # Calculate correlation excluding zeros
                corr = calculate_correlation_excluding_zeros(x, y)
                correlation_matrix[i, j] = corr if corr is not None else np.nan
    
    # Create DataFrame with proper labels
    correlation_df = pd.DataFrame(
        correlation_matrix,
        index=value_columns,
        columns=value_columns
    )
    
    return correlation_df


def create_correlation_data_for_plotting(
    portfolio_data_dict: Dict[str, pd.DataFrame],
    pnl_column: str = 'P/L'
) -> pd.DataFrame:
    """
    Create correlation data DataFrame suitable for plotting heatmaps.
    
    This function aligns all portfolio data on common dates and creates
    a DataFrame ready for correlation analysis.
    
    Args:
        portfolio_data_dict: Dict mapping portfolio names to their DataFrames
        pnl_column: Name of the P&L column in the DataFrames
    
    Returns:
        DataFrame with portfolio P&L data aligned by date
    """
    correlation_data = pd.DataFrame()
    
    for portfolio_name, df in portfolio_data_dict.items():
        if pnl_column in df.columns and 'Date' in df.columns:
            # Create a series with Date as index and P&L as values
            portfolio_series = df.set_index('Date')[pnl_column]
            portfolio_series.name = portfolio_name
            
            if correlation_data.empty:
                correlation_data = portfolio_series.to_frame()
            else:
                # Join with outer join to include all dates
                correlation_data = correlation_data.join(portfolio_series, how='outer')
    
    # Fill NaN values with 0 (representing non-trading days)
    correlation_data = correlation_data.fillna(0)
    
    return correlation_data


def get_correlation_summary_stats(correlation_matrix: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate summary statistics for a correlation matrix.
    
    Args:
        correlation_matrix: DataFrame containing correlation values
    
    Returns:
        Dictionary with summary statistics
    """
    # Get upper triangle values (excluding diagonal)
    mask = np.triu(np.ones_like(correlation_matrix, dtype=bool), k=1)
    upper_triangle_values = correlation_matrix.values[mask]
    
    # Filter out NaN values
    valid_correlations = upper_triangle_values[~np.isnan(upper_triangle_values)]
    
    if len(valid_correlations) == 0:
        return {
            'mean_correlation': 0.0,
            'median_correlation': 0.0,
            'max_correlation': 0.0,
            'min_correlation': 0.0,
            'std_correlation': 0.0
        }
    
    return {
        'mean_correlation': float(np.mean(valid_correlations)),
        'median_correlation': float(np.median(valid_correlations)),
        'max_correlation': float(np.max(valid_correlations)),
        'min_correlation': float(np.min(valid_correlations)),
        'std_correlation': float(np.std(valid_correlations))
    }