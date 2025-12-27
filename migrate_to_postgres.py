#!/usr/bin/env python3
"""
Migration script to copy data from SQLite to PostgreSQL
Usage: python migrate_to_postgres.py
"""
import os
import sys
from sqlalchemy import create_engine, MetaData, Table, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database URLs
SQLITE_URL = "sqlite:///./portfolio_analysis.db"

# Get PostgreSQL URL from environment or use default
POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://cmtool:password@localhost:5432/portfolio_analysis")

def verify_postgres_connection():
    """Verify PostgreSQL connection before migration"""
    try:
        from sqlalchemy import text
        engine = create_engine(POSTGRES_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            logger.info(f"✅ PostgreSQL connection successful: {version.split(',')[0]}")
        engine.dispose()
        return True
    except Exception as e:
        logger.error(f"❌ PostgreSQL connection failed: {e}")
        logger.error("\nPlease check:")
        logger.error("1. PostgreSQL is running: sudo systemctl status postgresql")
        logger.error("2. Database exists: sudo -u postgres psql -c '\\l'")
        logger.error("3. User has permissions: sudo -u postgres psql -c '\\du'")
        logger.error(f"4. DATABASE_URL is correct: {POSTGRES_URL.split('@')[0].split('://')[0]}://***@{POSTGRES_URL.split('@')[1]}")
        return False

def get_table_order():
    """
    Define table migration order to respect foreign key constraints
    Tables with no dependencies come first
    """
    return [
        'users',
        'portfolios',
        'portfolio_data',
        'portfolio_margin_data',
        'analysis_results',
        'analysis_plots',
        'blended_portfolios',
        'blended_portfolio_mappings',
        'optimization_cache',
        'favorite_settings',
        'robustness_tests',
        'robustness_periods',
        'robustness_statistics',
        'market_regime_history',
        'regime_alerts',
        'regime_performance',
        'margin_validation_rules',
        'daily_margin_aggregate'
    ]

def count_rows(engine, table_name):
    """Count rows in a table"""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            return result.fetchone()[0]
    except:
        return 0

def migrate_table(sqlite_engine, postgres_engine, table_name, batch_size=1000):
    """
    Migrate a single table from SQLite to PostgreSQL
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Migrating table: {table_name}")
    logger.info(f"{'='*60}")

    try:
        # Get source table count
        source_count = count_rows(sqlite_engine, table_name)

        if source_count == 0:
            logger.info(f"⏭️  Skipping {table_name} (empty table)")
            return True

        logger.info(f"📊 Source rows: {source_count:,}")

        # Reflect table structure from SQLite
        metadata = MetaData()
        metadata.reflect(bind=sqlite_engine)

        if table_name not in metadata.tables:
            logger.warning(f"⚠️  Table {table_name} not found in SQLite, skipping")
            return True

        table = metadata.tables[table_name]

        # Create table in PostgreSQL (using SQLAlchemy models)
        # The tables should already be created by create_tables()

        # Migrate data in batches
        sqlite_session = sessionmaker(bind=sqlite_engine)()
        postgres_session = sessionmaker(bind=postgres_engine)()

        try:
            # Read all data from SQLite
            select_stmt = table.select()

            with sqlite_engine.connect() as sqlite_conn:
                result = sqlite_conn.execute(select_stmt)

                migrated = 0
                failed = 0
                batch = []

                for row in result:
                    batch.append(dict(row._mapping))

                    if len(batch) >= batch_size:
                        # Insert batch
                        try:
                            with postgres_engine.connect() as postgres_conn:
                                postgres_conn.execute(table.insert(), batch)
                                postgres_conn.commit()
                            migrated += len(batch)
                            logger.info(f"  ✓ Migrated {migrated:,} / {source_count:,} rows ({migrated*100//source_count}%)")
                            batch = []
                        except IntegrityError as e:
                            logger.warning(f"  ⚠️  Integrity error in batch, trying row-by-row...")
                            # Try inserting rows individually
                            for row_data in batch:
                                try:
                                    with postgres_engine.connect() as postgres_conn:
                                        postgres_conn.execute(table.insert(), [row_data])
                                        postgres_conn.commit()
                                    migrated += 1
                                except IntegrityError:
                                    failed += 1
                            batch = []
                        except Exception as e:
                            logger.error(f"  ❌ Batch insert failed: {e}")
                            failed += len(batch)
                            batch = []

                # Insert remaining batch
                if batch:
                    try:
                        with postgres_engine.connect() as postgres_conn:
                            postgres_conn.execute(table.insert(), batch)
                            postgres_conn.commit()
                        migrated += len(batch)
                    except IntegrityError:
                        logger.warning(f"  ⚠️  Integrity error in final batch, trying row-by-row...")
                        for row_data in batch:
                            try:
                                with postgres_engine.connect() as postgres_conn:
                                    postgres_conn.execute(table.insert(), [row_data])
                                    postgres_conn.commit()
                                migrated += 1
                            except IntegrityError:
                                failed += 1
                    except Exception as e:
                        logger.error(f"  ❌ Final batch insert failed: {e}")
                        failed += len(batch)

            # Verify migration
            dest_count = count_rows(postgres_engine, table_name)

            logger.info(f"\n📈 Migration Summary for {table_name}:")
            logger.info(f"  • Source rows: {source_count:,}")
            logger.info(f"  • Migrated: {migrated:,}")
            logger.info(f"  • Failed: {failed:,}")
            logger.info(f"  • Destination rows: {dest_count:,}")

            if dest_count >= source_count - failed:
                logger.info(f"✅ {table_name} migration successful!")
                return True
            else:
                logger.warning(f"⚠️  {table_name} migration incomplete (expected {source_count}, got {dest_count})")
                return False

        finally:
            sqlite_session.close()
            postgres_session.close()

    except Exception as e:
        logger.error(f"❌ Failed to migrate {table_name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def reset_sequences(postgres_engine):
    """Reset PostgreSQL sequences after migration"""
    from sqlalchemy import text
    logger.info("\n🔄 Resetting PostgreSQL sequences...")

    with postgres_engine.connect() as conn:
        # Get all tables with id columns
        tables = get_table_order()

        for table_name in tables:
            try:
                # Try to reset the sequence
                result = conn.execute(text(f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table_name}', 'id'),
                        COALESCE((SELECT MAX(id) FROM {table_name}), 1)
                    );
                """))
                logger.info(f"  ✓ Reset sequence for {table_name}")
            except Exception as e:
                # Skip if table doesn't have an id column or sequence
                pass

    logger.info("✅ Sequences reset complete")

def main():
    """Main migration function"""
    logger.info("=" * 80)
    logger.info("SQLite to PostgreSQL Migration Tool")
    logger.info("=" * 80)

    # Check if .env file exists with DATABASE_URL
    if not os.getenv("DATABASE_URL"):
        logger.warning("\n⚠️  DATABASE_URL not set in environment")
        logger.info("Using default: postgresql://cmtool:password@localhost:5432/portfolio_analysis")
        logger.info("\nTo set a custom password, run:")
        logger.info("  export DATABASE_URL='postgresql://cmtool:your_password@localhost:5432/portfolio_analysis'")

        response = input("\nContinue with default? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Migration cancelled. Please set DATABASE_URL and try again.")
            sys.exit(0)

    # Verify connections
    logger.info("\n📡 Verifying database connections...")

    if not verify_postgres_connection():
        logger.error("\n❌ Cannot proceed without PostgreSQL connection")
        sys.exit(1)

    if not os.path.exists("portfolio_analysis.db"):
        logger.error("\n❌ SQLite database not found: portfolio_analysis.db")
        logger.error("Make sure you're running this script from the project root directory")
        sys.exit(1)

    logger.info("✅ SQLite database found")

    # Ask for confirmation
    logger.info("\n⚠️  WARNING: This will copy all data from SQLite to PostgreSQL")
    logger.info("Existing data in PostgreSQL will be preserved (no truncation)")
    response = input("\nProceed with migration? (yes/no): ")

    if response.lower() != 'yes':
        logger.info("Migration cancelled")
        sys.exit(0)

    # Create engines
    logger.info("\n🔧 Creating database engines...")
    sqlite_engine = create_engine(SQLITE_URL)
    postgres_engine = create_engine(POSTGRES_URL)

    # Import models to create tables
    logger.info("\n📋 Creating PostgreSQL tables...")
    try:
        from models import Base
        Base.metadata.create_all(bind=postgres_engine)
        logger.info("✅ Tables created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create tables: {e}")
        sys.exit(1)

    # Migrate tables in order
    logger.info("\n🚀 Starting data migration...")
    table_order = get_table_order()

    success_count = 0
    failed_tables = []

    for table_name in table_order:
        if migrate_table(sqlite_engine, postgres_engine, table_name):
            success_count += 1
        else:
            failed_tables.append(table_name)

    # Reset sequences
    reset_sequences(postgres_engine)

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("MIGRATION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"✅ Successfully migrated: {success_count} tables")

    if failed_tables:
        logger.warning(f"⚠️  Failed tables: {len(failed_tables)}")
        for table in failed_tables:
            logger.warning(f"  • {table}")

    logger.info("\n📝 Next steps:")
    logger.info("1. Set DATABASE_URL in your production environment")
    logger.info("2. Restart your application: sudo systemctl restart cmtool")
    logger.info("3. Test the application")
    logger.info("4. Keep the SQLite backup for safety")

    # Cleanup
    sqlite_engine.dispose()
    postgres_engine.dispose()

if __name__ == "__main__":
    main()
