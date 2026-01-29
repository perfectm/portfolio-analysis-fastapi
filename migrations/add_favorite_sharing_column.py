#!/usr/bin/env python3
"""
Migration: Add is_shared column to favorite_settings table

This migration adds a boolean column to allow users to share their
favorite settings publicly with other users.
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
from database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade():
    """Add is_shared column to favorite_settings"""
    logger.info("Adding is_shared column to favorite_settings table...")

    with engine.connect() as conn:
        # Detect database type
        db_url = str(engine.url)
        is_postgres = 'postgresql' in db_url

        # Check if column already exists
        if is_postgres:
            result = conn.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_name = 'favorite_settings'
                AND column_name = 'is_shared'
            """))
        else:
            result = conn.execute(text("""
                SELECT COUNT(*) FROM pragma_table_info('favorite_settings')
                WHERE name = 'is_shared'
            """))

        if result.scalar() > 0:
            logger.warning("is_shared column already exists. Skipping migration.")
            return

        try:
            conn.execute(text("""
                ALTER TABLE favorite_settings
                ADD COLUMN is_shared BOOLEAN NOT NULL DEFAULT FALSE
            """))
            logger.info("  Added is_shared column")
        except Exception as e:
            logger.warning(f"  is_shared: {e}")

        conn.commit()

    logger.info("Migration completed successfully")


if __name__ == "__main__":
    upgrade()
