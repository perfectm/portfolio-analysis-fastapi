"""
Regime Analysis Service
Handles database operations and business logic for market regime analysis
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, func

from models import (
    MarketRegimeHistory, RegimePerformance, RegimeAlert,
    Portfolio, PortfolioData
)
from market_regime_analyzer import MarketRegimeAnalyzer, MarketRegime, RegimeClassification
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class RegimeService:
    """Service class for regime analysis operations"""
    
    def __init__(self):
        self.analyzer = MarketRegimeAnalyzer()
    
    def detect_and_store_current_regime(self, db: Session, symbol: str = "^GSPC") -> RegimeClassification:
        """
        Detect current market regime and store in database
        
        Args:
            db: Database session
            symbol: Market symbol to analyze
            
        Returns:
            RegimeClassification object
        """
        try:
            # Detect current regime
            classification = self.analyzer.detect_current_regime(symbol)
            
            # Check if we already have a classification for today
            today = datetime.now().date()
            existing = db.query(MarketRegimeHistory).filter(
                func.date(MarketRegimeHistory.date) == today,
                MarketRegimeHistory.market_symbol == symbol
            ).first()
            
            if existing:
                # Update existing record
                existing.regime = classification.regime.value
                existing.confidence = classification.confidence
                existing.volatility_percentile = classification.indicators.get('volatility_percentile')
                existing.trend_strength = classification.indicators.get('trend_strength')
                existing.momentum_score = classification.indicators.get('momentum_score')
                existing.drawdown_severity = classification.indicators.get('drawdown_severity')
                existing.volume_anomaly = classification.indicators.get('volume_anomaly')
                existing.description = classification.description
                logger.info(f"Updated regime classification for {today}: {classification.regime.value}")
            else:
                # Create new record
                regime_record = MarketRegimeHistory(
                    date=classification.detected_at,
                    regime=classification.regime.value,
                    confidence=classification.confidence,
                    volatility_percentile=classification.indicators.get('volatility_percentile'),
                    trend_strength=classification.indicators.get('trend_strength'),
                    momentum_score=classification.indicators.get('momentum_score'),
                    drawdown_severity=classification.indicators.get('drawdown_severity'),
                    volume_anomaly=classification.indicators.get('volume_anomaly'),
                    market_symbol=symbol,
                    description=classification.description
                )
                db.add(regime_record)
                logger.info(f"Stored new regime classification: {classification.regime.value}")
            
            db.commit()
            return classification
            
        except Exception as e:
            logger.error(f"Failed to detect and store regime: {e}")
            db.rollback()
            raise
    
    def get_regime_history(self, db: Session, 
                          days: int = 90, 
                          symbol: str = "^GSPC") -> List[MarketRegimeHistory]:
        """
        Get historical regime classifications
        
        Args:
            db: Database session
            days: Number of days to look back
            symbol: Market symbol
            
        Returns:
            List of MarketRegimeHistory records
        """
        start_date = datetime.now() - timedelta(days=days)
        
        return db.query(MarketRegimeHistory).filter(
            MarketRegimeHistory.date >= start_date,
            MarketRegimeHistory.market_symbol == symbol
        ).order_by(desc(MarketRegimeHistory.date)).all()
    
    def calculate_strategy_regime_performance(self, db: Session, portfolio_id: int) -> Dict[str, Dict[str, float]]:
        """
        Calculate how a strategy performs in different market regimes
        
        Args:
            db: Database session
            portfolio_id: Portfolio ID to analyze
            
        Returns:
            Dict mapping regime names to performance metrics
        """
        try:
            # Get portfolio data
            portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
            if not portfolio:
                raise ValueError(f"Portfolio {portfolio_id} not found")
            
            # Get portfolio trading data
            portfolio_data = db.query(PortfolioData).filter(
                PortfolioData.portfolio_id == portfolio_id
            ).order_by(PortfolioData.date).all()
            
            if not portfolio_data:
                logger.warning(f"No data found for portfolio {portfolio_id}")
                return {}
            
            # Convert to DataFrame
            df = pd.DataFrame([{
                'Date': row.date,
                'P/L': row.pl,
                'Daily_Return': row.daily_return or 0
            } for row in portfolio_data])
            
            # Get regime history for the same period
            start_date = df['Date'].min()
            end_date = df['Date'].max()
            
            regime_history = db.query(MarketRegimeHistory).filter(
                MarketRegimeHistory.date >= start_date,
                MarketRegimeHistory.date <= end_date
            ).order_by(MarketRegimeHistory.date).all()
            
            # Map dates to regimes
            regime_df = pd.DataFrame([{
                'Date': row.date.date(),
                'Regime': row.regime
            } for row in regime_history])
            
            if regime_df.empty:
                logger.warning("No regime history available for analysis period")
                return self._calculate_default_regime_performance(df)
            
            # Merge portfolio data with regime data
            df['Date'] = pd.to_datetime(df['Date']).dt.date
            merged = pd.merge(df, regime_df, on='Date', how='left')
            
            # Forward fill missing regimes
            merged['Regime'] = merged['Regime'].fillna(method='ffill').fillna('transitioning')
            
            # Calculate performance by regime
            regime_performance = {}
            
            for regime in ['bull', 'bear', 'volatile', 'transitioning']:
                regime_data = merged[merged['Regime'] == regime]
                
                if len(regime_data) > 0:
                    returns = regime_data['Daily_Return'].dropna()
                    
                    if len(returns) > 0:
                        regime_performance[regime] = {
                            'total_return': (1 + returns).prod() - 1,
                            'avg_daily_return': returns.mean(),
                            'volatility': returns.std() * np.sqrt(252) if returns.std() != 0 else 0,
                            'sharpe_ratio': returns.mean() / returns.std() * np.sqrt(252) if returns.std() != 0 else 0,
                            'max_drawdown': self._calculate_max_drawdown(returns),
                            'win_rate': (returns > 0).sum() / len(returns),
                            'total_trading_days': len(returns)
                        }
                    else:
                        regime_performance[regime] = self._empty_performance_metrics()
                else:
                    regime_performance[regime] = self._empty_performance_metrics()
            
            # Store in database
            self._store_regime_performance(db, portfolio_id, regime_performance, start_date, end_date)
            
            return regime_performance
            
        except Exception as e:
            logger.error(f"Failed to calculate regime performance for portfolio {portfolio_id}: {e}")
            return {}
    
    def _calculate_default_regime_performance(self, df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
        """Calculate performance metrics using synthetic regime periods"""
        # Use volatility to create synthetic regimes
        df['Volatility'] = df['Daily_Return'].rolling(window=20).std()
        vol_75th = df['Volatility'].quantile(0.75)
        vol_25th = df['Volatility'].quantile(0.25)
        
        # Simple regime classification based on volatility
        def classify_regime(vol, ret):
            if pd.isna(vol):
                return 'transitioning'
            elif vol > vol_75th:
                return 'volatile'
            elif ret > 0.001:  # Positive returns
                return 'bull'
            elif ret < -0.001:  # Negative returns
                return 'bear'
            else:
                return 'transitioning'
        
        df['Synthetic_Regime'] = df.apply(lambda x: classify_regime(x['Volatility'], x['Daily_Return']), axis=1)
        
        # Calculate performance by synthetic regime
        regime_performance = {}
        for regime in ['bull', 'bear', 'volatile', 'transitioning']:
            regime_data = df[df['Synthetic_Regime'] == regime]
            returns = regime_data['Daily_Return'].dropna()
            
            if len(returns) > 0:
                regime_performance[regime] = {
                    'total_return': (1 + returns).prod() - 1,
                    'avg_daily_return': returns.mean(),
                    'volatility': returns.std() * np.sqrt(252) if returns.std() != 0 else 0,
                    'sharpe_ratio': returns.mean() / returns.std() * np.sqrt(252) if returns.std() != 0 else 0,
                    'max_drawdown': self._calculate_max_drawdown(returns),
                    'win_rate': (returns > 0).sum() / len(returns),
                    'total_trading_days': len(returns)
                }
            else:
                regime_performance[regime] = self._empty_performance_metrics()
        
        return regime_performance
    
    def _empty_performance_metrics(self) -> Dict[str, float]:
        """Return empty performance metrics"""
        return {
            'total_return': 0.0,
            'avg_daily_return': 0.0,
            'volatility': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'total_trading_days': 0
        }
    
    def _calculate_max_drawdown(self, returns: pd.Series) -> float:
        """Calculate maximum drawdown from returns series"""
        if returns.empty:
            return 0.0
        
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = cumulative / running_max - 1
        return drawdown.min()
    
    def _store_regime_performance(self, db: Session, portfolio_id: int, 
                                 performance: Dict[str, Dict[str, float]],
                                 start_date: datetime, end_date: datetime):
        """Store regime performance results in database"""
        try:
            for regime, metrics in performance.items():
                # Check if record exists
                existing = db.query(RegimePerformance).filter(
                    RegimePerformance.portfolio_id == portfolio_id,
                    RegimePerformance.regime == regime
                ).first()
                
                if existing:
                    # Update existing
                    existing.total_return = metrics['total_return']
                    existing.avg_daily_return = metrics['avg_daily_return']
                    existing.volatility = metrics['volatility']
                    existing.sharpe_ratio = metrics['sharpe_ratio']
                    existing.max_drawdown = metrics['max_drawdown']
                    existing.win_rate = metrics['win_rate']
                    existing.analysis_period_start = start_date
                    existing.analysis_period_end = end_date
                    existing.total_trading_days = metrics.get('total_trading_days', 0)
                else:
                    # Create new
                    perf_record = RegimePerformance(
                        portfolio_id=portfolio_id,
                        regime=regime,
                        total_return=metrics['total_return'],
                        avg_daily_return=metrics['avg_daily_return'],
                        volatility=metrics['volatility'],
                        sharpe_ratio=metrics['sharpe_ratio'],
                        max_drawdown=metrics['max_drawdown'],
                        win_rate=metrics['win_rate'],
                        analysis_period_start=start_date,
                        analysis_period_end=end_date,
                        total_trading_days=metrics.get('total_trading_days', 0)
                    )
                    db.add(perf_record)
            
            db.commit()
            logger.info(f"Stored regime performance for portfolio {portfolio_id}")
            
        except Exception as e:
            logger.error(f"Failed to store regime performance: {e}")
            db.rollback()
    
    def get_regime_allocation_recommendations(self, db: Session, 
                                           portfolio_ids: List[int]) -> Dict[str, float]:
        """
        Get allocation recommendations based on current regime
        
        Args:
            db: Database session
            portfolio_ids: List of portfolio IDs to get recommendations for
            
        Returns:
            Dict mapping portfolio names to recommended allocations
        """
        try:
            # Get current regime
            current_regime = self.get_current_regime(db)
            if not current_regime:
                logger.warning("No current regime available, using equal weighting")
                return self._equal_weighting(db, portfolio_ids)
            
            # Get strategy performances for current regime
            strategy_performances = {}
            
            for portfolio_id in portfolio_ids:
                portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
                if portfolio:
                    # Get regime performance
                    regime_perf = db.query(RegimePerformance).filter(
                        RegimePerformance.portfolio_id == portfolio_id,
                        RegimePerformance.regime == current_regime.regime
                    ).first()
                    
                    if regime_perf:
                        strategy_performances[portfolio.name] = {
                            MarketRegime(current_regime.regime): {
                                'total_return': regime_perf.total_return,
                                'avg_daily_return': regime_perf.avg_daily_return,
                                'volatility': regime_perf.volatility,
                                'sharpe_ratio': regime_perf.sharpe_ratio,
                                'max_drawdown': regime_perf.max_drawdown,
                                'win_rate': regime_perf.win_rate
                            }
                        }
            
            if not strategy_performances:
                logger.warning("No regime performance data available, using equal weighting")
                return self._equal_weighting(db, portfolio_ids)
            
            # Get recommendations from analyzer
            current_regime_classification = RegimeClassification(
                regime=MarketRegime(current_regime.regime),
                confidence=current_regime.confidence,
                indicators={},
                detected_at=current_regime.date
            )
            
            recommendations = self.analyzer.get_regime_allocation_recommendations(
                current_regime_classification, 
                strategy_performances
            )
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to get allocation recommendations: {e}")
            return self._equal_weighting(db, portfolio_ids)
    
    def _equal_weighting(self, db: Session, portfolio_ids: List[int]) -> Dict[str, float]:
        """Generate equal weighting allocation"""
        portfolios = db.query(Portfolio).filter(Portfolio.id.in_(portfolio_ids)).all()
        if not portfolios:
            return {}
        
        weight = 1.0 / len(portfolios)
        return {portfolio.name: weight for portfolio in portfolios}
    
    def get_current_regime(self, db: Session, symbol: str = "^GSPC") -> Optional[MarketRegimeHistory]:
        """Get the most recent regime classification"""
        return db.query(MarketRegimeHistory).filter(
            MarketRegimeHistory.market_symbol == symbol
        ).order_by(desc(MarketRegimeHistory.date)).first()
    
    def create_regime_change_alert(self, db: Session, 
                                 previous_regime: Optional[str],
                                 new_regime: str,
                                 confidence: float,
                                 recommended_allocations: Dict[str, float]) -> RegimeAlert:
        """
        Create a regime change alert
        
        Args:
            db: Database session
            previous_regime: Previous regime (if any)
            new_regime: New detected regime
            confidence: Confidence score
            recommended_allocations: Recommended portfolio allocations
            
        Returns:
            Created RegimeAlert object
        """
        try:
            # Create alert message
            if previous_regime and previous_regime != new_regime:
                title = f"Market Regime Changed: {previous_regime.title()} → {new_regime.title()}"
                message = f"Market regime has shifted from {previous_regime} to {new_regime} market conditions with {confidence:.1%} confidence."
                severity = "warning" if confidence > 0.7 else "info"
            else:
                title = f"Market Regime Update: {new_regime.title()} Market"
                message = f"Current market regime confirmed as {new_regime} with {confidence:.1%} confidence."
                severity = "info"
            
            # Create alert
            alert = RegimeAlert(
                alert_type="regime_change",
                previous_regime=previous_regime,
                new_regime=new_regime,
                confidence=confidence,
                title=title,
                message=message,
                severity=severity,
                recommended_allocations=json.dumps(recommended_allocations),
                expires_at=datetime.now() + timedelta(days=7)  # Expire in 1 week
            )
            
            db.add(alert)
            db.commit()
            
            logger.info(f"Created regime change alert: {title}")
            return alert
            
        except Exception as e:
            logger.error(f"Failed to create regime change alert: {e}")
            db.rollback()
            raise
    
    def get_active_alerts(self, db: Session) -> List[RegimeAlert]:
        """Get all active regime alerts"""
        return db.query(RegimeAlert).filter(
            RegimeAlert.is_active == True,
            RegimeAlert.expires_at > datetime.now()
        ).order_by(desc(RegimeAlert.created_at)).all()
    
    def dismiss_alert(self, db: Session, alert_id: int) -> bool:
        """Dismiss an alert"""
        try:
            alert = db.query(RegimeAlert).filter(RegimeAlert.id == alert_id).first()
            if alert:
                alert.is_active = False
                alert.dismissed_at = datetime.now()
                db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to dismiss alert {alert_id}: {e}")
            db.rollback()
            return False