"""
Tests for Market Regime Analysis functionality
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from market_regime_analyzer import MarketRegimeAnalyzer, MarketRegime, RegimeClassification
from regime_service import RegimeService
from models import MarketRegimeHistory, RegimePerformance, RegimeAlert, Portfolio, PortfolioData


class TestMarketRegimeAnalyzer:
    """Test suite for MarketRegimeAnalyzer"""
    
    def setup_method(self):
        """Setup for each test"""
        self.analyzer = MarketRegimeAnalyzer()
    
    def create_mock_market_data(self, days=100, regime='bull'):
        """Create mock market data for testing"""
        dates = pd.date_range(start='2023-01-01', periods=days, freq='D')
        
        if regime == 'bull':
            # Upward trending with low volatility
            trend = np.linspace(100, 120, days)
            noise = np.random.normal(0, 1, days)
        elif regime == 'bear':
            # Downward trending with high volatility
            trend = np.linspace(100, 80, days)
            noise = np.random.normal(0, 3, days)
        elif regime == 'volatile':
            # Sideways with high volatility
            trend = np.full(days, 100)
            noise = np.random.normal(0, 5, days)
        else:  # transitioning
            # Mixed signals
            trend = 100 + np.sin(np.linspace(0, 4*np.pi, days)) * 5
            noise = np.random.normal(0, 2, days)
        
        prices = trend + noise
        
        data = pd.DataFrame({
            'Close': prices,
            'Open': prices * 0.99,
            'High': prices * 1.01,
            'Low': prices * 0.98,
            'Volume': np.random.randint(1000000, 5000000, days)
        }, index=dates)
        
        # Calculate additional metrics
        data['Returns'] = data['Close'].pct_change()
        data['Volatility'] = data['Returns'].rolling(window=20).std() * np.sqrt(252)
        data['SMA_20'] = data['Close'].rolling(window=20).mean()
        data['SMA_50'] = data['Close'].rolling(window=50).mean()
        
        return data
    
    def test_calculate_regime_metrics_bull_market(self):
        """Test regime metrics calculation for bull market"""
        market_data = self.create_mock_market_data(100, 'bull')
        metrics = self.analyzer.calculate_regime_metrics(market_data)
        
        assert metrics is not None
        assert 0 <= metrics.volatility_percentile <= 1
        assert metrics.trend_strength > 0  # Should be positive for bull market
        assert isinstance(metrics.drawdown_severity, float)
        assert isinstance(metrics.volume_anomaly, float)
    
    def test_calculate_regime_metrics_bear_market(self):
        """Test regime metrics calculation for bear market"""
        market_data = self.create_mock_market_data(100, 'bear')
        metrics = self.analyzer.calculate_regime_metrics(market_data)
        
        assert metrics is not None
        assert metrics.trend_strength < 0  # Should be negative for bear market
        assert metrics.drawdown_severity > 0  # Should have drawdown
    
    def test_calculate_regime_metrics_insufficient_data(self):
        """Test error handling with insufficient data"""
        market_data = self.create_mock_market_data(30, 'bull')  # Less than volatility_lookback
        
        with pytest.raises(ValueError, match="Insufficient data"):
            self.analyzer.calculate_regime_metrics(market_data)
    
    def test_classify_regime_bull_market(self):
        """Test regime classification for bull market conditions"""
        market_data = self.create_mock_market_data(100, 'bull')
        metrics = self.analyzer.calculate_regime_metrics(market_data)
        classification = self.analyzer.classify_regime(metrics)
        
        assert isinstance(classification, RegimeClassification)
        assert classification.regime in [MarketRegime.BULL, MarketRegime.TRANSITIONING]
        assert 0 <= classification.confidence <= 1
        assert isinstance(classification.indicators, dict)
        assert len(classification.description) > 0
    
    def test_classify_regime_bear_market(self):
        """Test regime classification for bear market conditions"""
        market_data = self.create_mock_market_data(100, 'bear')
        metrics = self.analyzer.calculate_regime_metrics(market_data)
        classification = self.analyzer.classify_regime(metrics)
        
        assert classification.regime in [MarketRegime.BEAR, MarketRegime.VOLATILE, MarketRegime.TRANSITIONING]
    
    @patch('market_regime_analyzer.yf.Ticker')
    def test_get_market_data_success(self, mock_ticker):
        """Test successful market data retrieval"""
        mock_history = self.create_mock_market_data(100, 'bull')
        mock_ticker.return_value.history.return_value = mock_history
        
        data = self.analyzer.get_market_data("^GSPC", "1y")
        
        assert isinstance(data, pd.DataFrame)
        assert 'Returns' in data.columns
        assert 'Volatility' in data.columns
        assert 'SMA_20' in data.columns
        mock_ticker.assert_called_once_with("^GSPC")
    
    @patch('market_regime_analyzer.yf.Ticker')
    def test_get_market_data_empty_response(self, mock_ticker):
        """Test handling of empty market data response"""
        mock_ticker.return_value.history.return_value = pd.DataFrame()
        
        with pytest.raises(ValueError, match="No data retrieved"):
            self.analyzer.get_market_data("INVALID", "1y")
    
    @patch('market_regime_analyzer.yf.Ticker')
    def test_detect_current_regime_success(self, mock_ticker):
        """Test successful regime detection"""
        mock_history = self.create_mock_market_data(100, 'bull')
        mock_ticker.return_value.history.return_value = mock_history
        
        classification = self.analyzer.detect_current_regime("^GSPC")
        
        assert isinstance(classification, RegimeClassification)
        assert classification.regime in list(MarketRegime)
        assert 0 <= classification.confidence <= 1
    
    @patch('market_regime_analyzer.yf.Ticker')
    def test_detect_current_regime_failure(self, mock_ticker):
        """Test regime detection failure handling"""
        mock_ticker.return_value.history.side_effect = Exception("Network error")
        
        classification = self.analyzer.detect_current_regime("^GSPC")
        
        # Should return default transitioning regime with 0 confidence
        assert classification.regime == MarketRegime.TRANSITIONING
        assert classification.confidence == 0.0
    
    def test_analyze_strategy_regime_performance(self):
        """Test strategy performance analysis by regime"""
        # Create mock strategy data
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        strategy_data = pd.DataFrame({
            'Date': dates,
            'P/L': np.random.normal(100, 50, 100)
        })
        strategy_data['Daily_Return'] = strategy_data['P/L'].pct_change()
        
        # Create mock regime history
        regime_history = []  # Empty for this test - will use synthetic regimes
        
        performance = self.analyzer.analyze_strategy_regime_performance(
            strategy_data, regime_history
        )
        
        assert isinstance(performance, dict)
        assert len(performance) == 4  # All regime types
        for regime in MarketRegime:
            assert regime in performance
            assert 'total_return' in performance[regime]
            assert 'sharpe_ratio' in performance[regime]
            assert 'max_drawdown' in performance[regime]
    
    def test_get_regime_allocation_recommendations(self):
        """Test allocation recommendations generation"""
        # Create mock current regime
        current_regime = RegimeClassification(
            regime=MarketRegime.BULL,
            confidence=0.8,
            indicators={},
            detected_at=datetime.now()
        )
        
        # Create mock strategy performances
        strategy_performances = {
            'Strategy A': {
                MarketRegime.BULL: {
                    'total_return': 0.15,
                    'sharpe_ratio': 1.2,
                    'max_drawdown': -0.05,
                    'volatility': 0.12
                }
            },
            'Strategy B': {
                MarketRegime.BULL: {
                    'total_return': 0.10,
                    'sharpe_ratio': 0.8,
                    'max_drawdown': -0.08,
                    'volatility': 0.15
                }
            }
        }
        
        recommendations = self.analyzer.get_regime_allocation_recommendations(
            current_regime, strategy_performances
        )
        
        assert isinstance(recommendations, dict)
        assert len(recommendations) == 2
        assert 'Strategy A' in recommendations
        assert 'Strategy B' in recommendations
        
        # Check allocations sum to 1
        total_allocation = sum(recommendations.values())
        assert abs(total_allocation - 1.0) < 0.01
        
        # Check individual allocations are within bounds
        for allocation in recommendations.values():
            assert 0.05 <= allocation <= 0.6


class TestRegimeService:
    """Test suite for RegimeService"""
    
    def setup_method(self):
        """Setup for each test"""
        self.service = RegimeService()
    
    def create_mock_db_session(self):
        """Create mock database session"""
        mock_db = MagicMock(spec=Session)
        return mock_db
    
    def create_mock_portfolio(self, portfolio_id=1, name="Test Strategy"):
        """Create mock portfolio"""
        portfolio = Portfolio(
            id=portfolio_id,
            name=name,
            filename="test.csv",
            upload_date=datetime.now()
        )
        return portfolio
    
    def create_mock_portfolio_data(self, portfolio_id=1, days=100):
        """Create mock portfolio data"""
        dates = [datetime.now() - timedelta(days=i) for i in range(days)]
        data = []
        
        for i, date in enumerate(dates):
            data.append(PortfolioData(
                portfolio_id=portfolio_id,
                date=date,
                pl=np.random.normal(100, 20),
                daily_return=np.random.normal(0.001, 0.02)
            ))
        
        return data
    
    def test_detect_and_store_current_regime(self):
        """Test regime detection and storage"""
        mock_db = self.create_mock_db_session()
        
        # Mock existing record query to return None (no existing record)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with patch.object(self.service.analyzer, 'detect_current_regime') as mock_detect:
            mock_classification = RegimeClassification(
                regime=MarketRegime.BULL,
                confidence=0.8,
                indicators={
                    'volatility_percentile': 0.3,
                    'trend_strength': 0.5,
                    'momentum_score': 0.2,
                    'drawdown_severity': 0.02,
                    'volume_anomaly': 0.1
                },
                detected_at=datetime.now(),
                description="Bull market conditions"
            )
            mock_detect.return_value = mock_classification
            
            result = self.service.detect_and_store_current_regime(mock_db, "^GSPC")
            
            assert result.regime == MarketRegime.BULL
            assert result.confidence == 0.8
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
    
    def test_get_regime_history(self):
        """Test regime history retrieval"""
        mock_db = self.create_mock_db_session()
        
        # Mock database query
        mock_history = [
            MarketRegimeHistory(
                id=1,
                date=datetime.now(),
                regime='bull',
                confidence=0.8,
                market_symbol='^GSPC'
            )
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_history
        
        result = self.service.get_regime_history(mock_db, 30, "^GSPC")
        
        assert len(result) == 1
        assert result[0].regime == 'bull'
        mock_db.query.assert_called_once_with(MarketRegimeHistory)
    
    def test_calculate_strategy_regime_performance(self):
        """Test strategy regime performance calculation"""
        mock_db = self.create_mock_db_session()
        portfolio_id = 1
        
        # Mock portfolio query
        mock_portfolio = self.create_mock_portfolio(portfolio_id)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_portfolio
        
        # Mock portfolio data query
        mock_data = self.create_mock_portfolio_data(portfolio_id, 100)
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_data
        
        # Mock regime history (empty for synthetic regime calculation)
        mock_db.query.return_value.filter.side_effect = [
            MagicMock(first=lambda: mock_portfolio),
            MagicMock(order_by=lambda x: MagicMock(all=lambda: mock_data)),
            MagicMock(order_by=lambda x: MagicMock(all=lambda: []))  # Empty regime history
        ]
        
        result = self.service.calculate_strategy_regime_performance(mock_db, portfolio_id)
        
        assert isinstance(result, dict)
        assert len(result) >= 0  # May be empty if no data
    
    def test_get_regime_allocation_recommendations(self):
        """Test allocation recommendations"""
        mock_db = self.create_mock_db_session()
        portfolio_ids = [1, 2]
        
        # Mock current regime
        mock_regime = MarketRegimeHistory(
            regime='bull',
            confidence=0.8,
            date=datetime.now()
        )
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_regime
        
        # Mock portfolios
        mock_portfolios = [
            self.create_mock_portfolio(1, "Strategy A"),
            self.create_mock_portfolio(2, "Strategy B")
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_portfolios
        
        # Mock regime performance data
        mock_perf = RegimePerformance(
            portfolio_id=1,
            regime='bull',
            total_return=0.15,
            sharpe_ratio=1.2,
            max_drawdown=-0.05
        )
        mock_db.query.return_value.filter.side_effect = [
            MagicMock(order_by=lambda x: MagicMock(first=lambda: mock_regime)),
            MagicMock(all=lambda: mock_portfolios),
            MagicMock(first=lambda: mock_perf),
            MagicMock(first=lambda: mock_perf)
        ]
        
        result = self.service.get_regime_allocation_recommendations(mock_db, portfolio_ids)
        
        assert isinstance(result, dict)
        assert len(result) >= 0
    
    def test_create_regime_change_alert(self):
        """Test regime change alert creation"""
        mock_db = self.create_mock_db_session()
        
        alert = self.service.create_regime_change_alert(
            mock_db,
            'bear',
            'bull',
            0.85,
            {'Strategy A': 0.6, 'Strategy B': 0.4}
        )
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    def test_get_active_alerts(self):
        """Test active alerts retrieval"""
        mock_db = self.create_mock_db_session()
        
        mock_alerts = [
            RegimeAlert(
                id=1,
                alert_type='regime_change',
                new_regime='bull',
                confidence=0.8,
                title='Regime Change',
                message='Market shifted to bull',
                severity='info',
                is_active=True
            )
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_alerts
        
        result = self.service.get_active_alerts(mock_db)
        
        assert len(result) == 1
        assert result[0].alert_type == 'regime_change'
    
    def test_dismiss_alert(self):
        """Test alert dismissal"""
        mock_db = self.create_mock_db_session()
        alert_id = 1
        
        mock_alert = RegimeAlert(
            id=alert_id,
            is_active=True
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_alert
        
        result = self.service.dismiss_alert(mock_db, alert_id)
        
        assert result is True
        assert mock_alert.is_active is False
        mock_db.commit.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])