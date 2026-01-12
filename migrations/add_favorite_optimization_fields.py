#!/usr/bin/env python3
"""
Migration: Add optimization tracking fields to favorite_settings table

This migration adds fields to track:
- When favorites were last optimized
- The optimized weights from the last run
- Which optimization method was used
- Whether there's a new optimization result to show the user
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from database import engine, SessionLocal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    """Add optimization tracking fields to favorite_settings"""
    logger.info("Adding optimization tracking fields to favorite_settings table...")

    with engine.connect() as conn:
        # Check if columns already exist
        result = conn.execute(text("""
            SELECT COUNT(*) FROM pragma_table_info('favorite_settings')
            WHERE name IN ('last_optimized', 'optimized_weights_json', 'optimization_method', 'has_new_optimization')
        """))
        existing_count = result.scalar()

        if existing_count > 0:
            logger.warning(f"Some optimization fields already exist ({existing_count}/4). Skipping migration.")
            return

        # Add columns
        try:
            conn.execute(text("""
                ALTER TABLE favorite_settings
                ADD COLUMN last_optimized TIMESTAMP NULL
            """))
            logger.info("  ✅ Added last_optimized column")
        except Exception as e:
            logger.warning(f"  ⚠️  last_optimized: {e}")

        try:
            conn.execute(text("""
                ALTER TABLE favorite_settings
                ADD COLUMN optimized_weights_json TEXT NULL
            """))
            logger.info("  ✅ Added optimized_weights_json column")
        except Exception as e:
            logger.warning(f"  ⚠️  optimized_weights_json: {e}")

        try:
            conn.execute(text("""
                ALTER TABLE favorite_settings
                ADD COLUMN optimization_method VARCHAR(50) NULL
            """))
            logger.info("  ✅ Added optimization_method column")
        except Exception as e:
            logger.warning(f"  ⚠️  optimization_method: {e}")

        try:
            conn.execute(text("""
                ALTER TABLE favorite_settings
                ADD COLUMN has_new_optimization BOOLEAN DEFAULT FALSE
            """))
            logger.info("  ✅ Added has_new_optimization column")
        except Exception as e:
            logger.warning(f"  ⚠️  has_new_optimization: {e}")

        conn.commit()

    logger.info("✅ Migration completed successfully")


def downgrade():
    """Remove optimization tracking fields from favorite_settings"""
    logger.info("Removing optimization tracking fields from favorite_settings table...")

    # SQLite doesn't support DROP COLUMN easily, so we'd need to recreate the table
    logger.warning("⚠️  Downgrade not implemented for SQLite. Manual intervention required.")
    logger.info("   To manually downgrade, you would need to recreate the favorite_settings table.")


if __name__ == "__main__":
    upgrade()
