#!/usr/bin/env python3
"""
Cron Script: Optimize User Favorite Portfolios

This script runs at midnight to optimize each user's saved favorite portfolio settings.
It only runs optimization if the favorites have been modified since the last optimization.

Setup:
    # Add to crontab to run daily at midnight
    0 0 * * * cd /path/to/portfolio-analysis-fastapi && /path/to/venv/bin/python optimize_favorites_cron.py >> logs/optimize_cron.log 2>&1

Usage:
    # Run manually
    python optimize_favorites_cron.py

    # Run for specific user only
    python optimize_favorites_cron.py --user-id 1

    # Force optimization even if no changes
    python optimize_favorites_cron.py --force
"""
import sys
import argparse
import logging
from datetime import datetime
import json
from pathlib import Path

# Load environment variables from .env file (must be before database imports)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip

# Setup imports
from database import SessionLocal
from models import FavoriteSettings, Portfolio
from portfolio_optimizer import PortfolioOptimizer

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "optimize_cron.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def should_optimize(favorite: FavoriteSettings, force: bool = False) -> bool:
    """
    Determine if optimization should run for this favorite setting

    Returns True if:
    - Force flag is set, OR
    - Never optimized before, OR
    - Favorites were updated after last optimization
    """
    if force:
        logger.info(f"  ✓ Force flag set - will optimize")
        return True

    if not favorite.last_optimized:
        logger.info(f"  ✓ Never optimized before - will optimize")
        return True

    if favorite.updated_at > favorite.last_optimized:
        logger.info(f"  ✓ Settings updated since last optimization - will optimize")
        logger.info(f"    Last updated: {favorite.updated_at}")
        logger.info(f"    Last optimized: {favorite.last_optimized}")
        return True

    logger.info(f"  ⏭  No changes since last optimization - skipping")
    logger.info(f"    Last optimized: {favorite.last_optimized}")
    return False


def optimize_favorite(db: SessionLocal, favorite: FavoriteSettings) -> dict:
    """
    Run optimization for a single favorite setting

    Returns dict with optimization results or error
    """
    try:
        logger.info(f"  📊 Starting optimization for '{favorite.name}'...")

        # Parse portfolio IDs and current weights
        portfolio_ids = json.loads(favorite.portfolio_ids_json)
        current_weights = json.loads(favorite.weights_json)

        logger.info(f"    Portfolios: {len(portfolio_ids)} selected")
        logger.info(f"    Current weights: {current_weights}")

        # Fetch portfolio data
        portfolios = db.query(Portfolio).filter(Portfolio.id.in_(portfolio_ids)).all()
        if len(portfolios) != len(portfolio_ids):
            raise ValueError(f"Some portfolios not found. Expected {len(portfolio_ids)}, got {len(portfolios)}")

        # Create optimizer instance
        optimizer = PortfolioOptimizer(
            rf_rate=favorite.risk_free_rate,
            sma_window=favorite.sma_window,
            use_trading_filter=favorite.use_trading_filter,
            starting_capital=favorite.starting_capital,
            portfolio_count=len(portfolio_ids)
        )

        # Determine optimization method based on portfolio count
        # For large portfolios (>10), use simple optimization for faster results
        num_portfolios = len(portfolio_ids)
        if num_portfolios <= 10:
            method = "differential_evolution"
            logger.info(f"    Using full optimization (differential_evolution) for {num_portfolios} portfolios")
        else:
            method = "simple"
            logger.info(f"    Using simple optimization (greedy hill-climbing) for {num_portfolios} portfolios")

        # Run optimization (with extended timeout for cron jobs - no rush)
        result = optimizer.optimize_weights(
            portfolio_ids=portfolio_ids,
            db_session=db,
            method=method,
            max_time_seconds=3600,  # 1 hour max for cron jobs
            resume_from_weights=current_weights  # Start from current weights
        )

        if not result or 'optimal_weights_array' not in result:
            raise ValueError("Optimization returned no results")

        logger.info(f"  ✅ Optimization completed successfully!")
        logger.info(f"    Optimized weights: {result['optimal_weights_array']}")
        logger.info(f"    Objective value: {result.get('objective_value', 'N/A')}")

        return {
            'success': True,
            'optimized_weights': result['optimal_weights_array'],
            'method': method,
            'objective_value': result.get('objective_value'),
            'metrics': result.get('metrics', {})
        }

    except Exception as e:
        logger.error(f"  ❌ Optimization failed: {e}")
        import traceback
        logger.error(f"    Traceback: {traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e)
        }


def process_favorites(user_id: int = None, force: bool = False):
    """
    Process all favorite settings (or just one user's) and optimize if needed
    """
    db = SessionLocal()
    try:
        logger.info("=" * 80)
        logger.info("🚀 Starting Favorite Portfolio Optimization Cron Job")
        logger.info(f"   Time: {datetime.now()}")
        logger.info(f"   User filter: {'All users' if not user_id else f'User ID {user_id}'}")
        logger.info(f"   Force: {force}")
        logger.info("=" * 80)

        # Query favorites
        query = db.query(FavoriteSettings)
        if user_id:
            query = query.filter(FavoriteSettings.user_id == user_id)

        favorites = query.all()
        logger.info(f"\n📋 Found {len(favorites)} favorite settings to process\n")

        if not favorites:
            logger.info("⏭  No favorites found. Exiting.")
            return

        # Process each favorite
        optimized_count = 0
        skipped_count = 0
        error_count = 0

        for idx, favorite in enumerate(favorites, 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"[{idx}/{len(favorites)}] Processing favorite: '{favorite.name}' (User ID: {favorite.user_id})")
            logger.info(f"{'='*80}")

            # Check if optimization is needed
            if not should_optimize(favorite, force):
                skipped_count += 1
                continue

            # Run optimization
            result = optimize_favorite(db, favorite)

            if result['success']:
                # Update favorite settings with optimized results
                favorite.optimized_weights_json = json.dumps(result['optimized_weights'])
                favorite.optimization_method = result['method']
                favorite.last_optimized = datetime.now()
                favorite.has_new_optimization = True  # Set flag for UI alert

                db.commit()
                optimized_count += 1
                logger.info(f"  💾 Saved optimized weights to database")
            else:
                error_count += 1

        # Summary
        logger.info(f"\n{'='*80}")
        logger.info("📊 Optimization Summary")
        logger.info(f"{'='*80}")
        logger.info(f"  Total favorites: {len(favorites)}")
        logger.info(f"  ✅ Optimized: {optimized_count}")
        logger.info(f"  ⏭  Skipped (no changes): {skipped_count}")
        logger.info(f"  ❌ Errors: {error_count}")
        logger.info(f"{'='*80}\n")
        logger.info("✅ Cron job completed successfully!")

    except Exception as e:
        logger.error(f"❌ Cron job failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
    finally:
        db.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Optimize user favorite portfolio settings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Optimize all users' favorites (if changed)
  python optimize_favorites_cron.py

  # Optimize specific user only
  python optimize_favorites_cron.py --user-id 1

  # Force optimization even if no changes
  python optimize_favorites_cron.py --force

  # Force for specific user
  python optimize_favorites_cron.py --user-id 1 --force
        """
    )

    parser.add_argument(
        '--user-id',
        type=int,
        help='Only optimize favorites for this user ID'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force optimization even if favorites have not changed'
    )

    args = parser.parse_args()

    try:
        process_favorites(user_id=args.user_id, force=args.force)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
