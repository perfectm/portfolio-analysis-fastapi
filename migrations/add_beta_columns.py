"""
Database migration to add Beta metrics columns to analysis_results table
Run this script to add beta, alpha, r_squared, and beta_observation_count columns
"""

import os
import sys
import sqlite3
import psycopg2
from urllib.parse import urlparse
import logging

# Add parent directory to path to import database config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Add Beta metric columns to analysis_results table"""

    database_url = DATABASE_URL
    logger.info(f"Running Beta columns migration on database: {database_url[:20]}...")

    if database_url.startswith('sqlite'):
        # SQLite migration
        db_path = database_url.replace('sqlite:///', '')

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Check if beta column already exists
            cursor.execute("PRAGMA table_info(analysis_results)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'beta' not in columns:
                logger.info("Adding Beta metrics columns to analysis_results table...")

                # Add the new columns
                cursor.execute("ALTER TABLE analysis_results ADD COLUMN beta REAL")
                cursor.execute("ALTER TABLE analysis_results ADD COLUMN alpha REAL")
                cursor.execute("ALTER TABLE analysis_results ADD COLUMN r_squared REAL")
                cursor.execute("ALTER TABLE analysis_results ADD COLUMN beta_observation_count INTEGER")

                # Set default values for existing records
                cursor.execute("""
                    UPDATE analysis_results
                    SET beta = 0.0, alpha = 0.0, r_squared = 0.0, beta_observation_count = 0
                    WHERE beta IS NULL
                """)

                conn.commit()
                logger.info("Beta columns added successfully to SQLite database")
            else:
                logger.info("Beta columns already exist in SQLite database")

    elif database_url.startswith('postgres'):
        # PostgreSQL migration
        parsed = urlparse(database_url)

        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],  # Remove leading slash
            user=parsed.username,
            password=parsed.password
        )

        with conn:
            with conn.cursor() as cursor:
                # Check if beta column already exists
                cursor.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'analysis_results' AND column_name = 'beta'
                """)

                if not cursor.fetchone():
                    logger.info("Adding Beta metrics columns to analysis_results table...")

                    # Add the new columns
                    cursor.execute("ALTER TABLE analysis_results ADD COLUMN beta REAL")
                    cursor.execute("ALTER TABLE analysis_results ADD COLUMN alpha REAL")
                    cursor.execute("ALTER TABLE analysis_results ADD COLUMN r_squared REAL")
                    cursor.execute("ALTER TABLE analysis_results ADD COLUMN beta_observation_count INTEGER")

                    # Set default values for existing records
                    cursor.execute("""
                        UPDATE analysis_results
                        SET beta = 0.0, alpha = 0.0, r_squared = 0.0, beta_observation_count = 0
                        WHERE beta IS NULL
                    """)

                    logger.info("Beta columns added successfully to PostgreSQL database")
                else:
                    logger.info("Beta columns already exist in PostgreSQL database")

        conn.close()

    else:
        raise ValueError(f"Unsupported database type: {database_url}")


if __name__ == "__main__":
    try:
        run_migration()
        logger.info("Migration completed successfully!")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)