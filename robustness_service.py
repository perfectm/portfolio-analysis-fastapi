"""
Robustness testing service for portfolio analysis
"""
import random
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from models import Portfolio, RobustnessTest, RobustnessPeriod, RobustnessStatistic, PortfolioData
from portfolio_service import PortfolioService
from portfolio_processor import process_portfolio_data

logger = logging.getLogger(__name__)


class RobustnessTestService:
    """Service class for portfolio robustness testing"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_available_portfolios(self, min_period_days: int = 30) -> List[Dict[str, Any]]:
        """Get all portfolios available for robustness testing with metadata"""
        portfolios = self.db.query(Portfolio).all()
        result = []
        
        for portfolio in portfolios:
            # Check if portfolio has sufficient data for testing
            min_date = portfolio.date_range_start
            max_date = portfolio.date_range_end
            
            if not min_date or not max_date:
                continue
                
            # Check both calendar days and actual trading days
            max_start_date = max_date - timedelta(days=min_period_days)  # Use minimum period for eligibility

            if min_date > max_start_date:
                logger.warning(f"Portfolio {portfolio.id} has insufficient calendar days for robustness testing")
                continue

            # Get unique trading days for informational purposes but don't filter on it
            unique_trading_days = self.db.query(PortfolioData.date).filter(
                PortfolioData.portfolio_id == portfolio.id
            ).distinct().count()
            
            # Get full dataset metrics if available
            full_metrics = self._get_full_dataset_metrics(portfolio.id)
            
            result.append({
                'id': portfolio.id,
                'name': portfolio.name,
                'filename': portfolio.filename,
                'date_range_start': min_date.isoformat() if min_date else None,
                'date_range_end': max_date.isoformat() if max_date else None,
                'row_count': portfolio.row_count,
                'unique_trading_days': unique_trading_days,
                'available_for_testing': True,
                'max_testable_start_date': max_start_date.isoformat() if max_start_date else None,
                'full_dataset_metrics': full_metrics
            })

        # Sort portfolios alphabetically by name
        result.sort(key=lambda p: p['name'].lower())

        return result
    
    def _get_full_dataset_metrics(self, portfolio_id: int) -> Optional[Dict[str, Any]]:
        """Get full dataset metrics for a portfolio"""
        try:
            # Load full portfolio data
            portfolio_data = PortfolioService.get_portfolio_dataframe(self.db, portfolio_id)
            if portfolio_data is None or portfolio_data.empty:
                return None
            
            # Process the full dataset
            processed_df, metrics = process_portfolio_data(portfolio_data)
            
            # Extract key metrics
            return {
                'cagr': metrics.get('cagr'),
                'sharpe_ratio': metrics.get('sharpe_ratio'),
                'sortino_ratio': metrics.get('sortino_ratio'),
                'max_drawdown': metrics.get('max_drawdown'),
                'max_drawdown_percent': metrics.get('max_drawdown_percent'),
                'volatility': metrics.get('annual_volatility'),
                'total_return': metrics.get('total_return'),
                'total_pl': metrics.get('total_pl'),
                'ulcer_index': metrics.get('ulcer_index'),
                'upi': metrics.get('upi'),
                'kelly_criterion': metrics.get('kelly_criterion'),
                'mar_ratio': metrics.get('mar_ratio'),
                'pcr': metrics.get('pcr'),
                'win_rate': metrics.get('win_rate'),
                'profit_factor': metrics.get('profit_factor'),
                'avg_trade_return': metrics.get('avg_trade_return'),
                'trade_count': len(portfolio_data) if portfolio_data is not None else 0
            }
        except Exception as e:
            logger.error(f"Error getting full dataset metrics for portfolio {portfolio_id}: {e}")
            return None
    
    def create_robustness_test(
        self,
        portfolio_id: int,
        num_periods: int = 10,
        period_length_days: int = 252,
        rf_rate: float = 0.043,
        sma_window: int = 20,
        use_trading_filter: bool = True,
        starting_capital: float = 1000000
    ) -> RobustnessTest:
        """Create a new robustness test"""
        
        # Validate portfolio exists and has sufficient data
        portfolio = self.db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        
        # Check data availability
        if not portfolio.date_range_start or not portfolio.date_range_end:
            raise ValueError(f"Portfolio {portfolio_id} has no date range information")

        # Check calendar days span
        total_days = (portfolio.date_range_end - portfolio.date_range_start).days
        min_required_days = period_length_days  # Just need enough for one test period

        if total_days < min_required_days:
            raise ValueError(f"Portfolio {portfolio_id} has insufficient data. Has {total_days} calendar days, needs {min_required_days}")

        # Note: We only check calendar date range here. The period generation logic
        # will handle cases where there are gaps in trading data by selecting
        # periods based on available trading days within the overall date range.
        
        # Create the robustness test record
        robustness_test = RobustnessTest(
            portfolio_id=portfolio_id,
            num_periods=num_periods,
            min_period_length_days=period_length_days,
            rf_rate=rf_rate,
            daily_rf_rate=rf_rate / 252,
            sma_window=sma_window,
            use_trading_filter=use_trading_filter,
            starting_capital=starting_capital,
            status="pending"
        )
        
        self.db.add(robustness_test)
        self.db.commit()
        self.db.refresh(robustness_test)
        
        return robustness_test
    
    def run_robustness_test(self, test_id: int) -> RobustnessTest:
        """Execute a robustness test"""
        
        # Get the test record
        test = self.db.query(RobustnessTest).filter(RobustnessTest.id == test_id).first()
        if not test:
            raise ValueError(f"Robustness test {test_id} not found")
        
        try:
            # Update status to running
            test.status = "running"
            test.progress = 0
            self.db.commit()
            
            # Generate random periods
            periods = self._generate_random_periods(
                test.portfolio_id,
                test.num_periods,
                test.min_period_length_days
            )
            
            if not periods:
                raise ValueError("Could not generate valid test periods")
            
            # Get full dataset metrics for comparison
            full_metrics = self._get_full_dataset_metrics(test.portfolio_id)
            if not full_metrics:
                raise ValueError("Could not calculate full dataset metrics")
            
            # Run analysis for each period
            period_results = []
            for i, (start_date, end_date) in enumerate(periods):
                logger.info(f"Processing period {i+1}/{len(periods)}: {start_date} to {end_date}")
                
                try:
                    # Analyze this period
                    period_metrics = self._analyze_period(
                        test.portfolio_id,
                        start_date,
                        end_date,
                        test.rf_rate,
                        test.daily_rf_rate,
                        test.sma_window,
                        test.use_trading_filter,
                        test.starting_capital
                    )
                    
                    # Create period record
                    period_record = RobustnessPeriod(
                        robustness_test_id=test.id,
                        period_number=i + 1,
                        start_date=start_date,
                        end_date=end_date,
                        **period_metrics
                    )
                    
                    self.db.add(period_record)
                    period_results.append(period_metrics)
                    
                    # Update progress
                    test.progress = int(((i + 1) / len(periods)) * 80)  # 80% for period analysis
                    self.db.commit()
                    
                except Exception as e:
                    logger.error(f"Error processing period {i+1}: {e}")
                    continue
            
            if not period_results:
                raise ValueError("No periods were successfully analyzed")
            
            # Calculate descriptive statistics
            test.progress = 85
            self.db.commit()
            
            statistics = self._calculate_statistics(period_results, full_metrics)
            
            # Save statistics to database
            for metric_name, stats in statistics.items():
                stat_record = RobustnessStatistic(
                    robustness_test_id=test.id,
                    metric_name=metric_name,
                    **stats
                )
                self.db.add(stat_record)
            
            # Calculate overall robustness score
            test.progress = 95
            self.db.commit()
            
            robustness_score = self._calculate_robustness_score(statistics)
            
            # Update test record with completion
            test.overall_robustness_score = robustness_score
            test.status = "completed"
            test.progress = 100
            test.completed_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(test)
            
            logger.info(f"Robustness test {test_id} completed with score {robustness_score:.2f}")
            
            return test
            
        except Exception as e:
            logger.error(f"Error running robustness test {test_id}: {e}")
            test.status = "failed"
            test.error_message = str(e)
            self.db.commit()
            raise
    
    def _generate_random_periods(
        self, 
        portfolio_id: int, 
        num_periods: int, 
        period_length_days: int
    ) -> List[Tuple[datetime, datetime]]:
        """Generate random test periods for the portfolio"""
        
        # Get portfolio date range
        portfolio = self.db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if not portfolio:
            return []
        
        start_date = portfolio.date_range_start
        end_date = portfolio.date_range_end
        
        # Calculate valid range for period start dates
        # Only constraint is that the period must fit within the dataset
        max_start_date = end_date - timedelta(days=period_length_days)
        
        if start_date > max_start_date:
            logger.warning(f"Insufficient data range for portfolio {portfolio_id}")
            return []
        
        # Get all available trading dates for this portfolio
        all_dates_query = self.db.query(PortfolioData.date).filter(
            PortfolioData.portfolio_id == portfolio_id
        ).order_by(PortfolioData.date).distinct()
        all_dates = [row.date for row in all_dates_query.all()]
        
        if len(all_dates) < 10:  # Need at least 10 trading days for any meaningful analysis
            logger.warning(f"Portfolio {portfolio_id} has too few trading days: {len(all_dates)} < 10")
            return []
        
        # Generate periods based on calendar date ranges
        periods = []

        # Create periods by calendar date ranges, not by trading day count
        min_date = all_dates[0]
        max_date = all_dates[-1]

        # Calculate the latest possible start date for a period of the given length
        latest_start_date = max_date - timedelta(days=period_length_days)

        # Check if we have enough calendar date range for the requested period length
        if min_date > latest_start_date:
            logger.warning(f"Portfolio {portfolio_id} date range too short: {min_date} to {max_date}, need {period_length_days} day periods")
            return []

        # Generate random periods based on calendar dates
        attempts = 0
        max_attempts = num_periods * 50  # More attempts for calendar-based generation

        while len(periods) < num_periods and attempts < max_attempts:
            attempts += 1

            # Generate random start date within valid range
            total_range_days = (latest_start_date - min_date).days
            if total_range_days <= 0:
                random_start_date = min_date
            else:
                random_offset = random.randint(0, total_range_days)
                random_start_date = min_date + timedelta(days=random_offset)

            # Calculate end date based on period length
            period_end_date = random_start_date + timedelta(days=period_length_days)

            # Check if this period has some overlap with existing periods (to avoid too much overlap)
            has_significant_overlap = False
            for existing_start, existing_end in periods:
                # Calculate overlap days
                overlap_start = max(random_start_date, existing_start)
                overlap_end = min(period_end_date, existing_end)
                if overlap_start < overlap_end:
                    overlap_days = (overlap_end - overlap_start).days
                    if overlap_days > period_length_days * 0.5:  # More than 50% overlap
                        has_significant_overlap = True
                        break

            # Add period if no significant overlap, or if we've tried many times
            if not has_significant_overlap or attempts > max_attempts // 2:
                periods.append((random_start_date, period_end_date))
        
        # Sort periods chronologically by start date
        periods.sort(key=lambda period: period[0])
        
        logger.info(f"Generated {len(periods)} random periods for portfolio {portfolio_id}")
        return periods
    
    def _analyze_period(
        self,
        portfolio_id: int,
        start_date: datetime,
        end_date: datetime,
        rf_rate: float,
        daily_rf_rate: float,
        sma_window: int,
        use_trading_filter: bool,
        starting_capital: float
    ) -> Dict[str, Any]:
        """Analyze a specific time period for the portfolio"""
        
        # Get portfolio data for the period
        portfolio_data_query = self.db.query(PortfolioData).filter(
            PortfolioData.portfolio_id == portfolio_id,
            PortfolioData.date >= start_date,
            PortfolioData.date <= end_date
        ).order_by(PortfolioData.date)
        
        data_records = portfolio_data_query.all()
        
        if not data_records:
            raise ValueError(f"No data found for period {start_date} to {end_date}")
        
        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'Date': record.date,
                'P/L': record.pl,
                'Premium': record.premium,  # Include premium for PCR calculation
                'Contracts': record.contracts,  # Include contracts for PCR calculation
                'Date Opened': record.date  # Use same date for consistency
            }
            for record in data_records
        ])
        
        if df.empty:
            raise ValueError("Empty DataFrame for period")
        
        # Process the period data
        processed_df, metrics = process_portfolio_data(
            df,
            rf_rate=rf_rate,
            daily_rf_rate=daily_rf_rate,
            sma_window=sma_window,
            use_trading_filter=use_trading_filter,
            starting_capital=starting_capital
        )
        
        # Calculate additional metrics
        trade_count = len(df)
        winning_trades = len(df[df['P/L'] > 0]) if 'P/L' in df.columns else 0
        losing_trades = len(df[df['P/L'] < 0]) if 'P/L' in df.columns else 0
        
        # Extract and clean metrics
        result = {
            'cagr': float(metrics.get('cagr', 0)),
            'sharpe_ratio': float(metrics.get('sharpe_ratio', 0)),
            'sortino_ratio': float(metrics.get('sortino_ratio', 0)),
            'max_drawdown': float(metrics.get('max_drawdown', 0)),
            'max_drawdown_percent': float(metrics.get('max_drawdown_percent', 0)),
            'volatility': float(metrics.get('annual_volatility', 0)),
            'win_rate': float(metrics.get('win_rate', 0)),
            'profit_factor': float(metrics.get('profit_factor', 0)),
            'avg_trade_return': float(metrics.get('avg_trade_return', 0)),
            'total_return': float(metrics.get('total_return', 0)),
            'total_pl': float(metrics.get('total_pl', 0)),
            'final_account_value': float(metrics.get('final_account_value', starting_capital)),
            'ulcer_index': float(metrics.get('ulcer_index', 0)),
            'upi': float(metrics.get('upi', 0)),
            'kelly_criterion': float(metrics.get('kelly_criterion', 0)),
            'mar_ratio': float(metrics.get('mar_ratio', 0)),
            'pcr': float(metrics.get('pcr', 0)),
            'cvar': float(metrics.get('cvar', 0)),
            'trade_count': trade_count,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades
        }
        
        # Handle NaN/infinite values
        for key, value in result.items():
            if pd.isna(value) or np.isinf(value):
                result[key] = 0.0
        
        return result
    
    def _calculate_statistics(
        self, 
        period_results: List[Dict[str, Any]], 
        full_metrics: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate descriptive statistics for all metrics across periods"""
        
        statistics = {}
        
        # Define metrics to analyze
        metrics_to_analyze = [
            'cagr', 'sharpe_ratio', 'sortino_ratio', 'max_drawdown', 
            'max_drawdown_percent', 'volatility', 'win_rate', 'profit_factor',
            'avg_trade_return', 'total_return', 'total_pl', 'ulcer_index', 'upi',
            'kelly_criterion', 'mar_ratio', 'pcr'
        ]
        
        for metric in metrics_to_analyze:
            values = [result.get(metric, 0) for result in period_results]
            values = [v for v in values if not pd.isna(v) and not np.isinf(v)]
            
            if not values:
                continue
            
            values = np.array(values)
            full_value = full_metrics.get(metric, 0)
            
            # Calculate descriptive statistics
            # For max drawdown metrics, invert min/max since drawdowns are negative
            # (min = best performance closest to 0, max = worst performance farthest from 0)
            if metric in ['max_drawdown', 'max_drawdown_percent']:
                stats = {
                    'max_value': float(np.min(values)),  # Most negative = worst performance
                    'min_value': float(np.max(values)),  # Closest to 0 = best performance
                    'mean_value': float(np.mean(values)),
                    'median_value': float(np.median(values)),
                    'std_deviation': float(np.std(values)),
                    'q1_value': float(np.percentile(values, 75)),  # Inverted percentiles for drawdown
                    'q3_value': float(np.percentile(values, 25)),
                    'full_dataset_value': float(full_value) if full_value else 0.0
                }
            else:
                stats = {
                    'max_value': float(np.max(values)),
                    'min_value': float(np.min(values)),
                    'mean_value': float(np.mean(values)),
                    'median_value': float(np.median(values)),
                    'std_deviation': float(np.std(values)),
                    'q1_value': float(np.percentile(values, 25)),
                    'q3_value': float(np.percentile(values, 75)),
                    'full_dataset_value': float(full_value) if full_value else 0.0
                }
            
            # Calculate relative deviation
            if full_value is not None and abs(full_value) > 1e-10:  # Avoid division by zero
                stats['relative_deviation'] = (stats['mean_value'] - full_value) / abs(full_value)
            else:
                stats['relative_deviation'] = 0.0
            
            # Calculate component robustness score
            stats['robustness_component_score'] = self._calculate_component_score(
                stats['mean_value'], 
                full_value, 
                stats['std_deviation']
            )
            
            statistics[metric] = stats
        
        return statistics
    
    def delete_robustness_test(self, test_id: int) -> bool:
        """Delete a robustness test and all related data"""
        try:
            # Get the test to ensure it exists
            test = self.db.query(RobustnessTest).filter(RobustnessTest.id == test_id).first()
            if not test:
                return False
            
            # Delete related periods first (cascade should handle this, but being explicit)
            self.db.query(RobustnessPeriod).filter(RobustnessPeriod.robustness_test_id == test_id).delete()
            
            # Delete related statistics
            self.db.query(RobustnessStatistic).filter(RobustnessStatistic.robustness_test_id == test_id).delete()
            
            # Delete the test itself
            self.db.delete(test)
            self.db.commit()
            
            logger.info(f"Deleted robustness test {test_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting robustness test {test_id}: {e}")
            self.db.rollback()
            return False
    
    def _calculate_component_score(self, mean_value: float, full_value: float, std_dev: float) -> float:
        """Calculate robustness score for a single metric component"""
        
        # Handle None values and convert to float to ensure proper calculation
        try:
            mean_value = float(mean_value) if mean_value is not None else 0.0
            full_value = float(full_value) if full_value is not None else 0.0
            std_dev = float(std_dev) if std_dev is not None else 0.0
        except (ValueError, TypeError):
            return 0.0
        
        # Handle zero/near-zero full values
        if abs(full_value) < 1e-8:  # More reasonable threshold
            return 100.0 if abs(mean_value) < 1e-8 else 0.0
        
        # Calculate relative deviation
        relative_deviation = abs(mean_value - full_value) / abs(full_value)
        
        # Calculate consistency score based on standard deviation
        consistency_penalty = min(std_dev / abs(full_value), 1.0)
        
        # Base score starts at 100 and is reduced by deviation and inconsistency
        base_score = 100.0
        deviation_penalty = min(relative_deviation * 100, 100.0)  # Cap at 100%
        consistency_penalty_scaled = consistency_penalty * 50  # Max 50 point penalty for inconsistency
        
        score = max(0, base_score - deviation_penalty - consistency_penalty_scaled)
        
        # Debug logging for zero scores
        if score == 0.0:
            logger.warning(f"Zero score calculated - mean: {mean_value}, full: {full_value}, std: {std_dev}, "
                         f"rel_dev: {relative_deviation}, dev_penalty: {deviation_penalty}, "
                         f"consist_penalty: {consistency_penalty_scaled}")
        
        return float(score)
    
    def _calculate_robustness_score(self, statistics: Dict[str, Dict[str, Any]]) -> float:
        """Calculate overall robustness score from component statistics"""
        
        # Define weights for different metrics
        weights = {
            'cagr': 0.25,
            'sharpe_ratio': 0.20,
            'max_drawdown': 0.20,  # Lower is better for drawdown
            'volatility': 0.10,
            'win_rate': 0.10,
            'sortino_ratio': 0.15
        }
        
        weighted_scores = []
        total_weight = 0
        
        for metric, weight in weights.items():
            if metric in statistics:
                component_score = statistics[metric]['robustness_component_score']
                
                # For drawdown, invert the score since lower drawdown is better
                if metric == 'max_drawdown':
                    component_score = 100 - component_score
                
                weighted_scores.append(component_score * weight)
                total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        # Calculate weighted average
        overall_score = sum(weighted_scores) / total_weight
        
        return float(max(0, min(100, overall_score)))  # Ensure score is between 0-100
    
    def get_test_results(self, test_id: int) -> Optional[Dict[str, Any]]:
        """Get comprehensive results for a robustness test"""
        
        test = self.db.query(RobustnessTest).filter(RobustnessTest.id == test_id).first()
        if not test:
            return None
        
        # Get all periods
        periods = self.db.query(RobustnessPeriod).filter(
            RobustnessPeriod.robustness_test_id == test_id
        ).order_by(RobustnessPeriod.period_number).all()
        
        # Get all statistics
        statistics = self.db.query(RobustnessStatistic).filter(
            RobustnessStatistic.robustness_test_id == test_id
        ).all()
        
        # Format results
        result = {
            'test_id': test.id,
            'portfolio_id': test.portfolio_id,
            'portfolio_name': test.portfolio.name if test.portfolio else 'Unknown',
            'status': test.status,
            'progress': test.progress,
            'num_periods': test.num_periods,
            'period_length_days': test.min_period_length_days,
            'overall_robustness_score': test.overall_robustness_score,
            'created_at': test.created_at.isoformat() if test.created_at else None,
            'completed_at': test.completed_at.isoformat() if test.completed_at else None,
            'error_message': test.error_message,
            'parameters': {
                'rf_rate': test.rf_rate,
                'sma_window': test.sma_window,
                'use_trading_filter': test.use_trading_filter,
                'starting_capital': test.starting_capital
            },
            'periods': [
                {
                    'period_number': period.period_number,
                    'start_date': period.start_date.isoformat(),
                    'end_date': period.end_date.isoformat(),
                    'cagr': period.cagr,
                    'sharpe_ratio': period.sharpe_ratio,
                    'max_drawdown': period.max_drawdown,
                    'volatility': period.volatility,
                    'win_rate': period.win_rate,
                    'total_return': period.total_return,
                    'total_pl': period.total_pl,
                    'pcr': period.pcr,
                    'trade_count': period.trade_count
                }
                for period in periods
            ],
            'statistics': {
                stat.metric_name: {
                    'max_value': stat.max_value,
                    'min_value': stat.min_value,
                    'mean_value': stat.mean_value,
                    'median_value': stat.median_value,
                    'std_deviation': stat.std_deviation,
                    'q1_value': stat.q1_value,
                    'q3_value': stat.q3_value,
                    'full_dataset_value': stat.full_dataset_value,
                    'robustness_component_score': stat.robustness_component_score,
                    'relative_deviation': stat.relative_deviation
                }
                for stat in statistics
            }
        }
        
        return result
    
    def delete_test(self, test_id: int) -> bool:
        """Delete a robustness test and all associated data"""
        test = self.db.query(RobustnessTest).filter(RobustnessTest.id == test_id).first()
        if not test:
            return False
        
        self.db.delete(test)
        self.db.commit()
        return True
    
    def get_portfolio_tests(self, portfolio_id: int) -> List[Dict[str, Any]]:
        """Get all robustness tests for a specific portfolio"""
        tests = self.db.query(RobustnessTest).filter(
            RobustnessTest.portfolio_id == portfolio_id
        ).order_by(RobustnessTest.created_at.desc()).all()
        
        return [
            {
                'test_id': test.id,
                'status': test.status,
                'num_periods': test.num_periods,
                'min_period_length_days': test.min_period_length_days,
                'overall_robustness_score': test.overall_robustness_score,
                'created_at': test.created_at.isoformat() if test.created_at else None,
                'completed_at': test.completed_at.isoformat() if test.completed_at else None
            }
            for test in tests
        ]