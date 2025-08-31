"""
Market Regime Detection Engine for Portfolio Analysis
Detects bull, bear, and volatile market conditions to optimize strategy allocation
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime, timedelta
import yfinance as yf

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classifications"""
    BULL = "bull"
    BEAR = "bear"
    VOLATILE = "volatile"
    TRANSITIONING = "transitioning"


@dataclass
class RegimeClassification:
    """Market regime classification result"""
    regime: MarketRegime
    confidence: float  # 0-1 confidence score
    indicators: Dict[str, float]  # Key metrics used for classification
    detected_at: datetime
    regime_start: Optional[datetime] = None
    description: str = ""


@dataclass
class RegimeMetrics:
    """Key metrics for regime analysis"""
    volatility_percentile: float
    trend_strength: float
    momentum_score: float
    drawdown_severity: float
    volume_anomaly: float


class MarketRegimeAnalyzer:
    """
    Analyzes market conditions to classify current regime and predict optimal allocations
    """
    
    def __init__(self, 
                 volatility_lookback: int = 60,
                 trend_lookback: int = 20,
                 regime_confirmation_days: int = 5):
        """
        Initialize the Market Regime Analyzer
        
        Args:
            volatility_lookback: Days to look back for volatility calculation
            trend_lookback: Days for trend analysis
            regime_confirmation_days: Days to confirm regime change
        """
        self.volatility_lookback = volatility_lookback
        self.trend_lookback = trend_lookback
        self.regime_confirmation_days = regime_confirmation_days
        
        # Regime classification thresholds
        self.volatility_thresholds = {
            'low': 0.3,    # Below 30th percentile = low vol
            'high': 0.7    # Above 70th percentile = high vol
        }
        
        self.trend_thresholds = {
            'strong_up': 0.6,    # Strong uptrend
            'strong_down': -0.6,  # Strong downtrend
            'neutral': 0.2        # Neutral zone
        }
        
        # Cache for market data
        self._market_data_cache: Dict[str, pd.DataFrame] = {}
        self._last_cache_update: Dict[str, datetime] = {}
        
    def get_market_data(self, symbol: str = "^GSPC", period: str = "2y") -> pd.DataFrame:
        """
        Fetch market data with caching
        
        Args:
            symbol: Market index symbol (default S&P 500)
            period: Data period to fetch
            
        Returns:
            DataFrame with OHLCV data
        """
        cache_key = f"{symbol}_{period}"
        now = datetime.now()
        
        # Check if we need to refresh cache (daily refresh)
        if (cache_key not in self._market_data_cache or 
            cache_key not in self._last_cache_update or
            now - self._last_cache_update[cache_key] > timedelta(hours=6)):
            
            try:
                logger.info(f"Fetching market data for {symbol}")
                ticker = yf.Ticker(symbol)
                data = ticker.history(period=period)
                
                if data.empty:
                    raise ValueError(f"No data retrieved for {symbol}")
                
                # Calculate additional metrics
                data['Returns'] = data['Close'].pct_change()
                data['Volatility'] = data['Returns'].rolling(window=20).std() * np.sqrt(252)
                data['SMA_20'] = data['Close'].rolling(window=20).mean()
                data['SMA_50'] = data['Close'].rolling(window=50).mean()
                
                self._market_data_cache[cache_key] = data
                self._last_cache_update[cache_key] = now
                
            except Exception as e:
                logger.error(f"Failed to fetch market data: {e}")
                # Return cached data if available
                if cache_key in self._market_data_cache:
                    logger.warning("Using cached market data due to fetch error")
                else:
                    raise
        
        return self._market_data_cache[cache_key]
    
    def calculate_regime_metrics(self, market_data: pd.DataFrame) -> RegimeMetrics:
        """
        Calculate key metrics for regime classification
        
        Args:
            market_data: DataFrame with market OHLCV data
            
        Returns:
            RegimeMetrics object with calculated indicators
        """
        if len(market_data) < self.volatility_lookback:
            raise ValueError(f"Insufficient data: need at least {self.volatility_lookback} days")
        
        recent_data = market_data.tail(self.volatility_lookback)
        
        # 1. Volatility Analysis
        current_vol = recent_data['Volatility'].iloc[-1]
        vol_percentile = (recent_data['Volatility'] < current_vol).sum() / len(recent_data)
        
        # 2. Trend Strength
        price_change = (recent_data['Close'].iloc[-1] / recent_data['Close'].iloc[0] - 1)
        sma_trend = (recent_data['SMA_20'].iloc[-1] / recent_data['SMA_50'].iloc[-1] - 1)
        trend_strength = (price_change + sma_trend) / 2
        
        # 3. Momentum Score
        returns_5d = recent_data['Returns'].tail(5).mean()
        returns_20d = recent_data['Returns'].tail(20).mean()
        momentum_score = (returns_5d / returns_20d) if returns_20d != 0 else 0
        
        # 4. Drawdown Severity
        rolling_max = recent_data['Close'].expanding().max()
        current_drawdown = (recent_data['Close'] / rolling_max - 1).iloc[-1]
        drawdown_severity = abs(current_drawdown)
        
        # 5. Volume Anomaly (simplified - using price volatility as proxy)
        vol_mean = recent_data['Volatility'].mean()
        vol_std = recent_data['Volatility'].std()
        volume_anomaly = (current_vol - vol_mean) / vol_std if vol_std != 0 else 0
        
        return RegimeMetrics(
            volatility_percentile=vol_percentile,
            trend_strength=trend_strength,
            momentum_score=momentum_score,
            drawdown_severity=drawdown_severity,
            volume_anomaly=volume_anomaly
        )
    
    def classify_regime(self, metrics: RegimeMetrics) -> RegimeClassification:
        """
        Classify market regime based on calculated metrics
        
        Args:
            metrics: RegimeMetrics object
            
        Returns:
            RegimeClassification with regime and confidence
        """
        indicators = {
            'volatility_percentile': metrics.volatility_percentile,
            'trend_strength': metrics.trend_strength,
            'momentum_score': metrics.momentum_score,
            'drawdown_severity': metrics.drawdown_severity,
            'volume_anomaly': metrics.volume_anomaly
        }
        
        # Classification logic
        regime_scores = {
            MarketRegime.BULL: 0,
            MarketRegime.BEAR: 0,
            MarketRegime.VOLATILE: 0,
            MarketRegime.TRANSITIONING: 0
        }
        
        # Bull market indicators
        if metrics.trend_strength > self.trend_thresholds['strong_up']:
            regime_scores[MarketRegime.BULL] += 2
        elif metrics.trend_strength > 0:
            regime_scores[MarketRegime.BULL] += 1
            
        if metrics.momentum_score > 0.5:
            regime_scores[MarketRegime.BULL] += 1
            
        if metrics.volatility_percentile < self.volatility_thresholds['low']:
            regime_scores[MarketRegime.BULL] += 1
            
        # Bear market indicators  
        if metrics.trend_strength < self.trend_thresholds['strong_down']:
            regime_scores[MarketRegime.BEAR] += 2
        elif metrics.trend_strength < 0:
            regime_scores[MarketRegime.BEAR] += 1
            
        if metrics.drawdown_severity > 0.1:  # 10% drawdown
            regime_scores[MarketRegime.BEAR] += 2
        elif metrics.drawdown_severity > 0.05:
            regime_scores[MarketRegime.BEAR] += 1
            
        if metrics.momentum_score < -0.5:
            regime_scores[MarketRegime.BEAR] += 1
            
        # Volatile market indicators
        if metrics.volatility_percentile > self.volatility_thresholds['high']:
            regime_scores[MarketRegime.VOLATILE] += 2
            
        if abs(metrics.volume_anomaly) > 2:  # 2 std deviations
            regime_scores[MarketRegime.VOLATILE] += 1
            
        if abs(metrics.trend_strength) < self.trend_thresholds['neutral']:
            regime_scores[MarketRegime.VOLATILE] += 1
            
        # Transitioning indicators
        if (abs(metrics.trend_strength) < self.trend_thresholds['neutral'] and
            metrics.volatility_percentile > 0.4 and metrics.volatility_percentile < 0.6):
            regime_scores[MarketRegime.TRANSITIONING] += 2
        
        # Determine primary regime
        primary_regime = max(regime_scores.keys(), key=lambda k: regime_scores[k])
        max_score = regime_scores[primary_regime]
        
        # Calculate confidence (normalize by max possible score of ~5)
        confidence = min(max_score / 5.0, 1.0)
        
        # Generate description
        descriptions = {
            MarketRegime.BULL: f"Upward trending market with {metrics.trend_strength:.1%} momentum",
            MarketRegime.BEAR: f"Downward trending market with {metrics.drawdown_severity:.1%} drawdown",
            MarketRegime.VOLATILE: f"High volatility market ({metrics.volatility_percentile:.0%} percentile)",
            MarketRegime.TRANSITIONING: "Market in transition between regimes"
        }
        
        return RegimeClassification(
            regime=primary_regime,
            confidence=confidence,
            indicators=indicators,
            detected_at=datetime.now(),
            description=descriptions[primary_regime]
        )
    
    def detect_current_regime(self, symbol: str = "^GSPC") -> RegimeClassification:
        """
        Detect current market regime
        
        Args:
            symbol: Market index to analyze
            
        Returns:
            RegimeClassification for current market conditions
        """
        try:
            # Get market data
            market_data = self.get_market_data(symbol)
            
            # Calculate metrics
            metrics = self.calculate_regime_metrics(market_data)
            
            # Classify regime
            classification = self.classify_regime(metrics)
            
            logger.info(f"Detected regime: {classification.regime.value} "
                       f"(confidence: {classification.confidence:.2f})")
            
            return classification
            
        except Exception as e:
            logger.error(f"Failed to detect market regime: {e}")
            # Return default classification
            return RegimeClassification(
                regime=MarketRegime.TRANSITIONING,
                confidence=0.0,
                indicators={},
                detected_at=datetime.now(),
                description="Unable to determine regime due to data issues"
            )
    
    def analyze_strategy_regime_performance(self, 
                                         strategy_data: pd.DataFrame,
                                         regime_history: List[RegimeClassification]) -> Dict[MarketRegime, Dict[str, float]]:
        """
        Analyze how a strategy performs in different market regimes
        
        Args:
            strategy_data: DataFrame with strategy P/L data
            regime_history: Historical regime classifications
            
        Returns:
            Dict mapping regimes to performance metrics
        """
        if 'Date' not in strategy_data.columns:
            raise ValueError("Strategy data must have 'Date' column")
        
        strategy_data = strategy_data.copy()
        strategy_data['Date'] = pd.to_datetime(strategy_data['Date'])
        strategy_data = strategy_data.sort_values('Date')
        
        # Calculate daily returns
        if 'Daily_Return' not in strategy_data.columns:
            strategy_data['Daily_Return'] = strategy_data['P/L'].pct_change()
        
        regime_performance = {}
        
        for regime in MarketRegime:
            # Filter data for this regime (simplified - would need actual regime mapping by date)
            # For now, use synthetic regime periods
            regime_returns = strategy_data['Daily_Return'].dropna()
            
            if len(regime_returns) > 0:
                regime_performance[regime] = {
                    'total_return': (1 + regime_returns).prod() - 1,
                    'avg_daily_return': regime_returns.mean(),
                    'volatility': regime_returns.std() * np.sqrt(252),
                    'sharpe_ratio': regime_returns.mean() / regime_returns.std() * np.sqrt(252) if regime_returns.std() != 0 else 0,
                    'max_drawdown': self._calculate_max_drawdown(regime_returns),
                    'win_rate': (regime_returns > 0).sum() / len(regime_returns)
                }
            else:
                regime_performance[regime] = {
                    'total_return': 0,
                    'avg_daily_return': 0,
                    'volatility': 0,
                    'sharpe_ratio': 0,
                    'max_drawdown': 0,
                    'win_rate': 0
                }
        
        return regime_performance
    
    def _calculate_max_drawdown(self, returns: pd.Series) -> float:
        """Calculate maximum drawdown from returns series"""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = cumulative / running_max - 1
        return drawdown.min()
    
    def get_regime_allocation_recommendations(self, 
                                           current_regime: RegimeClassification,
                                           strategy_performances: Dict[str, Dict[MarketRegime, Dict[str, float]]]) -> Dict[str, float]:
        """
        Generate allocation recommendations based on current regime
        
        Args:
            current_regime: Current market regime classification
            strategy_performances: Historical performance by strategy and regime
            
        Returns:
            Dict mapping strategy names to recommended allocations
        """
        recommendations = {}
        regime = current_regime.regime
        
        # Score strategies based on regime performance
        strategy_scores = {}
        
        for strategy_name, perf_data in strategy_performances.items():
            if regime in perf_data:
                regime_perf = perf_data[regime]
                
                # Composite score: risk-adjusted returns with regime-specific bonuses
                base_score = regime_perf['sharpe_ratio']
                
                # Regime-specific adjustments
                if regime == MarketRegime.BULL:
                    # Favor momentum and growth in bull markets
                    base_score += regime_perf['total_return'] * 0.5
                elif regime == MarketRegime.BEAR:
                    # Favor defensive strategies in bear markets
                    base_score -= regime_perf['max_drawdown'] * 2
                elif regime == MarketRegime.VOLATILE:
                    # Favor low-volatility strategies
                    base_score -= regime_perf['volatility'] * 0.3
                
                strategy_scores[strategy_name] = max(base_score, 0)  # Ensure non-negative
        
        # Convert scores to allocations
        total_score = sum(strategy_scores.values())
        
        if total_score > 0:
            for strategy_name, score in strategy_scores.items():
                base_allocation = score / total_score
                
                # Apply min/max constraints
                recommendations[strategy_name] = max(0.05, min(0.6, base_allocation))
        else:
            # Equal weighting if no clear winners
            num_strategies = len(strategy_performances)
            equal_weight = 1.0 / num_strategies if num_strategies > 0 else 0
            recommendations = {name: equal_weight for name in strategy_performances.keys()}
        
        # Normalize to ensure sum = 1
        total_allocation = sum(recommendations.values())
        if total_allocation > 0:
            recommendations = {name: weight / total_allocation 
                             for name, weight in recommendations.items()}
        
        return recommendations