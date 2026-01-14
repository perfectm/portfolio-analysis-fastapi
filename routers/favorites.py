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
    Save user's current portfolio analysis settings as a named favorite

    Expected settings:
    - name: str (REQUIRED) - unique name for this favorite
    - portfolio_ids: List[int]
    - weights: Dict[int, float]
    - starting_capital: float
    - risk_free_rate: float
    - sma_window: int
    - use_trading_filter: bool
    - date_range_start: Optional[str]
    - date_range_end: Optional[str]
    - is_default: Optional[bool] - mark as default favorite
    - tags: Optional[List[str]] - categorization tags
    """
    try:
        # Extract and validate name (REQUIRED)
        name = settings.get("name")
        if not name or not name.strip():
            raise HTTPException(status_code=400, detail="Favorite name is required")

        name = name.strip()

        # Extract settings
        portfolio_ids = settings.get("portfolio_ids", [])
        weights = settings.get("weights", {})
        starting_capital = settings.get("starting_capital", 500000.0)
        risk_free_rate = settings.get("risk_free_rate", 0.043)
        sma_window = settings.get("sma_window", 20)
        use_trading_filter = settings.get("use_trading_filter", True)
        date_range_start = settings.get("date_range_start")
        date_range_end = settings.get("date_range_end")
        is_default = settings.get("is_default", False)
        tags = settings.get("tags", [])

        # Validate
        if not portfolio_ids:
            raise HTTPException(status_code=400, detail="No portfolios selected")

        # Convert weights dict to array matching portfolio_ids order
        weights_array = [weights.get(str(pid), 1.0) for pid in portfolio_ids]

        # Convert tags to JSON
        tags_json = json.dumps(tags) if tags else None

        # If marking as default, clear other defaults first
        if is_default:
            db.query(FavoriteSettings).filter(
                FavoriteSettings.user_id == current_user.id
            ).update({"is_default": False})

        # Check if user already has a favorite with this name
        existing = db.query(FavoriteSettings).filter(
            FavoriteSettings.user_id == current_user.id,
            FavoriteSettings.name == name
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
            existing.is_default = is_default
            existing.tags = tags_json
            existing.updated_at = datetime.utcnow()

            db.commit()
            logger.info(f"Updated favorite '{name}' for user {current_user.id}")

            return {
                "success": True,
                "message": f"Favorite '{name}' updated successfully",
                "id": existing.id
            }
        else:
            # Create new
            favorite = FavoriteSettings(
                user_id=current_user.id,
                name=name,
                portfolio_ids_json=json.dumps(portfolio_ids),
                weights_json=json.dumps(weights_array),
                starting_capital=starting_capital,
                risk_free_rate=risk_free_rate,
                sma_window=sma_window,
                use_trading_filter=use_trading_filter,
                date_range_start=datetime.fromisoformat(date_range_start) if date_range_start else None,
                date_range_end=datetime.fromisoformat(date_range_end) if date_range_end else None,
                is_default=is_default,
                tags=tags_json
            )

            db.add(favorite)
            db.commit()
            db.refresh(favorite)

            logger.info(f"Created favorite '{name}' for user {current_user.id}")

            return {
                "success": True,
                "message": f"Favorite '{name}' saved successfully",
                "id": favorite.id
            }

    except HTTPException:
        raise
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
    Load ALL user's favorite portfolio analysis settings (returns array)
    """
    try:
        # Get ALL user's favorite settings, ordered by default first, then by update time
        favorites = db.query(FavoriteSettings).filter(
            FavoriteSettings.user_id == current_user.id
        ).order_by(
            FavoriteSettings.is_default.desc(),
            FavoriteSettings.updated_at.desc()
        ).all()

        if not favorites:
            return {
                "success": False,
                "message": "No favorite settings found",
                "has_favorites": False,
                "favorites": []
            }

        # Parse each favorite
        favorites_data = []
        for fav in favorites:
            portfolio_ids = json.loads(fav.portfolio_ids_json)
            weights_array = json.loads(fav.weights_json)
            tags = json.loads(fav.tags) if fav.tags else []

            # Convert weights array to dict
            weights = {str(pid): weight for pid, weight in zip(portfolio_ids, weights_array)}

            favorites_data.append({
                "id": fav.id,
                "name": fav.name,
                "is_default": fav.is_default,
                "tags": tags,
                "portfolio_ids": portfolio_ids,
                "weights": weights,
                "starting_capital": fav.starting_capital,
                "risk_free_rate": fav.risk_free_rate,
                "sma_window": fav.sma_window,
                "use_trading_filter": fav.use_trading_filter,
                "date_range_start": fav.date_range_start.isoformat() if fav.date_range_start else None,
                "date_range_end": fav.date_range_end.isoformat() if fav.date_range_end else None,
                "last_optimized": fav.last_optimized.isoformat() if fav.last_optimized else None,
                "has_new_optimization": fav.has_new_optimization,
                "created_at": fav.created_at.isoformat(),
                "updated_at": fav.updated_at.isoformat()
            })

        return {
            "success": True,
            "has_favorites": True,
            "favorites": favorites_data
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


# ==================== Multiple Favorites CRUD Endpoints ====================


@router.get("/api/favorites/list")
async def list_favorites(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    List all favorites for user (lightweight - metadata only)

    Returns minimal data for displaying in tables/dropdowns.
    """
    try:
        favorites = db.query(FavoriteSettings).filter(
            FavoriteSettings.user_id == current_user.id
        ).order_by(
            FavoriteSettings.is_default.desc(),
            FavoriteSettings.name.asc()
        ).all()

        favorites_list = []
        for fav in favorites:
            portfolio_ids = json.loads(fav.portfolio_ids_json)
            tags = json.loads(fav.tags) if fav.tags else []

            favorites_list.append({
                "id": fav.id,
                "name": fav.name,
                "is_default": fav.is_default,
                "tags": tags,
                "portfolio_count": len(portfolio_ids),
                "last_optimized": fav.last_optimized.isoformat() if fav.last_optimized else None,
                "has_new_optimization": fav.has_new_optimization,
                "created_at": fav.created_at.isoformat(),
                "updated_at": fav.updated_at.isoformat()
            })

        return {
            "success": True,
            "favorites": favorites_list
        }

    except Exception as e:
        logger.error(f"Error listing favorites: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list favorites: {str(e)}")


@router.get("/api/favorites/{favorite_id}")
async def get_favorite(
    favorite_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Get a specific favorite by ID

    Returns full favorite settings for applying to UI.
    """
    try:
        favorite = db.query(FavoriteSettings).filter(
            FavoriteSettings.id == favorite_id,
            FavoriteSettings.user_id == current_user.id  # Security: ensure user owns it
        ).first()

        if not favorite:
            raise HTTPException(status_code=404, detail="Favorite not found")

        # Parse JSON fields
        portfolio_ids = json.loads(favorite.portfolio_ids_json)
        weights_array = json.loads(favorite.weights_json)
        tags = json.loads(favorite.tags) if favorite.tags else []

        # Convert weights array to dict
        weights = {str(pid): weight for pid, weight in zip(portfolio_ids, weights_array)}

        return {
            "success": True,
            "favorite": {
                "id": favorite.id,
                "name": favorite.name,
                "is_default": favorite.is_default,
                "tags": tags,
                "portfolio_ids": portfolio_ids,
                "weights": weights,
                "starting_capital": favorite.starting_capital,
                "risk_free_rate": favorite.risk_free_rate,
                "sma_window": favorite.sma_window,
                "use_trading_filter": favorite.use_trading_filter,
                "date_range_start": favorite.date_range_start.isoformat() if favorite.date_range_start else None,
                "date_range_end": favorite.date_range_end.isoformat() if favorite.date_range_end else None,
                "last_optimized": favorite.last_optimized.isoformat() if favorite.last_optimized else None,
                "has_new_optimization": favorite.has_new_optimization,
                "created_at": favorite.created_at.isoformat(),
                "updated_at": favorite.updated_at.isoformat()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting favorite: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get favorite: {str(e)}")


@router.put("/api/favorites/{favorite_id}/name")
async def rename_favorite(
    favorite_id: int,
    data: Dict,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Rename a favorite

    Request body: {"name": "new name"}
    """
    try:
        new_name = data.get("name")
        if not new_name or not new_name.strip():
            raise HTTPException(status_code=400, detail="Name is required")

        new_name = new_name.strip()

        favorite = db.query(FavoriteSettings).filter(
            FavoriteSettings.id == favorite_id,
            FavoriteSettings.user_id == current_user.id
        ).first()

        if not favorite:
            raise HTTPException(status_code=404, detail="Favorite not found")

        # Check for duplicate name (excluding current favorite)
        existing = db.query(FavoriteSettings).filter(
            FavoriteSettings.user_id == current_user.id,
            FavoriteSettings.name == new_name,
            FavoriteSettings.id != favorite_id
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="A favorite with this name already exists")

        favorite.name = new_name
        favorite.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Renamed favorite {favorite_id} to '{new_name}' for user {current_user.id}")

        return {
            "success": True,
            "message": "Favorite renamed successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error renaming favorite: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to rename favorite: {str(e)}")


@router.put("/api/favorites/{favorite_id}/default")
async def set_default_favorite(
    favorite_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Set a favorite as the default (clears other defaults)
    """
    try:
        # Clear all defaults for user
        db.query(FavoriteSettings).filter(
            FavoriteSettings.user_id == current_user.id
        ).update({"is_default": False})

        # Set this one as default
        favorite = db.query(FavoriteSettings).filter(
            FavoriteSettings.id == favorite_id,
            FavoriteSettings.user_id == current_user.id
        ).first()

        if not favorite:
            raise HTTPException(status_code=404, detail="Favorite not found")

        favorite.is_default = True
        db.commit()

        logger.info(f"Set favorite {favorite_id} as default for user {current_user.id}")

        return {
            "success": True,
            "message": "Default favorite set successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting default favorite: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to set default: {str(e)}")


@router.put("/api/favorites/{favorite_id}/tags")
async def update_favorite_tags(
    favorite_id: int,
    data: Dict,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Update tags for a favorite

    Request body: {"tags": ["tag1", "tag2"]}
    """
    try:
        tags = data.get("tags", [])

        favorite = db.query(FavoriteSettings).filter(
            FavoriteSettings.id == favorite_id,
            FavoriteSettings.user_id == current_user.id
        ).first()

        if not favorite:
            raise HTTPException(status_code=404, detail="Favorite not found")

        favorite.tags = json.dumps(tags)
        favorite.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Updated tags for favorite {favorite_id} for user {current_user.id}")

        return {
            "success": True,
            "message": "Tags updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tags: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update tags: {str(e)}")


@router.delete("/api/favorites/{favorite_id}")
async def delete_favorite(
    favorite_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Delete a favorite
    """
    try:
        favorite = db.query(FavoriteSettings).filter(
            FavoriteSettings.id == favorite_id,
            FavoriteSettings.user_id == current_user.id
        ).first()

        if not favorite:
            raise HTTPException(status_code=404, detail="Favorite not found")

        favorite_name = favorite.name
        db.delete(favorite)
        db.commit()

        logger.info(f"Deleted favorite '{favorite_name}' (ID: {favorite_id}) for user {current_user.id}")

        return {
            "success": True,
            "message": f"Favorite '{favorite_name}' deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting favorite: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete favorite: {str(e)}")
