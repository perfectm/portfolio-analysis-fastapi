"""
Profit-based portfolio optimization module for achieving target annual profit while minimizing drawdown
"""
import numpy as np
import pandas as pd
import logging
from typing import List, Tuple, Dict, Any, Optional
from scipy.optimize import minimize, differential_evolution
from dataclasses import dataclass
import warnings
import time
from sqlalchemy.orm import Session

from portfolio_blender import create_blended_portfolio_from_files
from portfolio_service import PortfolioService

logger = logging.getLogger(__name__)

@dataclass
class ProfitOptimizationResult:
    """Result of profit-based portfolio optimization"""
    success: bool
    message: str
    optimal_weights: List[float]
    optimal_ratios: List[float]
    target_annual_profit: float
    achieved_annual_profit: float
    metrics: Dict[str, float]
    portfolio_names: List[str]
    portfolio_ids: List[int]
    optimization_method: str
    iterations: int
    execution_time_seconds: float

class ProfitOptimizationObjective:
    """
    Optimization objective for profit-based portfolio optimization.
    Two-stage approach: First achieve target profit, then minimize drawdown above all else.
    """

    def __init__(self, target_annual_profit: float = 100000.0, profit_tolerance: float = 0.05):
        self.target_annual_profit = target_annual_profit
        self.profit_tolerance = profit_tolerance  # Allow 5% deviation from target (e.g., 95K-105K for 100K target)
        
    def calculate_objective(self, weights: np.ndarray, portfolios_data: List[Tuple[str, pd.DataFrame]],
                          rf_rate: float, sma_window: int, use_trading_filter: bool,
                          starting_capital: float) -> float:
        """
        Calculate objective function value for given weights.
        Two-stage optimization: First achieve target profit, then minimize drawdown.
        Lower values are better (minimization problem).
        """
        try:
            # Normalize weights
            weights = weights / np.sum(weights)

            # Create blended portfolio
            blended_df, blended_metrics, _ = create_blended_portfolio_from_files(
                files_data=portfolios_data,
                rf_rate=rf_rate,
                sma_window=sma_window,
                use_trading_filter=use_trading_filter,
                starting_capital=starting_capital,
                weights=weights.tolist()
            )

            if blended_df is None or blended_metrics is None:
                return 1e10  # Large penalty for invalid combinations

            # Extract key metrics
            cagr = blended_metrics.get('cagr', 0.0)
            max_drawdown_percent = abs(blended_metrics.get('max_drawdown_percent', 1.0))
            final_account_value = blended_metrics.get('final_account_value', starting_capital)

            # Calculate annual profit achieved
            annual_profit = final_account_value - starting_capital
            if blended_metrics.get('time_period_years', 1.0) > 0:
                annual_profit = annual_profit / blended_metrics.get('time_period_years', 1.0)

            # Calculate profit achievement ratio
            target_min = self.target_annual_profit * (1 - self.profit_tolerance)
            target_max = self.target_annual_profit * (1 + self.profit_tolerance)

            # Stage 1: Check if target profit is achieved within tolerance
            profit_achieved = target_min <= annual_profit <= target_max

            if profit_achieved:
                # Stage 2: Target achieved - focus entirely on minimizing drawdown
                # Return drawdown directly as the objective (lower is better)
                objective_value = max_drawdown_percent

                # Small bonus for being closer to target within tolerance range
                target_closeness_bonus = abs(annual_profit - self.target_annual_profit) / max(self.target_annual_profit, 1000) * 0.01
                objective_value += target_closeness_bonus

                logger.debug(f"[PROFIT OPT] STAGE 2 - Target achieved! Minimizing drawdown. "
                            f"Annual Profit: ${annual_profit:,.0f} (target: ${self.target_annual_profit:,.0f}), "
                            f"Drawdown: {max_drawdown_percent:.3f}, Objective: {objective_value:.6f}")

            else:
                # Stage 1: Target not achieved - heavily penalize profit gap
                if annual_profit < target_min:
                    # Below target - large penalty proportional to shortfall
                    profit_shortfall = (target_min - annual_profit) / max(self.target_annual_profit, 1000)
                    objective_value = 100 + profit_shortfall * 50  # Heavy penalty for missing target
                else:
                    # Above target max - moderate penalty for overshooting
                    profit_overshoot = (annual_profit - target_max) / max(self.target_annual_profit, 1000)
                    objective_value = 50 + profit_overshoot * 10  # Moderate penalty for overshooting

                # Add drawdown as secondary concern in stage 1
                objective_value += max_drawdown_percent * 0.1

                logger.debug(f"[PROFIT OPT] STAGE 1 - Target NOT achieved. "
                            f"Annual Profit: ${annual_profit:,.0f} (target: ${self.target_annual_profit:,.0f}), "
                            f"Drawdown: {max_drawdown_percent:.3f}, Objective: {objective_value:.6f}")

            # Add penalty for catastrophic performance regardless of stage
            if cagr < -0.8 or max_drawdown_percent > 0.9:  # More than 80% loss or 90% drawdown
                objective_value += 1000

            # Small penalty for extreme concentration to encourage reasonable diversification
            max_weight = np.max(weights)
            if max_weight > 0.9:  # More than 90% in single portfolio
                concentration_penalty = (max_weight - 0.9) * 20
                objective_value += concentration_penalty

            return objective_value

        except Exception as e:
            logger.warning(f"[PROFIT OPT] Error in objective calculation: {e}")
            return 1e10

class ProfitOptimizer:
    """
    Portfolio optimizer that targets specific annual profit while minimizing drawdown
    """
    
    def __init__(self, target_annual_profit: float = 100000.0,
                 rf_rate: float = 0.043, sma_window: int = 20, use_trading_filter: bool = True,
                 starting_capital: float = 1000000.0, portfolio_count: int = None,
                 min_weight: float = 0.05, max_weight: float = 0.60):
        
        self.target_annual_profit = target_annual_profit
        self.rf_rate = rf_rate
        self.sma_window = sma_window
        self.use_trading_filter = use_trading_filter
        self.starting_capital = starting_capital
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.portfolio_count = portfolio_count or 3
        
        # Calculate dynamic constraints based on portfolio count
        if portfolio_count and portfolio_count > 0:
            base_weight = 1.0 / portfolio_count
            # Allow up to 3x the base weight, but not more than max_weight
            dynamic_max = min(base_weight * 3.0, max_weight)
            self.max_weight = min(self.max_weight, dynamic_max)
        
        logger.info(f"[PROFIT OPT] Initialized with target profit: ${target_annual_profit:,.0f}")
        logger.info(f"[PROFIT OPT] Weight constraints: {self.min_weight:.3f} to {self.max_weight:.3f}")
        
        # Create objective function with two-stage approach
        self.objective = ProfitOptimizationObjective(target_annual_profit, profit_tolerance=0.05)
    
    def optimize_weights_from_ids(self, db: Session, portfolio_ids: List[int], 
                                method: str = "differential_evolution") -> ProfitOptimizationResult:
        """
        Optimize portfolio weights from database portfolio IDs
        """
        start_time = time.time()
        
        try:
            # Fetch portfolio data
            portfolios_data = []
            portfolio_names = []
            
            for portfolio_id in portfolio_ids:
                portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
                if not portfolio:
                    raise ValueError(f"Portfolio {portfolio_id} not found")
                
                df = PortfolioService.get_portfolio_dataframe(db, portfolio_id, 
                                                            columns=["Date", "P/L", "Daily_Return"])
                if df.empty:
                    raise ValueError(f"No data found for portfolio {portfolio_id}")
                
                portfolios_data.append((portfolio.name, df))
                portfolio_names.append(portfolio.name)
            
            return self._optimize_weights(portfolios_data, portfolio_names, portfolio_ids, method, start_time)
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[PROFIT OPT] Optimization failed: {e}")
            return ProfitOptimizationResult(
                success=False,
                message=f"Optimization failed: {str(e)}",
                optimal_weights=[],
                optimal_ratios=[],
                target_annual_profit=self.target_annual_profit,
                achieved_annual_profit=0.0,
                metrics={},
                portfolio_names=[],
                portfolio_ids=portfolio_ids,
                optimization_method=method,
                iterations=0,
                execution_time_seconds=execution_time
            )
    
    def _optimize_weights(self, portfolios_data: List[Tuple[str, pd.DataFrame]], 
                         portfolio_names: List[str], portfolio_ids: List[int],
                         method: str, start_time: float) -> ProfitOptimizationResult:
        """
        Internal method to perform the actual optimization
        """
        
        n_portfolios = len(portfolios_data)
        
        # Define optimization constraints
        def weight_constraint(weights):
            return np.sum(weights) - 1.0  # Weights must sum to 1
        
        # Weight bounds: min_weight to max_weight for each portfolio
        bounds = [(self.min_weight, self.max_weight) for _ in range(n_portfolios)]
        
        # Constraint: weights sum to 1
        constraints = {'type': 'eq', 'fun': weight_constraint}
        
        # Initial guess: equal weights
        initial_weights = np.array([1.0 / n_portfolios] * n_portfolios)
        
        logger.info(f"[PROFIT OPT] Starting optimization with {method}")
        logger.info(f"[PROFIT OPT] Target annual profit: ${self.target_annual_profit:,.0f}")
        
        best_result = None
        best_objective = float('inf')
        iterations = 0
        
        def objective_wrapper(weights):
            nonlocal iterations
            iterations += 1
            return self.objective.calculate_objective(
                weights, portfolios_data, self.rf_rate, self.sma_window, 
                self.use_trading_filter, self.starting_capital
            )
        
        try:
            if method == "differential_evolution":
                # Global optimization approach
                result = differential_evolution(
                    objective_wrapper,
                    bounds,
                    seed=42,
                    maxiter=50,  # Reduced for faster execution
                    popsize=15,
                    atol=1e-6,
                    tol=1e-6
                )
                
                if result.success:
                    optimal_weights = result.x / np.sum(result.x)  # Normalize
                    best_objective = result.fun
                    iterations = result.nit if hasattr(result, 'nit') else iterations
                
            elif method == "scipy_minimize":
                # Local optimization approach
                result = minimize(
                    objective_wrapper,
                    initial_weights,
                    method='SLSQP',
                    bounds=bounds,
                    constraints=constraints,
                    options={'maxiter': 100, 'ftol': 1e-6}
                )
                
                if result.success:
                    optimal_weights = result.x / np.sum(result.x)  # Normalize
                    best_objective = result.fun
                    iterations = result.nit if hasattr(result, 'nit') else iterations
            
            else:
                raise ValueError(f"Unknown optimization method: {method}")
            
            # If optimization failed, fall back to equal weights
            if best_objective == float('inf') or 'optimal_weights' not in locals():
                logger.warning(f"[PROFIT OPT] Optimization failed, using equal weights")
                optimal_weights = np.array([1.0 / n_portfolios] * n_portfolios)
            
            # Calculate final metrics with optimal weights
            blended_df, blended_metrics, _ = create_blended_portfolio_from_files(
                files_data=portfolios_data,
                rf_rate=self.rf_rate, 
                sma_window=self.sma_window, 
                use_trading_filter=self.use_trading_filter,
                starting_capital=self.starting_capital,
                weights=optimal_weights.tolist()
            )
            
            if blended_metrics is None:
                raise ValueError("Failed to calculate final metrics")
            
            # Calculate achieved annual profit
            final_account_value = blended_metrics.get('final_account_value', self.starting_capital)
            annual_profit = final_account_value - self.starting_capital
            if blended_metrics.get('time_period_years', 1.0) > 0:
                annual_profit = annual_profit / blended_metrics.get('time_period_years', 1.0)
            
            # Convert weights to ratios for display
            optimal_ratios = self._convert_weights_to_ratios(optimal_weights)
            
            execution_time = time.time() - start_time
            
            logger.info(f"[PROFIT OPT] Optimization completed in {execution_time:.1f}s")
            logger.info(f"[PROFIT OPT] Target: ${self.target_annual_profit:,.0f}, "
                       f"Achieved: ${annual_profit:,.0f}")
            logger.info(f"[PROFIT OPT] Optimal weights: {[f'{w:.3f}' for w in optimal_weights]}")
            
            return ProfitOptimizationResult(
                success=True,
                message=f"Profit optimization completed using {method}",
                optimal_weights=optimal_weights.tolist(),
                optimal_ratios=optimal_ratios,
                target_annual_profit=self.target_annual_profit,
                achieved_annual_profit=annual_profit,
                metrics={
                    'cagr': blended_metrics.get('cagr', 0.0),
                    'max_drawdown_percent': blended_metrics.get('max_drawdown_percent', 0.0),
                    'sharpe_ratio': blended_metrics.get('sharpe_ratio', 0.0),
                    'return_drawdown_ratio': blended_metrics.get('cagr', 0.0) / max(abs(blended_metrics.get('max_drawdown_percent', 0.01)), 0.01)
                },
                portfolio_names=portfolio_names,
                portfolio_ids=portfolio_ids,
                optimization_method=method,
                iterations=iterations,
                execution_time_seconds=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[PROFIT OPT] Optimization error: {e}")
            
            # Fallback to equal weights
            equal_weights = [1.0 / n_portfolios] * n_portfolios
            equal_ratios = [1.0] * n_portfolios
            
            return ProfitOptimizationResult(
                success=False,
                message=f"Optimization failed, using equal weights: {str(e)}",
                optimal_weights=equal_weights,
                optimal_ratios=equal_ratios,
                target_annual_profit=self.target_annual_profit,
                achieved_annual_profit=0.0,
                metrics={
                    'cagr': 0.0,
                    'max_drawdown_percent': 0.0,
                    'sharpe_ratio': 0.0,
                    'return_drawdown_ratio': 0.0
                },
                portfolio_names=portfolio_names,
                portfolio_ids=portfolio_ids,
                optimization_method=f"{method}_fallback",
                iterations=iterations,
                execution_time_seconds=execution_time
            )
    
    def _convert_weights_to_ratios(self, weights: np.ndarray) -> List[float]:
        """Convert decimal weights to display ratios"""
        base_weight = 1.0 / len(weights)
        ratios = weights / base_weight
        return ratios.tolist()