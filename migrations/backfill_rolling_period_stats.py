"""
Backfill script to calculate rolling period stats for all existing portfolios.
Run this after add_rolling_period_stats.py migration to populate stats for existing data.
"""

import os
import sys
import logging

# Add parent directory to path to import database config and services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip

from database import SessionLocal
from models import Portfolio
from rolling_period_service import RollingPeriodService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def backfill_rolling_stats(starting_capital: float = 100000.0, period_length_days: int = 365):
    """
    Calculate and store rolling period stats for all existing portfolios.

    Args:
        starting_capital: Starting capital to use for calculations
        period_length_days: Length of rolling period in days
    """
    logger.info(f"Starting backfill of rolling period stats...")
    logger.info(f"Using starting capital: ${starting_capital:,.2f}")
    logger.info(f"Period length: {period_length_days} days")

    db = SessionLocal()

    try:
        # Get all portfolios
        portfolios = db.query(Portfolio).all()
        total_portfolios = len(portfolios)

        logger.info(f"Found {total_portfolios} portfolios to process")

        successful = 0
        failed = 0
        skipped = 0

        for i, portfolio in enumerate(portfolios, 1):
            logger.info(f"Processing portfolio {i}/{total_portfolios}: {portfolio.name} (ID: {portfolio.id})")

            try:
                success = RollingPeriodService.calculate_and_store_rolling_stats(
                    db, portfolio.id, period_length_days, starting_capital
                )

                if success:
                    successful += 1
                    logger.info(f"  ✅ Successfully calculated rolling stats for {portfolio.name}")
                else:
                    skipped += 1
                    logger.info(f"  ⏭️ Skipped {portfolio.name} (insufficient data for {period_length_days}-day analysis)")

            except Exception as e:
                failed += 1
                logger.error(f"  ❌ Failed to calculate rolling stats for {portfolio.name}: {e}")

        logger.info("=" * 60)
        logger.info("Backfill completed!")
        logger.info(f"  Successful: {successful}")
        logger.info(f"  Skipped (insufficient data): {skipped}")
        logger.info(f"  Failed: {failed}")
        logger.info(f"  Total: {total_portfolios}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        raise
    finally:
        db.close()


def verify_backfill():
    """Verify the backfill was successful by checking the rolling_period_stats table."""
    from models import RollingPeriodStats

    db = SessionLocal()

    try:
        # Count total records
        total_stats = db.query(RollingPeriodStats).count()
        best_count = db.query(RollingPeriodStats).filter(RollingPeriodStats.period_type == 'best').count()
        worst_count = db.query(RollingPeriodStats).filter(RollingPeriodStats.period_type == 'worst').count()

        # Count portfolios
        total_portfolios = db.query(Portfolio).count()

        logger.info("=" * 60)
        logger.info("Verification Results:")
        logger.info(f"  Total portfolios: {total_portfolios}")
        logger.info(f"  Total rolling period stats: {total_stats}")
        logger.info(f"  Best period records: {best_count}")
        logger.info(f"  Worst period records: {worst_count}")

        if best_count == worst_count:
            logger.info(f"  Coverage: {best_count}/{total_portfolios} portfolios have rolling stats")
        else:
            logger.warning(f"  ⚠️ Mismatch: {best_count} best vs {worst_count} worst records")

        logger.info("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Backfill rolling period stats for existing portfolios')
    parser.add_argument('--starting-capital', type=float, default=100000.0,
                       help='Starting capital for calculations (default: 100000)')
    parser.add_argument('--period-days', type=int, default=365,
                       help='Rolling period length in days (default: 365)')
    parser.add_argument('--verify-only', action='store_true',
                       help='Only verify existing data, do not backfill')
    args = parser.parse_args()

    try:
        if args.verify_only:
            verify_backfill()
        else:
            backfill_rolling_stats(args.starting_capital, args.period_days)
            verify_backfill()
        logger.info("Done!")
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)
