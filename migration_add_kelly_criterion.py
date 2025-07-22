#!/usr/bin/env python3
"""
Database migration: Add kelly_criterion column to analysis_results table
- kelly_criterion: Kelly criterion for optimal position sizing based on win/loss probabilities
"""
import logging
from sqlalchemy import text
from database import engine

logger = logging.getLogger(__name__)

def add_kelly_criterion_column():
    """Add kelly_criterion column to analysis_results table if it doesn't exist"""
    try:
        with engine.begin() as connection:
            # Check database type
            if engine.dialect.name == 'postgresql':
                # Check if column already exists for PostgreSQL
                result = connection.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'analysis_results' AND column_name = 'kelly_criterion'
                """))
                
                if result.fetchone():
                    logger.info("Column kelly_criterion already exists in analysis_results table")
                else:
                    connection.execute(text("""
                        ALTER TABLE analysis_results ADD COLUMN kelly_criterion FLOAT
                    """))
                    logger.info("Successfully added kelly_criterion column to analysis_results table")
                
            else:  # SQLite
                # Check existing columns for SQLite
                result = connection.execute(text("""
                    PRAGMA table_info(analysis_results)
                """))
                existing_columns = [row[1] for row in result.fetchall()]
                
                if 'kelly_criterion' not in existing_columns:
                    connection.execute(text("""
                        ALTER TABLE analysis_results ADD COLUMN kelly_criterion FLOAT
                    """))
                    logger.info("Successfully added kelly_criterion column to analysis_results table")
                else:
                    logger.info("Column kelly_criterion already exists in analysis_results table")
                
            return True
            
    except Exception as e:
        logger.error(f"Error adding kelly_criterion column: {e}")
        return False

def main():
    """Run the migration"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    logger.info("Starting database migration: Add kelly_criterion column")
    
    if add_kelly_criterion_column():
        logger.info("Migration completed successfully")
    else:
        logger.error("Migration failed")
        exit(1)

if __name__ == "__main__":
    main()
