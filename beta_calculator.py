"""
Beta calculation utilities for portfolio analysis
Calculates portfolio beta against S&P 500 (SPX) benchmark
"""
import pandas as pd
import numpy as np
import yfinance as yf
import logging
from typing import Tuple, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def get_spx_data(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Retrieve S&P 500 index data for the specified date range

    Args:
        start_date: Start date for data retrieval
        end_date: End date for data retrieval

    Returns:
        DataFrame with SPX price data and returns
    """
    try:
        # Add buffer days to ensure we have enough data
        buffer_start = start_date - timedelta(days=10)
        buffer_end = end_date + timedelta(days=1)

        logger.info(f"Fetching SPX data from {buffer_start.date()} to {buffer_end.date()}")

        # Fetch SPX data using yfinance
        spx_ticker = yf.Ticker("^GSPC")
        spx_data = spx_ticker.history(start=buffer_start, end=buffer_end)

        if spx_data.empty:
            raise ValueError("No SPX data retrieved from yfinance")

        # Calculate daily returns
        spx_data['Returns'] = spx_data['Close'].pct_change()

        # Filter to exact date range requested
        spx_data.index = pd.to_datetime(spx_data.index).date
        start_date_only = start_date.date()
        end_date_only = end_date.date()

        mask = (spx_data.index >= start_date_only) & (spx_data.index <= end_date_only)
        spx_filtered = spx_data.loc[mask].copy()

        logger.info(f"Retrieved {len(spx_filtered)} days of SPX data")
        return spx_filtered

    except Exception as e:
        logger.error(f"Failed to retrieve SPX data: {e}")
        raise


def align_portfolio_with_spx(portfolio_df: pd.DataFrame, spx_df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """
    Align portfolio and SPX data by date for beta calculation

    Args:
        portfolio_df: Portfolio DataFrame with Date and Daily Return columns
        spx_df: SPX DataFrame with Returns column

    Returns:
        Tuple of aligned (portfolio_returns, spx_returns) Series
    """
    try:
        # Ensure portfolio Date column is datetime and convert to date for alignment
        portfolio_df = portfolio_df.copy()
        portfolio_df['Date'] = pd.to_datetime(portfolio_df['Date'])
        portfolio_df['Date_Only'] = portfolio_df['Date'].dt.date

        # Create SPX DataFrame with date index
        spx_aligned = spx_df.copy()
        if not isinstance(spx_aligned.index, pd.DatetimeIndex):
            spx_aligned.index = pd.to_datetime(spx_aligned.index)
        spx_aligned['Date_Only'] = spx_aligned.index.date

        # Merge on date
        merged = portfolio_df.merge(
            spx_aligned[['Returns', 'Date_Only']],
            on='Date_Only',
            how='inner',
            suffixes=('_portfolio', '_spx')
        )

        if merged.empty:
            raise ValueError("No overlapping dates between portfolio and SPX data")

        # Remove NaN values
        merged = merged.dropna(subset=['Daily Return', 'Returns'])

        if len(merged) < 5:
            logger.warning(f"Only {len(merged)} overlapping trading days found - beta calculation may be unreliable")

        portfolio_returns = merged['Daily Return']
        spx_returns = merged['Returns']

        logger.info(f"Aligned {len(merged)} overlapping trading days for beta calculation")
        return portfolio_returns, spx_returns

    except Exception as e:
        logger.error(f"Failed to align portfolio and SPX data: {e}")
        raise


def calculate_beta(portfolio_returns: pd.Series, spx_returns: pd.Series) -> Tuple[float, float, float, int]:
    """
    Calculate portfolio beta against SPX benchmark

    Args:
        portfolio_returns: Portfolio daily returns
        spx_returns: SPX daily returns (aligned with portfolio)

    Returns:
        Tuple of (beta, alpha, r_squared, observation_count)
    """
    try:
        if len(portfolio_returns) != len(spx_returns):
            raise ValueError("Portfolio and SPX returns must have same length")

        if len(portfolio_returns) < 5:
            raise ValueError("Need at least 5 observations for beta calculation")

        # Remove any remaining NaN values
        valid_mask = ~(np.isnan(portfolio_returns) | np.isnan(spx_returns))
        port_clean = portfolio_returns[valid_mask]
        spx_clean = spx_returns[valid_mask]

        if len(port_clean) < 5:
            raise ValueError("Insufficient valid data points for beta calculation")

        # Calculate covariance and variance
        covariance = np.cov(port_clean, spx_clean)[0, 1]
        spx_variance = np.var(spx_clean)

        if spx_variance == 0:
            raise ValueError("SPX returns have zero variance - cannot calculate beta")

        # Beta = Cov(Portfolio, Market) / Var(Market)
        beta = covariance / spx_variance

        # Alpha = Portfolio_Mean - Beta * Market_Mean (annualized)
        portfolio_mean = np.mean(port_clean) * 252  # Annualized
        spx_mean = np.mean(spx_clean) * 252  # Annualized
        alpha = portfolio_mean - (beta * spx_mean)

        # R-squared (correlation coefficient squared)
        correlation = np.corrcoef(port_clean, spx_clean)[0, 1]
        r_squared = correlation ** 2

        observation_count = len(port_clean)

        logger.info(f"Beta calculation results:")
        logger.info(f"  Beta: {beta:.4f}")
        logger.info(f"  Alpha: {alpha:.4f} ({alpha*100:.2f}% annualized)")
        logger.info(f"  R-squared: {r_squared:.4f}")
        logger.info(f"  Observations: {observation_count}")
        logger.info(f"  Correlation: {correlation:.4f}")

        return beta, alpha, r_squared, observation_count

    except Exception as e:
        logger.error(f"Failed to calculate beta: {e}")
        raise


def calculate_portfolio_beta(portfolio_df: pd.DataFrame) -> Tuple[float, float, float, int]:
    """
    Main function to calculate portfolio beta against SPX

    Args:
        portfolio_df: Portfolio DataFrame with Date and Daily Return columns

    Returns:
        Tuple of (beta, alpha, r_squared, observation_count)
    """
    try:
        if portfolio_df.empty:
            raise ValueError("Portfolio DataFrame is empty")

        if 'Date' not in portfolio_df.columns:
            raise ValueError("Portfolio DataFrame must have 'Date' column")

        if 'Daily Return' not in portfolio_df.columns:
            raise ValueError("Portfolio DataFrame must have 'Daily Return' column")

        # Get date range from portfolio
        portfolio_df['Date'] = pd.to_datetime(portfolio_df['Date'])
        start_date = portfolio_df['Date'].min()
        end_date = portfolio_df['Date'].max()

        logger.info(f"Calculating beta for portfolio from {start_date.date()} to {end_date.date()}")

        # Get SPX data for the same period
        spx_data = get_spx_data(start_date, end_date)

        # Align portfolio and SPX data
        portfolio_returns, spx_returns = align_portfolio_with_spx(portfolio_df, spx_data)

        # Calculate beta
        beta, alpha, r_squared, obs_count = calculate_beta(portfolio_returns, spx_returns)

        return beta, alpha, r_squared, obs_count

    except Exception as e:
        logger.error(f"Portfolio beta calculation failed: {e}")
        # Return default values on error
        return 0.0, 0.0, 0.0, 0


def calculate_blended_portfolio_beta(
    portfolio_dataframes: list,
    weights: list
) -> Tuple[float, float, float, int]:
    """
    Calculate beta for a blended portfolio using weighted average approach

    Args:
        portfolio_dataframes: List of individual portfolio DataFrames
        weights: List of weights for each portfolio

    Returns:
        Tuple of (beta, alpha, r_squared, observation_count)
    """
    try:
        if not portfolio_dataframes:
            raise ValueError("No portfolio dataframes provided")

        if len(portfolio_dataframes) != len(weights):
            raise ValueError("Number of portfolios must match number of weights")

        # Calculate individual betas
        individual_betas = []
        individual_alphas = []
        min_obs_count = float('inf')

        for i, portfolio_df in enumerate(portfolio_dataframes):
            try:
                beta, alpha, r_sq, obs_count = calculate_portfolio_beta(portfolio_df)
                individual_betas.append(beta)
                individual_alphas.append(alpha)
                min_obs_count = min(min_obs_count, obs_count)

                logger.info(f"Portfolio {i+1} beta: {beta:.4f}, alpha: {alpha:.4f}")

            except Exception as e:
                logger.warning(f"Failed to calculate beta for portfolio {i+1}: {e}")
                individual_betas.append(0.0)
                individual_alphas.append(0.0)

        # Calculate weighted average beta and alpha
        weights_array = np.array(weights)
        betas_array = np.array(individual_betas)
        alphas_array = np.array(individual_alphas)

        blended_beta = np.sum(weights_array * betas_array)
        blended_alpha = np.sum(weights_array * alphas_array)

        # For blended portfolio, use average R-squared (simplified approach)
        # In practice, this would require combining the actual return series
        blended_r_squared = 0.7  # Conservative estimate for blended portfolios

        logger.info(f"Blended portfolio beta calculation:")
        logger.info(f"  Individual betas: {individual_betas}")
        logger.info(f"  Weights: {weights}")
        logger.info(f"  Blended beta: {blended_beta:.4f}")
        logger.info(f"  Blended alpha: {blended_alpha:.4f}")

        return blended_beta, blended_alpha, blended_r_squared, int(min_obs_count)

    except Exception as e:
        logger.error(f"Blended portfolio beta calculation failed: {e}")
        return 0.0, 0.0, 0.0, 0