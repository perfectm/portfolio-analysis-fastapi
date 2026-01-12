"""
API endpoints for managing user's favorite portfolio settings
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import FavoriteSettings, User
from typing import Dict, Annotated
import json
import logging
from datetime import datetime
from auth_middleware import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/api/favorites/save")
async def save_favorite_settings(
    settings: Dict,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Save user's current portfolio analysis settings as favorites

    Expected settings:
    - portfolio_ids: List[int]
    - weights: Dict[int, float]
    - starting_capital: float
    - risk_free_rate: float
    - sma_window: int
    - use_trading_filter: bool
    - date_range_start: Optional[str]
    - date_range_end: Optional[str]
    """
    try:
        # Extract settings
        portfolio_ids = settings.get("portfolio_ids", [])
        weights = settings.get("weights", {})
        starting_capital = settings.get("starting_capital", 500000.0)
        risk_free_rate = settings.get("risk_free_rate", 0.043)
        sma_window = settings.get("sma_window", 20)
        use_trading_filter = settings.get("use_trading_filter", True)
        date_range_start = settings.get("date_range_start")
        date_range_end = settings.get("date_range_end")

        # Validate
        if not portfolio_ids:
            raise HTTPException(status_code=400, detail="No portfolios selected")

        # Convert weights dict to array matching portfolio_ids order
        weights_array = [weights.get(str(pid), 1.0) for pid in portfolio_ids]

        # Check if user already has favorite settings
        existing = db.query(FavoriteSettings).filter(
            FavoriteSettings.user_id == current_user.id
        ).first()

        if existing:
            # Update existing
            existing.portfolio_ids_json = json.dumps(portfolio_ids)
            existing.weights_json = json.dumps(weights_array)
            existing.starting_capital = starting_capital
            existing.risk_free_rate = risk_free_rate
            existing.sma_window = sma_window
            existing.use_trading_filter = use_trading_filter
            existing.date_range_start = datetime.fromisoformat(date_range_start) if date_range_start else None
            existing.date_range_end = datetime.fromisoformat(date_range_end) if date_range_end else None
            existing.updated_at = datetime.utcnow()

            db.commit()
            logger.info(f"Updated favorite settings for user {current_user.id}")

            return {
                "success": True,
                "message": "Favorite settings updated successfully",
                "id": existing.id
            }
        else:
            # Create new
            favorite = FavoriteSettings(
                user_id=current_user.id,
                name="My Favorite Settings",
                portfolio_ids_json=json.dumps(portfolio_ids),
                weights_json=json.dumps(weights_array),
                starting_capital=starting_capital,
                risk_free_rate=risk_free_rate,
                sma_window=sma_window,
                use_trading_filter=use_trading_filter,
                date_range_start=datetime.fromisoformat(date_range_start) if date_range_start else None,
                date_range_end=datetime.fromisoformat(date_range_end) if date_range_end else None
            )

            db.add(favorite)
            db.commit()
            db.refresh(favorite)

            logger.info(f"Created favorite settings for user {current_user.id}")

            return {
                "success": True,
                "message": "Favorite settings saved successfully",
                "id": favorite.id
            }

    except Exception as e:
        logger.error(f"Error saving favorite settings: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")

@router.get("/api/favorites/load")
async def load_favorite_settings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Load user's favorite portfolio analysis settings
    """
    try:
        # Get user's favorite settings
        favorite = db.query(FavoriteSettings).filter(
            FavoriteSettings.user_id == current_user.id
        ).first()

        if not favorite:
            return {
                "success": False,
                "message": "No favorite settings found",
                "has_favorites": False
            }

        # Parse JSON fields
        portfolio_ids = json.loads(favorite.portfolio_ids_json)
        weights_array = json.loads(favorite.weights_json)

        # Convert weights array to dict
        weights = {str(pid): weight for pid, weight in zip(portfolio_ids, weights_array)}

        return {
            "success": True,
            "has_favorites": True,
            "settings": {
                "portfolio_ids": portfolio_ids,
                "weights": weights,
                "starting_capital": favorite.starting_capital,
                "risk_free_rate": favorite.risk_free_rate,
                "sma_window": favorite.sma_window,
                "use_trading_filter": favorite.use_trading_filter,
                "date_range_start": favorite.date_range_start.isoformat() if favorite.date_range_start else None,
                "date_range_end": favorite.date_range_end.isoformat() if favorite.date_range_end else None
            },
            "saved_at": favorite.updated_at.isoformat()
        }

    except Exception as e:
        logger.error(f"Error loading favorite settings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to load settings: {str(e)}")

@router.get("/api/favorites/optimization-status")
async def get_optimization_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Check if there's a new optimization available for the user's favorites

    Returns:
    - has_new_optimization: bool
    - optimized_weights: array (if available)
    - optimization_method: string (if available)
    - last_optimized: timestamp (if available)
    """
    try:
        favorite = db.query(FavoriteSettings).filter(
            FavoriteSettings.user_id == current_user.id
        ).first()

        if not favorite:
            return {
                "success": True,
                "has_new_optimization": False,
                "message": "No favorite settings found"
            }

        # Check if there's a new optimization
        if not favorite.has_new_optimization or not favorite.optimized_weights_json:
            return {
                "success": True,
                "has_new_optimization": False,
                "last_optimized": favorite.last_optimized.isoformat() if favorite.last_optimized else None
            }

        # Parse optimized weights
        optimized_weights = json.loads(favorite.optimized_weights_json)
        portfolio_ids = json.loads(favorite.portfolio_ids_json)

        # Convert to dict format for frontend
        weights_dict = {str(pid): weight for pid, weight in zip(portfolio_ids, optimized_weights)}

        return {
            "success": True,
            "has_new_optimization": True,
            "optimized_weights": weights_dict,
            "optimized_weights_array": optimized_weights,
            "optimization_method": favorite.optimization_method,
            "last_optimized": favorite.last_optimized.isoformat() if favorite.last_optimized else None,
            "portfolio_ids": portfolio_ids
        }

    except Exception as e:
        logger.error(f"Error checking optimization status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to check optimization status: {str(e)}")

@router.post("/api/favorites/mark-optimization-seen")
async def mark_optimization_seen(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Mark the new optimization as seen by the user (dismisses the UI alert)
    """
    try:
        favorite = db.query(FavoriteSettings).filter(
            FavoriteSettings.user_id == current_user.id
        ).first()

        if not favorite:
            raise HTTPException(status_code=404, detail="No favorite settings found")

        # Clear the new optimization flag
        favorite.has_new_optimization = False
        db.commit()

        logger.info(f"Marked optimization as seen for user {current_user.id}")

        return {
            "success": True,
            "message": "Optimization marked as seen"
        }

    except Exception as e:
        logger.error(f"Error marking optimization as seen: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to mark as seen: {str(e)}")

@router.post("/api/favorites/apply-optimized-weights")
async def apply_optimized_weights(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Apply the optimized weights to the user's favorite settings
    (copies optimized_weights_json to weights_json)
    """
    try:
        favorite = db.query(FavoriteSettings).filter(
            FavoriteSettings.user_id == current_user.id
        ).first()

        if not favorite:
            raise HTTPException(status_code=404, detail="No favorite settings found")

        if not favorite.optimized_weights_json:
            raise HTTPException(status_code=400, detail="No optimized weights available")

        # Apply optimized weights
        favorite.weights_json = favorite.optimized_weights_json
        favorite.has_new_optimization = False  # Also clear the flag
        favorite.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Applied optimized weights for user {current_user.id}")

        # Parse and return the applied weights
        weights_array = json.loads(favorite.optimized_weights_json)
        portfolio_ids = json.loads(favorite.portfolio_ids_json)
        weights_dict = {str(pid): weight for pid, weight in zip(portfolio_ids, weights_array)}

        return {
            "success": True,
            "message": "Optimized weights applied successfully",
            "weights": weights_dict
        }

    except Exception as e:
        logger.error(f"Error applying optimized weights: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to apply weights: {str(e)}")
