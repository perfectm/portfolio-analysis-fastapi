"""
Database migration to add rolling_period_stats table for best/worst 365-day rolling period analysis.
Run this script to create the table that stores pre-calculated rolling period statistics for portfolios.
"""

import os
import sys
import sqlite3
import psycopg2
from urllib.parse import urlparse
import logging

# Add parent directory to path to import database config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file if it exists (for production DATABASE_URL)
# Must be done BEFORE importing from database module
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(env_path):
    print(f"Loading environment from {env_path}")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # Remove surrounding quotes if present
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                os.environ[key] = value
                if key == 'DATABASE_URL':
                    masked = value.replace(value.split('@')[0].split('://')[-1], '***') if '@' in value else value
                    print(f"  Loaded DATABASE_URL: {masked}")
else:
    print(f"WARNING: .env file not found at {env_path}")

from database import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Create rolling_period_stats table"""

    database_url = DATABASE_URL
    logger.info(f"Running rolling_period_stats migration on database: {database_url[:20]}...")

    if database_url.startswith('sqlite'):
        # SQLite migration
        db_path = database_url.replace('sqlite:///', '')

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Check if table already exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='rolling_period_stats'
            """)

            if not cursor.fetchone():
                logger.info("Creating rolling_period_stats table...")

                cursor.execute("""
                    CREATE TABLE rolling_period_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        portfolio_id INTEGER NOT NULL,
                        period_type VARCHAR(20) NOT NULL,
                        period_length_days INTEGER NOT NULL DEFAULT 365,
                        start_date TIMESTAMP NOT NULL,
                        end_date TIMESTAMP NOT NULL,
                        total_profit REAL NOT NULL,
                        cagr REAL,
                        sharpe_ratio REAL,
                        sortino_ratio REAL,
                        max_drawdown_percent REAL,
                        mar_ratio REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP,
                        FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
                    )
                """)

                # Create unique index for portfolio_id + period_type + period_length_days
                cursor.execute("""
                    CREATE UNIQUE INDEX idx_portfolio_period_type
                    ON rolling_period_stats(portfolio_id, period_type, period_length_days)
                """)

                # Create index on portfolio_id for faster lookups
                cursor.execute("""
                    CREATE INDEX idx_rolling_period_portfolio_id
                    ON rolling_period_stats(portfolio_id)
                """)

                conn.commit()
                logger.info("rolling_period_stats table created successfully in SQLite database")
            else:
                logger.info("rolling_period_stats table already exists in SQLite database")

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
                # Check if table already exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'rolling_period_stats'
                    )
                """)

                if not cursor.fetchone()[0]:
                    logger.info("Creating rolling_period_stats table...")

                    cursor.execute("""
                        CREATE TABLE rolling_period_stats (
                            id SERIAL PRIMARY KEY,
                            portfolio_id INTEGER NOT NULL REFERENCES portfolios(id),
                            period_type VARCHAR(20) NOT NULL,
                            period_length_days INTEGER NOT NULL DEFAULT 365,
                            start_date TIMESTAMP NOT NULL,
                            end_date TIMESTAMP NOT NULL,
                            total_profit DOUBLE PRECISION NOT NULL,
                            cagr DOUBLE PRECISION,
                            sharpe_ratio DOUBLE PRECISION,
                            sortino_ratio DOUBLE PRECISION,
                            max_drawdown_percent DOUBLE PRECISION,
                            mar_ratio DOUBLE PRECISION,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP WITH TIME ZONE
                        )
                    """)

                    # Create unique index for portfolio_id + period_type + period_length_days
                    cursor.execute("""
                        CREATE UNIQUE INDEX idx_portfolio_period_type
                        ON rolling_period_stats(portfolio_id, period_type, period_length_days)
                    """)

                    # Create index on portfolio_id for faster lookups
                    cursor.execute("""
                        CREATE INDEX idx_rolling_period_portfolio_id
                        ON rolling_period_stats(portfolio_id)
                    """)

                    logger.info("rolling_period_stats table created successfully in PostgreSQL database")
                else:
                    logger.info("rolling_period_stats table already exists in PostgreSQL database")

        conn.close()

    else:
        raise ValueError(f"Unsupported database type: {database_url}")


def rollback_migration():
    """Drop rolling_period_stats table"""

    database_url = DATABASE_URL
    logger.info(f"Rolling back rolling_period_stats migration on database: {database_url[:20]}...")

    if database_url.startswith('sqlite'):
        db_path = database_url.replace('sqlite:///', '')

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS rolling_period_stats")
            conn.commit()
            logger.info("rolling_period_stats table dropped from SQLite database")

    elif database_url.startswith('postgres'):
        parsed = urlparse(database_url)

        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password
        )

        with conn:
            with conn.cursor() as cursor:
                cursor.execute("DROP TABLE IF EXISTS rolling_period_stats CASCADE")
                logger.info("rolling_period_stats table dropped from PostgreSQL database")

        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Rolling period stats migration')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    args = parser.parse_args()

    try:
        if args.rollback:
            rollback_migration()
        else:
            run_migration()
        logger.info("Migration completed successfully!")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
