from fastapi import APIRouter, UploadFile, File, Form, Depends
from starlette.formparsers import MultiPartParser
from sqlalchemy.orm import Session
import logging
import pandas as pd

from config import DEFAULT_STARTING_CAPITAL, POSITION_NAME_COLUMNS
from database import get_db
from portfolio_service import PortfolioService
from portfolio_processor import extract_margin_data_from_df
from margin_service import MarginService
from rolling_period_service import RollingPeriodService

# Increase max upload size to 50MB (default is 1MB)
MultiPartParser.max_file_size = 50 * 1024 * 1024

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("")
async def mega_upload(
    file: UploadFile = File(...),
    starting_capital: float = Form(DEFAULT_STARTING_CAPITAL),
    db: Session = Depends(get_db)
):
    """
    Upload a single CSV file containing multiple portfolios.
    A 'Position Name' column determines which portfolio each row belongs to.
    Each unique Position Name value becomes a separate portfolio.
    """
    try:
        logger.info(f"[Mega Upload] Received file: {file.filename}")
        contents = await file.read()
        df = pd.read_csv(pd.io.common.BytesIO(contents))
        logger.info(f"[Mega Upload] Parsed CSV with shape {df.shape}")

        # Detect Position Name column
        position_col = None
        for col in POSITION_NAME_COLUMNS:
            if col in df.columns:
                position_col = col
                break

        if position_col is None:
            return {
                "success": False,
                "error": f"No Position Name column found. Expected one of: {POSITION_NAME_COLUMNS}. "
                         f"Available columns: {df.columns.tolist()}"
            }

        unique_positions = df[position_col].dropna().unique()
        logger.info(f"[Mega Upload] Found {len(unique_positions)} unique positions: {list(unique_positions)}")

        # Use filename (without extension) as the strategy name so all portfolios are grouped together
        strategy_name = file.filename.replace('.csv', '').replace('.CSV', '').replace('_', ' ').strip()

        created = []
        updated = []
        errors = []

        for position_name in unique_positions:
            position_name_str = str(position_name).strip()
            if not position_name_str:
                continue

            try:
                # Filter rows for this position
                sub_df = df[df[position_col] == position_name].copy()
                # Drop the Position Name column before storing
                sub_df = sub_df.drop(columns=[position_col])

                logger.info(f"[Mega Upload] Processing '{position_name_str}' with {len(sub_df)} rows")

                # Convert sub_df to bytes for create/update portfolio
                sub_contents = sub_df.to_csv(index=False).encode('utf-8')

                # Check if portfolio with this name already exists
                existing_portfolio = PortfolioService.get_portfolio_by_name(db, position_name_str)

                if existing_portfolio:
                    portfolio = PortfolioService.update_portfolio_data(
                        db, existing_portfolio.id, file.filename, sub_contents, sub_df
                    )
                    logger.info(f"[Mega Upload] Updated existing portfolio '{position_name_str}' (ID: {portfolio.id})")
                    updated.append({"id": portfolio.id, "name": position_name_str})
                else:
                    portfolio = PortfolioService.create_portfolio(
                        db, position_name_str, file.filename, sub_contents, sub_df
                    )
                    logger.info(f"[Mega Upload] Created new portfolio '{position_name_str}' (ID: {portfolio.id})")
                    created.append({"id": portfolio.id, "name": position_name_str})

                # Set strategy field to filename so all portfolios from this file are grouped together
                PortfolioService.update_portfolio_strategy(db, portfolio.id, strategy_name)

                # Store portfolio data rows
                PortfolioService.store_portfolio_data(db, portfolio.id, sub_df)

                # Extract and store margin data if present
                try:
                    margin_df = extract_margin_data_from_df(sub_df)
                    if not margin_df.empty:
                        success = MarginService.store_margin_data(db, portfolio.id, margin_df)
                        if success:
                            logger.info(f"[Mega Upload] Stored {len(margin_df)} margin records for '{position_name_str}'")
                except Exception as margin_error:
                    logger.warning(f"[Mega Upload] Error extracting margin data for '{position_name_str}': {margin_error}")

                # Calculate rolling period stats
                try:
                    success = RollingPeriodService.calculate_and_store_rolling_stats(
                        db, portfolio.id, period_length_days=90, starting_capital=starting_capital
                    )
                    if success:
                        logger.info(f"[Mega Upload] Calculated rolling stats for '{position_name_str}'")
                except Exception as rolling_error:
                    logger.warning(f"[Mega Upload] Error calculating rolling stats for '{position_name_str}': {rolling_error}")

            except Exception as e:
                error_msg = f"Error processing position '{position_name_str}': {str(e)}"
                logger.error(f"[Mega Upload] {error_msg}", exc_info=True)
                errors.append({"name": position_name_str, "error": str(e)})

        logger.info(f"[Mega Upload] Complete: {len(created)} created, {len(updated)} updated, {len(errors)} errors")

        return {
            "success": True,
            "message": f"Processed {len(unique_positions)} portfolios from {file.filename}",
            "created": created,
            "updated": updated,
            "errors": errors,
            "total_positions": len(unique_positions)
        }

    except Exception as e:
        error_msg = f"Unexpected error in mega_upload: {str(e)}"
        logger.error(f"[Mega Upload] {error_msg}", exc_info=True)
        return {"success": False, "error": error_msg}
