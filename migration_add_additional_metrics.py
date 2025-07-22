#!/usr/bin/env python3
"""
Database migration: Add additional metrics columns to analysis_results table
- sortino_ratio: Sortino ratio for risk-adjusted returns using downside deviation
- ulcer_index: Ulcer index for measuring drawdown risk
- max_drawdown_date: Date when maximum drawdown occurred
"""
import logging
from sqlalchemy import text
from database import engine

logger = logging.getLogger(__name__)

def add_additional_metrics_columns():
    """Add new metrics columns to analysis_results table if they don't exist"""
    try:
        with engine.begin() as connection:
            # Check database type
            if engine.dialect.name == 'postgresql':
                # Check if columns already exist for PostgreSQL
                columns_to_add = ['sortino_ratio', 'ulcer_index', 'max_drawdown_date']
                existing_columns = []
                
                for column in columns_to_add:
                    result = connection.execute(text(f"""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'analysis_results' AND column_name = '{column}'
                    """))
                    if result.fetchone():
                        existing_columns.append(column)
                        logger.info(f"Column {column} already exists in analysis_results table")
                
                # Add missing columns for PostgreSQL
                for column in columns_to_add:
                    if column not in existing_columns:
                        if column == 'max_drawdown_date':
                            connection.execute(text(f"""
                                ALTER TABLE analysis_results ADD COLUMN {column} VARCHAR(20)
                            """))
                        else:
                            connection.execute(text(f"""
                                ALTER TABLE analysis_results ADD COLUMN {column} FLOAT
                            """))
                        logger.info(f"Successfully added {column} column to analysis_results table")
                
            else:  # SQLite
                # Check existing columns for SQLite
                result = connection.execute(text("""
                    PRAGMA table_info(analysis_results)
                """))
                existing_columns = [row[1] for row in result.fetchall()]
                
                columns_to_add = {
                    'sortino_ratio': 'FLOAT',
                    'ulcer_index': 'FLOAT', 
                    'max_drawdown_date': 'VARCHAR(20)'
                }
                
                for column, data_type in columns_to_add.items():
                    if column not in existing_columns:
                        connection.execute(text(f"""
                            ALTER TABLE analysis_results ADD COLUMN {column} {data_type}
                        """))
                        logger.info(f"Successfully added {column} column to analysis_results table")
                    else:
                        logger.info(f"Column {column} already exists in analysis_results table")
                
            return True
            
    except Exception as e:
        logger.error(f"Error adding additional metrics columns: {e}")
        return False

def main():
    """Run the migration"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    logger.info("Starting database migration: Add additional metrics columns")
    
    if add_additional_metrics_columns():
        logger.info("Migration completed successfully")
    else:
        logger.error("Migration failed")
        exit(1)

if __name__ == "__main__":
    main()
