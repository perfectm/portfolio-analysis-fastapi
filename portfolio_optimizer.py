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
from fractions import Fraction
import math
import json
import hashlib
import time
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from portfolio_blender import create_blended_portfolio_from_files
from portfolio_service import PortfolioService

logger = logging.getLogger(__name__)

def generate_portfolio_hash(portfolio_ids: List[int]) -> str:
    """Generate a hash for a sorted list of portfolio IDs"""
    sorted_ids = sorted(portfolio_ids)
    ids_str = ",".join(map(str, sorted_ids))
    return hashlib.sha256(ids_str.encode()).hexdigest()

def generate_params_key(rf_rate: float, sma_window: int, use_trading_filter: bool, 
                       starting_capital: float, min_weight: float, max_weight: float) -> str:
    """Generate a parameter key for cache lookup"""
    params = f"{rf_rate:.6f}_{sma_window}_{use_trading_filter}_{starting_capital:.2f}_{min_weight:.3f}_{max_weight:.3f}"
    return params

def convert_weights_to_ratios(weights: List[float], min_units: int = 1, max_ratio: int = 10) -> List[int]:
    """
    Convert decimal weights to whole number ratios with minimum allocation.
    
    Args:
        weights: List of decimal weights (e.g., [0.12, 0.07, 0.73, 0.07])
        min_units: Minimum units per strategy (default: 1)
        
    Returns:
        List of whole number ratios (e.g., [1, 1, 7, 1])
        
    Examples:
        [0.12, 0.07, 0.73, 0.07] -> [1, 1, 7, 1]
        [0.25, 0.50, 0.25] -> [1, 2, 1]
        [0.10, 0.30, 0.60] -> [1, 3, 6]
    """
    if not weights or len(weights) == 0:
        return []
    
    # Convert to numpy array for easier manipulation
    weights_array = np.array(weights)
    
    # Method 1: Scale relative to smallest weight and round
    min_weight = np.min(weights_array[weights_array > 0])
    scaled_weights = weights_array / min_weight
    basic_ratios = np.maximum(np.round(scaled_weights), min_units).astype(int)
    
    # Method 2: Try multiple scaling factors to find the best simple ratio
    best_ratios = basic_ratios
    best_max = max(basic_ratios)
    
    # Try scaling factors that might give simpler ratios
    for scale_factor in [100, 1000, 10]:
        try:
            # Scale up and find GCD
            scaled = (weights_array * scale_factor).astype(int)
            if np.all(scaled > 0):  # Ensure no zeros
                # Find GCD of all values
                ratio_gcd = scaled[0]
                for val in scaled[1:]:
                    ratio_gcd = math.gcd(ratio_gcd, val)
                
                if ratio_gcd > 0:
                    candidate_ratios = np.maximum(scaled // ratio_gcd, min_units)
                    candidate_max = max(candidate_ratios)
                    
                    # Prefer ratios with smaller maximum values (simpler)
                    if candidate_max < best_max:
                        best_ratios = candidate_ratios
                        best_max = candidate_max
        except:
            continue
    
    # Method 3: Try fraction-based approach for very precise results
    try:
        fractions = [Fraction(w).limit_denominator(1000) for w in weights]
        denominators = [f.denominator for f in fractions if f.denominator > 0]
        
        if denominators:
            # Find LCM of denominators
            lcm = denominators[0]
            for d in denominators[1:]:
                lcm = lcm * d // math.gcd(lcm, d)
            
            # Convert to integers and simplify
            fraction_ratios = [int(f * lcm) for f in fractions]
            if all(r > 0 for r in fraction_ratios):  # Ensure no zeros
                ratio_gcd = fraction_ratios[0]
                for r in fraction_ratios[1:]:
                    ratio_gcd = math.gcd(ratio_gcd, r)
                
                if ratio_gcd > 0:
                    simplified_ratios = np.maximum(
                        np.array(fraction_ratios) // ratio_gcd, min_units
                    )
                    candidate_max = max(simplified_ratios)
                    
                    if candidate_max < best_max:
                        best_ratios = simplified_ratios
    except:
        pass
    
    # If ratios are still too large, try to simplify further by allowing some approximation
    if max(best_ratios) >= max_ratio:
        # Try a more aggressive approach - cap the maximum ratio
        capped_ratios = best_ratios.copy()
        if isinstance(capped_ratios, np.ndarray):
            capped_ratios = capped_ratios.astype(float)
        else:
            capped_ratios = np.array(capped_ratios, dtype=float)
            
        while max(capped_ratios) >= max_ratio and max(capped_ratios) > min_units:
            # Find the largest ratio and reduce proportionally
            reduction_factor = (max_ratio - 1) / max(capped_ratios)
            capped_ratios = np.maximum(
                np.round(capped_ratios * reduction_factor), min_units
            ).astype(int)
        
        # Use capped version if it's simpler (lower maximum)
        if max(capped_ratios) < max(best_ratios):
            best_ratios = capped_ratios
    
    return best_ratios.tolist() if isinstance(best_ratios, np.ndarray) else best_ratios

@dataclass
class OptimizationResult:
    """Container for optimization results"""
    optimal_weights: List[float]
    optimal_ratios: List[int]  # Whole number ratios for trading units
    optimal_cagr: float
    optimal_max_drawdown: float
    optimal_return_drawdown_ratio: float
    optimal_sharpe_ratio: float
    optimization_method: str
    iterations: int
    success: bool
    message: str
    explored_combinations: List[Dict[str, Any]]

class OptimizationCache:
    """Helper class for optimization cache operations"""
    
    @staticmethod
    def lookup_cache(db_session: Session, portfolio_ids: List[int], 
                    rf_rate: float, sma_window: int, use_trading_filter: bool,
                    starting_capital: float, min_weight: float, max_weight: float) -> Optional[Dict]:
        """Look up optimization results in cache"""
        from models import OptimizationCache as CacheModel
        
        portfolio_hash = generate_portfolio_hash(portfolio_ids)
        
        cache_entry = db_session.query(CacheModel).filter(
            and_(
                CacheModel.portfolio_ids_hash == portfolio_hash,
                CacheModel.rf_rate == rf_rate,
                CacheModel.sma_window == sma_window,
                CacheModel.use_trading_filter == use_trading_filter,
                CacheModel.starting_capital == starting_capital,
                CacheModel.min_weight == min_weight,
                CacheModel.max_weight == max_weight
            )
        ).first()
        
        if cache_entry:
            # Update access tracking
            cache_entry.last_accessed_at = pd.Timestamp.now()
            cache_entry.access_count += 1
            db_session.commit()
            
            return {
                'optimal_weights': json.loads(cache_entry.optimal_weights),
                'optimal_ratios': json.loads(cache_entry.optimal_ratios),
                'optimal_cagr': cache_entry.optimal_cagr,
                'optimal_max_drawdown': cache_entry.optimal_max_drawdown,
                'optimal_return_drawdown_ratio': cache_entry.optimal_return_drawdown_ratio,
                'optimal_sharpe_ratio': cache_entry.optimal_sharpe_ratio,
                'optimization_method': cache_entry.optimization_method,
                'iterations': cache_entry.iterations,
                'success': cache_entry.success,
                'execution_time_seconds': cache_entry.execution_time_seconds,
                'explored_combinations_count': cache_entry.explored_combinations_count
            }
        
        return None
    
    @staticmethod
    def store_cache(db_session: Session, portfolio_ids: List[int], 
                   result: 'OptimizationResult', execution_time: float,
                   rf_rate: float, sma_window: int, use_trading_filter: bool,
                   starting_capital: float, min_weight: float, max_weight: float) -> None:
        """Store optimization results in cache"""
        from models import OptimizationCache as CacheModel
        
        portfolio_hash = generate_portfolio_hash(portfolio_ids)
        sorted_ids = sorted(portfolio_ids)
        
        cache_entry = CacheModel(
            portfolio_ids_hash=portfolio_hash,
            portfolio_ids=",".join(map(str, sorted_ids)),
            portfolio_count=len(portfolio_ids),
            rf_rate=rf_rate,
            sma_window=sma_window,
            use_trading_filter=use_trading_filter,
            starting_capital=starting_capital,
            min_weight=min_weight,
            max_weight=max_weight,
            optimization_method=result.optimization_method,
            optimal_weights=json.dumps(result.optimal_weights),
            optimal_ratios=json.dumps(result.optimal_ratios),
            iterations=result.iterations,
            success=result.success,
            optimal_cagr=result.optimal_cagr,
            optimal_max_drawdown=result.optimal_max_drawdown,
            optimal_return_drawdown_ratio=result.optimal_return_drawdown_ratio,
            optimal_sharpe_ratio=result.optimal_sharpe_ratio,
            execution_time_seconds=execution_time,
            explored_combinations_count=len(result.explored_combinations)
        )
        
        db_session.add(cache_entry)
        db_session.commit()
    
    @staticmethod
    def find_subset_caches(db_session: Session, portfolio_ids: List[int],
                          rf_rate: float, sma_window: int, use_trading_filter: bool,
                          starting_capital: float, min_weight: float, max_weight: float) -> List[Dict]:
        """Find cached optimization results for subsets of the given portfolios"""
        from models import OptimizationCache as CacheModel
        
        sorted_ids = sorted(portfolio_ids)
        subset_caches = []
        
        # Look for cached results with fewer portfolios that are subsets of our portfolio list
        cache_entries = db_session.query(CacheModel).filter(
            and_(
                CacheModel.portfolio_count < len(portfolio_ids),
                CacheModel.rf_rate == rf_rate,
                CacheModel.sma_window == sma_window,
                CacheModel.use_trading_filter == use_trading_filter,
                CacheModel.starting_capital == starting_capital,
                CacheModel.min_weight == min_weight,
                CacheModel.max_weight == max_weight,
                CacheModel.success == True
            )
        ).all()
        
        for entry in cache_entries:
            entry_ids = set(map(int, entry.portfolio_ids.split(',')))
            if entry_ids.issubset(set(sorted_ids)):
                subset_caches.append({
                    'portfolio_ids': list(entry_ids),
                    'optimal_weights': json.loads(entry.optimal_weights),
                    'optimal_ratios': json.loads(entry.optimal_ratios),
                    'metrics': {
                        'cagr': entry.optimal_cagr,
                        'max_drawdown': entry.optimal_max_drawdown,
                        'return_drawdown_ratio': entry.optimal_return_drawdown_ratio,
                        'sharpe_ratio': entry.optimal_sharpe_ratio
                    }
                })
        
        return subset_caches

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
                 starting_capital: float = 1000000.0):
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
        self.rf_rate = float(rf_rate)
        self.sma_window = int(sma_window)  # Ensure it's an integer
        self.use_trading_filter = bool(use_trading_filter)
        self.starting_capital = float(starting_capital)
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
        
        # Check cache first
        start_time = time.time()
        cached_result = OptimizationCache.lookup_cache(
            db_session, portfolio_ids, 
            self.rf_rate, self.sma_window, self.use_trading_filter,
            self.starting_capital, self.objective.min_weight, self.objective.max_weight
        )
        
        if cached_result:
            logger.info(f"Found cached optimization result for portfolios {portfolio_ids}")
            return OptimizationResult(
                optimal_weights=cached_result['optimal_weights'],
                optimal_ratios=cached_result['optimal_ratios'],
                optimal_cagr=cached_result['optimal_cagr'],
                optimal_max_drawdown=cached_result['optimal_max_drawdown'],
                optimal_return_drawdown_ratio=cached_result['optimal_return_drawdown_ratio'],
                optimal_sharpe_ratio=cached_result['optimal_sharpe_ratio'],
                optimization_method=f"{cached_result['optimization_method']} (cached)",
                iterations=cached_result['iterations'],
                success=cached_result['success'],
                message="Retrieved from cache",
                explored_combinations=[]
            )
        
        # Check if we can leverage cached subsets for initial guess
        subset_caches = OptimizationCache.find_subset_caches(
            db_session, portfolio_ids,
            self.rf_rate, self.sma_window, self.use_trading_filter,
            self.starting_capital, self.objective.min_weight, self.objective.max_weight
        )
        
        if subset_caches:
            logger.info(f"Found {len(subset_caches)} cached subsets to inform optimization")
            
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
                optimal_ratios=[],
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
        
        # Run optimization with smart initial guess from cached subsets
        result = self.optimize_weights(portfolios_data, method, subset_caches)
        
        # Store result in cache
        execution_time = time.time() - start_time
        if result.success:
            try:
                OptimizationCache.store_cache(
                    db_session, portfolio_ids, result, execution_time,
                    self.rf_rate, self.sma_window, self.use_trading_filter,
                    self.starting_capital, self.objective.min_weight, self.objective.max_weight
                )
                logger.info(f"Stored optimization result in cache for portfolios {portfolio_ids}")
            except Exception as e:
                logger.warning(f"Failed to store optimization result in cache: {e}")
        
        return result
    
    def optimize_weights(self, 
                        portfolios_data: List[Tuple[str, pd.DataFrame]], 
                        method: str = 'differential_evolution',
                        subset_caches: List[Dict] = None) -> OptimizationResult:
        """
        Optimize portfolio weights to maximize return/drawdown ratio
        
        Args:
            portfolios_data: List of (name, dataframe) tuples
            method: Optimization method ('scipy', 'differential_evolution', 'grid_search')
            subset_caches: Cached optimization results for portfolio subsets
            
        Returns:
            OptimizationResult with optimal weights and metrics
        """
        num_portfolios = len(portfolios_data)
        if num_portfolios < 2:
            return OptimizationResult(
                optimal_weights=[],
                optimal_ratios=[],
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
                return self._optimize_with_scipy(portfolios_data, subset_caches)
            elif method == 'differential_evolution':
                return self._optimize_with_differential_evolution(portfolios_data, subset_caches)
            elif method == 'grid_search':
                return self._optimize_with_grid_search(portfolios_data, subset_caches)
            else:
                raise ValueError(f"Unknown optimization method: {method}")
                
        except Exception as e:
            logger.error(f"Optimization failed: {str(e)}", exc_info=True)
            equal_weights = [1.0 / num_portfolios] * num_portfolios  # Equal weights fallback
            equal_ratios = convert_weights_to_ratios(equal_weights)
            return OptimizationResult(
                optimal_weights=equal_weights,
                optimal_ratios=equal_ratios,
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
            blended_df, blended_metrics, _ = create_blended_portfolio_from_files(
                portfolios_data,
                rf_rate=self.rf_rate,
                sma_window=self.sma_window,
                use_trading_filter=self.use_trading_filter,
                starting_capital=self.starting_capital,
                weights=weights.tolist(),
                use_capital_allocation=True  # For optimization, use capital allocation
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
    
    def _generate_smart_initial_guess(self, portfolios_data: List[Tuple[str, pd.DataFrame]], 
                                     subset_caches: List[Dict] = None) -> np.ndarray:
        """Generate intelligent initial guess using cached subset results"""
        num_portfolios = len(portfolios_data)
        portfolio_names = [name for name, _ in portfolios_data]
        
        if not subset_caches:
            return np.array([1.0 / num_portfolios] * num_portfolios)
        
        # Find the largest subset cache that we can use
        best_subset = None
        best_subset_size = 0
        
        for subset_cache in subset_caches:
            # Count how many portfolios from this subset are in our current request
            subset_size = len(subset_cache['portfolio_ids'])
            
            if subset_size > best_subset_size:
                best_subset = subset_cache
                best_subset_size = subset_size
        
        if best_subset and best_subset_size >= 2:
            # Start with cached weights and extend for new portfolios
            initial_weights = np.array([self.objective.min_weight] * num_portfolios)
            
            # Distribute remaining weight proportionally based on cached results
            remaining_weight = 1.0 - (num_portfolios * self.objective.min_weight)
            
            # Apply cached weights where possible (simplified mapping)
            for i, weight in enumerate(best_subset['optimal_weights']):
                if i < num_portfolios:
                    initial_weights[i] = max(weight, self.objective.min_weight)
            
            # Normalize to ensure sum equals 1
            initial_weights = initial_weights / np.sum(initial_weights)
            
            logger.info(f"Using smart initial guess based on cached subset of size {best_subset_size}")
            return initial_weights
        
        # Fallback to equal weights
        return np.array([1.0 / num_portfolios] * num_portfolios)

    def _optimize_with_scipy(self, portfolios_data: List[Tuple[str, pd.DataFrame]], 
                            subset_caches: List[Dict] = None) -> OptimizationResult:
        """Optimize using scipy's minimize function"""
        num_portfolios = len(portfolios_data)
        
        # Generate smart initial guess using cached subsets
        initial_weights = self._generate_smart_initial_guess(portfolios_data, subset_caches)
        
        # Constraints: weights sum to 1
        constraints = {'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0}
        
        # Bounds: each weight between min_weight and max_weight
        bounds = [(self.objective.min_weight, self.objective.max_weight) for _ in range(num_portfolios)]
        
        logger.info("Starting scipy optimization...")
        
        # Suppress scipy warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            
            # Adjust iterations based on complexity
            maxiter = min(200 + num_portfolios * 20, 500)  # Scale with portfolio count
            
            result = minimize(
                fun=self._objective_function,
                x0=initial_weights,
                args=(portfolios_data,),
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': maxiter, 'ftol': 1e-6}
            )
        
        if result.success:
            optimal_weights = result.x / np.sum(result.x)  # Normalize
            return self._create_result_from_weights(optimal_weights, portfolios_data, 'scipy', result.nit, True, "Optimization successful")
        else:
            # Provide more specific error messages
            error_message = result.message
            if "Maximum number of iterations" in str(result.message):
                error_message = f"Scipy optimization timeout after {result.nit} iterations with {num_portfolios} portfolios. Try 'differential_evolution' method or reduce portfolio count."
            elif "Positive directional derivative" in str(result.message):
                error_message = f"Scipy optimization stuck in local minimum with {num_portfolios} portfolios. Try 'differential_evolution' for global optimization."
            
            logger.warning(f"Scipy optimization failed: {error_message}")
            return self._create_result_from_weights(initial_weights, portfolios_data, 'scipy', result.nit, False, error_message)
    
    def _optimize_with_differential_evolution(self, portfolios_data: List[Tuple[str, pd.DataFrame]], 
                                            subset_caches: List[Dict] = None) -> OptimizationResult:
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
            
            # Adjust parameters based on portfolio count
            maxiter = min(100 + num_portfolios * 10, 300)  # Scale iterations with complexity
            popsize = min(15 + num_portfolios, 30)  # Scale population with complexity
            
            result = differential_evolution(
                func=constrained_objective,
                bounds=bounds,
                maxiter=maxiter,
                popsize=popsize,
                seed=42,
                polish=True,
                atol=1e-4
            )
        
        if result.success:
            optimal_weights = result.x / np.sum(result.x)  # Normalize
            return self._create_result_from_weights(optimal_weights, portfolios_data, 'differential_evolution', result.nit, True, "Optimization successful")
        else:
            # Provide more specific error messages
            error_message = result.message
            if "Maximum number of iterations" in str(result.message):
                error_message = f"Optimization timeout after {result.nit} iterations with {num_portfolios} portfolios. Try with fewer portfolios (≤6 recommended) or use 'scipy' method."
            elif "convergence" in str(result.message).lower():
                error_message = f"Failed to converge with {num_portfolios} portfolios. Consider reducing portfolio count or trying 'grid_search' method."
            
            logger.warning(f"Differential evolution failed: {error_message}")
            equal_weights = np.array([1.0 / num_portfolios] * num_portfolios)
            return self._create_result_from_weights(equal_weights, portfolios_data, 'differential_evolution', result.nit, False, error_message)
    
    def _optimize_with_grid_search(self, portfolios_data: List[Tuple[str, pd.DataFrame]], 
                                  subset_caches: List[Dict] = None) -> OptimizationResult:
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
            # For more portfolios, use random sampling with scaled sample count
            np.random.seed(42)
            max_samples = min(500 + num_portfolios * 50, 2000)  # Scale with portfolio count
            
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
            blended_df, blended_metrics, _ = create_blended_portfolio_from_files(
                portfolios_data,
                rf_rate=self.rf_rate,
                sma_window=self.sma_window,
                use_trading_filter=self.use_trading_filter,
                starting_capital=self.starting_capital,
                weights=weights.tolist(),
                use_capital_allocation=True  # For optimization, use capital allocation
            )
            
            if blended_metrics is not None:
                # Convert weights to ratios
                ratios = convert_weights_to_ratios(weights.tolist())
                
                return OptimizationResult(
                    optimal_weights=weights.tolist(),
                    optimal_ratios=ratios,
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
        ratios = convert_weights_to_ratios(weights.tolist()) if len(weights) > 0 else []
        return OptimizationResult(
            optimal_weights=weights.tolist(),
            optimal_ratios=ratios,
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