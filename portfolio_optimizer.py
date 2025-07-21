"""
Portfolio weight optimization module for maximizing return/drawdown ratio
"""
import numpy as np
import pandas as pd
import logging
from typing import List, Tuple, Dict, Any, Optional
from scipy.optimize import minimize, differential_evolution
from dataclasses import dataclass
import warnings

from portfolio_blender import create_blended_portfolio
from portfolio_service import PortfolioService

logger = logging.getLogger(__name__)

@dataclass
class OptimizationResult:
    """Container for optimization results"""
    optimal_weights: List[float]
    optimal_cagr: float
    optimal_max_drawdown: float
    optimal_return_drawdown_ratio: float
    optimal_sharpe_ratio: float
    optimization_method: str
    iterations: int
    success: bool
    message: str
    explored_combinations: List[Dict[str, Any]]

@dataclass
class OptimizationObjective:
    """Configuration for optimization objectives"""
    return_weight: float = 0.6  # Weight for return in objective function
    drawdown_weight: float = 0.4  # Weight for drawdown penalty in objective function
    min_weight: float = 0.05  # Minimum weight per portfolio
    max_weight: float = 0.60  # Maximum weight per portfolio
    sharpe_bonus: float = 0.1  # Bonus multiplier for high Sharpe ratios

class PortfolioOptimizer:
    """
    Portfolio weight optimizer that maximizes return while minimizing drawdown
    """
    
    def __init__(self, 
                 objective: OptimizationObjective = None,
                 rf_rate: float = 0.05,
                 sma_window: int = 20,
                 use_trading_filter: bool = True,
                 starting_capital: float = 100000.0):
        """
        Initialize the portfolio optimizer
        
        Args:
            objective: Optimization objective configuration
            rf_rate: Risk-free rate for calculations
            sma_window: SMA window for trading filter
            use_trading_filter: Whether to apply SMA filter
            starting_capital: Starting capital for calculations
        """
        self.objective = objective or OptimizationObjective()
        self.rf_rate = rf_rate
        self.sma_window = sma_window
        self.use_trading_filter = use_trading_filter
        self.starting_capital = starting_capital
        self.explored_combinations = []
        
    def optimize_weights_from_ids(self, 
                                  db_session, 
                                  portfolio_ids: List[int],
                                  method: str = 'differential_evolution') -> OptimizationResult:
        """
        Optimize portfolio weights using portfolio IDs from database
        
        Args:
            db_session: Database session
            portfolio_ids: List of portfolio IDs to optimize
            method: Optimization method ('scipy', 'differential_evolution', 'grid_search')
            
        Returns:
            OptimizationResult with optimal weights and metrics
        """
        logger.info(f"Starting weight optimization for portfolios: {portfolio_ids}")
        logger.info(f"Using method: {method}")
        
        # Get portfolio data from database
        portfolios_data = []
        portfolio_names = []
        
        for portfolio_id in portfolio_ids:
            portfolio = PortfolioService.get_portfolio_by_id(db_session, portfolio_id)
            if not portfolio:
                logger.warning(f"Portfolio {portfolio_id} not found")
                continue
                
            df = PortfolioService.get_portfolio_dataframe(db_session, portfolio_id)
            if df.empty:
                logger.warning(f"No data found for portfolio {portfolio_id}")
                continue
                
            portfolios_data.append((portfolio.name, df))
            portfolio_names.append(portfolio.name)
        
        if len(portfolios_data) < 2:
            return OptimizationResult(
                optimal_weights=[],
                optimal_cagr=0,
                optimal_max_drawdown=0,
                optimal_return_drawdown_ratio=0,
                optimal_sharpe_ratio=0,
                optimization_method=method,
                iterations=0,
                success=False,
                message="Need at least 2 portfolios for optimization",
                explored_combinations=[]
            )
        
        return self.optimize_weights(portfolios_data, method)
    
    def optimize_weights(self, 
                        portfolios_data: List[Tuple[str, pd.DataFrame]], 
                        method: str = 'differential_evolution') -> OptimizationResult:
        """
        Optimize portfolio weights to maximize return/drawdown ratio
        
        Args:
            portfolios_data: List of (name, dataframe) tuples
            method: Optimization method ('scipy', 'differential_evolution', 'grid_search')
            
        Returns:
            OptimizationResult with optimal weights and metrics
        """
        num_portfolios = len(portfolios_data)
        if num_portfolios < 2:
            return OptimizationResult(
                optimal_weights=[],
                optimal_cagr=0,
                optimal_max_drawdown=0,
                optimal_return_drawdown_ratio=0,
                optimal_sharpe_ratio=0,
                optimization_method=method,
                iterations=0,
                success=False,
                message="Need at least 2 portfolios for optimization",
                explored_combinations=[]
            )
        
        logger.info(f"Optimizing weights for {num_portfolios} portfolios using {method}")
        logger.info(f"Portfolio names: {[name for name, _ in portfolios_data]}")
        
        self.explored_combinations = []
        
        try:
            if method == 'scipy':
                return self._optimize_with_scipy(portfolios_data)
            elif method == 'differential_evolution':
                return self._optimize_with_differential_evolution(portfolios_data)
            elif method == 'grid_search':
                return self._optimize_with_grid_search(portfolios_data)
            else:
                raise ValueError(f"Unknown optimization method: {method}")
                
        except Exception as e:
            logger.error(f"Optimization failed: {str(e)}", exc_info=True)
            return OptimizationResult(
                optimal_weights=[1.0 / num_portfolios] * num_portfolios,  # Equal weights fallback
                optimal_cagr=0,
                optimal_max_drawdown=0,
                optimal_return_drawdown_ratio=0,
                optimal_sharpe_ratio=0,
                optimization_method=method,
                iterations=0,
                success=False,
                message=f"Optimization failed: {str(e)}",
                explored_combinations=self.explored_combinations
            )
    
    def _objective_function(self, weights: np.ndarray, portfolios_data: List[Tuple[str, pd.DataFrame]]) -> float:
        """
        Objective function to minimize (negative return-to-drawdown ratio)
        
        Args:
            weights: Portfolio weights array
            portfolios_data: Portfolio data
            
        Returns:
            Negative of the objective value (for minimization)
        """
        try:
            # Ensure weights sum to 1
            weights = weights / np.sum(weights)
            
            # Create blended portfolio with these weights
            blended_df, blended_metrics, _ = create_blended_portfolio(
                portfolios_data,
                rf_rate=self.rf_rate,
                sma_window=self.sma_window,
                use_trading_filter=self.use_trading_filter,
                starting_capital=self.starting_capital,
                weights=weights.tolist()
            )
            
            if blended_df is None or blended_metrics is None:
                logger.warning("Failed to create blended portfolio, returning high penalty")
                return 1000  # High penalty for failed combinations
            
            # Extract key metrics
            cagr = blended_metrics.get('cagr', 0)
            max_drawdown_pct = blended_metrics.get('max_drawdown_percent', 0.01)  # Avoid division by zero
            sharpe_ratio = blended_metrics.get('sharpe_ratio', 0)
            
            # Ensure max_drawdown is positive for the ratio calculation
            max_drawdown_pct = max(abs(max_drawdown_pct), 0.001)  # Minimum 0.1% drawdown
            
            # Calculate return-to-drawdown ratio
            return_drawdown_ratio = abs(cagr) / max_drawdown_pct
            
            # Apply objective function with weights
            # Higher return is better (positive contribution)
            # Lower drawdown is better (positive contribution when inverted)
            # Higher Sharpe is better (bonus)
            objective_value = (
                self.objective.return_weight * abs(cagr) +
                self.objective.drawdown_weight * (1.0 / max_drawdown_pct) +
                self.objective.sharpe_bonus * max(sharpe_ratio, 0)
            )
            
            # Store this combination for analysis
            combination = {
                'weights': weights.tolist(),
                'cagr': float(cagr),
                'max_drawdown_pct': float(max_drawdown_pct),
                'return_drawdown_ratio': float(return_drawdown_ratio),
                'sharpe_ratio': float(sharpe_ratio),
                'objective_value': float(objective_value)
            }
            self.explored_combinations.append(combination)
            
            # Return negative value for minimization (we want to maximize the objective)
            return -objective_value
            
        except Exception as e:
            logger.warning(f"Error in objective function with weights {weights}: {str(e)}")
            return 1000  # High penalty for error cases
    
    def _optimize_with_scipy(self, portfolios_data: List[Tuple[str, pd.DataFrame]]) -> OptimizationResult:
        """Optimize using scipy's minimize function"""
        num_portfolios = len(portfolios_data)
        
        # Initial guess: equal weights
        initial_weights = np.array([1.0 / num_portfolios] * num_portfolios)
        
        # Constraints: weights sum to 1
        constraints = {'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0}
        
        # Bounds: each weight between min_weight and max_weight
        bounds = [(self.objective.min_weight, self.objective.max_weight) for _ in range(num_portfolios)]
        
        logger.info("Starting scipy optimization...")
        
        # Suppress scipy warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            
            result = minimize(
                fun=self._objective_function,
                x0=initial_weights,
                args=(portfolios_data,),
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 100, 'ftol': 1e-6}
            )
        
        if result.success:
            optimal_weights = result.x / np.sum(result.x)  # Normalize
            return self._create_result_from_weights(optimal_weights, portfolios_data, 'scipy', result.nit, True, "Optimization successful")
        else:
            logger.warning(f"Scipy optimization failed: {result.message}")
            return self._create_result_from_weights(initial_weights, portfolios_data, 'scipy', result.nit, False, result.message)
    
    def _optimize_with_differential_evolution(self, portfolios_data: List[Tuple[str, pd.DataFrame]]) -> OptimizationResult:
        """Optimize using differential evolution (global optimizer)"""
        num_portfolios = len(portfolios_data)
        
        # Bounds for each weight
        bounds = [(self.objective.min_weight, self.objective.max_weight) for _ in range(num_portfolios)]
        
        logger.info("Starting differential evolution optimization...")
        
        def constrained_objective(weights):
            # Normalize weights to sum to 1
            normalized_weights = weights / np.sum(weights)
            return self._objective_function(normalized_weights, portfolios_data)
        
        # Suppress warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            
            result = differential_evolution(
                func=constrained_objective,
                bounds=bounds,
                maxiter=50,  # Reduced for performance
                popsize=10,
                seed=42,
                polish=True,
                atol=1e-4
            )
        
        if result.success:
            optimal_weights = result.x / np.sum(result.x)  # Normalize
            return self._create_result_from_weights(optimal_weights, portfolios_data, 'differential_evolution', result.nit, True, "Optimization successful")
        else:
            logger.warning(f"Differential evolution failed: {result.message}")
            equal_weights = np.array([1.0 / num_portfolios] * num_portfolios)
            return self._create_result_from_weights(equal_weights, portfolios_data, 'differential_evolution', result.nit, False, result.message)
    
    def _optimize_with_grid_search(self, portfolios_data: List[Tuple[str, pd.DataFrame]]) -> OptimizationResult:
        """Optimize using grid search (thorough but slower)"""
        num_portfolios = len(portfolios_data)
        
        logger.info(f"Starting grid search optimization for {num_portfolios} portfolios...")
        
        best_objective = float('inf')
        best_weights = None
        iterations = 0
        
        # Generate weight combinations
        if num_portfolios == 2:
            # For 2 portfolios, search in 5% increments
            weight_options = np.arange(self.objective.min_weight, self.objective.max_weight + 0.05, 0.05)
            
            for w1 in weight_options:
                w2 = 1.0 - w1
                if self.objective.min_weight <= w2 <= self.objective.max_weight:
                    weights = np.array([w1, w2])
                    objective_value = self._objective_function(weights, portfolios_data)
                    iterations += 1
                    
                    if objective_value < best_objective:
                        best_objective = objective_value
                        best_weights = weights
                        
        elif num_portfolios == 3:
            # For 3 portfolios, search in 10% increments
            weight_options = np.arange(self.objective.min_weight, self.objective.max_weight + 0.1, 0.1)
            
            for w1 in weight_options:
                for w2 in weight_options:
                    w3 = 1.0 - w1 - w2
                    if self.objective.min_weight <= w3 <= self.objective.max_weight:
                        weights = np.array([w1, w2, w3])
                        objective_value = self._objective_function(weights, portfolios_data)
                        iterations += 1
                        
                        if objective_value < best_objective:
                            best_objective = objective_value
                            best_weights = weights
        else:
            # For more portfolios, use random sampling
            np.random.seed(42)
            max_samples = 200
            
            for _ in range(max_samples):
                # Generate random weights
                weights = np.random.dirichlet(np.ones(num_portfolios))
                
                # Ensure constraints
                if np.all(weights >= self.objective.min_weight) and np.all(weights <= self.objective.max_weight):
                    objective_value = self._objective_function(weights, portfolios_data)
                    iterations += 1
                    
                    if objective_value < best_objective:
                        best_objective = objective_value
                        best_weights = weights
        
        if best_weights is not None:
            return self._create_result_from_weights(best_weights, portfolios_data, 'grid_search', iterations, True, "Grid search completed")
        else:
            equal_weights = np.array([1.0 / num_portfolios] * num_portfolios)
            return self._create_result_from_weights(equal_weights, portfolios_data, 'grid_search', iterations, False, "No valid weights found in grid search")
    
    def _create_result_from_weights(self, 
                                   weights: np.ndarray, 
                                   portfolios_data: List[Tuple[str, pd.DataFrame]], 
                                   method: str, 
                                   iterations: int, 
                                   success: bool, 
                                   message: str) -> OptimizationResult:
        """Create OptimizationResult from optimal weights"""
        try:
            # Calculate final metrics with optimal weights
            blended_df, blended_metrics, _ = create_blended_portfolio(
                portfolios_data,
                rf_rate=self.rf_rate,
                sma_window=self.sma_window,
                use_trading_filter=self.use_trading_filter,
                starting_capital=self.starting_capital,
                weights=weights.tolist()
            )
            
            if blended_metrics is not None:
                return OptimizationResult(
                    optimal_weights=weights.tolist(),
                    optimal_cagr=float(blended_metrics.get('cagr', 0)),
                    optimal_max_drawdown=float(blended_metrics.get('max_drawdown_percent', 0)),
                    optimal_return_drawdown_ratio=float(abs(blended_metrics.get('cagr', 0)) / max(abs(blended_metrics.get('max_drawdown_percent', 0.001)), 0.001)),
                    optimal_sharpe_ratio=float(blended_metrics.get('sharpe_ratio', 0)),
                    optimization_method=method,
                    iterations=iterations,
                    success=success,
                    message=message,
                    explored_combinations=self.explored_combinations
                )
        except Exception as e:
            logger.error(f"Error creating result: {str(e)}")
        
        # Fallback result
        return OptimizationResult(
            optimal_weights=weights.tolist(),
            optimal_cagr=0,
            optimal_max_drawdown=0,
            optimal_return_drawdown_ratio=0,
            optimal_sharpe_ratio=0,
            optimization_method=method,
            iterations=iterations,
            success=False,
            message=f"Error calculating final metrics: {message}",
            explored_combinations=self.explored_combinations
        )


def suggest_optimal_weights(portfolios_data: List[Tuple[str, pd.DataFrame]], 
                          method: str = 'differential_evolution',
                          rf_rate: float = 0.05) -> Dict[str, Any]:
    """
    Convenience function to suggest optimal portfolio weights
    
    Args:
        portfolios_data: List of (name, dataframe) tuples
        method: Optimization method
        rf_rate: Risk-free rate
        
    Returns:
        Dictionary with optimization results and suggested weights
    """
    optimizer = PortfolioOptimizer(rf_rate=rf_rate)
    result = optimizer.optimize_weights(portfolios_data, method)
    
    portfolio_names = [name for name, _ in portfolios_data]
    
    return {
        'success': result.success,
        'message': result.message,
        'optimal_weights': dict(zip(portfolio_names, result.optimal_weights)),
        'metrics': {
            'cagr': result.optimal_cagr,
            'max_drawdown_percent': result.optimal_max_drawdown,
            'return_drawdown_ratio': result.optimal_return_drawdown_ratio,
            'sharpe_ratio': result.optimal_sharpe_ratio
        },
        'optimization_method': result.optimization_method,
        'iterations': result.iterations,
        'explored_combinations': len(result.explored_combinations)
    }