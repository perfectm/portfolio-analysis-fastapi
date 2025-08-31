#!/usr/bin/env python3
"""
Migration to add optimization cache table
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_optimization_cache_table():
    """Add the optimization_cache table to the database"""
    
    logger.info("Adding optimization_cache table...")
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS optimization_cache (
        id INTEGER PRIMARY KEY,
        portfolio_ids_hash VARCHAR(64) NOT NULL,
        portfolio_ids VARCHAR(500) NOT NULL,
        portfolio_count INTEGER NOT NULL,
        rf_rate FLOAT NOT NULL,
        sma_window INTEGER NOT NULL,
        use_trading_filter BOOLEAN NOT NULL,
        starting_capital FLOAT NOT NULL,
        min_weight FLOAT NOT NULL,
        max_weight FLOAT NOT NULL,
        optimization_method VARCHAR(50) NOT NULL,
        optimal_weights TEXT NOT NULL,
        optimal_ratios TEXT NOT NULL,
        iterations INTEGER NOT NULL,
        success BOOLEAN NOT NULL,
        optimal_cagr FLOAT NOT NULL,
        optimal_max_drawdown FLOAT NOT NULL,
        optimal_return_drawdown_ratio FLOAT NOT NULL,
        optimal_sharpe_ratio FLOAT NOT NULL,
        execution_time_seconds FLOAT,
        explored_combinations_count INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        access_count INTEGER DEFAULT 1
    );
    """
    
    # Create indexes
    create_indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_portfolio_hash_params ON optimization_cache (portfolio_ids_hash, rf_rate, sma_window, use_trading_filter);",
        "CREATE INDEX IF NOT EXISTS idx_portfolio_count ON optimization_cache (portfolio_count);",
        "CREATE INDEX IF NOT EXISTS idx_created_at ON optimization_cache (created_at);",
        "CREATE INDEX IF NOT EXISTS idx_portfolio_ids_hash ON optimization_cache (portfolio_ids_hash);"
    ]
    
    try:
        with engine.connect() as conn:
            # Create table
            conn.execute(text(create_table_sql))
            logger.info("Created optimization_cache table")
            
            # Create indexes
            for index_sql in create_indexes_sql:
                conn.execute(text(index_sql))
                logger.info(f"Created index: {index_sql.split('idx_')[1].split(' ')[0] if 'idx_' in index_sql else 'unknown'}")
            
            conn.commit()
            logger.info("Migration completed successfully!")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    add_optimization_cache_table()