#!/usr/bin/env python3
"""
Migration: Add favorite_settings table

Creates the favorite_settings table for storing user portfolio analysis preferences.
This migration should be run BEFORE add_favorite_optimization_fields.py
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip

from sqlalchemy import text
from database import engine, SessionLocal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    """Create favorite_settings table"""
    logger.info("Creating favorite_settings table...")

    with engine.connect() as conn:
        # Check if table already exists
        result = conn.execute(text("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = 'favorite_settings'
        """))
        table_exists = result.scalar() > 0

        if table_exists:
            logger.warning("Table 'favorite_settings' already exists. Skipping creation.")
            return

        # Create the table
        conn.execute(text("""
            CREATE TABLE favorite_settings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                name VARCHAR(255) NOT NULL DEFAULT 'My Favorite Settings',

                -- Portfolio selection and weights
                portfolio_ids_json TEXT NOT NULL,
                weights_json TEXT NOT NULL,

                -- Analysis parameters
                starting_capital DOUBLE PRECISION NOT NULL DEFAULT 500000.0,
                risk_free_rate DOUBLE PRECISION NOT NULL DEFAULT 0.043,
                sma_window INTEGER NOT NULL DEFAULT 20,
                use_trading_filter BOOLEAN NOT NULL DEFAULT TRUE,

                -- Date range (optional - null means use all data)
                date_range_start TIMESTAMP NULL,
                date_range_end TIMESTAMP NULL,

                -- Timestamps
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        logger.info("  ✅ Created favorite_settings table")

        # Create index on user_id
        conn.execute(text("""
            CREATE INDEX ix_favorite_settings_user_id ON favorite_settings(user_id)
        """))
        logger.info("  ✅ Created index on user_id")

        conn.commit()

    logger.info("✅ Migration completed successfully")


def downgrade():
    """Drop favorite_settings table"""
    logger.info("Dropping favorite_settings table...")

    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS favorite_settings CASCADE"))
        conn.commit()

    logger.info("✅ Downgrade completed successfully")


if __name__ == "__main__":
    upgrade()
