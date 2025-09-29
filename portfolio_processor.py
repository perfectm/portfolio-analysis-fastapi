"""
Portfolio data processing utilities
"""
import pandas as pd
import numpy as np
import logging
from typing import Tuple, Dict, Any

from config import DATE_COLUMNS, PL_COLUMNS, PREMIUM_COLUMNS, CONTRACTS_COLUMNS
from beta_calculator import calculate_portfolio_beta

logger = logging.getLogger(__name__)


def _convert_numpy_types(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Convert numpy and pandas types to Python native types for JSON serialization"""
    converted = {}
    for key, value in metrics.items():
        if isinstance(value, (np.integer, np.int32, np.int64)):
            converted[key] = int(value)
        elif isinstance(value, (np.floating, np.float32, np.float64)):
            converted[key] = float(value)
        elif isinstance(value, np.bool_):
            converted[key] = bool(value)
        elif pd.isna(value):
            converted[key] = None
        elif isinstance(value, dict):
            # Recursively convert nested dictionaries
            converted[key] = _convert_numpy_types(value)
        elif isinstance(value, (list, tuple)):
            # Convert lists and tuples
            converted[key] = [_convert_numpy_types({0: item})[0] if isinstance(item, dict) 
                             else float(item) if isinstance(item, (np.floating, np.float32, np.float64))
                             else int(item) if isinstance(item, (np.integer, np.int32, np.int64))
                             else bool(item) if isinstance(item, np.bool_)
                             else item for item in value]
        else:
            converted[key] = value
    return converted


def process_portfolio_data(
    df: pd.DataFrame, 
    rf_rate: float = 0.043, 
    daily_rf_rate: float = 0.000171, 
    sma_window: int = 20, 
    use_trading_filter: bool = True, 
    starting_capital: float = 1000000, 
    is_blended: bool = False
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Process portfolio data and calculate performance metrics with memory optimization
    """
    import psutil
    process = psutil.Process()
    logger.info(f"[MEMORY] Start processing - RSS: {process.memory_info().rss / 1024 / 1024:.2f} MB")
    
    # For blended portfolio, we already have the correct columns
    if is_blended:
        clean_df = df
        logger.info("Processing as blended portfolio with pre-cleaned data")
    else:
        clean_df = _clean_portfolio_data(df)
        del df  # Free up memory from original DataFrame
    
    # Optimize memory usage for numeric columns
    for col in clean_df.select_dtypes(include=['float64']).columns:
        clean_df[col] = pd.to_numeric(clean_df[col], downcast='float')
    for col in clean_df.select_dtypes(include=['int64']).columns:
        clean_df[col] = pd.to_numeric(clean_df[col], downcast='integer')
    
    # Sort by date without inplace
    clean_df = clean_df.sort_values('Date')
    
    logger.info(f"[MEMORY] After cleaning - RSS: {process.memory_info().rss / 1024 / 1024:.2f} MB")
    
    # Calculate cumulative P/L and account value
    clean_df['Cumulative P/L'] = clean_df['P/L'].cumsum()
    clean_df['Account Value'] = starting_capital + clean_df['Cumulative P/L']
    
    # Calculate returns based on account value
    clean_df['Daily Return'] = clean_df['Account Value'].pct_change()
    clean_df['Daily Return'] = clean_df['Daily Return'].replace([np.inf, -np.inf], np.nan)
    
    # Calculate SMA if using trading filter
    if use_trading_filter:
        clean_df['SMA'] = clean_df['Account Value'].rolling(window=int(sma_window), min_periods=1).mean()
        clean_df['Position'] = np.where(clean_df['Account Value'] > clean_df['SMA'], 1, 0)
        clean_df['Strategy Return'] = clean_df['Daily Return'] * clean_df['Position'].shift(1).fillna(0)
        # Free memory from intermediate columns without inplace
        clean_df = clean_df.drop(['SMA', 'Position'], axis=1)
    else:
        clean_df['Strategy Return'] = clean_df['Daily Return']
    
    # Keep track of only days with actual trades
    clean_df['Has_Trade'] = clean_df['P/L'] != 0
    clean_df.loc[~clean_df['Has_Trade'], 'Strategy Return'] = np.nan
    
    logger.info(f"[MEMORY] After calculations - RSS: {process.memory_info().rss / 1024 / 1024:.2f} MB")
    
    # Dynamic starting capital calculation
    if not clean_df.empty:
        first_cumulative_pl = clean_df['Cumulative P/L'].iloc[0]
        actual_starting_capital = starting_capital - first_cumulative_pl
    else:
        actual_starting_capital = starting_capital
    
    # Calculate metrics
    metrics = _calculate_portfolio_metrics(
        clean_df, rf_rate, daily_rf_rate, starting_capital, actual_starting_capital
    )
    
    # Calculate drawdown inplace
    clean_df = _calculate_drawdown(clean_df)
    
    # Update metrics with drawdown information
    drawdown_metrics = _calculate_drawdown_metrics(clean_df)
    metrics.update(drawdown_metrics)
    
    _log_portfolio_summary(clean_df, metrics, actual_starting_capital)
    
    # Convert numpy types to Python native types
    metrics = _convert_numpy_types(metrics)
    
    logger.info(f"[MEMORY] End processing - RSS: {process.memory_info().rss / 1024 / 1024:.2f} MB")
    
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
    
    # Find the Premium column (optional)
    premium_column = None
    for col in PREMIUM_COLUMNS:
        if col in df.columns:
            premium_column = col
            break
    
    if premium_column:
        logger.info(f"Using '{premium_column}' as premium column")
    else:
        logger.info("No premium column found - PCR calculation will be unavailable")
    
    # Find the Contracts column (optional)
    contracts_column = None
    for col in CONTRACTS_COLUMNS:
        if col in df.columns:
            contracts_column = col
            break
    
    if contracts_column:
        logger.info(f"Using '{contracts_column}' as contracts column")
    else:
        logger.info("No contracts column found - will use total P/L for PCR calculation")
    
    # Create a clean DataFrame with standardized column names
    clean_df = pd.DataFrame()
    clean_df['Date'] = pd.to_datetime(df[date_column])
    
    # Clean P/L data - remove any currency symbols and convert to float
    clean_df['P/L'] = df[pl_column].astype(str).str.replace('$', '').str.replace(',', '').str.replace('(', '-').str.replace(')', '').astype(float)
    
    # Clean Premium data if available - remove any currency symbols and convert to float
    if premium_column:
        # Handle None/NaN values by replacing with 0 before string processing
        premium_series = df[premium_column].fillna(0)
        clean_df['Premium'] = premium_series.astype(str).str.replace('$', '').str.replace(',', '').str.replace('(', '-').str.replace(')', '').str.replace('None', '0').astype(float)
    
    # Clean Contracts data if available - convert to integer
    if contracts_column:
        # Handle None/NaN values by replacing with 0 before conversion
        contracts_series = df[contracts_column].fillna(0)
        clean_df['Contracts'] = contracts_series.astype(int)
    
    return clean_df


def _calculate_portfolio_metrics(
    clean_df: pd.DataFrame, 
    rf_rate: float, 
    daily_rf_rate: float, 
    original_starting_capital: float,
    actual_starting_capital: float
) -> Dict[str, Any]:
    """Calculate portfolio performance metrics"""
    # Initialize variables with default values
    strategy_mean_return = 0
    strategy_std = 0
    sharpe_ratio = 0
    total_return = 0
    num_years = 0

    # Initialize Beta variables with default values
    beta = 0.0
    alpha = 0.0
    r_squared = 0.0
    beta_obs_count = 0
    
    try:
        # Calculate strategy metrics with error handling - only use days with trades
        valid_returns = clean_df['Strategy Return'][clean_df['Has_Trade']]
        
        logger.info(f"  - Clean DF shape: {clean_df.shape}")
        logger.info(f"  - Original starting capital: {original_starting_capital}")
        logger.info(f"  - Actual starting capital: {actual_starting_capital}")
        logger.info(f"  - Has trades count: {clean_df['Has_Trade'].sum()}")
        logger.info(f"  - Valid returns count: {len(valid_returns)}")
        logger.info(f"  - Account value range: {clean_df['Account Value'].min():.2f} to {clean_df['Account Value'].max():.2f}")
        logger.info(f"  - Cumulative P/L final: {clean_df['Cumulative P/L'].iloc[-1]:.2f}")
        
        if len(valid_returns) > 0:
            # Debug: Let's trace the calculation step by step
            final_account_value = clean_df['Account Value'].iloc[-1]
            total_pl = clean_df['Cumulative P/L'].iloc[-1]
            
            logger.info(f"  - [DEBUG] Original starting capital: ${original_starting_capital:,.2f}")
            logger.info(f"  - [DEBUG] Actual starting capital: ${actual_starting_capital:,.2f}")
            logger.info(f"  - [DEBUG] Final account value: ${final_account_value:,.2f}")
            logger.info(f"  - [DEBUG] Total P/L: ${total_pl:,.2f}")
            logger.info(f"  - [DEBUG] Expected account value: ${original_starting_capital + total_pl:,.2f}")
            
            # Calculate total return based on ORIGINAL starting capital for percentage calculation
            total_return = (final_account_value / original_starting_capital) - 1
            
            logger.info(f"  - [DEBUG] Total return calculation: ({final_account_value:,.2f} / {original_starting_capital:,.2f}) - 1 = {total_return:.6f}")
            logger.info(f"  - [DEBUG] Total return as percentage: {total_return*100:.2f}%")
            
            # Calculate number of years using actual/actual basis
            num_years = _calculate_years_fraction(clean_df['Date'].min(), clean_df['Date'].max())
            
            logger.info(f"  - [DEBUG] Time period years: {num_years:.4f}")
            
            # Calculate annualized return (CAGR)
            if num_years > 0:
                strategy_mean_return = (1 + total_return) ** (1/num_years) - 1
            else:
                strategy_mean_return = total_return
                
            logger.info(f"  - [DEBUG] CAGR calculation: (1 + {total_return:.6f}) ^ (1/{num_years:.4f}) - 1 = {strategy_mean_return:.6f}")
            logger.info(f"  - [DEBUG] CAGR as percentage: {strategy_mean_return*100:.2f}%")
            
            logger.info(f"  - CAGR calculated: {strategy_mean_return:.4f}")
            
            # Calculate Sharpe ratio and volatility - use actual starting capital for returns calculation
            sharpe_ratio, strategy_std = _calculate_sharpe_ratio(
                clean_df, rf_rate, actual_starting_capital
            )
            
            # Calculate additional risk metrics
            sortino_ratio = _calculate_sortino_ratio(clean_df, rf_rate)
            ulcer_index = _calculate_ulcer_index(clean_df)
            upi = _calculate_upi(clean_df, rf_rate)
            kelly_criterion, win_rate = _calculate_kelly_criterion(clean_df)
            pcr, total_premium = _calculate_pcr(clean_df)

            # Calculate Beta against SPX
            try:
                beta, alpha, r_squared, beta_obs_count = calculate_portfolio_beta(clean_df)
                logger.info(f"  - Beta vs SPX: {beta:.4f}")
                logger.info(f"  - Alpha: {alpha:.4f}")
                logger.info(f"  - R-squared: {r_squared:.4f}")
            except Exception as e:
                logger.warning(f"Beta calculation failed: {e}")
                beta, alpha, r_squared, beta_obs_count = 0.0, 0.0, 0.0, 0

            logger.info(f"  - Sharpe ratio: {sharpe_ratio:.4f}")
            logger.info(f"  - Sortino ratio: {sortino_ratio:.4f}")
            logger.info(f"  - Ulcer index: {ulcer_index:.4f}")
            logger.info(f"  - UPI: {upi:.4f}")
            logger.info(f"  - Kelly criterion: {kelly_criterion:.4f}")
            logger.info(f"  - PCR: {pcr:.4f}")
            logger.info(f"  - Annual volatility: {strategy_std:.4f}")

        else:
            logger.warning("No valid returns found for strategy metrics calculation")
            # Still calculate Beta even if no valid returns for other metrics
            try:
                beta, alpha, r_squared, beta_obs_count = calculate_portfolio_beta(clean_df)
                logger.info(f"  - Beta vs SPX (no returns case): {beta:.4f}")
            except Exception as e:
                logger.warning(f"Beta calculation failed (no returns case): {e}")
                beta, alpha, r_squared, beta_obs_count = 0.0, 0.0, 0.0, 0
            # Get default metrics but include calculated Beta values
            default_metrics = _get_default_metrics(original_starting_capital, clean_df)
            default_metrics.update({
                'beta': float(beta),
                'alpha': float(alpha),
                'r_squared': float(r_squared),
                'beta_observation_count': int(beta_obs_count)
            })
            return default_metrics
            
    except Exception as e:
        logger.error(f"Error calculating metrics: {str(e)}")
        return _get_default_metrics(original_starting_capital, clean_df)
    
    return {
        'sharpe_ratio': float(sharpe_ratio),
        'sortino_ratio': float(sortino_ratio),
        'ulcer_index': float(ulcer_index),
        'upi': float(upi),
        'kelly_criterion': float(kelly_criterion),
        'win_rate': float(win_rate),
        'pcr': float(pcr),
        'total_premium': float(total_premium),
        'beta': float(beta),
        'alpha': float(alpha),
        'r_squared': float(r_squared),
        'beta_observation_count': int(beta_obs_count),
        'cagr': float(strategy_mean_return),  # Already as decimal
        'annual_volatility': float(strategy_std),  # Already as decimal
        'total_return': float(total_return),  # Already as decimal
        'total_pl': float(clean_df['Cumulative P/L'].iloc[-1]),
        'final_account_value': float(clean_df['Account Value'].iloc[-1]),
        'peak_value': float(clean_df['Account Value'].max()),
        'number_of_trading_days': len(clean_df[clean_df['Has_Trade']]),
        'time_period_years': float(num_years),
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


def _calculate_sortino_ratio(
    clean_df: pd.DataFrame, 
    rf_rate: float
) -> float:
    """Calculate Sortino ratio (risk-adjusted return using downside deviation)"""
    # Calculate portfolio returns
    portfolio_returns = clean_df['Account Value'].pct_change().dropna()
    
    # Convert annual risk-free rate to daily
    daily_rf = (1 + rf_rate) ** (1/252) - 1
    
    # Calculate excess returns
    excess_returns = portfolio_returns - daily_rf
    
    # Calculate downside deviation (only negative excess returns)
    downside_returns = excess_returns[excess_returns < 0]
    downside_deviation = downside_returns.std() if len(downside_returns) > 0 else 0
    
    # Annualized Sortino ratio
    mean_excess_return = excess_returns.mean()
    sortino_ratio = (mean_excess_return / downside_deviation) * np.sqrt(252) if downside_deviation != 0 else 0
    
    logger.info(f"Sortino Ratio Calculation:")
    logger.info(f"Mean daily excess return: {mean_excess_return:.6f}")
    logger.info(f"Downside deviation: {downside_deviation:.6f}")
    logger.info(f"Annualized Sortino Ratio: {sortino_ratio:.4f}")
    
    return sortino_ratio


def _calculate_ulcer_index(clean_df: pd.DataFrame) -> float:
    """Calculate Ulcer Index (measure of downside risk)"""
    # Ulcer Index measures the depth and duration of drawdowns
    # UI = sqrt(mean(drawdown_percentage^2))
    
    # Calculate running maximum (peaks)
    running_max = clean_df['Account Value'].expanding().max()
    
    # Calculate drawdown percentages
    drawdown_pct = ((clean_df['Account Value'] - running_max) / running_max) * 100
    
    # Calculate Ulcer Index
    ulcer_index = np.sqrt((drawdown_pct ** 2).mean())
    
    logger.info(f"Ulcer Index Calculation:")
    logger.info(f"Mean squared drawdown: {(drawdown_pct ** 2).mean():.4f}")
    logger.info(f"Ulcer Index: {ulcer_index:.4f}")
    
    return ulcer_index


def _calculate_kelly_criterion(clean_df: pd.DataFrame) -> float:
    """Calculate Kelly Criterion for optimal position sizing"""
    # Kelly Criterion = (bp - q) / b
    # Where:
    # b = odds received on the wager (average win / average loss)
    # p = probability of winning
    # q = probability of losing (1 - p)
    
    # Get winning and losing trades
    winning_trades = clean_df[clean_df['P/L'] > 0]['P/L']
    losing_trades = clean_df[clean_df['P/L'] < 0]['P/L']
    
    if len(winning_trades) == 0 or len(losing_trades) == 0:
        logger.info("Kelly Criterion: Not enough winning or losing trades for calculation")
        return 0.0, 0.0
    
    # Calculate win probability
    total_trades = len(clean_df)
    win_probability = len(winning_trades) / total_trades
    loss_probability = 1 - win_probability
    
    # Calculate average win and average loss
    avg_win = winning_trades.mean()
    avg_loss = abs(losing_trades.mean())  # Make positive for calculation
    
    # Calculate odds (b)
    if avg_loss == 0:
        logger.info("Kelly Criterion: Average loss is zero, cannot calculate")
        return 0.0, win_probability
    
    odds = avg_win / avg_loss
    
    # Calculate Kelly Criterion percentage
    kelly_percentage = (odds * win_probability - loss_probability) / odds
    
    logger.info(f"Kelly Criterion Calculation:")
    logger.info(f"Win Probability: {win_probability:.4f}")
    logger.info(f"Loss Probability: {loss_probability:.4f}")
    logger.info(f"Average Win: ${avg_win:.2f}")
    logger.info(f"Average Loss: ${avg_loss:.2f}")
    logger.info(f"Odds (Win/Loss ratio): {odds:.4f}")
    logger.info(f"Kelly Criterion: {kelly_percentage:.4f} ({kelly_percentage*100:.2f}%)")
    
    return kelly_percentage, win_probability


def _calculate_pcr(clean_df: pd.DataFrame) -> tuple[float, float]:
    """Calculate PCR (Premium Capture Rate) for options strategies"""
    # PCR = (Total P/L ÷ Average Contracts) ÷ Total Premium
    # Premium column is already per contract
    
    if 'Premium' not in clean_df.columns:
        logger.info("PCR: No Premium column found - PCR calculation unavailable")
        return 0.0, 0.0
    
    # Get all premium and P/L values (excluding NaN/None values)
    valid_rows = clean_df.dropna(subset=['Premium', 'P/L'])
    
    if len(valid_rows) == 0:
        logger.info("PCR: No valid premium and P/L values found")
        return 0.0, 0.0
    
    total_premium_collected = valid_rows['Premium'].sum()
    total_pl = valid_rows['P/L'].sum()
    
    if total_premium_collected == 0:
        logger.info("PCR: Total premium collected is zero")
        return 0.0, 0.0
    
    # Calculate average contracts and adjust P/L
    if 'Contracts' in clean_df.columns:
        contracts_data = valid_rows.dropna(subset=['Contracts'])
        if len(contracts_data) > 0:
            avg_contracts = contracts_data['Contracts'].mean()
            per_contract_total_pl = total_pl / avg_contracts if avg_contracts > 0 else total_pl
            
            logger.info(f"PCR Calculation (with contracts):")
            logger.info(f"Total P/L: ${total_pl:.2f}")
            logger.info(f"Average contracts per trade: {avg_contracts:.2f}")
            logger.info(f"Per-contract total P/L: ${per_contract_total_pl:.2f}")
        else:
            # No valid contract data, fall back to total P/L
            per_contract_total_pl = total_pl
            logger.info("PCR: No valid contract values found, using total P/L")
    else:
        # No contracts column - For now, assume 2 contracts per trade for proper PCR calculation
        # This handles cases where contracts data isn't stored in the DataFrame yet
        # TODO: Remove this when contracts column is properly stored in database
        per_contract_total_pl = total_pl / 2.0  # Temporary fix for 2-contract trades
        logger.info("PCR: No contracts column found, applying 2-contract adjustment for accurate PCR")
        logger.info(f"Total P/L: ${total_pl:.2f}")
        logger.info(f"Adjusted per-contract P/L (÷2): ${per_contract_total_pl:.2f}")
    
    # Calculate PCR = Per-contract total P/L / Total premium collected
    pcr = per_contract_total_pl / total_premium_collected if total_premium_collected > 0 else 0.0
    
    logger.info(f"Premium entries found: {len(valid_rows)}")
    logger.info(f"Total Premium Collected: ${total_premium_collected:.2f}")
    logger.info(f"Final PCR: {pcr:.4f} ({pcr*100:.2f}%)")
    
    return pcr, total_premium_collected


def _calculate_upi(clean_df: pd.DataFrame, rf_rate: float) -> float:
    """Calculate UPI (Ulcer Performance Index) - risk-adjusted returns using Ulcer Index"""
    # UPI = (Annualized Return - Risk Free Rate) / Ulcer Index
    # This measures excess return per unit of downside risk
    
    # Calculate annualized return (CAGR)
    total_return = (clean_df['Account Value'].iloc[-1] / clean_df['Account Value'].iloc[0]) - 1
    num_years = _calculate_years_fraction(clean_df['Date'].min(), clean_df['Date'].max())
    
    if num_years > 0:
        annualized_return = (1 + total_return) ** (1/num_years) - 1
    else:
        annualized_return = total_return
    
    # Calculate Ulcer Index
    running_max = clean_df['Account Value'].expanding().max()
    drawdown_pct = ((clean_df['Account Value'] - running_max) / running_max) * 100
    ulcer_index = np.sqrt((drawdown_pct ** 2).mean())
    
    if ulcer_index == 0:
        logger.info("UPI: Ulcer Index is zero, cannot calculate UPI")
        return 0.0
    
    # Calculate excess return over risk-free rate
    excess_return = annualized_return - rf_rate
    
    # Calculate UPI
    upi = excess_return / (ulcer_index / 100)  # Convert ulcer_index back to decimal
    
    logger.info(f"UPI Calculation:")
    logger.info(f"Annualized Return: {annualized_return:.4f} ({annualized_return*100:.2f}%)")
    logger.info(f"Risk-Free Rate: {rf_rate:.4f} ({rf_rate*100:.2f}%)")
    logger.info(f"Excess Return: {excess_return:.4f} ({excess_return*100:.2f}%)")
    logger.info(f"Ulcer Index: {ulcer_index:.4f}")
    logger.info(f"UPI: {upi:.4f}")
    
    return upi


def _calculate_drawdown(clean_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate drawdown metrics with memory optimization"""
    clean_df['Rolling Peak'] = clean_df['Account Value'].expanding().max()
    clean_df['Drawdown Amount'] = clean_df['Account Value'] - clean_df['Rolling Peak']
    clean_df['Drawdown Pct'] = clean_df['Drawdown Amount'] / clean_df['Rolling Peak']
    
    # Free memory from intermediate columns without inplace
    clean_df = clean_df.drop(['Rolling Peak'], axis=1)  # Keep Drawdown Amount for metrics
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
    
    # Calculate peak value at time of max drawdown
    peak_value = max_drawdown_account_value - max_drawdown
    
    # Find the date when the drawdown began
    pre_drawdown_data = clean_df.loc[:max_drawdown_idx]
    drawdown_peak_idx = pre_drawdown_data[pre_drawdown_data['Account Value'] == peak_value].index[-1]
    drawdown_start_date = clean_df.loc[drawdown_peak_idx, 'Date']
    
    # Calculate recovery info
    recovery_days = None
    if max_drawdown_idx < len(clean_df) - 1:
        recovery_series = clean_df.loc[max_drawdown_idx:, 'Account Value']
        recovered_points = recovery_series[recovery_series >= peak_value]
        if not recovered_points.empty:
            recovery_idx = recovered_points.index[0]
            recovery_days = (clean_df.loc[recovery_idx, 'Date'] - clean_df.loc[max_drawdown_idx, 'Date']).days

    # Calculate MAR ratio (Annualized Return / Maximum Drawdown)
    cagr = _calculate_cagr_from_df(clean_df)
    mar_ratio = abs(cagr / abs(max_drawdown_pct)) if max_drawdown_pct != 0 else 0

    # Clean up the Drawdown Amount column after metrics calculation without inplace
    clean_df = clean_df.drop(['Drawdown Amount'], axis=1)

    return {
        'mar_ratio': float(mar_ratio),
        'max_drawdown': float(max_drawdown),
        'max_drawdown_percent': float(abs(max_drawdown_pct)),  # Already as decimal
        'max_drawdown_date': max_drawdown_date.strftime('%Y-%m-%d'),
        'drawdown_start_date': drawdown_start_date.strftime('%Y-%m-%d'),
        'account_value_at_drawdown_start': float(peak_value),
        'account_value_at_max_drawdown': float(max_drawdown_account_value),
        'recovery_days': float(recovery_days) if recovery_days is not None else 0.0,
        'has_recovered': recovery_days is not None
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
        'sharpe_ratio': 0,
        'sortino_ratio': 0,
        'ulcer_index': 0,
        'upi': 0,
        'kelly_criterion': 0,
        'win_rate': 0,
        'pcr': 0,
        'total_premium': 0,
        'beta': 0,
        'alpha': 0,
        'r_squared': 0,
        'beta_observation_count': 0,
        'mar_ratio': 0,
        'cagr': 0,
        'annual_volatility': 0,
        'total_return': 0,
        'total_pl': 0,
        'final_account_value': starting_capital,
        'peak_value': starting_capital,
        'max_drawdown': 0,
        'max_drawdown_percent': 0,
        'number_of_trading_days': 0,
        'time_period_years': 0,
        'recovery_days': 0,
        'has_recovered': False
    }
    
    if clean_df is not None:
        base_metrics.update({
            'total_pl': float(clean_df['Cumulative P/L'].iloc[-1]) if 'Cumulative P/L' in clean_df.columns else 0,
            'final_account_value': float(clean_df['Account Value'].iloc[-1]) if 'Account Value' in clean_df.columns else starting_capital,
            'peak_value': float(clean_df['Account Value'].max()) if 'Account Value' in clean_df.columns else starting_capital,
            'number_of_trading_days': len(clean_df[clean_df['P/L'] != 0]) if 'P/L' in clean_df.columns else len(clean_df),
        })
    
    return base_metrics


def _log_portfolio_summary(clean_df: pd.DataFrame, metrics: Dict[str, Any], starting_capital: float) -> None:
    """Log portfolio summary information"""
    num_years = metrics.get('time_period_years', 0)
    max_drawdown = metrics.get('Max Drawdown', 0)
    recovery_days = metrics.get('Recovery Days')
    
    logger.info(f"Processed {len(clean_df):,} trades")
    logger.info(f"Date range: {clean_df['Date'].min()} to {clean_df['Date'].max()} ({num_years:.1f} years)")
    logger.info(f"Starting Capital: ${starting_capital:,.2f}")
    logger.info(f"Final Account Value: ${metrics['final_account_value']:,.2f}")
    logger.info(f"Total P/L: ${metrics['total_pl']:,.2f}")
    logger.info(f"Total Return: {metrics['total_return']:.2f}%")
    logger.info(f"CAGR: {metrics['cagr']:.2f}%")
    logger.info(f"Annual Volatility: {metrics['annual_volatility']:.2f}%")
    logger.info(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    logger.info(f"Maximum Drawdown: ${abs(max_drawdown):,.2f} ({metrics['max_drawdown_percent']:.2f}%)")
    logger.info(f"MAR Ratio: {metrics['mar_ratio']:.2f}")
    
    if recovery_days is not None and recovery_days > 0:
        logger.info(f"Recovery Time: {recovery_days} days")
    else:
        logger.info("Drawdown not yet recovered")
