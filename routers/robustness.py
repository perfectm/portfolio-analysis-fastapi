"""
API router for portfolio robustness testing
"""
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from database import get_db
from robustness_service import RobustnessTestService

logger = logging.getLogger(__name__)

router = APIRouter()


class RobustnessTestRequest(BaseModel):
    """Request model for creating a robustness test"""
    num_periods: int = Field(default=10, ge=5, le=50, description="Number of random periods to test")
    period_length_days: int = Field(default=252, ge=30, le=1000, description="Length of each test period in days")
    rf_rate: float = Field(default=0.043, ge=0, le=1, description="Risk-free rate")
    sma_window: int = Field(default=20, ge=1, le=100, description="SMA window for analysis")
    use_trading_filter: bool = Field(default=True, description="Whether to use trading filter")
    starting_capital: float = Field(default=1000000, gt=0, description="Starting capital for analysis")


class RobustnessTestResponse(BaseModel):
    """Response model for robustness test creation"""
    test_id: int
    portfolio_id: int
    status: str
    message: str


def run_robustness_test_background(test_id: int, db: Session):
    """Background task to run robustness test"""
    try:
        service = RobustnessTestService(db)
        service.run_robustness_test(test_id)
        logger.info(f"Completed robustness test {test_id}")
    except Exception as e:
        logger.error(f"Failed to complete robustness test {test_id}: {e}")


@router.get("/portfolios", response_model=List[Dict[str, Any]])
async def get_available_portfolios(
    period_length: Optional[int] = 30,
    db: Session = Depends(get_db)
):
    """
    Get all portfolios available for robustness testing with metadata
    
    Args:
        period_length: Minimum period length in days to check eligibility (default: 30)
    """
    try:
        service = RobustnessTestService(db)
        portfolios = service.get_available_portfolios(min_period_days=period_length or 30)
        return portfolios
    except Exception as e:
        logger.error(f"Error getting available portfolios: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve portfolios")


@router.post("/{portfolio_id}/test", response_model=RobustnessTestResponse)
async def create_robustness_test(
    portfolio_id: int,
    request: RobustnessTestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create and start a robustness test for a portfolio
    """
    try:
        service = RobustnessTestService(db)
        
        # Create the test
        test = service.create_robustness_test(
            portfolio_id=portfolio_id,
            num_periods=request.num_periods,
            period_length_days=request.period_length_days,
            rf_rate=request.rf_rate,
            sma_window=request.sma_window,
            use_trading_filter=request.use_trading_filter,
            starting_capital=request.starting_capital
        )
        
        # Start the test in the background
        background_tasks.add_task(run_robustness_test_background, test.id, db)
        
        return RobustnessTestResponse(
            test_id=test.id,
            portfolio_id=portfolio_id,
            status=test.status,
            message=f"Robustness test started with {request.num_periods} periods"
        )
        
    except ValueError as e:
        logger.warning(f"Invalid request for robustness test: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating robustness test: {e}")
        raise HTTPException(status_code=500, detail="Failed to create robustness test")


@router.get("/test/{test_id}/status")
async def get_test_status(test_id: int, db: Session = Depends(get_db)):
    """
    Get the current status and progress of a robustness test
    """
    try:
        service = RobustnessTestService(db)
        
        # Get basic test info
        from models import RobustnessTest
        test = db.query(RobustnessTest).filter(RobustnessTest.id == test_id).first()
        
        if not test:
            raise HTTPException(status_code=404, detail="Robustness test not found")
        
        return {
            "test_id": test.id,
            "portfolio_id": test.portfolio_id,
            "status": test.status,
            "progress": test.progress,
            "overall_robustness_score": test.overall_robustness_score,
            "error_message": test.error_message,
            "created_at": test.created_at.isoformat() if test.created_at else None,
            "completed_at": test.completed_at.isoformat() if test.completed_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting test status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get test status")


@router.get("/test/{test_id}/results")
async def get_test_results(test_id: int, db: Session = Depends(get_db)):
    """
    Get comprehensive results for a completed robustness test
    """
    try:
        service = RobustnessTestService(db)
        results = service.get_test_results(test_id)
        
        if not results:
            raise HTTPException(status_code=404, detail="Robustness test not found")
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting test results: {e}")
        raise HTTPException(status_code=500, detail="Failed to get test results")


@router.get("/test/{test_id}/periods")
async def get_test_periods(test_id: int, db: Session = Depends(get_db)):
    """
    Get individual period results for detailed analysis
    """
    try:
        from models import RobustnessPeriod
        
        periods = db.query(RobustnessPeriod).filter(
            RobustnessPeriod.robustness_test_id == test_id
        ).order_by(RobustnessPeriod.period_number).all()
        
        if not periods:
            raise HTTPException(status_code=404, detail="No periods found for this test")
        
        return [
            {
                "period_number": period.period_number,
                "start_date": period.start_date.isoformat(),
                "end_date": period.end_date.isoformat(),
                "cagr": period.cagr,
                "sharpe_ratio": period.sharpe_ratio,
                "sortino_ratio": period.sortino_ratio,
                "max_drawdown": period.max_drawdown,
                "max_drawdown_percent": period.max_drawdown_percent,
                "volatility": period.volatility,
                "win_rate": period.win_rate,
                "profit_factor": period.profit_factor,
                "total_return": period.total_return,
                "total_pl": period.total_pl,
                "trade_count": period.trade_count,
                "winning_trades": period.winning_trades,
                "losing_trades": period.losing_trades
            }
            for period in periods
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting test periods: {e}")
        raise HTTPException(status_code=500, detail="Failed to get test periods")


@router.delete("/test/{test_id}")
async def delete_robustness_test(test_id: int, db: Session = Depends(get_db)):
    """
    Delete a robustness test and all associated data
    """
    try:
        service = RobustnessTestService(db)
        success = service.delete_test(test_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Robustness test not found")
        
        return {"message": "Robustness test deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting test: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete robustness test")


@router.get("/portfolio/{portfolio_id}/tests")
async def get_portfolio_tests(portfolio_id: int, db: Session = Depends(get_db)):
    """
    Get all robustness tests for a specific portfolio
    """
    try:
        service = RobustnessTestService(db)
        tests = service.get_portfolio_tests(portfolio_id)
        return tests
        
    except Exception as e:
        logger.error(f"Error getting portfolio tests: {e}")
        raise HTTPException(status_code=500, detail="Failed to get portfolio tests")


@router.get("/portfolio/{portfolio_id}/metrics")
async def get_portfolio_full_metrics(portfolio_id: int, db: Session = Depends(get_db)):
    """
    Get full dataset metrics for a portfolio (for comparison)
    """
    try:
        service = RobustnessTestService(db)
        metrics = service._get_full_dataset_metrics(portfolio_id)
        
        if not metrics:
            raise HTTPException(status_code=404, detail="Portfolio not found or no metrics available")
        
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting portfolio metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get portfolio metrics")


