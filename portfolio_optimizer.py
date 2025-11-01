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

def convert_weights_to_ratios(weights: List[float], min_units: int = 1, max_ratio: int = 10, portfolio_count: int = None) -> List[int]:
    """
    Convert decimal weights to whole number ratios with minimum allocation.
    
    Args:
        weights: List of decimal weights (e.g., [0.12, 0.07, 0.73, 0.07])
        min_units: Minimum units per strategy (default: 1)
        max_ratio: Maximum ratio allowed (default: 10)
        portfolio_count: Number of portfolios (for dynamic constraint calculation)
        
    Returns:
        List of whole number ratios (e.g., [1, 1, 7, 1])
        
    Examples:
        [0.12, 0.07, 0.73, 0.07] -> [1, 1, 7, 1]
        [0.25, 0.50, 0.25] -> [1, 2, 1]
        [0.10, 0.30, 0.60] -> [1, 3, 6]
    """
    if not weights or len(weights) == 0:
        return []
    
    # Calculate dynamic max_ratio if portfolio_count is provided
    if portfolio_count is not None and portfolio_count > 0:
        base_weight = 1.0 / portfolio_count
        max_weight = calculate_dynamic_max_weight(portfolio_count)
        # Use ceiling to allow the full constraint (e.g., 2.9x becomes 3x)
        dynamic_max_ratio = int(math.ceil(max_weight / base_weight))
        max_ratio = min(max_ratio, dynamic_max_ratio)  # Use the more restrictive limit
        logger.info(f"[RATIO CONVERSION] Portfolio count: {portfolio_count}, base_weight: {base_weight:.3f}, max_weight: {max_weight:.3f}")
        logger.info(f"[RATIO CONVERSION] Calculated dynamic max ratio: {max_weight/base_weight:.1f}x -> ceiling: {dynamic_max_ratio}, using max_ratio: {max_ratio}")
    else:
        logger.info(f"[RATIO CONVERSION] No portfolio count provided, using default max_ratio: {max_ratio}")
    
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
    
    # If ratios are still too large, apply constraint-respecting scaling
    if max(best_ratios) > max_ratio:
        logger.info(f"[RATIO CONVERSION] Original ratios exceed max_ratio ({max_ratio}): {best_ratios.tolist() if isinstance(best_ratios, np.ndarray) else best_ratios}")
        
        # Scale ratios to fit within max_ratio constraint while maintaining proportions
        capped_ratios = np.array(best_ratios, dtype=float)
        
        # Scale down proportionally so the maximum doesn't exceed max_ratio
        scale_factor = max_ratio / max(capped_ratios)
        scaled_ratios = capped_ratios * scale_factor
        
        # Round and ensure minimum units
        final_ratios = np.maximum(np.round(scaled_ratios), min_units).astype(int)
        
        # If the constraint is still violated after rounding, cap the maximum
        if max(final_ratios) > max_ratio:
            final_ratios = np.minimum(final_ratios, max_ratio)
        
        logger.info(f"[RATIO CONVERSION] Scale factor: {scale_factor:.3f}, scaled result: {final_ratios.tolist()}")
        best_ratios = final_ratios
    
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
    # Progressive optimization fields
    is_partial_result: bool = False  # True if optimization timed out but found good result
    progress_percentage: float = 0.0  # Estimated completion percentage (0-100)
    remaining_iterations: int = 0  # Estimated remaining iterations for completion
    execution_time_seconds: float = 0.0  # Actual execution time
    can_continue: bool = False  # True if optimization can be resumed

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

def calculate_dynamic_max_weight(portfolio_count: int) -> float:
    """
    Calculate maximum weight per portfolio based on portfolio count.
    
    Dynamic scaling ensures reasonable diversification:
    - 2 portfolios: 80% max (limited options)
    - 3-6 portfolios: 70% to 50% max (moderate concentration)
    - 7+ portfolios: 40% to 22% max (diversification focus)
    
    Args:
        portfolio_count: Number of portfolios in optimization
        
    Returns:
        Maximum weight as decimal (e.g., 0.50 for 50%)
    """
    if portfolio_count < 2:
        return 0.80  # Edge case: single portfolio
    elif portfolio_count == 2:
        return 0.80  # 2 portfolios: allow up to 80% concentration
    elif portfolio_count <= 6:
        # Linear decrease from 70% to 50% for 3-6 portfolios
        # Formula: 70% - ((count - 3) * 6.25%)
        return 0.70 - ((portfolio_count - 3) * 0.0625)
    elif portfolio_count <= 12:
        # Linear decrease from 40% to 30% for 7-12 portfolios
        # Formula: 40% - ((count - 7) * 1.67%)
        return 0.40 - ((portfolio_count - 7) * 0.0167)
    else:
        # 13+ portfolios: cap at decreasing rate, minimum 20%
        return max(0.20, 0.30 - ((portfolio_count - 12) * 0.01))

def calculate_dynamic_min_weight(portfolio_count: int) -> float:
    """
    Calculate minimum weight per portfolio based on portfolio count.
    
    Ensures meaningful allocation while maintaining feasible constraints:
    - Basic minimum: 1/(portfolio_count * 5) but at least 1%
    - Never more than max_weight / 5 to maintain feasible constraints
    - Must ensure total minimum weights don't exceed 1.0
    
    Args:
        portfolio_count: Number of portfolios in optimization
        
    Returns:
        Minimum weight as decimal (e.g., 0.05 for 5%)
    """
    if portfolio_count < 2:
        return 0.05
    
    # Basic minimum: more conservative approach
    basic_min = max(0.01, 1.0 / (portfolio_count * 5))
    
    # But never more than 1/5 of the maximum weight to maintain feasibility
    max_weight = calculate_dynamic_max_weight(portfolio_count)
    feasible_min = max_weight / 5
    
    # Ensure the sum of minimum weights doesn't exceed reasonable bounds
    candidate_min = min(basic_min, feasible_min)
    max_feasible_min = 0.8 / portfolio_count  # Leave 20% room for weight variation
    
    return min(candidate_min, max_feasible_min)

@dataclass
class OptimizationObjective:
    """Configuration for optimization objectives"""
    return_weight: float = 0.6  # Weight for return in objective function
    drawdown_weight: float = 0.4  # Weight for drawdown penalty in objective function
    # Note: min_weight and max_weight are now calculated dynamically based on portfolio count

class PortfolioOptimizer:
    """
    Portfolio weight optimizer that maximizes return while minimizing drawdown
    """
    
    def __init__(self, 
                 objective: OptimizationObjective = None,
                 rf_rate: float = 0.05,
                 sma_window: int = 20,
                 use_trading_filter: bool = True,
                 starting_capital: float = 1000000.0,
                 portfolio_count: int = None,
                 max_time_seconds: float = None):
        """
        Initialize the portfolio optimizer
        
        Args:
            objective: Optimization objective configuration
            rf_rate: Risk-free rate for calculations
            sma_window: SMA window for trading filter
            use_trading_filter: Whether to apply SMA filter
            starting_capital: Starting capital for calculations
            portfolio_count: Number of portfolios (for dynamic weight constraints)
            max_time_seconds: Maximum optimization time before returning partial result
        """
        self.objective = objective or OptimizationObjective()
        self.rf_rate = float(rf_rate)
        self.sma_window = int(sma_window)  # Ensure it's an integer
        self.use_trading_filter = bool(use_trading_filter)
        self.starting_capital = float(starting_capital)
        self.explored_combinations = []
        
        # Progressive optimization tracking
        self.start_time = None
        self.max_time_seconds = max_time_seconds or self._calculate_default_timeout(portfolio_count)
        self.best_result_so_far = None
        self.current_iteration = 0
        self.total_iterations = 0
        
        # Weight discretization for practical trading units
        # 0.5% increments (0.005) reduces search space dramatically:
        # - Without discretization: infinite precision = infinite search space
        # - With discretization: 200 possible values per weight (0% to 100% in 0.5% steps)
        # - For 2 portfolios: ~200 meaningful combinations vs infinite
        # - For 3 portfolios: ~40,000 combinations vs infinite  
        self.weight_precision = 0.005  # 0.5% increments - can be adjusted for finer/coarser precision
        
        # Dynamic weight constraints (will be set when portfolio_count is known)
        self.portfolio_count = portfolio_count
        self.min_weight = None
        self.max_weight = None
        if portfolio_count is not None:
            self.set_dynamic_constraints(portfolio_count)
    
    def _calculate_default_timeout(self, portfolio_count: int = None) -> float:
        """Calculate reasonable default timeout based on portfolio count"""
        if not portfolio_count:
            return 60.0  # Default 1 minute
        
        # Progressive timeouts: more portfolios = more time needed
        if portfolio_count <= 3:
            return 30.0  # 30 seconds for simple cases
        elif portfolio_count <= 5:
            return 60.0  # 1 minute for moderate complexity
        elif portfolio_count <= 7:
            return 120.0  # 2 minutes for higher complexity
        else:
            return 180.0  # 3 minutes for very complex cases
    
    def _is_timeout_reached(self) -> bool:
        """Check if optimization should timeout"""
        if not self.start_time or not self.max_time_seconds:
            return False
        return (time.time() - self.start_time) >= self.max_time_seconds
    
    def _update_best_result(self, weights: np.ndarray, portfolios_data: List[Tuple[str, pd.DataFrame]], 
                           objective_value: float, iteration: int) -> None:
        """Update the best result found so far"""
        if self.best_result_so_far is None or objective_value < self.best_result_so_far['objective_value']:
            self.best_result_so_far = {
                'weights': weights.copy(),
                'objective_value': objective_value,
                'iteration': iteration,
                'timestamp': time.time()
            }
    
    def set_dynamic_constraints(self, portfolio_count: int):
        """
        Set dynamic min/max weight constraints based on portfolio count
        
        Args:
            portfolio_count: Number of portfolios in optimization
        """
        self.portfolio_count = portfolio_count
        self.min_weight = calculate_dynamic_min_weight(portfolio_count)
        self.max_weight = calculate_dynamic_max_weight(portfolio_count)
        
        logger.info(f"[DYNAMIC WEIGHTS] Portfolio count: {portfolio_count}")
        logger.info(f"[DYNAMIC WEIGHTS] Min weight: {self.min_weight:.3f} ({self.min_weight*100:.1f}%)")
        logger.info(f"[DYNAMIC WEIGHTS] Max weight: {self.max_weight:.3f} ({self.max_weight*100:.1f}%)")
        
    def optimize_weights_from_ids(self, 
                                  db_session, 
                                  portfolio_ids: List[int],
                                  method: str = 'differential_evolution',
                                  resume_from_weights: List[float] = None) -> OptimizationResult:
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
        
        # Set dynamic constraints based on portfolio count
        self.set_dynamic_constraints(len(portfolio_ids))
        
        # Check cache first, but skip cache if resuming from previous weights
        start_time = time.time()
        cached_result = None
        
        if not resume_from_weights:
            # Only use cache for fresh optimizations, not continuations
            cached_result = OptimizationCache.lookup_cache(
                db_session, portfolio_ids, 
                self.rf_rate, self.sma_window, self.use_trading_filter,
                self.starting_capital, self.min_weight, self.max_weight
            )
        else:
            logger.info(f"Skipping cache lookup because resuming from previous weights: {resume_from_weights}")
        
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
            self.starting_capital, self.min_weight, self.max_weight
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
        
        # Run optimization with smart initial guess from cached subsets or resume weights
        result = self.optimize_weights(portfolios_data, method, subset_caches, resume_from_weights)
        
        # Store result in cache
        execution_time = time.time() - start_time
        if result.success:
            try:
                OptimizationCache.store_cache(
                    db_session, portfolio_ids, result, execution_time,
                    self.rf_rate, self.sma_window, self.use_trading_filter,
                    self.starting_capital, self.min_weight, self.max_weight
                )
                logger.info(f"Stored optimization result in cache for portfolios {portfolio_ids}")
            except Exception as e:
                logger.warning(f"Failed to store optimization result in cache: {e}")
        
        return result
    
    def optimize_weights(self, 
                        portfolios_data: List[Tuple[str, pd.DataFrame]], 
                        method: str = 'differential_evolution',
                        subset_caches: List[Dict] = None,
                        resume_from_weights: List[float] = None) -> OptimizationResult:
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

        # Update dynamic weight constraints based on portfolio count
        self.set_dynamic_constraints(num_portfolios)

        self.explored_combinations = []

        try:
            if method == 'scipy':
                return self._optimize_with_scipy(portfolios_data, subset_caches, resume_from_weights)
            elif method == 'differential_evolution':
                return self._optimize_with_differential_evolution(portfolios_data, subset_caches, resume_from_weights)
            elif method == 'grid_search':
                return self._optimize_with_grid_search(portfolios_data, subset_caches, resume_from_weights)
            else:
                raise ValueError(f"Unknown optimization method: {method}")
                
        except Exception as e:
            logger.error(f"Optimization failed: {str(e)}", exc_info=True)
            equal_weights = [1.0 / num_portfolios] * num_portfolios  # Equal weights fallback
            equal_ratios = convert_weights_to_ratios(equal_weights, portfolio_count=num_portfolios)
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
            # Increment iteration counters
            self.current_iteration += 1
            if hasattr(self, 'cumulative_iterations'):
                self.cumulative_iterations += 1
            
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
            # Lower drawdown is better (subtract drawdown penalty)
            objective_value = (
                self.objective.return_weight * abs(cagr) -
                self.objective.drawdown_weight * max_drawdown_pct
            )
            
            # Update best result tracking (store negative value since we're minimizing)
            negative_objective = -objective_value
            self._update_best_result(weights, portfolios_data, negative_objective, self.current_iteration)
            
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
            return negative_objective
            
        except Exception as e:
            logger.warning(f"Error in objective function with weights {weights}: {str(e)}")
            return 1000  # High penalty for error cases
    
    def _generate_smart_initial_guess(self, portfolios_data: List[Tuple[str, pd.DataFrame]], 
                                     subset_caches: List[Dict] = None) -> np.ndarray:
        """Generate intelligent initial guess using cached subset results"""
        num_portfolios = len(portfolios_data)
        portfolio_names = [name for name, _ in portfolios_data]
        
        if not subset_caches:
            # Use equal weights but ensure they respect dynamic constraints
            equal_weight = 1.0 / num_portfolios
            if equal_weight < self.min_weight:
                # If equal weights would be too small, use minimum weight
                return np.array([self.min_weight] * num_portfolios) / np.sum([self.min_weight] * num_portfolios)
            elif equal_weight > self.max_weight:
                # If equal weights would be too large, use maximum weight  
                return np.array([self.max_weight] * num_portfolios) / np.sum([self.max_weight] * num_portfolios)
            else:
                return np.array([equal_weight] * num_portfolios)
        
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
            # Start with cached weights and extend for new portfolios using dynamic constraints
            initial_weights = np.array([self.min_weight] * num_portfolios)
            
            # Distribute remaining weight proportionally based on cached results
            remaining_weight = 1.0 - (num_portfolios * self.min_weight)
            
            # Apply cached weights where possible (simplified mapping)
            for i, weight in enumerate(best_subset['optimal_weights']):
                if i < num_portfolios:
                    initial_weights[i] = max(weight, self.min_weight)
            
            # Normalize to ensure sum equals 1
            initial_weights = initial_weights / np.sum(initial_weights)
            
            logger.info(f"Using smart initial guess based on cached subset of size {best_subset_size}")
            return initial_weights
        
        # Fallback to equal weights respecting dynamic constraints
        equal_weight = 1.0 / num_portfolios
        if equal_weight < self.min_weight:
            return np.array([self.min_weight] * num_portfolios) / np.sum([self.min_weight] * num_portfolios)
        elif equal_weight > self.max_weight:
            return np.array([self.max_weight] * num_portfolios) / np.sum([self.max_weight] * num_portfolios)
        else:
            return np.array([equal_weight] * num_portfolios)

    def _optimize_with_scipy(self, portfolios_data: List[Tuple[str, pd.DataFrame]], 
                            subset_caches: List[Dict] = None,
                            resume_from_weights: List[float] = None) -> OptimizationResult:
        """Optimize using scipy's minimize function"""
        num_portfolios = len(portfolios_data)
        
        # Generate smart initial guess using cached subsets
        initial_weights = self._generate_smart_initial_guess(portfolios_data, subset_caches)
        
        # Constraints: weights sum to 1
        constraints = {'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0}
        
        # Bounds: each weight between dynamic min_weight and max_weight
        bounds = [(self.min_weight, self.max_weight) for _ in range(num_portfolios)]
        
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
                                            subset_caches: List[Dict] = None,
                                            resume_from_weights: List[float] = None) -> OptimizationResult:
        """Optimize using differential evolution (global optimizer)"""
        num_portfolios = len(portfolios_data)

        # Initialize optimization tracking
        self.start_time = time.time()
        self.optimization_stopped = False  # Flag to track if we stopped due to timeout

        # For continuation, don't reset iteration counter - keep accumulating progress
        if not resume_from_weights:
            self.current_iteration = 0
            self.cumulative_iterations = 0
            # Use coarser precision for initial exploration (faster convergence)
            self.weight_precision = 0.01  # 1% increments for fresh optimization
            logger.info(f"Fresh optimization: using coarser precision ({self.weight_precision * 100:.1f}% increments)")
        else:
            # Keep existing iteration count and continue from there
            self.cumulative_iterations = getattr(self, 'cumulative_iterations', 0)
            # Use finer precision for refinement
            self.weight_precision = 0.005  # 0.5% increments for continuation
            logger.info(f"Continuing optimization from {self.cumulative_iterations} cumulative iterations")
            logger.info(f"Continuation: using finer precision ({self.weight_precision * 100:.1f}% increments)")

        self.best_result_so_far = None

        # Bounds for each weight using dynamic constraints
        bounds = [(self.min_weight, self.max_weight) for _ in range(num_portfolios)]

        logger.info(f"Starting differential evolution optimization (timeout: {self.max_time_seconds}s)...")

        # Prepare initial guess if resume weights are provided
        initial_guess = None
        if resume_from_weights and len(resume_from_weights) == num_portfolios:
            initial_guess = np.array(resume_from_weights)
            # Normalize to sum to 1
            initial_guess = initial_guess / np.sum(initial_guess)
            # Ensure weights are within bounds
            initial_guess = np.clip(initial_guess, self.min_weight, self.max_weight)
            logger.info(f"Using resume weights as initial guess: {initial_guess}")

        def constrained_objective(weights):
            # Check for timeout before evaluating
            if self._is_timeout_reached():
                # Set flag and return high value to discourage this solution
                self.optimization_stopped = True
                return 1000

            # Discretize weights to practical increments (reduces search space)
            # This dramatically reduces the search space and speeds up convergence
            discretized_weights = np.round(weights / self.weight_precision) * self.weight_precision

            # Log discretization effect occasionally for debugging
            if self.current_iteration % 50 == 0:
                logger.info(f"Weight discretization example: {weights[:2]} → {discretized_weights[:2]}")

            # Normalize discretized weights to sum to 1
            normalized_weights = discretized_weights / np.sum(discretized_weights)

            # Ensure weights are within bounds after discretization
            normalized_weights = np.clip(normalized_weights, self.min_weight, self.max_weight)

            # Re-normalize after clipping
            normalized_weights = normalized_weights / np.sum(normalized_weights)

            return self._objective_function(normalized_weights, portfolios_data)

        def optimization_callback(xk, convergence):
            """Callback to check for timeout and stop optimization early if needed"""
            if self._is_timeout_reached():
                logger.info(f"Timeout reached ({self.max_time_seconds}s), stopping optimization early")
                self.optimization_stopped = True
                return True  # Return True to stop optimization
            return False  # Continue optimization

        # Suppress warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            # Adjust parameters based on portfolio count and timeout
            # For large portfolios, reduce iterations to ensure we can complete within timeout
            if num_portfolios <= 5:
                base_maxiter = 100
                base_popsize = 15
            elif num_portfolios <= 10:
                base_maxiter = 80
                base_popsize = 20
            elif num_portfolios <= 15:
                base_maxiter = 50
                base_popsize = 20
            elif num_portfolios <= 20:
                base_maxiter = 30
                base_popsize = 15
            else:  # 20+ portfolios
                base_maxiter = 20
                base_popsize = 10

            # For continuations, reduce iterations since we're starting from a better point
            if resume_from_weights:
                # Reduce iterations for continuation (30% of original) since we start from good point
                maxiter = max(int(base_maxiter * 0.3), 10)
                popsize = max(int(base_popsize * 0.5), 8)  # Smaller population for focused search
                logger.info(f"Continuation optimization: reduced maxiter={maxiter}, popsize={popsize}")
            else:
                maxiter = base_maxiter
                popsize = base_popsize
                logger.info(f"Fresh optimization: maxiter={maxiter}, popsize={popsize} for {num_portfolios} portfolios")

            # Update total iterations estimate accounting for cumulative runs
            if hasattr(self, 'cumulative_iterations') and self.cumulative_iterations > 0:
                # Add to existing total estimate
                additional_iterations = maxiter * popsize
                self.total_iterations = getattr(self, 'total_iterations', base_maxiter * base_popsize) + additional_iterations
                logger.info(f"Updated total iterations estimate: {self.total_iterations}")
            else:
                self.total_iterations = maxiter * popsize  # Fresh start

            # Build parameters for differential evolution
            de_params = {
                'func': constrained_objective,
                'bounds': bounds,
                'maxiter': maxiter,
                'popsize': popsize,
                'seed': 42,
                'polish': True,
                'atol': 1e-4,
                'callback': optimization_callback  # Add callback for early stopping
            }

            # Add initial guess if resuming from previous weights
            if initial_guess is not None:
                de_params['x0'] = initial_guess

            result = differential_evolution(**de_params)
        
        # Calculate execution time and progress
        execution_time = time.time() - self.start_time

        # Use cumulative iterations for progress calculation when continuing
        iterations_for_progress = getattr(self, 'cumulative_iterations', self.current_iteration)
        progress_percentage = min((iterations_for_progress / max(self.total_iterations, 1)) * 100, 100.0)

        logger.info(f"Progress calculation: {iterations_for_progress} / {self.total_iterations} = {progress_percentage:.1f}%")
        logger.info(f"Optimization completed in {execution_time:.1f}s, stopped={self.optimization_stopped}")

        # Check if we have a good result (either from success or timeout with best result)
        has_good_result = result.success or (self.best_result_so_far is not None)

        # Determine if this is a partial result (stopped due to timeout)
        timed_out = self.optimization_stopped or self._is_timeout_reached()

        if has_good_result:
            # Use best result if we have one, especially if we timed out
            if self.best_result_so_far is not None and (not result.success or timed_out):
                optimal_weights = self.best_result_so_far['weights']
                is_partial = timed_out and progress_percentage < 100.0
                message = "Partial optimization completed (timeout reached)" if is_partial else "Optimization successful"
                logger.info(f"Using best result found (timed_out={timed_out}, is_partial={is_partial})")
            else:
                optimal_weights = result.x / np.sum(result.x)  # Normalize
                is_partial = False
                message = "Optimization successful"
                logger.info(f"Using scipy result (success={result.success})")
            
            # Apply final discretization to ensure results match trading unit precision
            logger.info(f"Raw optimal weights before discretization: {optimal_weights}")
            
            # Round to exact precision to avoid floating point errors
            discrete_weights = np.round(optimal_weights / self.weight_precision) * self.weight_precision
            logger.info(f"After discretization: {discrete_weights} (step: {self.weight_precision})")
            
            # Normalize discretized weights to sum to 1
            discrete_weights = discrete_weights / np.sum(discrete_weights)
            
            # Ensure weights are within bounds after discretization
            discrete_weights = np.clip(discrete_weights, self.min_weight, self.max_weight)
            
            # Re-normalize after clipping and round again to clean up floating point errors
            optimal_weights = discrete_weights / np.sum(discrete_weights)
            
            # Final cleanup - round to avoid floating point precision artifacts
            optimal_weights = np.round(optimal_weights / self.weight_precision) * self.weight_precision
            optimal_weights = optimal_weights / np.sum(optimal_weights)  # Final normalization
            
            # Additional cleanup to ensure clean discretized results  
            # Round to the discretization precision and normalize again
            optimal_weights = np.round(optimal_weights / self.weight_precision) * self.weight_precision
            optimal_weights = optimal_weights / np.sum(optimal_weights)
            
            # Final precision cleanup - round to avoid tiny floating point errors
            # Use one more decimal place than discretization for internal precision
            decimal_places = max(2, int(-np.log10(self.weight_precision)) + 1)
            optimal_weights = np.round(optimal_weights, decimal_places)
            
            logger.info(f"Final discretized weights: {optimal_weights} (precision: {self.weight_precision * 100:.1f}%, decimals: {decimal_places})")
            
            optimization_result = self._create_result_from_weights(
                optimal_weights, portfolios_data, 'differential_evolution', 
                self.current_iteration, has_good_result, message
            )
            
            # Set progressive optimization fields
            optimization_result.is_partial_result = is_partial
            optimization_result.progress_percentage = progress_percentage
            # Calculate remaining iterations based on cumulative progress
            remaining_iterations = max(0, self.total_iterations - iterations_for_progress)
            optimization_result.remaining_iterations = remaining_iterations
            optimization_result.execution_time_seconds = execution_time
            # Allow continuation if:
            # 1. Optimization was partial (timeout), OR
            # 2. For complete optimizations: only if significant exploration remains (< 80%) AND remaining iterations
            if is_partial:
                # Partial optimization - allow continuation if progress < 95%
                optimization_result.can_continue = progress_percentage < 95.0
            else:
                # Complete optimization - do not allow continuation
                # Reasoning: If the optimization completed successfully, it found a satisfactory result
                # Users can manually re-run optimization if they want to explore further
                optimization_result.can_continue = False
            
            return optimization_result
        else:
            # No good result found - provide more specific error messages
            error_message = result.message
            if "Maximum number of iterations" in str(result.message):
                error_message = f"Optimization timeout after {result.nit} iterations with {num_portfolios} portfolios. Try with fewer portfolios (≤10 recommended) or use 'scipy' method."
            elif "convergence" in str(result.message).lower():
                error_message = f"Failed to converge with {num_portfolios} portfolios. Consider reducing portfolio count or trying 'grid_search' method."
            
            logger.warning(f"Differential evolution failed: {error_message}")
            equal_weights = np.array([1.0 / num_portfolios] * num_portfolios)
            return self._create_result_from_weights(equal_weights, portfolios_data, 'differential_evolution', self.current_iteration, False, error_message)
    
    def _optimize_with_grid_search(self, portfolios_data: List[Tuple[str, pd.DataFrame]], 
                                  subset_caches: List[Dict] = None,
                                  resume_from_weights: List[float] = None) -> OptimizationResult:
        """Optimize using grid search (thorough but slower)"""
        num_portfolios = len(portfolios_data)
        
        logger.info(f"Starting grid search optimization for {num_portfolios} portfolios...")
        
        best_objective = float('inf')
        best_weights = None
        iterations = 0
        
        # Generate weight combinations
        if num_portfolios == 2:
            # For 2 portfolios, search in 5% increments using dynamic bounds
            weight_options = np.arange(self.min_weight, self.max_weight + 0.05, 0.05)
            
            for w1 in weight_options:
                w2 = 1.0 - w1
                if self.min_weight <= w2 <= self.max_weight:
                    weights = np.array([w1, w2])
                    objective_value = self._objective_function(weights, portfolios_data)
                    iterations += 1
                    
                    if objective_value < best_objective:
                        best_objective = objective_value
                        best_weights = weights
                        
        elif num_portfolios == 3:
            # For 3 portfolios, search in 10% increments using dynamic bounds
            weight_options = np.arange(self.min_weight, self.max_weight + 0.1, 0.1)
            
            for w1 in weight_options:
                for w2 in weight_options:
                    w3 = 1.0 - w1 - w2
                    if self.min_weight <= w3 <= self.max_weight:
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
                
                # Ensure constraints using dynamic bounds
                if np.all(weights >= self.min_weight) and np.all(weights <= self.max_weight):
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
                # Apply final discretization to weights before converting to list
                # This ensures clean values like 0.18 instead of 0.18487394957983194
                clean_weights = np.round(weights / self.weight_precision) * self.weight_precision
                clean_weights = clean_weights / np.sum(clean_weights)  # Normalize
                # Final precision cleanup
                decimal_places = max(2, int(-np.log10(self.weight_precision)) + 1)
                clean_weights = np.round(clean_weights, decimal_places)
                
                # Convert weights to ratios with dynamic constraints
                ratios = convert_weights_to_ratios(clean_weights.tolist(), portfolio_count=self.portfolio_count)
                
                return OptimizationResult(
                    optimal_weights=clean_weights.tolist(),
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
        
        # Fallback result - apply discretization here too
        clean_weights = weights
        if len(weights) > 0:
            clean_weights = np.round(weights / self.weight_precision) * self.weight_precision
            clean_weights = clean_weights / np.sum(clean_weights)
            decimal_places = max(2, int(-np.log10(self.weight_precision)) + 1)
            clean_weights = np.round(clean_weights, decimal_places)
        
        ratios = convert_weights_to_ratios(clean_weights.tolist(), portfolio_count=self.portfolio_count) if len(clean_weights) > 0 else []
        return OptimizationResult(
            optimal_weights=clean_weights.tolist(),
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