"""
Service for calculating and managing rolling period statistics for portfolios.
Calculates best/worst 365-day rolling periods with overlapping windows.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models import RollingPeriodStats, Portfolio, PortfolioData
from portfolio_processor import process_portfolio_data

logger = logging.getLogger(__name__)


def _to_python_float(value) -> Optional[float]:
    """Convert numpy/pandas numeric types to Python float."""
    if value is None:
        return None
    if isinstance(value, (np.floating, np.integer)):
        return float(value)
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


class RollingPeriodService:
    """Service for rolling period calculations and storage"""

    @staticmethod
    def calculate_rolling_periods(
        db: Session,
        portfolio_id: int,
        period_length_days: int = 365,
        starting_capital: float = 100000.0,
        rf_rate: float = 0.0,  # Default to 0% for rolling period calculations
        sma_window: int = 20,
        use_trading_filter: bool = False  # Disable for rolling period calculations
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Calculate all overlapping rolling periods and find the best and worst.

        Args:
            db: Database session
            portfolio_id: Portfolio ID to analyze
            period_length_days: Length of rolling period (default 365 days)
            starting_capital: Starting capital for calculations
            rf_rate: Risk-free rate (default 0% for rolling calculations)
            sma_window: SMA window for trading filter
            use_trading_filter: Whether to use trading filter

        Returns:
            Tuple of (best_period_dict, worst_period_dict) or (None, None) if insufficient data
        """
        logger.info(f"[Rolling Period] Calculating {period_length_days}-day rolling periods for portfolio {portfolio_id}")

        # Get portfolio data from database
        portfolio_data = db.query(PortfolioData).filter(
            PortfolioData.portfolio_id == portfolio_id
        ).order_by(PortfolioData.date.asc()).all()

        if not portfolio_data:
            logger.warning(f"[Rolling Period] No data found for portfolio {portfolio_id}")
            return None, None

        # Convert to DataFrame
        df = pd.DataFrame([{
            'Date': pd.to_datetime(d.date),
            'P/L': d.pl
        } for d in portfolio_data])

        df = df.sort_values('Date').reset_index(drop=True)

        # Check if we have enough data
        date_range = (df['Date'].max() - df['Date'].min()).days
        if date_range < period_length_days:
            logger.warning(f"[Rolling Period] Insufficient data for {period_length_days}-day period. "
                          f"Portfolio only has {date_range} days of data.")
            return None, None

        # Find all unique dates
        unique_dates = df['Date'].unique()
        unique_dates = sorted(unique_dates)

        best_period = None
        worst_period = None
        best_profit = float('-inf')
        worst_profit = float('inf')

        periods_analyzed = 0

        # Iterate through each potential start date
        for start_date in unique_dates:
            end_date = start_date + pd.Timedelta(days=period_length_days)

            # Filter data for this period
            period_df = df[(df['Date'] >= start_date) & (df['Date'] < end_date)].copy()

            if len(period_df) < 10:  # Need at least 10 trading days for meaningful analysis
                continue

            # Quick profit calculation
            total_profit = period_df['P/L'].sum()

            # Track best and worst by total profit
            if total_profit > best_profit:
                best_profit = total_profit
                best_period = {
                    'start_date': pd.Timestamp(start_date).to_pydatetime(),
                    'end_date': end_date.to_pydatetime() if hasattr(end_date, 'to_pydatetime') else end_date,
                    'total_profit': total_profit,
                    'period_df': period_df.copy()
                }

            if total_profit < worst_profit:
                worst_profit = total_profit
                worst_period = {
                    'start_date': pd.Timestamp(start_date).to_pydatetime(),
                    'end_date': end_date.to_pydatetime() if hasattr(end_date, 'to_pydatetime') else end_date,
                    'total_profit': total_profit,
                    'period_df': period_df.copy()
                }

            periods_analyzed += 1

        logger.info(f"[Rolling Period] Analyzed {periods_analyzed} overlapping periods")

        if best_period is None or worst_period is None:
            logger.warning(f"[Rolling Period] Could not find valid periods for portfolio {portfolio_id}")
            return None, None

        # Now calculate detailed metrics for best and worst periods
        best_metrics = RollingPeriodService._calculate_period_metrics(
            best_period['period_df'],
            starting_capital,
            rf_rate,
            sma_window,
            use_trading_filter
        )
        best_period.update(best_metrics)
        del best_period['period_df']  # Remove DataFrame from result

        worst_metrics = RollingPeriodService._calculate_period_metrics(
            worst_period['period_df'],
            starting_capital,
            rf_rate,
            sma_window,
            use_trading_filter
        )
        worst_period.update(worst_metrics)
        del worst_period['period_df']  # Remove DataFrame from result

        logger.info(f"[Rolling Period] Best period: {best_period['start_date'].strftime('%Y-%m-%d')} to "
                   f"{best_period['end_date'].strftime('%Y-%m-%d')}, profit: ${best_period['total_profit']:,.2f}")
        logger.info(f"[Rolling Period] Worst period: {worst_period['start_date'].strftime('%Y-%m-%d')} to "
                   f"{worst_period['end_date'].strftime('%Y-%m-%d')}, profit: ${worst_period['total_profit']:,.2f}")

        return best_period, worst_period

    @staticmethod
    def _calculate_period_metrics(
        df: pd.DataFrame,
        starting_capital: float,
        rf_rate: float,
        sma_window: int,
        use_trading_filter: bool
    ) -> Dict[str, Any]:
        """
        Calculate detailed metrics for a specific period.

        Args:
            df: DataFrame with Date and P/L columns
            starting_capital: Starting capital
            rf_rate: Risk-free rate
            sma_window: SMA window
            use_trading_filter: Whether to use trading filter

        Returns:
            Dictionary with calculated metrics
        """
        try:
            # Use the standard portfolio processor to calculate metrics
            processed_df, metrics = process_portfolio_data(
                df.copy(),
                rf_rate=rf_rate,
                daily_rf_rate=rf_rate / 252,  # Convert annual to daily
                sma_window=sma_window,
                use_trading_filter=use_trading_filter,
                starting_capital=starting_capital,
                is_blended=False
            )

            return {
                'cagr': metrics.get('cagr', 0.0),
                'sharpe_ratio': metrics.get('sharpe_ratio', 0.0),
                'sortino_ratio': metrics.get('sortino_ratio', 0.0),
                'max_drawdown_percent': metrics.get('max_drawdown_percent', 0.0),
                'mar_ratio': metrics.get('mar_ratio', 0.0)
            }
        except Exception as e:
            logger.error(f"[Rolling Period] Error calculating period metrics: {e}")
            return {
                'cagr': 0.0,
                'sharpe_ratio': 0.0,
                'sortino_ratio': 0.0,
                'max_drawdown_percent': 0.0,
                'mar_ratio': 0.0
            }

    @staticmethod
    def store_rolling_period_stats(
        db: Session,
        portfolio_id: int,
        best_period: Dict[str, Any],
        worst_period: Dict[str, Any],
        period_length_days: int = 365
    ) -> bool:
        """
        Store or update rolling period statistics in the database.

        Args:
            db: Database session
            portfolio_id: Portfolio ID
            best_period: Best period metrics dictionary
            worst_period: Worst period metrics dictionary
            period_length_days: Period length in days

        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert numpy types to Python native types
            best_total_profit = _to_python_float(best_period['total_profit'])
            best_cagr = _to_python_float(best_period.get('cagr'))
            best_sharpe = _to_python_float(best_period.get('sharpe_ratio'))
            best_sortino = _to_python_float(best_period.get('sortino_ratio'))
            best_max_dd = _to_python_float(best_period.get('max_drawdown_percent'))
            best_mar = _to_python_float(best_period.get('mar_ratio'))

            worst_total_profit = _to_python_float(worst_period['total_profit'])
            worst_cagr = _to_python_float(worst_period.get('cagr'))
            worst_sharpe = _to_python_float(worst_period.get('sharpe_ratio'))
            worst_sortino = _to_python_float(worst_period.get('sortino_ratio'))
            worst_max_dd = _to_python_float(worst_period.get('max_drawdown_percent'))
            worst_mar = _to_python_float(worst_period.get('mar_ratio'))

            # Store best period
            existing_best = db.query(RollingPeriodStats).filter(
                and_(
                    RollingPeriodStats.portfolio_id == portfolio_id,
                    RollingPeriodStats.period_type == 'best',
                    RollingPeriodStats.period_length_days == period_length_days
                )
            ).first()

            if existing_best:
                # Update existing record
                existing_best.start_date = best_period['start_date']
                existing_best.end_date = best_period['end_date']
                existing_best.total_profit = best_total_profit
                existing_best.cagr = best_cagr
                existing_best.sharpe_ratio = best_sharpe
                existing_best.sortino_ratio = best_sortino
                existing_best.max_drawdown_percent = best_max_dd
                existing_best.mar_ratio = best_mar
                existing_best.updated_at = datetime.utcnow()
            else:
                # Create new record
                new_best = RollingPeriodStats(
                    portfolio_id=portfolio_id,
                    period_type='best',
                    period_length_days=period_length_days,
                    start_date=best_period['start_date'],
                    end_date=best_period['end_date'],
                    total_profit=best_total_profit,
                    cagr=best_cagr,
                    sharpe_ratio=best_sharpe,
                    sortino_ratio=best_sortino,
                    max_drawdown_percent=best_max_dd,
                    mar_ratio=best_mar
                )
                db.add(new_best)

            # Store worst period
            existing_worst = db.query(RollingPeriodStats).filter(
                and_(
                    RollingPeriodStats.portfolio_id == portfolio_id,
                    RollingPeriodStats.period_type == 'worst',
                    RollingPeriodStats.period_length_days == period_length_days
                )
            ).first()

            if existing_worst:
                # Update existing record
                existing_worst.start_date = worst_period['start_date']
                existing_worst.end_date = worst_period['end_date']
                existing_worst.total_profit = worst_total_profit
                existing_worst.cagr = worst_cagr
                existing_worst.sharpe_ratio = worst_sharpe
                existing_worst.sortino_ratio = worst_sortino
                existing_worst.max_drawdown_percent = worst_max_dd
                existing_worst.mar_ratio = worst_mar
                existing_worst.updated_at = datetime.utcnow()
            else:
                # Create new record
                new_worst = RollingPeriodStats(
                    portfolio_id=portfolio_id,
                    period_type='worst',
                    period_length_days=period_length_days,
                    start_date=worst_period['start_date'],
                    end_date=worst_period['end_date'],
                    total_profit=worst_total_profit,
                    cagr=worst_cagr,
                    sharpe_ratio=worst_sharpe,
                    sortino_ratio=worst_sortino,
                    max_drawdown_percent=worst_max_dd,
                    mar_ratio=worst_mar
                )
                db.add(new_worst)

            db.commit()
            logger.info(f"[Rolling Period] Stored rolling period stats for portfolio {portfolio_id}")
            return True

        except Exception as e:
            logger.error(f"[Rolling Period] Error storing rolling period stats: {e}")
            db.rollback()
            return False

    @staticmethod
    def get_rolling_period_stats(
        db: Session,
        portfolio_id: int,
        period_length_days: int = 365
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Retrieve stored rolling period statistics for a portfolio.

        Args:
            db: Database session
            portfolio_id: Portfolio ID
            period_length_days: Period length in days

        Returns:
            Dictionary with 'best' and 'worst' period data, or None for each if not found
        """
        result = {'best': None, 'worst': None}

        for period_type in ['best', 'worst']:
            stats = db.query(RollingPeriodStats).filter(
                and_(
                    RollingPeriodStats.portfolio_id == portfolio_id,
                    RollingPeriodStats.period_type == period_type,
                    RollingPeriodStats.period_length_days == period_length_days
                )
            ).first()

            if stats:
                result[period_type] = {
                    'start_date': stats.start_date.strftime('%Y-%m-%d') if stats.start_date else None,
                    'end_date': stats.end_date.strftime('%Y-%m-%d') if stats.end_date else None,
                    'total_profit': stats.total_profit,
                    'cagr': stats.cagr,
                    'sharpe_ratio': stats.sharpe_ratio,
                    'sortino_ratio': stats.sortino_ratio,
                    'max_drawdown_percent': stats.max_drawdown_percent,
                    'mar_ratio': stats.mar_ratio
                }

        return result

    @staticmethod
    def calculate_blended_rolling_stats(
        db: Session,
        portfolio_ids: List[int],
        weights: List[float],
        period_length_days: int = 365
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Calculate blended rolling period statistics by combining individual portfolio stats.

        The blending approach weight-combines each portfolio's best/worst metrics.
        Note: The dates may differ between portfolios since each has its own best/worst periods.

        Args:
            db: Database session
            portfolio_ids: List of portfolio IDs
            weights: List of weights corresponding to portfolio IDs
            period_length_days: Period length in days

        Returns:
            Dictionary with 'best_period' and 'worst_period' blended stats
        """
        if len(portfolio_ids) != len(weights):
            logger.error("[Rolling Period] Portfolio IDs and weights length mismatch")
            return {'best_period': None, 'worst_period': None}

        # Normalize weights
        total_weight = sum(weights)
        if total_weight == 0:
            logger.error("[Rolling Period] Total weight is zero")
            return {'best_period': None, 'worst_period': None}

        normalized_weights = [w / total_weight for w in weights]

        # Collect individual stats
        individual_stats = []
        for portfolio_id, weight in zip(portfolio_ids, weights):
            stats = RollingPeriodService.get_rolling_period_stats(db, portfolio_id, period_length_days)
            if stats['best'] is None or stats['worst'] is None:
                logger.warning(f"[Rolling Period] Missing stats for portfolio {portfolio_id}")
                continue
            individual_stats.append({
                'portfolio_id': portfolio_id,
                'weight': weight,
                'normalized_weight': weight / total_weight,
                'best': stats['best'],
                'worst': stats['worst']
            })

        if not individual_stats:
            logger.warning("[Rolling Period] No valid individual stats found for blending")
            return {'best_period': None, 'worst_period': None}

        # Calculate blended metrics for best period
        best_blended = RollingPeriodService._blend_period_metrics(
            individual_stats, 'best', weights
        )

        # Calculate blended metrics for worst period
        worst_blended = RollingPeriodService._blend_period_metrics(
            individual_stats, 'worst', weights
        )

        return {
            'best_period': best_blended,
            'worst_period': worst_blended
        }

    @staticmethod
    def _blend_period_metrics(
        individual_stats: List[Dict[str, Any]],
        period_type: str,
        weights: List[float]
    ) -> Dict[str, Any]:
        """
        Blend metrics from individual portfolios for a specific period type.

        Args:
            individual_stats: List of individual portfolio stats
            period_type: 'best' or 'worst'
            weights: Original weights (not normalized)

        Returns:
            Blended metrics dictionary
        """
        # Weight-combine metrics
        total_profit = 0.0
        weighted_cagr = 0.0
        weighted_sharpe = 0.0
        weighted_sortino = 0.0
        weighted_max_dd = 0.0
        weighted_mar = 0.0
        total_weight = sum(s['weight'] for s in individual_stats)

        portfolio_periods = []

        for stats in individual_stats:
            period = stats[period_type]
            weight = stats['weight']
            norm_weight = stats['normalized_weight']

            # Total profit is additive with weights
            total_profit += (period.get('total_profit') or 0) * weight

            # Other metrics are weight-averaged
            weighted_cagr += (period.get('cagr') or 0) * norm_weight
            weighted_sharpe += (period.get('sharpe_ratio') or 0) * norm_weight
            weighted_sortino += (period.get('sortino_ratio') or 0) * norm_weight
            weighted_max_dd += (period.get('max_drawdown_percent') or 0) * norm_weight
            weighted_mar += (period.get('mar_ratio') or 0) * norm_weight

            portfolio_periods.append({
                'portfolio_id': stats['portfolio_id'],
                'weight': weight,
                'start_date': period.get('start_date'),
                'end_date': period.get('end_date'),
                'total_profit': period.get('total_profit')
            })

        return {
            'total_profit': total_profit,
            'cagr': weighted_cagr,
            'sharpe_ratio': weighted_sharpe,
            'sortino_ratio': weighted_sortino,
            'max_drawdown_percent': weighted_max_dd,
            'mar_ratio': weighted_mar,
            'portfolio_periods': portfolio_periods
        }

    @staticmethod
    def calculate_and_store_rolling_stats(
        db: Session,
        portfolio_id: int,
        period_length_days: int = 365,
        starting_capital: float = 100000.0
    ) -> bool:
        """
        Convenience method to calculate and store rolling period stats in one call.

        Args:
            db: Database session
            portfolio_id: Portfolio ID
            period_length_days: Period length in days
            starting_capital: Starting capital for calculations

        Returns:
            True if successful, False otherwise
        """
        best_period, worst_period = RollingPeriodService.calculate_rolling_periods(
            db, portfolio_id, period_length_days, starting_capital
        )

        if best_period is None or worst_period is None:
            return False

        return RollingPeriodService.store_rolling_period_stats(
            db, portfolio_id, best_period, worst_period, period_length_days
        )
