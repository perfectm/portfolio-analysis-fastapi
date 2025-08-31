"""
Database migration: Add regime analysis tables
Run this to add market regime analysis functionality to existing databases
"""

from sqlalchemy import create_engine, text
import os
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DATABASE_URL, engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_regime_tables():
    """Create regime analysis tables"""
    
    # SQL statements to create tables
    create_tables_sql = [
        """
        CREATE TABLE IF NOT EXISTS market_regime_history (
            id SERIAL PRIMARY KEY,
            date TIMESTAMP NOT NULL,
            regime VARCHAR(20) NOT NULL,
            confidence FLOAT NOT NULL,
            volatility_percentile FLOAT,
            trend_strength FLOAT,
            momentum_score FLOAT,
            drawdown_severity FLOAT,
            volume_anomaly FLOAT,
            market_symbol VARCHAR(10) NOT NULL DEFAULT '^GSPC',
            regime_start_date TIMESTAMP,
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_regime_history_date 
        ON market_regime_history(date)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_regime_history_symbol 
        ON market_regime_history(market_symbol)
        """,
        """
        CREATE TABLE IF NOT EXISTS regime_performance (
            id SERIAL PRIMARY KEY,
            portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
            regime VARCHAR(20) NOT NULL,
            total_return FLOAT,
            avg_daily_return FLOAT,
            volatility FLOAT,
            sharpe_ratio FLOAT,
            max_drawdown FLOAT,
            win_rate FLOAT,
            analysis_period_start TIMESTAMP,
            analysis_period_end TIMESTAMP,
            total_trading_days INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolio_regime_unique 
        ON regime_performance(portfolio_id, regime)
        """,
        """
        CREATE TABLE IF NOT EXISTS regime_alerts (
            id SERIAL PRIMARY KEY,
            alert_type VARCHAR(30) NOT NULL,
            previous_regime VARCHAR(20),
            new_regime VARCHAR(20) NOT NULL,
            confidence FLOAT NOT NULL,
            title VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            severity VARCHAR(20) NOT NULL DEFAULT 'info',
            recommended_allocations TEXT,
            projected_impact TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            acknowledged_at TIMESTAMP,
            dismissed_at TIMESTAMP,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            expires_at TIMESTAMP
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_regime_alerts_active 
        ON regime_alerts(is_active, expires_at)
        """
    ]
    
    try:
        with engine.begin() as conn:
            logger.info("Creating regime analysis tables...")
            
            for sql in create_tables_sql:
                logger.info(f"Executing: {sql[:50]}...")
                conn.execute(text(sql))
            
            logger.info("✅ Regime analysis tables created successfully!")
            
    except Exception as e:
        logger.error(f"❌ Failed to create regime tables: {e}")
        raise


def add_sample_regime_data():
    """Add sample regime data for testing"""
    
    sample_data_sql = """
    INSERT INTO market_regime_history 
    (date, regime, confidence, volatility_percentile, trend_strength, momentum_score, drawdown_severity, volume_anomaly, description)
    VALUES 
    (NOW() - INTERVAL '7 days', 'bull', 0.85, 0.3, 0.6, 0.2, 0.02, 0.1, 'Strong bull market conditions with low volatility'),
    (NOW() - INTERVAL '14 days', 'bull', 0.78, 0.4, 0.5, 0.15, 0.03, -0.2, 'Continued bull market with slight volatility increase'),
    (NOW() - INTERVAL '21 days', 'volatile', 0.65, 0.8, 0.1, -0.1, 0.05, 1.5, 'High volatility period with mixed signals'),
    (NOW() - INTERVAL '30 days', 'bear', 0.72, 0.9, -0.4, -0.3, 0.12, 0.8, 'Bear market conditions with high volatility')
    ON CONFLICT DO NOTHING
    """
    
    try:
        with engine.begin() as conn:
            logger.info("Adding sample regime data...")
            conn.execute(text(sample_data_sql))
            logger.info("✅ Sample regime data added!")
            
    except Exception as e:
        logger.error(f"❌ Failed to add sample data: {e}")


def verify_tables():
    """Verify that tables were created successfully"""
    
    verify_sql = """
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name IN ('market_regime_history', 'regime_performance', 'regime_alerts')
    ORDER BY table_name
    """
    
    try:
        with engine.begin() as conn:
            result = conn.execute(text(verify_sql))
            tables = [row[0] for row in result]
            
            logger.info(f"Found regime tables: {tables}")
            
            expected_tables = ['market_regime_history', 'regime_performance', 'regime_alerts']
            if all(table in tables for table in expected_tables):
                logger.info("✅ All regime tables verified successfully!")
                return True
            else:
                missing = set(expected_tables) - set(tables)
                logger.error(f"❌ Missing tables: {missing}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Failed to verify tables: {e}")
        return False


if __name__ == "__main__":
    logger.info("=== Regime Analysis Migration ===")
    logger.info(f"Database URL: {DATABASE_URL[:50]}...")
    
    try:
        # Create tables
        create_regime_tables()
        
        # Verify creation
        if verify_tables():
            # Add sample data
            add_sample_regime_data()
            logger.info("🎉 Migration completed successfully!")
        else:
            logger.error("❌ Migration failed - tables not verified")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        exit(1)