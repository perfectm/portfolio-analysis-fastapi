"""
Portfolio data processing utilities
"""
import pandas as pd
import numpy as np
import logging
from typing import Tuple, Dict, Any

from config import DATE_COLUMNS, PL_COLUMNS

logger = logging.getLogger(__name__)


def process_portfolio_data(
    df: pd.DataFrame, 
    rf_rate: float = 0.043, 
    daily_rf_rate: float = 0.000171, 
    sma_window: int = 20, 
    use_trading_filter: bool = True, 
    starting_capital: float = 100000, 
    is_blended: bool = False
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Process portfolio data and calculate performance metrics
    
    Args:
        df: Input DataFrame with portfolio data
        rf_rate: Annual risk-free rate
        daily_rf_rate: Daily risk-free rate
        sma_window: Simple moving average window
        use_trading_filter: Whether to apply SMA trading filter
        starting_capital: Starting capital amount
        is_blended: Whether this is a blended portfolio
        
    Returns:
        Tuple of processed DataFrame and metrics dictionary
    """
    logger.info(f"Original columns in CSV: {df.columns.tolist()}")
    
    # For blended portfolio, we already have the correct columns
    if is_blended:
        clean_df = df.copy()
        logger.info("Processing as blended portfolio with pre-cleaned data")
    else:
        clean_df = _clean_portfolio_data(df)
    
    # Sort by date
    clean_df = clean_df.sort_values('Date')
    
    # Show sample of data after cleaning
    logger.info("\nSample of cleaned data:")
    logger.info(clean_df.head().to_string())
    logger.info(f"\nData shape after cleaning: {clean_df.shape}")
    logger.info(f"Date range: {clean_df['Date'].min()} to {clean_df['Date'].max()}")
    logger.info(f"Total P/L sum: ${clean_df['P/L'].sum():,.2f}")
    
    # Calculate cumulative P/L and account value
    clean_df['Cumulative P/L'] = clean_df['P/L'].cumsum()
    clean_df['Account Value'] = starting_capital + clean_df['Cumulative P/L']
    
    # Calculate returns based on account value
    clean_df['Daily Return'] = clean_df['Account Value'].pct_change()
    
    # Replace infinite values with NaN
    clean_df['Daily Return'] = clean_df['Daily Return'].replace([np.inf, -np.inf], np.nan)
    
    # Calculate SMA if using trading filter
    if use_trading_filter:
        clean_df['SMA'] = clean_df['Account Value'].rolling(window=sma_window, min_periods=1).mean()
        clean_df['Position'] = np.where(clean_df['Account Value'] > clean_df['SMA'], 1, 0)
        clean_df['Strategy Return'] = clean_df['Daily Return'] * clean_df['Position'].shift(1).fillna(0)
    else:
        clean_df['Strategy Return'] = clean_df['Daily Return']
    
    # Keep track of only days with actual trades
    clean_df['Has_Trade'] = clean_df['P/L'] != 0
    
    # For Sharpe calculation, we'll only use days with trades
    clean_df['Strategy Return'] = clean_df['Strategy Return'].where(clean_df['Has_Trade'])
    
    # Calculate metrics
    metrics = _calculate_portfolio_metrics(
        clean_df, rf_rate, daily_rf_rate, starting_capital
    )
    
    # Calculate drawdown
    clean_df = _calculate_drawdown(clean_df)
    
    # Update metrics with drawdown information
    drawdown_metrics = _calculate_drawdown_metrics(clean_df)
    metrics.update(drawdown_metrics)
    
    _log_portfolio_summary(clean_df, metrics, starting_capital)
    
    return clean_df, metrics


def _clean_portfolio_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardize portfolio data columns"""
    # Find the date column
    date_column = None
    for col in DATE_COLUMNS:
        if col in df.columns:
            date_column = col
            break
            
    if date_column is None:
        logger.error(f"No date column found. Looking for any of: {DATE_COLUMNS}")
        logger.error(f"Available columns are: {df.columns.tolist()}")
        raise ValueError(f"No date column found. Expected one of: {DATE_COLUMNS}")
    
    logger.info(f"Using '{date_column}' as date column")
    
    # Find the P/L column
    pl_column = None
    for col in PL_COLUMNS:
        if col in df.columns:
            pl_column = col
            break
            
    if pl_column is None:
        logger.error(f"No P/L column found. Looking for any of: {PL_COLUMNS}")
        logger.error(f"Available columns are: {df.columns.tolist()}")
        raise ValueError(f"No P/L column found. Expected one of: {PL_COLUMNS}")
    
    logger.info(f"Using '{pl_column}' as P/L column")
    
    # Create a clean DataFrame with standardized column names
    clean_df = pd.DataFrame()
    clean_df['Date'] = pd.to_datetime(df[date_column])
    
    # Clean P/L data - remove any currency symbols and convert to float
    clean_df['P/L'] = df[pl_column].astype(str).str.replace('$', '').str.replace(',', '').str.replace('(', '-').str.replace(')', '').astype(float)
    
    return clean_df


def _calculate_portfolio_metrics(
    clean_df: pd.DataFrame, 
    rf_rate: float, 
    daily_rf_rate: float, 
    starting_capital: float
) -> Dict[str, Any]:
    """Calculate portfolio performance metrics"""
    # Initialize variables with default values
    strategy_mean_return = 0
    strategy_std = 0
    sharpe_ratio = 0
    total_return = 0
    num_years = 0
    
    try:
        # Calculate strategy metrics with error handling - only use days with trades
        valid_returns = clean_df['Strategy Return'][clean_df['Has_Trade']]
        
        if len(valid_returns) > 0:
            # Calculate total return based on account value
            total_return = (clean_df['Account Value'].iloc[-1] / starting_capital) - 1
            
            # Calculate number of years using actual/actual basis
            num_years = _calculate_years_fraction(clean_df['Date'].min(), clean_df['Date'].max())
            
            # Calculate annualized return
            if num_years > 0:
                strategy_mean_return = (1 + total_return) ** (1/num_years) - 1
            else:
                strategy_mean_return = total_return
            
            # Calculate Sharpe ratio and volatility
            sharpe_ratio, strategy_std = _calculate_sharpe_ratio(
                clean_df, rf_rate, starting_capital
            )
            
        else:
            logger.warning("No valid returns found for strategy metrics calculation")
            return _get_default_metrics(starting_capital)
            
    except Exception as e:
        logger.error(f"Error calculating metrics: {str(e)}")
        return _get_default_metrics(starting_capital, clean_df)
    
    return {
        'Sharpe Ratio': float(sharpe_ratio),
        'CAGR': float(strategy_mean_return * 100),  # Convert to percentage
        'Annual Volatility': float(strategy_std * 100),  # Convert to percentage
        'Total Return': float(total_return * 100),  # Convert to percentage
        'Total P/L': float(clean_df['Cumulative P/L'].iloc[-1]),
        'Final Account Value': float(clean_df['Account Value'].iloc[-1]),
        'Peak Value': float(clean_df['Account Value'].max()),
        'Number of Trading Days': len(clean_df[clean_df['Has_Trade']]),
        'Time Period (Years)': float(num_years),
    }


def _calculate_years_fraction(start_date: pd.Timestamp, end_date: pd.Timestamp) -> float:
    """Calculate number of years using actual/actual basis (matching YEARFRAC)"""
    if start_date.year == end_date.year:
        # If same year, use actual days and actual year length
        days_in_year = 366 if pd.Timestamp(f"{start_date.year}-12-31").is_leap_year else 365
        num_years = (end_date - start_date).days / days_in_year
    else:
        # Calculate days in first partial year
        days_in_start_year = 366 if pd.Timestamp(f"{start_date.year}-12-31").is_leap_year else 365
        remaining_days_start = (pd.Timestamp(f"{start_date.year}-12-31") - start_date).days + 1
        first_year_fraction = remaining_days_start / days_in_start_year
        
        # Calculate days in last partial year
        days_in_end_year = 366 if pd.Timestamp(f"{end_date.year}-12-31").is_leap_year else 365
        days_in_end = (end_date - pd.Timestamp(f"{end_date.year}-01-01")).days + 1
        last_year_fraction = days_in_end / days_in_end_year
        
        # Add up complete years in between
        full_years = end_date.year - start_date.year - 1
        
        num_years = first_year_fraction + full_years + last_year_fraction
    
    return num_years


def _calculate_sharpe_ratio(
    clean_df: pd.DataFrame, 
    rf_rate: float, 
    starting_capital: float
) -> Tuple[float, float]:
    """Calculate Sharpe ratio and annual volatility"""
    # Standard Sharpe Ratio Calculation (Best Practice)
    # Use portfolio returns (not just trading days) and calculate properly
    
    # Method 1: Using account value returns (most common for portfolio analysis)
    portfolio_returns = clean_df['Account Value'].pct_change().dropna()
    
    # Convert annual risk-free rate to daily
    daily_rf_for_sharpe = (1 + rf_rate) ** (1/252) - 1
    
    # Calculate excess returns
    excess_returns = portfolio_returns - daily_rf_for_sharpe
    
    # Calculate Sharpe ratio components
    mean_excess_return = excess_returns.mean()
    volatility = excess_returns.std()
    
    # Annualized Sharpe ratio
    sharpe_ratio = (mean_excess_return / volatility) * np.sqrt(252) if volatility != 0 else 0
    
    logger.info(f"\nStandard Sharpe Ratio Calculation:")
    logger.info(f"Annual risk-free rate: {rf_rate:.4f}")
    logger.info(f"Daily risk-free rate: {daily_rf_for_sharpe:.6f}")
    logger.info(f"Mean daily excess return: {mean_excess_return:.6f}")
    logger.info(f"Daily volatility: {volatility:.6f}")
    logger.info(f"Annualized Sharpe Ratio: {sharpe_ratio:.4f}")
    
    # Use the portfolio-based volatility
    strategy_std = volatility * np.sqrt(252)
    
    return sharpe_ratio, strategy_std


def _calculate_drawdown(clean_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate drawdown metrics"""
    clean_df['Rolling Peak'] = clean_df['Account Value'].expanding().max()
    clean_df['Drawdown Amount'] = clean_df['Account Value'] - clean_df['Rolling Peak']
    clean_df['Drawdown Pct'] = clean_df['Drawdown Amount'] / clean_df['Rolling Peak']
    return clean_df


def _calculate_drawdown_metrics(clean_df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate detailed drawdown metrics"""
    # Get maximum drawdown info
    max_drawdown_idx = clean_df['Drawdown Pct'].idxmin()
    max_drawdown = clean_df.loc[max_drawdown_idx, 'Drawdown Amount']
    max_drawdown_pct = clean_df.loc[max_drawdown_idx, 'Drawdown Pct']
    
    # Get detailed drawdown information
    max_drawdown_date = clean_df.loc[max_drawdown_idx, 'Date']
    max_drawdown_account_value = clean_df.loc[max_drawdown_idx, 'Account Value']
    drawdown_peak_value = clean_df.loc[max_drawdown_idx, 'Rolling Peak']
    
    # Find the date when the drawdown began
    pre_drawdown_data = clean_df.loc[:max_drawdown_idx]
    drawdown_peak_idx = pre_drawdown_data[pre_drawdown_data['Account Value'] == drawdown_peak_value].index[-1]
    drawdown_start_date = clean_df.loc[drawdown_peak_idx, 'Date']
    
    # Calculate recovery info
    recovery_days = None
    if max_drawdown_idx < len(clean_df) - 1:
        recovery_series = clean_df.loc[max_drawdown_idx:, 'Account Value']
        drawdown_peak_value = clean_df.loc[max_drawdown_idx, 'Rolling Peak']
        recovered_points = recovery_series[recovery_series >= drawdown_peak_value]
        if not recovered_points.empty:
            recovery_idx = recovered_points.index[0]
            recovery_days = (clean_df.loc[recovery_idx, 'Date'] - clean_df.loc[max_drawdown_idx, 'Date']).days

    # Calculate MAR ratio (Annualized Return / Maximum Drawdown)
    cagr = _calculate_cagr_from_df(clean_df)
    mar_ratio = abs(cagr / abs(max_drawdown_pct)) if max_drawdown_pct != 0 else 0

    return {
        'MAR Ratio': float(mar_ratio),
        'Max Drawdown': float(max_drawdown),
        'Max Drawdown %': float(abs(max_drawdown_pct) * 100),
        'Max Drawdown Date': max_drawdown_date.strftime('%Y-%m-%d'),
        'Drawdown Start Date': drawdown_start_date.strftime('%Y-%m-%d'),
        'Account Value at Drawdown Start': float(drawdown_peak_value),
        'Account Value at Max Drawdown': float(max_drawdown_account_value),
        'Recovery Days': float(recovery_days) if recovery_days is not None else 0.0,
        'Has Recovered': recovery_days is not None
    }


def _calculate_cagr_from_df(clean_df: pd.DataFrame) -> float:
    """Calculate CAGR from DataFrame"""
    total_return = (clean_df['Account Value'].iloc[-1] / clean_df['Account Value'].iloc[0]) - 1
    num_years = _calculate_years_fraction(clean_df['Date'].min(), clean_df['Date'].max())
    if num_years > 0:
        return (1 + total_return) ** (1/num_years) - 1
    return total_return


def _get_default_metrics(starting_capital: float, clean_df: pd.DataFrame = None) -> Dict[str, Any]:
    """Get default metrics when calculation fails"""
    base_metrics = {
        'Sharpe Ratio': 0,
        'MAR Ratio': 0,
        'CAGR': 0,
        'Annual Volatility': 0,
        'Total Return': 0,
        'Total P/L': 0,
        'Final Account Value': starting_capital,
        'Peak Value': starting_capital,
        'Max Drawdown': 0,
        'Max Drawdown %': 0,
        'Number of Trading Days': 0,
        'Time Period (Years)': 0,
        'Recovery Days': 0,
        'Has Recovered': False
    }
    
    if clean_df is not None:
        base_metrics.update({
            'Total P/L': float(clean_df['Cumulative P/L'].iloc[-1]) if 'Cumulative P/L' in clean_df.columns else 0,
            'Final Account Value': float(clean_df['Account Value'].iloc[-1]) if 'Account Value' in clean_df.columns else starting_capital,
            'Peak Value': float(clean_df['Account Value'].max()) if 'Account Value' in clean_df.columns else starting_capital,
            'Number of Trading Days': len(clean_df[clean_df['P/L'] != 0]) if 'P/L' in clean_df.columns else len(clean_df),
        })
    
    return base_metrics


def _log_portfolio_summary(clean_df: pd.DataFrame, metrics: Dict[str, Any], starting_capital: float) -> None:
    """Log portfolio summary information"""
    num_years = metrics.get('Time Period (Years)', 0)
    max_drawdown = metrics.get('Max Drawdown', 0)
    recovery_days = metrics.get('Recovery Days')
    
    logger.info(f"Processed {len(clean_df):,} trades")
    logger.info(f"Date range: {clean_df['Date'].min()} to {clean_df['Date'].max()} ({num_years:.1f} years)")
    logger.info(f"Starting Capital: ${starting_capital:,.2f}")
    logger.info(f"Final Account Value: ${metrics['Final Account Value']:,.2f}")
    logger.info(f"Total P/L: ${metrics['Total P/L']:,.2f}")
    logger.info(f"Total Return: {metrics['Total Return']:.2f}%")
    logger.info(f"CAGR: {metrics['CAGR']:.2f}%")
    logger.info(f"Annual Volatility: {metrics['Annual Volatility']:.2f}%")
    logger.info(f"Sharpe Ratio: {metrics['Sharpe Ratio']:.2f}")
    logger.info(f"Maximum Drawdown: ${abs(max_drawdown):,.2f} ({metrics['Max Drawdown %']:.2f}%)")
    logger.info(f"MAR Ratio: {metrics['MAR Ratio']:.2f}")
    
    if recovery_days is not None and recovery_days > 0:
        logger.info(f"Recovery Time: {recovery_days} days")
    else:
        logger.info("Drawdown not yet recovered")
