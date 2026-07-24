#!/usr/bin/env python3
"""
Migration to add comparison_uploads and comparison_trades tables for
the Live vs Backtest comparison feature (TradeSteward + Backtick formats).
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CREATE_UPLOADS_SQL = """
CREATE TABLE IF NOT EXISTS comparison_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    upload_type VARCHAR(20) NOT NULL,
    source_format VARCHAR(30) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    period_start TIMESTAMP,
    period_end TIMESTAMP,
    trade_count INTEGER NOT NULL DEFAULT 0,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

CREATE_TRADES_SQL = """
CREATE TABLE IF NOT EXISTS comparison_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upload_id INTEGER NOT NULL,
    bot_name VARCHAR(255) NOT NULL,
    strategy VARCHAR(255),
    entry_date TIMESTAMP NOT NULL,
    exit_date TIMESTAMP,
    pl FLOAT NOT NULL,
    win_loss INTEGER,
    buying_power FLOAT,
    contracts INTEGER,
    account_num VARCHAR(50),
    FOREIGN KEY (upload_id) REFERENCES comparison_uploads(id) ON DELETE CASCADE
);
"""

# Postgres needs SERIAL instead of AUTOINCREMENT
CREATE_UPLOADS_SQL_PG = """
CREATE TABLE IF NOT EXISTS comparison_uploads (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    upload_type VARCHAR(20) NOT NULL,
    source_format VARCHAR(30) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    period_start TIMESTAMP,
    period_end TIMESTAMP,
    trade_count INTEGER NOT NULL DEFAULT 0,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_TRADES_SQL_PG = """
CREATE TABLE IF NOT EXISTS comparison_trades (
    id SERIAL PRIMARY KEY,
    upload_id INTEGER NOT NULL REFERENCES comparison_uploads(id) ON DELETE CASCADE,
    bot_name VARCHAR(255) NOT NULL,
    strategy VARCHAR(255),
    entry_date TIMESTAMP NOT NULL,
    exit_date TIMESTAMP,
    pl FLOAT NOT NULL,
    win_loss INTEGER,
    buying_power FLOAT,
    contracts INTEGER,
    account_num VARCHAR(50)
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_comparison_uploads_user_type ON comparison_uploads (user_id, upload_type);",
    "CREATE INDEX IF NOT EXISTS idx_comparison_trades_bot_date ON comparison_trades (bot_name, entry_date);",
    "CREATE INDEX IF NOT EXISTS idx_comparison_trades_upload_bot ON comparison_trades (upload_id, bot_name);",
    "CREATE INDEX IF NOT EXISTS idx_comparison_trades_upload ON comparison_trades (upload_id);",
]


def run_migration():
    is_postgres = engine.url.drivername.startswith("postgresql")
    uploads_sql = CREATE_UPLOADS_SQL_PG if is_postgres else CREATE_UPLOADS_SQL
    trades_sql = CREATE_TRADES_SQL_PG if is_postgres else CREATE_TRADES_SQL

    try:
        with engine.connect() as conn:
            conn.execute(text(uploads_sql))
            logger.info("Created comparison_uploads table")
            conn.execute(text(trades_sql))
            logger.info("Created comparison_trades table")
            for idx_sql in CREATE_INDEXES_SQL:
                conn.execute(text(idx_sql))
            conn.commit()
        logger.info("Comparison tables migration completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    run_migration()
