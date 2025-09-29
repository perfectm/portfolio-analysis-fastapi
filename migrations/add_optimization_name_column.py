#!/usr/bin/env python3
"""
Migration script to add 'name' column to optimization_cache table.
This allows users to give custom names to their optimizations.
"""

import sqlite3
import os
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_sqlite_database():
    """Add name column to optimization_cache table in SQLite database"""

    # Check if SQLite database exists
    db_path = "portfolio_analysis.db"
    if not os.path.exists(db_path):
        logger.warning(f"SQLite database not found at {db_path}")
        return False

    try:
        # Connect to SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='optimization_cache'
        """)

        if not cursor.fetchone():
            logger.warning("optimization_cache table not found")
            conn.close()
            return False

        # Check if name column already exists
        cursor.execute("PRAGMA table_info(optimization_cache)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'name' in columns:
            logger.info("✅ 'name' column already exists in optimization_cache table")
            conn.close()
            return True

        # Add the name column
        logger.info("Adding 'name' column to optimization_cache table...")
        cursor.execute("""
            ALTER TABLE optimization_cache
            ADD COLUMN name VARCHAR(200) NULL
        """)

        # Commit the changes
        conn.commit()

        # Verify the column was added
        cursor.execute("PRAGMA table_info(optimization_cache)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'name' in columns:
            logger.info("✅ Successfully added 'name' column to optimization_cache table")

            # Optionally, add some default names to existing entries
            cursor.execute("SELECT COUNT(*) FROM optimization_cache WHERE name IS NULL")
            unnamed_count = cursor.fetchone()[0]

            if unnamed_count > 0:
                logger.info(f"Found {unnamed_count} unnamed optimization entries")

                # Add default names based on method and date
                cursor.execute("""
                    UPDATE optimization_cache
                    SET name =
                        CASE optimization_method
                            WHEN 'differential_evolution' THEN 'Auto-Optimized (' || portfolio_count || ' portfolios)'
                            WHEN 'scipy' THEN 'Quick Optimization (' || portfolio_count || ' portfolios)'
                            WHEN 'grid_search' THEN 'Grid Search (' || portfolio_count || ' portfolios)'
                            ELSE 'Optimization #' || id
                        END
                    WHERE name IS NULL
                """)

                conn.commit()
                logger.info(f"✅ Added default names to {unnamed_count} optimization entries")

            conn.close()
            return True
        else:
            logger.error("❌ Failed to add 'name' column")
            conn.close()
            return False

    except Exception as e:
        logger.error(f"❌ Error during SQLite migration: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return False

def migrate_postgresql_database():
    """Add name column to optimization_cache table in PostgreSQL database"""

    try:
        # Import here to avoid dependency issues if psycopg2 is not installed
        import psycopg2
        from psycopg2 import sql

        # Get database URL from environment
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.warning("DATABASE_URL not found, skipping PostgreSQL migration")
            return False

        # Connect to PostgreSQL database
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'optimization_cache'
            )
        """)

        if not cursor.fetchone()[0]:
            logger.warning("optimization_cache table not found in PostgreSQL")
            conn.close()
            return False

        # Check if name column already exists
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'optimization_cache' AND column_name = 'name'
        """)

        if cursor.fetchone():
            logger.info("✅ 'name' column already exists in optimization_cache table (PostgreSQL)")
            conn.close()
            return True

        # Add the name column
        logger.info("Adding 'name' column to optimization_cache table (PostgreSQL)...")
        cursor.execute("""
            ALTER TABLE optimization_cache
            ADD COLUMN name VARCHAR(200) NULL
        """)

        # Commit the changes
        conn.commit()

        # Add default names to existing entries
        cursor.execute("SELECT COUNT(*) FROM optimization_cache WHERE name IS NULL")
        unnamed_count = cursor.fetchone()[0]

        if unnamed_count > 0:
            logger.info(f"Found {unnamed_count} unnamed optimization entries")

            cursor.execute("""
                UPDATE optimization_cache
                SET name =
                    CASE optimization_method
                        WHEN 'differential_evolution' THEN 'Auto-Optimized (' || portfolio_count || ' portfolios)'
                        WHEN 'scipy' THEN 'Quick Optimization (' || portfolio_count || ' portfolios)'
                        WHEN 'grid_search' THEN 'Grid Search (' || portfolio_count || ' portfolios)'
                        ELSE 'Optimization #' || id::text
                    END
                WHERE name IS NULL
            """)

            conn.commit()
            logger.info(f"✅ Added default names to {unnamed_count} optimization entries")

        logger.info("✅ Successfully added 'name' column to optimization_cache table (PostgreSQL)")
        conn.close()
        return True

    except ImportError:
        logger.warning("psycopg2 not available, skipping PostgreSQL migration")
        return False
    except Exception as e:
        logger.error(f"❌ Error during PostgreSQL migration: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return False

def main():
    """Run the migration for both SQLite and PostgreSQL if available"""

    logger.info("🚀 Starting optimization_cache name column migration...")
    logger.info(f"Migration started at: {datetime.now()}")

    success_count = 0

    # Try SQLite migration
    if migrate_sqlite_database():
        success_count += 1

    # Try PostgreSQL migration
    if migrate_postgresql_database():
        success_count += 1

    if success_count > 0:
        logger.info("✅ Migration completed successfully!")
        logger.info("Users can now name their optimization results.")
    else:
        logger.warning("⚠️ No databases were migrated. This might be expected if databases don't exist yet.")

    logger.info(f"Migration finished at: {datetime.now()}")

if __name__ == "__main__":
    main()