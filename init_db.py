"""
Database initialization script for portfolio analysis application
"""
import logging
from database import create_tables, drop_tables, engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    """Initialize the database with all required tables"""
    try:
        logger.info("Initializing database...")
        
        # Create all tables
        create_tables()
        
        # Test database connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("Database connection test successful")
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def reset_database():
    """Drop and recreate all tables (for development/testing)"""
    try:
        logger.warning("Resetting database - all data will be lost!")
        
        # Drop all tables
        drop_tables()
        logger.info("All tables dropped")
        
        # Recreate tables
        create_tables()
        logger.info("All tables recreated")
        
        logger.info("Database reset completed successfully")
        
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        raise

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        reset_database()
    else:
        init_database()
