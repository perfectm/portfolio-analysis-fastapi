#!/usr/bin/env python3
"""
Migration: Add Multiple Favorites Support

This migration adds support for multiple named favorites per user with:
- is_default column (Boolean) for marking one favorite as default per user
- tags column (Text/JSON) for categorization (e.g., 'Experimental', 'Production')
- Unique constraint on (user_id, name) to prevent duplicate names
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
    """Add multiple favorites support fields to favorite_settings"""
    logger.info("Adding multiple favorites support to favorite_settings table...")

    with engine.connect() as conn:
        # Detect database type
        db_url = str(engine.url)
        is_postgres = 'postgresql' in db_url

        logger.info(f"Database type: {'PostgreSQL' if is_postgres else 'SQLite'}")

        # Check if columns already exist
        if is_postgres:
            result = conn.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_name = 'favorite_settings'
                AND column_name IN ('is_default', 'tags')
            """))
        else:
            result = conn.execute(text("""
                SELECT COUNT(*) FROM pragma_table_info('favorite_settings')
                WHERE name IN ('is_default', 'tags')
            """))

        existing_count = result.scalar()

        if existing_count > 0:
            logger.warning(f"Some columns already exist ({existing_count}/2). Skipping migration.")
            return

        # Add is_default column
        try:
            conn.execute(text("""
                ALTER TABLE favorite_settings
                ADD COLUMN is_default BOOLEAN DEFAULT FALSE NOT NULL
            """))
            logger.info("  ✅ Added is_default column")
        except Exception as e:
            logger.warning(f"  ⚠️  is_default: {e}")

        # Add tags column
        try:
            conn.execute(text("""
                ALTER TABLE favorite_settings
                ADD COLUMN tags TEXT NULL
            """))
            logger.info("  ✅ Added tags column")
        except Exception as e:
            logger.warning(f"  ⚠️  tags: {e}")

        # Set existing favorites as default (one per user)
        try:
            # For each user, set their first (or only) favorite as default
            conn.execute(text("""
                UPDATE favorite_settings
                SET is_default = TRUE
                WHERE id IN (
                    SELECT MIN(id)
                    FROM favorite_settings
                    GROUP BY user_id
                )
            """))
            logger.info("  ✅ Set existing favorites as default (one per user)")
        except Exception as e:
            logger.warning(f"  ⚠️  Setting defaults: {e}")

        # Add unique constraint on (user_id, name)
        try:
            # Check if constraint already exists
            if is_postgres:
                check_constraint = conn.execute(text("""
                    SELECT COUNT(*)
                    FROM pg_constraint
                    WHERE conname = 'uq_user_favorite_name'
                """))
                if check_constraint.scalar() == 0:
                    conn.execute(text("""
                        ALTER TABLE favorite_settings
                        ADD CONSTRAINT uq_user_favorite_name UNIQUE (user_id, name)
                    """))
                    logger.info("  ✅ Added unique constraint on (user_id, name)")
                else:
                    logger.info("  ℹ️  Unique constraint already exists")
            else:
                # SQLite doesn't support ADD CONSTRAINT, need to check if index exists
                check_index = conn.execute(text("""
                    SELECT COUNT(*)
                    FROM sqlite_master
                    WHERE type = 'index'
                    AND name = 'idx_user_name_unique'
                """))
                if check_index.scalar() == 0:
                    conn.execute(text("""
                        CREATE UNIQUE INDEX idx_user_name_unique
                        ON favorite_settings (user_id, name)
                    """))
                    logger.info("  ✅ Created unique index on (user_id, name)")
                else:
                    logger.info("  ℹ️  Unique index already exists")
        except Exception as e:
            logger.warning(f"  ⚠️  Unique constraint: {e}")

        conn.commit()

    logger.info("✅ Migration completed successfully")


def downgrade():
    """Remove multiple favorites support fields from favorite_settings"""
    logger.info("Removing multiple favorites support from favorite_settings table...")

    with engine.connect() as conn:
        db_url = str(engine.url)
        is_postgres = 'postgresql' in db_url

        if is_postgres:
            # PostgreSQL supports DROP COLUMN
            try:
                conn.execute(text("ALTER TABLE favorite_settings DROP COLUMN is_default"))
                logger.info("  ✅ Dropped is_default column")
            except Exception as e:
                logger.warning(f"  ⚠️  Dropping is_default: {e}")

            try:
                conn.execute(text("ALTER TABLE favorite_settings DROP COLUMN tags"))
                logger.info("  ✅ Dropped tags column")
            except Exception as e:
                logger.warning(f"  ⚠️  Dropping tags: {e}")

            try:
                conn.execute(text("ALTER TABLE favorite_settings DROP CONSTRAINT uq_user_favorite_name"))
                logger.info("  ✅ Dropped unique constraint")
            except Exception as e:
                logger.warning(f"  ⚠️  Dropping constraint: {e}")
        else:
            # SQLite doesn't support DROP COLUMN easily
            logger.warning("⚠️  Downgrade not implemented for SQLite. Manual intervention required.")
            logger.info("   To manually downgrade, you would need to recreate the favorite_settings table.")

        conn.commit()

    logger.info("✅ Downgrade completed")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Add multiple favorites support to database")
    parser.add_argument('--downgrade', action='store_true', help='Revert the migration')
    args = parser.parse_args()

    if args.downgrade:
        downgrade()
    else:
        upgrade()
