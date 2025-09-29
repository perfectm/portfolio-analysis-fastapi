#!/usr/bin/env python3
"""
Database migration: Add contracts column to portfolio_data table
- contracts: Number of contracts for each trade (from CSV)
"""
import logging
from sqlalchemy import text
from database import engine

logger = logging.getLogger(__name__)

def add_contracts_column():
    """Add contracts column to portfolio_data table if it doesn't exist"""
    try:
        with engine.begin() as connection:
            # Check database type
            if engine.dialect.name == 'postgresql':
                # Check if column already exists for PostgreSQL
                result = connection.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'portfolio_data' AND column_name = 'contracts'
                """))
                
                if result.fetchone():
                    logger.info("Column contracts already exists in portfolio_data table")
                else:
                    connection.execute(text("""
                        ALTER TABLE portfolio_data ADD COLUMN contracts INTEGER
                    """))
                    logger.info("Successfully added contracts column to portfolio_data table")
                
            else:  # SQLite
                # Check existing columns for SQLite
                result = connection.execute(text("""
                    PRAGMA table_info(portfolio_data)
                """))
                existing_columns = [row[1] for row in result.fetchall()]
                
                if 'contracts' not in existing_columns:
                    connection.execute(text("""
                        ALTER TABLE portfolio_data ADD COLUMN contracts INTEGER
                    """))
                    logger.info("Successfully added contracts column to portfolio_data table")
                else:
                    logger.info("Column contracts already exists in portfolio_data table")
                
            return True
            
    except Exception as e:
        logger.error(f"Error adding contracts column: {e}")
        return False

def main():
    """Run the migration"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    logger.info("Starting database migration: Add contracts column")
    
    if add_contracts_column():
        logger.info("Migration completed successfully")
    else:
        logger.error("Migration failed")
        exit(1)

if __name__ == "__main__":
    main()