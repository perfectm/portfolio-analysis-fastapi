from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
from typing import Any
import logging
from database import get_db
from portfolio_service import PortfolioService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/{portfolio_id}")
async def get_portfolio_data(portfolio_id: int, db: Session = Depends(get_db)):
    try:
        portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
        if not portfolio:
            return {"error": "Portfolio not found"}
        data = PortfolioService.get_portfolio_data(db, portfolio_id, limit=1000)
        return {
            "portfolio": {
                "id": portfolio.id,
                "name": portfolio.name,
                "filename": portfolio.filename,
                "upload_date": portfolio.upload_date.isoformat(),
                "row_count": portfolio.row_count,
                "date_range_start": portfolio.date_range_start.isoformat() if portfolio.date_range_start else None,
                "date_range_end": portfolio.date_range_end.isoformat() if portfolio.date_range_end else None,
            },
            "data": [
                {
                    "date": item.date.isoformat(),
                    "pl": item.pl,
                    "cumulative_pl": item.cumulative_pl,
                    "account_value": item.account_value,
                    "daily_return": item.daily_return
                }
                for item in data
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching portfolio data: {e}")
        return {"error": str(e)}

@router.delete("/{portfolio_id}")
async def delete_portfolio(portfolio_id: int, db: Session = Depends(get_db)):
    try:
        portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
        if not portfolio:
            return {"success": False, "error": f"Portfolio with ID {portfolio_id} not found"}
        success = PortfolioService.delete_portfolio(db, portfolio_id)
        if success:
            logger.info(f"Portfolio {portfolio_id} ({portfolio.name}) deleted successfully")
            return {
                "success": True, 
                "message": f"Portfolio '{portfolio.name}' deleted successfully",
                "portfolio_id": portfolio_id
            }
        else:
            return {"success": False, "error": "Failed to delete portfolio"}
    except Exception as e:
        logger.error(f"Error deleting portfolio {portfolio_id}: {e}")
        return {"success": False, "error": str(e)}

@router.put("/{portfolio_id}/name")
async def update_portfolio_name(portfolio_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
        new_name = body.get("name", "").strip()
        if not new_name:
            return {"success": False, "error": "Portfolio name cannot be empty"}
        if len(new_name) > 255:
            return {"success": False, "error": "Portfolio name too long (max 255 characters)"}
        portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
        if not portfolio:
            return {"success": False, "error": f"Portfolio with ID {portfolio_id} not found"}
        old_name = portfolio.name
        success = PortfolioService.update_portfolio_name(db, portfolio_id, new_name)
        if success:
            logger.info(f"Portfolio {portfolio_id} name updated from '{old_name}' to '{new_name}'")
            return {
                "success": True, 
                "message": f"Portfolio name updated from '{old_name}' to '{new_name}'",
                "portfolio_id": portfolio_id,
                "old_name": old_name,
                "new_name": new_name
            }
        else:
            return {"success": False, "error": "Failed to update portfolio name"}
    except Exception as e:
        logger.error(f"Error updating portfolio {portfolio_id} name: {e}")
        return {"success": False, "error": str(e)}

@router.put("/{portfolio_id}/strategy")
async def update_portfolio_strategy(portfolio_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
        new_strategy = body.get("strategy", "").strip()
        if len(new_strategy) > 255:
            return {"success": False, "error": "Strategy description too long (max 255 characters)"}
        portfolio = PortfolioService.get_portfolio_by_id(db, portfolio_id)
        if not portfolio:
            return {"success": False, "error": f"Portfolio with ID {portfolio_id} not found"}
        old_strategy = portfolio.strategy
        success = PortfolioService.update_portfolio_strategy(db, portfolio_id, new_strategy)
        if success:
            logger.info(f"Portfolio {portfolio_id} strategy updated from '{old_strategy}' to '{new_strategy}'")
            return {
                "success": True, 
                "message": f"Portfolio strategy updated",
                "portfolio_id": portfolio_id,
                "old_strategy": old_strategy,
                "new_strategy": new_strategy
            }
        else:
            return {"success": False, "error": "Failed to update portfolio strategy"}
    except Exception as e:
        logger.error(f"Error updating portfolio {portfolio_id} strategy: {e}")
        return {"success": False, "error": str(e)} 