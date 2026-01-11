#!/usr/bin/env python3
"""
Sync Production Database to Development

This script safely imports data from the production PostgreSQL database
to the local development SQLite database for testing purposes.

Usage:
    # Using environment variable
    export PROD_DATABASE_URL="postgresql://user:pass@host:port/db"
    python sync_prod_to_dev.py

    # Or provide connection string directly
    python sync_prod_to_dev.py postgresql://user:pass@host:port/db

    # SSH tunnel to Hostinger VPS (if needed)
    ssh -L 5433:localhost:5432 cotton@srv1173534
    python sync_prod_to_dev.py postgresql://cmtool:password@localhost:5433/portfolio_analysis
"""

import os
import sys
from sqlalchemy import create_engine, inspect, MetaData, Table, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Local SQLite database path
LOCAL_DB_PATH = "sqlite:///./portfolio_analysis.db"

# Table sync order (respecting foreign key dependencies)
TABLE_ORDER = [
    'users',
    'portfolios',
    'portfolio_data',
    'analysis_results',
    'analysis_plots',
    'blended_portfolios',
    'blended_portfolio_mappings',
    'favorite_settings',
    'regime_data',
    'regime_performance',
    'margin_requirements',
    'portfolio_margin_data',
    'optimization_cache'
]


def get_production_url():
    """Get production database URL from environment or command line"""
    if len(sys.argv) > 1:
        return sys.argv[1]

    prod_url = os.getenv('PROD_DATABASE_URL')
    if prod_url:
        return prod_url

    logger.error("❌ No production database URL provided!")
    logger.error("   Set PROD_DATABASE_URL environment variable or pass as argument")
    logger.error("")
    logger.error("Examples:")
    logger.error("  export PROD_DATABASE_URL='postgresql://user:pass@host:port/db'")
    logger.error("  python sync_prod_to_dev.py 'postgresql://user:pass@host:port/db'")
    sys.exit(1)


def connect_databases(prod_url, local_url):
    """Create connections to both databases"""
    try:
        # Production (read-only)
        logger.info("🔌 Connecting to production database...")

        # Add retry logic and better connection handling
        prod_engine = create_engine(
            prod_url,
            poolclass=NullPool,  # No connection pooling for one-off script
            connect_args={
                "connect_timeout": 30,
                "application_name": "sync_prod_to_dev",  # Identify in pg_stat_activity
                "keepalives": 1,  # Enable TCP keepalives
                "keepalives_idle": 30,  # Start keepalives after 30s
                "keepalives_interval": 10,  # Send keepalive every 10s
                "keepalives_count": 5  # 5 failed keepalives = dead connection
            },
            pool_pre_ping=True,  # Check connection health before using
            echo=False
        )

        # Test connection
        with prod_engine.connect() as conn:
            result = conn.execute(text("SELECT current_database(), current_user, version()"))
            db_name, user, version = result.fetchone()
            logger.info(f"✅ Connected to production: {db_name} as {user}")
            logger.info(f"   PostgreSQL version: {version.split(',')[0]}")

        prod_session = sessionmaker(bind=prod_engine)()

        # Local development
        logger.info(f"🔌 Connecting to local database: {local_url}")
        local_engine = create_engine(
            local_url,
            connect_args={"check_same_thread": False},
            echo=False
        )

        # Test connection
        with local_engine.connect() as conn:
            result = conn.execute(text("SELECT sqlite_version()"))
            sqlite_version = result.fetchone()[0]
            logger.info(f"✅ Connected to local SQLite: version {sqlite_version}")

        local_session = sessionmaker(bind=local_engine)()

        return prod_engine, prod_session, local_engine, local_session

    except Exception as e:
        logger.error(f"❌ Failed to connect to databases: {e}")
        raise


def get_table_row_count(session, table_name):
    """Get row count for a table"""
    try:
        result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        return result.scalar()
    except Exception:
        return 0


def clear_local_database(local_session, local_engine):
    """Clear all data from local database (keep schema)"""
    logger.info("🗑️  Clearing local database...")

    # Disable foreign key constraints temporarily
    local_session.execute(text("PRAGMA foreign_keys = OFF"))

    # Delete data from tables in reverse order
    for table_name in reversed(TABLE_ORDER):
        try:
            local_session.execute(text(f"DELETE FROM {table_name}"))
            logger.info(f"   Cleared {table_name}")
        except Exception as e:
            logger.warning(f"   ⚠️  Could not clear {table_name}: {e}")

    local_session.commit()

    # Re-enable foreign key constraints
    local_session.execute(text("PRAGMA foreign_keys = ON"))
    local_session.commit()

    logger.info("✅ Local database cleared")


def sync_table(table_name, prod_session, local_session, prod_engine, local_engine):
    """Sync a single table from production to local"""
    try:
        # Get row count from production
        prod_count = get_table_row_count(prod_session, table_name)

        if prod_count == 0:
            logger.info(f"⏭️  Skipping {table_name} (empty in production)")
            return 0

        logger.info(f"📋 Syncing {table_name} ({prod_count:,} rows)...")

        # Reflect the table structure
        metadata = MetaData()
        table = Table(table_name, metadata, autoload_with=prod_engine)

        # Fetch all data from production
        with prod_engine.connect() as prod_conn:
            result = prod_conn.execute(table.select())
            rows = result.fetchall()
            columns = result.keys()

        if not rows:
            logger.info(f"   ⏭️  No data to sync")
            return 0

        # Insert into local database in batches
        batch_size = 1000
        total_inserted = 0

        with local_engine.begin() as local_conn:
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]

                # Convert rows to dicts
                batch_dicts = [dict(zip(columns, row)) for row in batch]

                # Insert batch
                local_conn.execute(table.insert(), batch_dicts)
                total_inserted += len(batch)

                if total_inserted % 5000 == 0:
                    logger.info(f"   ... {total_inserted:,} / {prod_count:,} rows")

        logger.info(f"   ✅ Synced {total_inserted:,} rows")
        return total_inserted

    except Exception as e:
        logger.error(f"   ❌ Failed to sync {table_name}: {e}")
        return 0


def sync_all_tables(prod_engine, prod_session, local_engine, local_session):
    """Sync all tables from production to local"""
    logger.info("=" * 70)
    logger.info("🔄 Starting database sync...")
    logger.info("=" * 70)

    total_synced = 0
    start_time = datetime.now()

    # Disable foreign key constraints during sync
    local_session.execute(text("PRAGMA foreign_keys = OFF"))
    local_session.commit()

    for table_name in TABLE_ORDER:
        synced = sync_table(table_name, prod_session, local_session, prod_engine, local_engine)
        total_synced += synced

    # Re-enable foreign key constraints
    local_session.execute(text("PRAGMA foreign_keys = ON"))
    local_session.commit()

    duration = datetime.now() - start_time

    logger.info("=" * 70)
    logger.info(f"✅ Sync completed!")
    logger.info(f"   Total rows synced: {total_synced:,}")
    logger.info(f"   Duration: {duration}")
    logger.info("=" * 70)


def show_summary(local_session):
    """Show summary of synced data"""
    logger.info("")
    logger.info("📊 Local Database Summary:")
    logger.info("-" * 70)

    for table_name in TABLE_ORDER:
        count = get_table_row_count(local_session, table_name)
        if count > 0:
            logger.info(f"   {table_name:<30} {count:>10,} rows")

    logger.info("-" * 70)


def main():
    """Main sync function"""
    try:
        # Get database URLs
        prod_url = get_production_url()
        local_url = LOCAL_DB_PATH

        # Hide password in logs
        display_url = prod_url
        if '@' in prod_url:
            parts = prod_url.split('@')
            user_pass = parts[0].split('://')[-1]
            display_url = prod_url.replace(user_pass, '***')

        logger.info("")
        logger.info("🚀 Production to Development Database Sync")
        logger.info(f"   Production: {display_url}")
        logger.info(f"   Local:      {local_url}")
        logger.info("")

        # Confirm with user
        response = input("⚠️  This will REPLACE all local data. Continue? [y/N]: ")
        if response.lower() not in ['y', 'yes']:
            logger.info("❌ Sync cancelled by user")
            return

        # Connect to databases
        prod_engine, prod_session, local_engine, local_session = connect_databases(
            prod_url, local_url
        )

        try:
            # Clear local database
            clear_local_database(local_session, local_engine)

            # Sync all tables
            sync_all_tables(prod_engine, prod_session, local_engine, local_session)

            # Show summary
            show_summary(local_session)

            logger.info("")
            logger.info("✅ Sync completed successfully!")
            logger.info("   Your local database now has production data for testing.")
            logger.info("")

        finally:
            prod_session.close()
            local_session.close()
            prod_engine.dispose()
            local_engine.dispose()

    except KeyboardInterrupt:
        logger.info("")
        logger.info("❌ Sync cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
