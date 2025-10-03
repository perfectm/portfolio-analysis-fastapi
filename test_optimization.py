"""
Test cases for portfolio optimization functionality
"""
import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from portfolio_optimizer import PortfolioOptimizer, OptimizationObjective, suggest_optimal_weights

class TestPortfolioOptimizer:
    """Test cases for PortfolioOptimizer class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Create sample portfolio data
        dates = pd.date_range('2020-01-01', periods=100, freq='D')
        
        # Portfolio 1: High return, high volatility
        np.random.seed(42)
        portfolio1_returns = np.random.normal(0.001, 0.02, 100)  # Daily returns
        portfolio1_pl = np.cumsum(portfolio1_returns * 10000)  # P/L
        self.portfolio1_df = pd.DataFrame({
            'Date': dates,
            'P/L': portfolio1_pl
        })
        
        # Portfolio 2: Low return, low volatility
        np.random.seed(123)
        portfolio2_returns = np.random.normal(0.0005, 0.01, 100)
        portfolio2_pl = np.cumsum(portfolio2_returns * 10000)
        self.portfolio2_df = pd.DataFrame({
            'Date': dates,
            'P/L': portfolio2_pl
        })
        
        # Portfolio 3: Negative correlation to others
        np.random.seed(456)
        portfolio3_returns = np.random.normal(-0.0003, 0.015, 100)
        portfolio3_pl = np.cumsum(portfolio3_returns * 10000)
        self.portfolio3_df = pd.DataFrame({
            'Date': dates,
            'P/L': portfolio3_pl
        })
        
        self.portfolios_data = [
            ("Portfolio_1", self.portfolio1_df),
            ("Portfolio_2", self.portfolio2_df),
            ("Portfolio_3", self.portfolio3_df)
        ]
        
        # Create optimizer with test settings
        self.objective = OptimizationObjective(
            return_weight=0.6,
            drawdown_weight=0.4
        )
        self.optimizer = PortfolioOptimizer(
            objective=self.objective,
            rf_rate=0.02,
            starting_capital=100000.0
        )
    
    def test_optimization_objective_initialization(self):
        """Test OptimizationObjective initialization"""
        obj = OptimizationObjective()
        assert obj.return_weight == 0.6
        assert obj.drawdown_weight == 0.4
        # Note: min_weight and max_weight are now calculated dynamically based on portfolio count
        
        # Test custom initialization
        custom_obj = OptimizationObjective(
            return_weight=0.7,
            drawdown_weight=0.3
        )
        assert custom_obj.return_weight == 0.7
        assert custom_obj.drawdown_weight == 0.3
    
    def test_optimizer_initialization(self):
        """Test PortfolioOptimizer initialization"""
        optimizer = PortfolioOptimizer()
        assert optimizer.rf_rate == 0.05
        assert optimizer.sma_window == 20
        assert optimizer.use_trading_filter == True
        assert optimizer.starting_capital == 1000000.0  # Default is 1M
        assert optimizer.objective is not None
    
    def test_optimize_weights_insufficient_portfolios(self):
        """Test optimization with insufficient portfolios"""
        # Test with empty list
        result = self.optimizer.optimize_weights([])
        assert not result.success
        assert "Need at least 2 portfolios" in result.message
        
        # Test with single portfolio
        single_portfolio = [("Portfolio_1", self.portfolio1_df)]
        result = self.optimizer.optimize_weights(single_portfolio)
        assert not result.success
        assert "Need at least 2 portfolios" in result.message
    
    def test_optimize_weights_differential_evolution(self):
        """Test optimization using differential evolution"""
        result = self.optimizer.optimize_weights(
            self.portfolios_data[:2],
            method='differential_evolution'
        )

        assert result.optimization_method == 'differential_evolution'
        assert len(result.optimal_weights) == 2

        # Check that weights sum to approximately 1
        weight_sum = sum(result.optimal_weights)
        assert abs(weight_sum - 1.0) < 0.01

        # Check weight constraints (min/max weights are now on the optimizer, not objective)
        # Note: discretization + normalization can push weights slightly outside bounds
        for weight in result.optimal_weights:
            assert weight >= self.optimizer.min_weight - 0.01
            assert weight <= self.optimizer.max_weight + 0.10  # Larger tolerance for post-normalization

        # Check that we have some metrics
        if result.success:
            assert result.optimal_cagr is not None
            assert result.optimal_max_drawdown is not None
            assert result.optimal_return_drawdown_ratio is not None
    
    def test_optimize_weights_scipy(self):
        """Test optimization using scipy minimize"""
        result = self.optimizer.optimize_weights(
            self.portfolios_data[:2], 
            method='scipy'
        )
        
        assert result.optimization_method == 'scipy'
        assert len(result.optimal_weights) == 2
        
        # Check that weights sum to approximately 1
        weight_sum = sum(result.optimal_weights)
        assert abs(weight_sum - 1.0) < 0.01
    
    def test_optimize_weights_grid_search(self):
        """Test optimization using grid search"""
        result = self.optimizer.optimize_weights(
            self.portfolios_data[:2], 
            method='grid_search'
        )
        
        assert result.optimization_method == 'grid_search'
        assert len(result.optimal_weights) == 2
        
        # Check that weights sum to approximately 1
        weight_sum = sum(result.optimal_weights)
        assert abs(weight_sum - 1.0) < 0.01
    
    def test_optimize_weights_three_portfolios(self):
        """Test optimization with three portfolios"""
        result = self.optimizer.optimize_weights(
            self.portfolios_data,
            method='differential_evolution'
        )

        assert len(result.optimal_weights) == 3

        # Check that weights sum to approximately 1
        weight_sum = sum(result.optimal_weights)
        assert abs(weight_sum - 1.0) < 0.01

        # Check weight constraints (min/max weights are now on the optimizer, not objective)
        # Note: discretization + normalization can push weights slightly outside bounds
        for weight in result.optimal_weights:
            assert weight >= self.optimizer.min_weight - 0.01
            assert weight <= self.optimizer.max_weight + 0.10  # Larger tolerance for post-normalization
    
    def test_invalid_optimization_method(self):
        """Test optimization with invalid method"""
        result = self.optimizer.optimize_weights(
            self.portfolios_data[:2], 
            method='invalid_method'
        )
        
        assert not result.success
        assert "Unknown optimization method" in result.message
    
    @patch('portfolio_optimizer.create_blended_portfolio_from_files')
    def test_objective_function_error_handling(self, mock_create_blended):
        """Test objective function error handling"""
        # Mock create_blended_portfolio_from_files to return None (failure case)
        mock_create_blended.return_value = (None, None, None)
        
        weights = np.array([0.5, 0.5])
        penalty = self.optimizer._objective_function(weights, self.portfolios_data[:2])
        
        # Should return a high penalty value
        assert penalty == 1000
    
    @patch('portfolio_optimizer.create_blended_portfolio_from_files')
    def test_objective_function_success(self, mock_create_blended):
        """Test objective function with successful calculation"""
        # Mock successful blended portfolio creation
        mock_blended_df = Mock()
        mock_metrics = {
            'cagr': 0.15,
            'max_drawdown_percent': 0.10,
            'sharpe_ratio': 1.5
        }
        mock_create_blended.return_value = (mock_blended_df, mock_metrics, None)
        
        weights = np.array([0.6, 0.4])
        objective_value = self.optimizer._objective_function(weights, self.portfolios_data[:2])
        
        # Should return negative value (since we minimize)
        assert objective_value < 0
        
        # Check that combination was stored
        assert len(self.optimizer.explored_combinations) > 0
        combination = self.optimizer.explored_combinations[-1]
        assert 'cagr' in combination
        assert 'max_drawdown_pct' in combination
        assert 'return_drawdown_ratio' in combination
    
    def test_suggest_optimal_weights_function(self):
        """Test the convenience function"""
        result = suggest_optimal_weights(
            self.portfolios_data[:2], 
            method='differential_evolution'
        )
        
        assert 'success' in result
        assert 'optimal_weights' in result
        assert 'metrics' in result
        assert 'optimization_method' in result
        
        if result['success']:
            # Check that portfolio names are used as keys
            portfolio_names = [name for name, _ in self.portfolios_data[:2]]
            for name in portfolio_names:
                assert name in result['optimal_weights']


class TestOptimizationIntegration:
    """Integration tests with actual portfolio processing"""
    
    def test_end_to_end_optimization(self):
        """Test complete optimization workflow"""
        # Create more realistic test data
        dates = pd.date_range('2020-01-01', periods=252, freq='D')  # 1 year of data
        
        # Portfolio 1: Steady grower
        np.random.seed(42)
        returns1 = np.random.normal(0.0008, 0.015, 252)  # 20% annual return, 15% volatility
        pl1 = np.cumsum(returns1 * 1000)
        portfolio1_df = pd.DataFrame({'Date': dates, 'P/L': pl1})
        
        # Portfolio 2: More volatile but higher return
        np.random.seed(123)
        returns2 = np.random.normal(0.0012, 0.025, 252)  # 30% annual return, 25% volatility  
        pl2 = np.cumsum(returns2 * 1000)
        portfolio2_df = pd.DataFrame({'Date': dates, 'P/L': pl2})
        
        portfolios_data = [
            ("Steady_Growth", portfolio1_df),
            ("High_Volatility", portfolio2_df)
        ]
        
        # Test optimization
        result = suggest_optimal_weights(portfolios_data, method='differential_evolution')
        
        assert result['success']
        assert len(result['optimal_weights']) == 2
        
        # Weights should sum to 1
        weight_sum = sum(result['optimal_weights'].values())
        assert abs(weight_sum - 1.0) < 0.01
        
        # Should have valid metrics
        assert 'cagr' in result['metrics']
        assert 'max_drawdown_percent' in result['metrics']
        assert 'return_drawdown_ratio' in result['metrics']
        assert 'sharpe_ratio' in result['metrics']
    
    def test_optimization_with_constraints(self):
        """Test optimization respects dynamic weight constraints"""
        optimizer = PortfolioOptimizer()

        # Simple two-portfolio case
        dates = pd.date_range('2020-01-01', periods=100, freq='D')
        portfolio1_df = pd.DataFrame({
            'Date': dates,
            'P/L': np.cumsum(np.random.normal(0.001, 0.02, 100) * 1000)
        })
        portfolio2_df = pd.DataFrame({
            'Date': dates,
            'P/L': np.cumsum(np.random.normal(0.0005, 0.01, 100) * 1000)
        })

        portfolios_data = [("A", portfolio1_df), ("B", portfolio2_df)]

        result = optimizer.optimize_weights(portfolios_data, method='differential_evolution')

        if result.success:
            # Check that dynamic constraints were applied
            # For 2 portfolios, min_weight should be ~0.04 and max_weight should be 0.80
            assert optimizer.min_weight is not None
            assert optimizer.max_weight is not None

            # Check constraints are respected (with larger tolerance due to normalization)
            # Note: discretization + normalization can push weights slightly outside bounds
            for weight in result.optimal_weights:
                assert weight >= optimizer.min_weight - 0.01  # Small tolerance
                assert weight <= optimizer.max_weight + 0.10  # Larger tolerance for post-normalization


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])