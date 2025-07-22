#!/usr/bin/env python3
"""
Database migration: Add strategy column to portfolios table
"""
import logging
from sqlalchemy import text
from database import engine

logger = logging.getLogger(__name__)

def add_strategy_column():
    """Add strategy column to portfolios table if it doesn't exist"""
    try:
        with engine.begin() as connection:  # Use begin() for auto-commit
            # Check if column already exists
            if engine.dialect.name == 'postgresql':
                result = connection.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'portfolios' AND column_name = 'strategy'
                """))
                if result.fetchone():
                    logger.info("Strategy column already exists in portfolios table")
                    return True
                
                # Add column for PostgreSQL
                connection.execute(text("""
                    ALTER TABLE portfolios ADD COLUMN strategy VARCHAR(255)
                """))
                logger.info("Successfully added strategy column to portfolios table")
                return True
            else:  # SQLite
                result = connection.execute(text("""
                    PRAGMA table_info(portfolios)
                """))
                columns = [row[1] for row in result.fetchall()]
                if 'strategy' in columns:
                    logger.info("Strategy column already exists in portfolios table")
                    return True
                
                # Add column for SQLite
                connection.execute(text("""
                    ALTER TABLE portfolios ADD COLUMN strategy VARCHAR(255)
                """))
                logger.info("Successfully added strategy column to portfolios table")
                return True
            
    except Exception as e:
        logger.error(f"Error adding strategy column: {e}")
        return False

def main():
    """Run the migration"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    logger.info("Starting database migration: Add strategy column")
    
    if add_strategy_column():
        logger.info("Migration completed successfully")
    else:
        logger.error("Migration failed")
        exit(1)

if __name__ == "__main__":
    main()
