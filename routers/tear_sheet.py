"""
Tear Sheet generation using QuantStats library
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import pandas as pd
import numpy as np
import io
import logging
import tempfile
import os
from typing import Optional, Annotated
import quantstats as qs
from database import get_db
from auth_middleware import get_current_user
from models import User
from config import DEFAULT_RF_RATE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tear-sheet", tags=["tear-sheet"])


def process_csv_to_returns(csv_content: str) -> pd.Series:
    """
    Convert blended portfolio CSV to returns series for QuantStats

    Expected CSV columns:
    - Date
    - Net Liquidity
    - Daily P/L $
    - Daily P/L %
    - Current Drawdown %
    """
    try:
        # Read CSV
        df = pd.read_csv(io.StringIO(csv_content))

        # Validate required columns
        required_columns = ['Date', 'Daily P/L %']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        # Convert Date to datetime
        df['Date'] = pd.to_datetime(df['Date'])

        # Set Date as index
        df = df.set_index('Date')

        # Convert Daily P/L % to decimal returns
        # CSV has percentage (e.g., 1.5 for 1.5%), convert to decimal (0.015)
        returns = df['Daily P/L %'] / 100.0

        # Sort by date
        returns = returns.sort_index()

        # Remove any NaN values
        returns = returns.dropna()

        logger.info(f"Processed {len(returns)} return observations from {returns.index[0]} to {returns.index[-1]}")

        return returns

    except Exception as e:
        logger.error(f"Error processing CSV: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to process CSV: {str(e)}")


@router.post("/generate-from-portfolios")
async def generate_tear_sheet_from_portfolios(
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Generate QuantStats tear sheet directly from portfolio analysis parameters
    """
    try:
        from portfolio_blender import create_blended_portfolio
        import pandas as pd

        portfolio_ids = request.get('portfolio_ids', [])
        portfolio_weights = request.get('portfolio_weights', [])
        starting_capital = request.get('starting_capital', 1000000.0)
        rf_rate = request.get('rf_rate', 0.043)
        sma_window = request.get('sma_window', 20)
        use_trading_filter = request.get('use_trading_filter', True)
        date_range_start = request.get('date_range_start')
        date_range_end = request.get('date_range_end')

        logger.info(f"[Tear Sheet] Generating from {len(portfolio_ids)} portfolios")

        # Create blended portfolio
        blended_df, blended_metrics, _ = create_blended_portfolio(
            db=db,
            portfolio_ids=portfolio_ids,
            weights=portfolio_weights,
            name="Tear Sheet Analysis",
            starting_capital=starting_capital,
            rf_rate=rf_rate,
            sma_window=sma_window,
            use_trading_filter=use_trading_filter,
            date_range_start=date_range_start,
            date_range_end=date_range_end
        )

        if blended_df is None or blended_df.empty:
            raise HTTPException(status_code=400, detail="Failed to generate blended portfolio data")

        # Convert to returns series
        if 'Daily Return' not in blended_df.columns:
            raise HTTPException(status_code=400, detail="Daily Return column not found in blended data")

        returns = blended_df.set_index('Date')['Daily Return']
        returns = returns.sort_index().dropna()

        logger.info(f"[Tear Sheet] Processed {len(returns)} return observations")

        # Generate tear sheet (same logic as file upload)
        if len(returns) < 2:
            raise HTTPException(
                status_code=400,
                detail="Not enough data points. At least 2 trading days required."
            )

        # Create temporary file and generate HTML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as tmp_file:
            tmp_path = tmp_file.name

        try:
            qs.reports.html(
                returns,
                output=tmp_path,
                title=f"Blended Portfolio Performance - {len(portfolio_ids)} Strategies",
                rf=rf_rate
            )

            with open(tmp_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            logger.info(f"[Tear Sheet] Successfully generated ({len(html_content)} bytes)")

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        return JSONResponse(content={
            "success": True,
            "html": html_content,
            "stats": {
                "total_observations": len(returns),
                "start_date": returns.index[0].strftime('%Y-%m-%d'),
                "end_date": returns.index[-1].strftime('%Y-%m-%d'),
                "total_return": float((1 + returns).prod() - 1),
                "avg_daily_return": float(returns.mean()),
                "volatility": float(returns.std()),
                "sharpe_ratio": float(qs.stats.sharpe(returns).iloc[0]) if len(returns) > 1 else None,
            }
        })

    except Exception as e:
        logger.error(f"[Tear Sheet] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate tear sheet: {str(e)}")


@router.post("/generate")
async def generate_tear_sheet(
    file: UploadFile = File(...),
    rf_rate: float = Form(DEFAULT_RF_RATE)
):
    """
    Generate QuantStats tear sheet from uploaded CSV file
    """
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are supported")

        # Read file content
        content = await file.read()
        csv_content = content.decode('utf-8')

        logger.info(f"[Tear Sheet] Uploaded {file.filename}")

        # Process CSV to returns series
        returns = process_csv_to_returns(csv_content)

        if len(returns) < 2:
            raise HTTPException(
                status_code=400,
                detail="Not enough data points. At least 2 trading days required."
            )

        # Generate tear sheet using QuantStats
        logger.info(f"[Tear Sheet] Generating tear sheet for {len(returns)} observations")

        # Create a temporary file for the HTML output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as tmp_file:
            tmp_path = tmp_file.name

        try:
            # Generate the full tear sheet HTML to the temp file
            qs.reports.html(
                returns,
                output=tmp_path,
                title=f"Portfolio Performance - {file.filename}",
                rf=rf_rate
            )

            # Read the HTML content from the temp file
            with open(tmp_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            logger.info(f"[Tear Sheet] Successfully generated tear sheet ({len(html_content)} bytes)")

        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        return JSONResponse(content={
            "success": True,
            "html": html_content,
            "stats": {
                "total_observations": len(returns),
                "start_date": returns.index[0].strftime('%Y-%m-%d'),
                "end_date": returns.index[-1].strftime('%Y-%m-%d'),
                "total_return": float((1 + returns).prod() - 1),
                "avg_daily_return": float(returns.mean()),
                "volatility": float(returns.std()),
                "sharpe_ratio": float(qs.stats.sharpe(returns)) if len(returns) > 1 else None,
            }
        })

    except ValueError as e:
        logger.error(f"[Tear Sheet] Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Tear Sheet] Error generating tear sheet: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate tear sheet: {str(e)}"
        )
