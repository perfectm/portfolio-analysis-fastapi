from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from typing import Any, List
import logging
from database import get_db
from portfolio_service import PortfolioService
from profit_optimizer import ProfitOptimizer

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/optimize")
async def optimize_for_profit(request: Request, db: Session = Depends(get_db)):
    """
    Optimize portfolio weights to achieve target annual profit while minimizing drawdown
    """
    try:
        body = await request.json()
        portfolio_ids = body.get("portfolio_ids", [])
        target_annual_profit = body.get("target_annual_profit", 100000.0)
        method = body.get("method", "differential_evolution")
        
        # Validation
        if not portfolio_ids:
            return {"success": False, "error": "No portfolio IDs provided"}
        if len(portfolio_ids) < 2:
            return {"success": False, "error": "Need at least 2 portfolios for profit optimization"}
        if len(portfolio_ids) > 20:
            return {"success": False, "error": "Maximum 20 portfolios allowed for optimization to prevent performance issues"}
        if target_annual_profit <= 0:
            return {"success": False, "error": "Target annual profit must be greater than 0"}
        
        logger.info(f"[Profit Optimization] Optimizing for target profit: ${target_annual_profit:,.0f}")
        logger.info(f"[Profit Optimization] Portfolio IDs: {portfolio_ids}")
        logger.info(f"[Profit Optimization] Method: {method}")
        
        # Validate portfolios exist and have data
        portfolio_info = []
        for portfolio_id in portfolio_ids:
            portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
            if not portfolio:
                return {
                    "success": False, 
                    "error": f"Portfolio {portfolio_id} not found",
                    "details": {
                        "error_type": "DataError",
                        "description": f"Portfolio with ID {portfolio_id} does not exist in the database",
                        "suggestion": "Please refresh the page and select valid portfolios from the dropdown"
                    }
                }
            
            df = PortfolioService.get_portfolio_dataframe(db, portfolio_id)
            if df.empty:
                return {
                    "success": False, 
                    "error": f"Portfolio '{portfolio.name}' contains no trading data",
                    "details": {
                        "error_type": "DataError",
                        "description": f"Portfolio '{portfolio.name}' (ID: {portfolio_id}) has no trades or P/L data",
                        "suggestion": "Please select portfolios that contain actual trading data with P/L values"
                    }
                }
            
            # Check if portfolio has meaningful P/L data
            if 'P/L' not in df.columns:
                return {
                    "success": False, 
                    "error": f"Portfolio '{portfolio.name}' is missing P/L data",
                    "details": {
                        "error_type": "DataError", 
                        "description": f"Portfolio '{portfolio.name}' does not contain required P/L column",
                        "suggestion": "Ensure the uploaded CSV files contain a profit/loss column (P/L, PnL, etc.)"
                    }
                }
            
            # Check if P/L data has any non-zero values
            pnl_sum = df['P/L'].sum() if 'P/L' in df.columns else 0
            if abs(pnl_sum) < 0.01:  # Very small total P/L
                return {
                    "success": False, 
                    "error": f"Portfolio '{portfolio.name}' has insufficient trading activity",
                    "details": {
                        "error_type": "DataError",
                        "description": f"Portfolio '{portfolio.name}' has total P/L of ${pnl_sum:.2f}, which is too small for meaningful optimization",
                        "suggestion": "Select portfolios with substantial trading activity and meaningful profit/loss values"
                    }
                }
            
            portfolio_info.append({
                "id": portfolio_id,
                "name": portfolio.name,
                "rows": len(df),
                "total_pnl": pnl_sum
            })
            
        logger.info(f"[Profit Optimization] Validated portfolios: {portfolio_info}")
        
        try:
            from profit_optimizer import ProfitOptimizer
        except ImportError as e:
            return {
                "success": False,
                "error": "Profit optimization requires scipy. Please install scipy>=1.10.0",
                "details": str(e)
            }
        
        # Create optimizer with profit target
        optimizer = ProfitOptimizer(
            target_annual_profit=target_annual_profit,
            rf_rate=0.043,
            sma_window=20,
            use_trading_filter=True,
            starting_capital=1000000.0,
            portfolio_count=len(portfolio_ids)
        )
        
        # Run optimization
        result = optimizer.optimize_weights_from_ids(db, portfolio_ids, method)
        
        if not result.success:
            # Provide more detailed error information
            error_details = {
                "success": False,
                "error": result.message,
                "details": {
                    "optimization_method": result.optimization_method,
                    "iterations_completed": result.iterations,
                    "execution_time_seconds": result.execution_time_seconds,
                    "portfolio_count": len(portfolio_ids),
                    "target_profit": target_annual_profit
                }
            }
            
            # Add specific troubleshooting suggestions
            suggestions = []
            if result.iterations == 0:
                suggestions.append("The optimization algorithm failed to start. This may indicate a problem with portfolio data or dependencies.")
            elif result.execution_time_seconds < 1.0:
                suggestions.append("The optimization failed very quickly, possibly due to invalid portfolio data or extreme parameter values.")
            elif len(portfolio_ids) > 10:
                suggestions.append("Try reducing the number of portfolios (use fewer than 10) as large combinations can be difficult to optimize.")
            
            if target_annual_profit > 500000:
                suggestions.append("The target profit may be unrealistically high. Try a lower target (e.g., $50,000 - $200,000).")
            elif target_annual_profit < 1000:
                suggestions.append("The target profit may be too low. Try a higher target (e.g., $10,000 or more).")
            
            if suggestions:
                error_details["suggestions"] = suggestions
            
            logger.warning(f"[Profit Optimization] Failed with details: {error_details}")
            return error_details
        
        # Prepare response data
        weight_mapping = dict(zip(result.portfolio_names, result.optimal_weights))
        ratio_mapping = dict(zip(result.portfolio_names, result.optimal_ratios))
        
        logger.info(f"[Profit Optimization] Optimization completed successfully")
        logger.info(f"[Profit Optimization] Target: ${result.target_annual_profit:,.0f}, "
                   f"Achieved: ${result.achieved_annual_profit:,.0f}")
        logger.info(f"[Profit Optimization] Optimal weights: {weight_mapping}")
        
        return {
            "success": True,
            "message": result.message,
            "optimal_weights": weight_mapping,
            "optimal_weights_array": result.optimal_weights,
            "optimal_ratios": ratio_mapping,
            "optimal_ratios_array": result.optimal_ratios,
            "target_annual_profit": result.target_annual_profit,
            "target_profit_achieved": result.achieved_annual_profit,
            "metrics": result.metrics,
            "optimization_details": {
                "method": result.optimization_method,
                "iterations": result.iterations,
                "execution_time_seconds": result.execution_time_seconds
            },
            "portfolio_names": result.portfolio_names,
            "portfolio_ids": result.portfolio_ids
        }
        
    except ImportError as e:
        logger.error(f"[Profit Optimization] Import Error: {str(e)}")
        return {
            "success": False, 
            "error": "Missing required dependencies for profit optimization",
            "details": {
                "error_type": "ImportError",
                "description": str(e),
                "suggestion": "Please ensure scipy>=1.10.0 is installed: pip install scipy>=1.10.0"
            }
        }
    except ValueError as e:
        logger.error(f"[Profit Optimization] Value Error: {str(e)}")
        return {
            "success": False, 
            "error": "Invalid input parameters for profit optimization",
            "details": {
                "error_type": "ValueError", 
                "description": str(e),
                "suggestion": "Check that all portfolio IDs are valid and contain trading data"
            }
        }
    except MemoryError as e:
        logger.error(f"[Profit Optimization] Memory Error: {str(e)}")
        return {
            "success": False, 
            "error": "Insufficient memory for profit optimization",
            "details": {
                "error_type": "MemoryError",
                "description": "The optimization requires too much memory",
                "suggestion": "Try reducing the number of portfolios or the complexity of the optimization"
            }
        }
    except TimeoutError as e:
        logger.error(f"[Profit Optimization] Timeout Error: {str(e)}")
        return {
            "success": False, 
            "error": "Profit optimization timed out",
            "details": {
                "error_type": "TimeoutError",
                "description": "The optimization took too long to complete",
                "suggestion": "Try reducing the number of portfolios or using a simpler optimization method"
            }
        }
    except Exception as e:
        logger.error(f"[Profit Optimization] Unexpected Error: {str(e)}", exc_info=True)
        
        # Try to categorize the error based on the message
        error_message = str(e).lower()
        if "scipy" in error_message or "optimization" in error_message:
            error_type = "OptimizationError"
            suggestion = "There was an issue with the optimization algorithm. Try using a different method or reducing the complexity."
        elif "database" in error_message or "portfolio" in error_message:
            error_type = "DataError"
            suggestion = "There was an issue accessing portfolio data. Please check that the selected portfolios contain valid trading data."
        elif "memory" in error_message:
            error_type = "ResourceError"
            suggestion = "The system ran out of memory. Try selecting fewer portfolios."
        else:
            error_type = "UnknownError"
            suggestion = "An unexpected error occurred. Please try again or contact support."
        
        return {
            "success": False, 
            "error": f"Profit optimization failed: {str(e)}",
            "details": {
                "error_type": error_type,
                "description": str(e),
                "suggestion": suggestion,
                "troubleshooting": [
                    "Verify that selected portfolios contain valid trading data",
                    "Try reducing the target profit amount",
                    "Try selecting fewer portfolios (2-5 recommended)",
                    "Check the browser console for additional error details"
                ]
            }
        }