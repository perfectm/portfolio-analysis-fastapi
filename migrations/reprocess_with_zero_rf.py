"""
Migration script to reprocess all portfolios with RF=0% and margin-based starting capital.

This creates new cached analysis results for each portfolio using:
- Risk-free rate: 0%
- Starting capital: 3x max daily margin (or fallback to $100,000 if no margin data)

Run with: python migrations/reprocess_with_zero_rf.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file if it exists (for production DATABASE_URL)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(env_path):
    print(f"Loading environment from {env_path}")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

from database import SessionLocal
from models import Portfolio, PortfolioMarginData, AnalysisResult, PortfolioData
from portfolio_service import PortfolioService
from portfolio_processor import process_portfolio_data
from sqlalchemy import func
import pandas as pd
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
RF_RATE = 0.0  # Zero risk-free rate
MARGIN_MULTIPLIER = 3.0  # 3x margin for starting capital
DEFAULT_STARTING_CAPITAL = 100000.0  # Fallback if no margin data
SMA_WINDOW = 20
USE_TRADING_FILTER = True


def get_portfolio_margin_capital(db, portfolio_id: int) -> tuple:
    """Get margin-based starting capital for a portfolio."""
    # Get max daily margin for this portfolio
    daily_totals_subquery = db.query(
        PortfolioMarginData.date,
        func.sum(PortfolioMarginData.margin_requirement).label('daily_total')
    ).filter(
        PortfolioMarginData.portfolio_id == portfolio_id
    ).group_by(PortfolioMarginData.date).subquery()

    max_daily_total = db.query(
        func.max(daily_totals_subquery.c.daily_total)
    ).scalar()

    if max_daily_total and float(max_daily_total) > 0:
        max_margin = float(max_daily_total)
        starting_capital = max_margin * MARGIN_MULTIPLIER
        return starting_capital, max_margin, True
    else:
        return DEFAULT_STARTING_CAPITAL, 0.0, False


def get_raw_portfolio_data(db, portfolio_id: int) -> pd.DataFrame:
    """Get raw portfolio data (Date, P/L) without any processing."""
    # Query raw data from database
    data = db.query(PortfolioData).filter(
        PortfolioData.portfolio_id == portfolio_id
    ).order_by(PortfolioData.date).all()

    if not data:
        return pd.DataFrame()

    # Create DataFrame with just the essential columns
    df = pd.DataFrame([{
        'Date': record.date,
        'P/L': record.pl
    } for record in data])

    return df


def reprocess_portfolio(db, portfolio: Portfolio) -> bool:
    """Reprocess a single portfolio with RF=0% and margin-based capital."""
    try:
        # Get RAW portfolio data (without any processing)
        df = get_raw_portfolio_data(db, portfolio.id)

        if df.empty:
            logger.warning(f"Portfolio {portfolio.id} ({portfolio.name}): No data found, skipping")
            return False

        # Get margin-based starting capital
        starting_capital, max_margin, has_margin = get_portfolio_margin_capital(db, portfolio.id)

        logger.info(f"Portfolio {portfolio.id} ({portfolio.name}): "
                   f"Starting capital=${starting_capital:,.0f} "
                   f"(margin=${max_margin:,.0f}, has_margin={has_margin})")

        # Process portfolio data with RF=0%
        clean_df, metrics = process_portfolio_data(
            df,
            rf_rate=RF_RATE,
            sma_window=SMA_WINDOW,
            use_trading_filter=USE_TRADING_FILTER,
            starting_capital=starting_capital
        )

        # Store the analysis result
        params = {
            "rf_rate": RF_RATE,
            "sma_window": SMA_WINDOW,
            "use_trading_filter": USE_TRADING_FILTER,
            "starting_capital": starting_capital,
            "max_margin": max_margin,
            "has_margin_data": has_margin,
            "margin_multiplier": MARGIN_MULTIPLIER
        }

        # Check if we already have a result with these exact parameters
        existing = db.query(AnalysisResult).filter(
            AnalysisResult.portfolio_id == portfolio.id,
            AnalysisResult.rf_rate == RF_RATE,
            AnalysisResult.starting_capital == starting_capital,
            AnalysisResult.use_trading_filter == USE_TRADING_FILTER
        ).first()

        if existing:
            # Update existing result
            existing.sharpe_ratio = metrics.get('sharpe_ratio', 0)
            existing.sortino_ratio = metrics.get('sortino_ratio', 0)
            existing.cagr = metrics.get('cagr', 0)
            existing.metrics_json = json.dumps(metrics)
            existing.parameters = json.dumps(params)
            logger.info(f"  Updated existing analysis result (id={existing.id})")
        else:
            # Create new result
            analysis_result = AnalysisResult(
                portfolio_id=portfolio.id,
                analysis_type="individual",
                rf_rate=RF_RATE,
                sma_window=SMA_WINDOW,
                use_trading_filter=USE_TRADING_FILTER,
                starting_capital=starting_capital,
                sharpe_ratio=metrics.get('sharpe_ratio', 0),
                sortino_ratio=metrics.get('sortino_ratio', 0),
                cagr=metrics.get('cagr', 0),
                metrics_json=json.dumps(metrics),
                parameters=json.dumps(params)
            )
            db.add(analysis_result)
            logger.info(f"  Created new analysis result")

        db.commit()

        logger.info(f"  Sharpe={metrics.get('sharpe_ratio', 0):.2f}, "
                   f"Sortino={metrics.get('sortino_ratio', 0):.2f}, "
                   f"CAGR={metrics.get('cagr', 0)*100:.2f}%")

        return True

    except Exception as e:
        logger.error(f"Portfolio {portfolio.id} ({portfolio.name}): Error - {e}")
        db.rollback()
        return False


def main():
    """Main migration function."""
    db = SessionLocal()

    try:
        # Get all portfolios
        portfolios = db.query(Portfolio).order_by(Portfolio.id).all()
        total = len(portfolios)

        logger.info(f"Starting reprocessing of {total} portfolios with RF=0%")
        logger.info(f"Configuration: RF={RF_RATE*100}%, Margin multiplier={MARGIN_MULTIPLIER}x, "
                   f"Default capital=${DEFAULT_STARTING_CAPITAL:,.0f}")
        logger.info("=" * 80)

        success_count = 0
        skip_count = 0
        error_count = 0

        for i, portfolio in enumerate(portfolios, 1):
            logger.info(f"[{i}/{total}] Processing portfolio {portfolio.id}: {portfolio.name}")

            if reprocess_portfolio(db, portfolio):
                success_count += 1
            else:
                skip_count += 1

        logger.info("=" * 80)
        logger.info(f"Reprocessing complete!")
        logger.info(f"  Successful: {success_count}")
        logger.info(f"  Skipped: {skip_count}")
        logger.info(f"  Errors: {error_count}")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
