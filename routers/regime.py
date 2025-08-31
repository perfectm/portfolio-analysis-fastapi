"""
Regime Analysis API Routes
Endpoints for market regime detection, analysis, and recommendations
"""

import json
import logging
from datetime import datetime
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from regime_service import RegimeService
from models import MarketRegimeHistory, RegimePerformance, RegimeAlert

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/regime", tags=["regime"])


# Pydantic models
class RegimeClassificationResponse(BaseModel):
    regime: str
    confidence: float
    indicators: Dict[str, float]
    detected_at: datetime
    description: str


class RegimeHistoryResponse(BaseModel):
    id: int
    date: datetime
    regime: str
    confidence: float
    volatility_percentile: Optional[float]
    trend_strength: Optional[float]
    momentum_score: Optional[float]
    drawdown_severity: Optional[float]
    volume_anomaly: Optional[float]
    description: Optional[str]


class RegimePerformanceResponse(BaseModel):
    portfolio_id: int
    portfolio_name: str
    regime_performance: Dict[str, Dict[str, float]]


class AllocationRecommendationResponse(BaseModel):
    current_regime: str
    confidence: float
    recommendations: Dict[str, float]
    reasoning: str


class RegimeAlertResponse(BaseModel):
    id: int
    alert_type: str
    previous_regime: Optional[str]
    new_regime: str
    confidence: float
    title: str
    message: str
    severity: str
    recommended_allocations: Dict[str, float]
    created_at: datetime
    is_active: bool


class PortfolioIdsRequest(BaseModel):
    portfolio_ids: List[int]


# Initialize service
regime_service = RegimeService()


@router.get("/current", response_model=RegimeClassificationResponse)
async def get_current_regime(
    symbol: str = Query("^GSPC", description="Market symbol to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get current market regime classification
    
    Returns the latest regime classification with confidence score and indicators.
    """
    try:
        # Try to get from database first
        current = regime_service.get_current_regime(db, symbol)
        
        if current and (datetime.now() - current.created_at).seconds < 3600:  # Less than 1 hour old
            return RegimeClassificationResponse(
                regime=current.regime,
                confidence=current.confidence,
                indicators={
                    "volatility_percentile": current.volatility_percentile or 0,
                    "trend_strength": current.trend_strength or 0,
                    "momentum_score": current.momentum_score or 0,
                    "drawdown_severity": current.drawdown_severity or 0,
                    "volume_anomaly": current.volume_anomaly or 0
                },
                detected_at=current.date,
                description=current.description or f"Current market regime: {current.regime}"
            )
        
        # Detect fresh regime
        classification = regime_service.detect_and_store_current_regime(db, symbol)
        
        return RegimeClassificationResponse(
            regime=classification.regime.value,
            confidence=classification.confidence,
            indicators=classification.indicators,
            detected_at=classification.detected_at,
            description=classification.description
        )
        
    except Exception as e:
        logger.error(f"Failed to get current regime: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze market regime: {str(e)}")


@router.get("/history", response_model=List[RegimeHistoryResponse])
async def get_regime_history(
    days: int = Query(90, ge=1, le=365, description="Number of days of history to retrieve"),
    symbol: str = Query("^GSPC", description="Market symbol"),
    db: Session = Depends(get_db)
):
    """
    Get historical market regime classifications
    
    Returns regime history for the specified time period.
    """
    try:
        history = regime_service.get_regime_history(db, days, symbol)
        
        return [
            RegimeHistoryResponse(
                id=record.id,
                date=record.date,
                regime=record.regime,
                confidence=record.confidence,
                volatility_percentile=record.volatility_percentile,
                trend_strength=record.trend_strength,
                momentum_score=record.momentum_score,
                drawdown_severity=record.drawdown_severity,
                volume_anomaly=record.volume_anomaly,
                description=record.description
            )
            for record in history
        ]
        
    except Exception as e:
        logger.error(f"Failed to get regime history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve regime history: {str(e)}")


@router.post("/analyze-portfolio/{portfolio_id}", response_model=RegimePerformanceResponse)
async def analyze_portfolio_regime_performance(
    portfolio_id: int,
    db: Session = Depends(get_db)
):
    """
    Analyze how a specific portfolio performs in different market regimes
    
    Calculates performance metrics for each regime type (bull, bear, volatile, transitioning).
    """
    try:
        # Get portfolio
        from models import Portfolio
        portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if not portfolio:
            raise HTTPException(status_code=404, detail=f"Portfolio {portfolio_id} not found")
        
        # Calculate regime performance
        performance = regime_service.calculate_strategy_regime_performance(db, portfolio_id)
        
        return RegimePerformanceResponse(
            portfolio_id=portfolio_id,
            portfolio_name=portfolio.name,
            regime_performance=performance
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze portfolio regime performance: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze performance: {str(e)}")


@router.post("/recommendations", response_model=AllocationRecommendationResponse)
async def get_allocation_recommendations(
    request: PortfolioIdsRequest,
    db: Session = Depends(get_db)
):
    """
    Get regime-optimized allocation recommendations
    
    Returns recommended portfolio allocations based on current market regime
    and historical performance of each strategy in similar conditions.
    """
    try:
        if not request.portfolio_ids:
            raise HTTPException(status_code=400, detail="At least one portfolio ID required")
        
        # Validate portfolios exist
        from models import Portfolio
        portfolios = db.query(Portfolio).filter(Portfolio.id.in_(request.portfolio_ids)).all()
        found_ids = {p.id for p in portfolios}
        missing_ids = set(request.portfolio_ids) - found_ids
        
        if missing_ids:
            raise HTTPException(status_code=404, detail=f"Portfolios not found: {list(missing_ids)}")
        
        # Get current regime
        current_regime = regime_service.get_current_regime(db)
        if not current_regime:
            raise HTTPException(status_code=503, detail="No current regime data available")
        
        # Get recommendations
        recommendations = regime_service.get_regime_allocation_recommendations(db, request.portfolio_ids)
        
        # Generate reasoning
        reasoning = f"Based on current {current_regime.regime} market conditions with {current_regime.confidence:.1%} confidence. "
        
        if current_regime.regime == "bull":
            reasoning += "Favoring momentum strategies with strong upside potential."
        elif current_regime.regime == "bear":
            reasoning += "Emphasizing defensive strategies with lower drawdown risk."
        elif current_regime.regime == "volatile":
            reasoning += "Prioritizing low-volatility strategies for stability."
        else:
            reasoning += "Using balanced allocation during transitional market conditions."
        
        return AllocationRecommendationResponse(
            current_regime=current_regime.regime,
            confidence=current_regime.confidence,
            recommendations=recommendations,
            reasoning=reasoning
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get allocation recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {str(e)}")


@router.get("/alerts", response_model=List[RegimeAlertResponse])
async def get_active_alerts(db: Session = Depends(get_db)):
    """
    Get active regime change alerts
    
    Returns all active alerts about regime changes and rebalancing recommendations.
    """
    try:
        alerts = regime_service.get_active_alerts(db)
        
        result = []
        for alert in alerts:
            # Parse recommended allocations JSON
            recommended_allocations = {}
            if alert.recommended_allocations:
                try:
                    recommended_allocations = json.loads(alert.recommended_allocations)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse recommended allocations for alert {alert.id}")
            
            result.append(RegimeAlertResponse(
                id=alert.id,
                alert_type=alert.alert_type,
                previous_regime=alert.previous_regime,
                new_regime=alert.new_regime,
                confidence=alert.confidence,
                title=alert.title,
                message=alert.message,
                severity=alert.severity,
                recommended_allocations=recommended_allocations,
                created_at=alert.created_at,
                is_active=alert.is_active
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get active alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve alerts: {str(e)}")


@router.post("/alerts/{alert_id}/dismiss")
async def dismiss_alert(
    alert_id: int,
    db: Session = Depends(get_db)
):
    """
    Dismiss a regime alert
    
    Marks the specified alert as dismissed and inactive.
    """
    try:
        success = regime_service.dismiss_alert(db, alert_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
        
        return {"message": "Alert dismissed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to dismiss alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to dismiss alert: {str(e)}")


@router.post("/detect-and-alert")
async def detect_regime_and_create_alerts(
    symbol: str = Query("^GSPC", description="Market symbol to analyze"),
    db: Session = Depends(get_db)
):
    """
    Detect current regime and create alerts if regime has changed
    
    This endpoint can be called periodically (e.g., daily) to monitor regime changes
    and automatically generate alerts when market conditions shift.
    """
    try:
        # Get previous regime
        previous_regime = regime_service.get_current_regime(db, symbol)
        previous_regime_name = previous_regime.regime if previous_regime else None
        
        # Detect current regime
        current_classification = regime_service.detect_and_store_current_regime(db, symbol)
        
        # Check if regime changed
        if (not previous_regime or 
            previous_regime.regime != current_classification.regime.value or
            abs(previous_regime.confidence - current_classification.confidence) > 0.2):
            
            # Get all portfolios for recommendations
            from models import Portfolio
            all_portfolios = db.query(Portfolio).all()
            portfolio_ids = [p.id for p in all_portfolios]
            
            if portfolio_ids:
                # Get allocation recommendations
                recommendations = regime_service.get_regime_allocation_recommendations(db, portfolio_ids)
                
                # Create alert
                alert = regime_service.create_regime_change_alert(
                    db,
                    previous_regime_name,
                    current_classification.regime.value,
                    current_classification.confidence,
                    recommendations
                )
                
                return {
                    "regime_changed": True,
                    "previous_regime": previous_regime_name,
                    "new_regime": current_classification.regime.value,
                    "confidence": current_classification.confidence,
                    "alert_created": True,
                    "alert_id": alert.id
                }
            else:
                return {
                    "regime_changed": True,
                    "previous_regime": previous_regime_name,
                    "new_regime": current_classification.regime.value,
                    "confidence": current_classification.confidence,
                    "alert_created": False,
                    "message": "No portfolios available for recommendations"
                }
        else:
            return {
                "regime_changed": False,
                "current_regime": current_classification.regime.value,
                "confidence": current_classification.confidence,
                "alert_created": False
            }
            
    except Exception as e:
        logger.error(f"Failed to detect regime and create alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process regime detection: {str(e)}")


@router.get("/performance-summary")
async def get_regime_performance_summary(
    db: Session = Depends(get_db)
):
    """
    Get performance summary across all portfolios and regimes
    
    Returns aggregate performance metrics to help understand which strategies
    work best in which market conditions.
    """
    try:
        from models import Portfolio
        from sqlalchemy import func
        
        # Get all regime performance records with portfolio names
        results = db.query(
            RegimePerformance,
            Portfolio.name.label('portfolio_name')
        ).join(
            Portfolio, RegimePerformance.portfolio_id == Portfolio.id
        ).all()
        
        if not results:
            return {"message": "No regime performance data available"}
        
        # Organize by regime
        summary = {}
        for regime_perf, portfolio_name in results:
            regime = regime_perf.regime
            if regime not in summary:
                summary[regime] = {
                    "strategies": [],
                    "avg_sharpe_ratio": 0,
                    "avg_total_return": 0,
                    "avg_max_drawdown": 0,
                    "best_strategy": "",
                    "worst_strategy": ""
                }
            
            strategy_data = {
                "name": portfolio_name,
                "total_return": regime_perf.total_return,
                "sharpe_ratio": regime_perf.sharpe_ratio,
                "max_drawdown": regime_perf.max_drawdown,
                "volatility": regime_perf.volatility,
                "win_rate": regime_perf.win_rate
            }
            
            summary[regime]["strategies"].append(strategy_data)
        
        # Calculate averages and best/worst for each regime
        for regime, data in summary.items():
            strategies = data["strategies"]
            if strategies:
                data["avg_sharpe_ratio"] = sum(s["sharpe_ratio"] for s in strategies) / len(strategies)
                data["avg_total_return"] = sum(s["total_return"] for s in strategies) / len(strategies)
                data["avg_max_drawdown"] = sum(s["max_drawdown"] for s in strategies) / len(strategies)
                
                # Find best and worst by Sharpe ratio
                best = max(strategies, key=lambda x: x["sharpe_ratio"])
                worst = min(strategies, key=lambda x: x["sharpe_ratio"])
                data["best_strategy"] = best["name"]
                data["worst_strategy"] = worst["name"]
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get regime performance summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")