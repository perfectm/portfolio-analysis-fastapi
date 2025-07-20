"""
Database configuration and session management for PostgreSQL
"""
import os
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database URL - can be configured via environment variables
# For Render PostgreSQL: dpg-d1u03gbipnbc73cqnl2g-a
# Priority: DATABASE_URL env var > Render components > localhost fallback
if os.getenv("DATABASE_URL"):
    DATABASE_URL = os.getenv("DATABASE_URL")
    logger.info("Using DATABASE_URL environment variable")
else:
    # Local development fallback
    DATABASE_URL = "postgresql://postgres:password@localhost:5432/portfolio_analysis"

logger.info(f"Database URL configured: {DATABASE_URL.replace(DATABASE_URL.split('@')[0].split('://')[-1], '***')}")  # Hide credentials in logs

# Create SQLAlchemy engine with improved error handling
def create_database_engine():
    """Create database engine with fallback mechanisms"""
    global DATABASE_URL, engine
    
    try:
        # First, try the configured DATABASE_URL
        if DATABASE_URL.startswith("postgresql://"):
            engine = create_engine(
                DATABASE_URL,
                pool_pre_ping=True,
                echo=False,  # Set to True for SQL query logging
                connect_args={"connect_timeout": 30}  # 30 second timeout for first connection
            )
            
            # Test the connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info("✅ Database engine created successfully with PostgreSQL")
            return True
        else:
            # SQLite case
            engine = create_engine(
                DATABASE_URL,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=False
            )
            logger.info("✅ Database engine created successfully with SQLite")
            return False
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Failed to create PostgreSQL engine: {e}")
        
        # Check for specific error types and provide helpful messages
        if "no password supplied" in error_msg or "password authentication failed" in error_msg:
            logger.error("🔑 AUTHENTICATION ERROR:")
            logger.error("  - Make sure DATABASE_URL contains correct password")
            logger.error("  - Check your Render environment variables")
        elif "could not translate host name" in error_msg:
            logger.error("🌐 HOSTNAME ERROR:")
            logger.error("  - Check DATABASE_URL hostname in environment variables")
            logger.error("  - Database server may not be accessible from this network")
        elif "timeout" in error_msg.lower() or "connection refused" in error_msg.lower():
            logger.error("⏱️ CONNECTION ERROR:")
            logger.error("  - Database server may be starting up")
            logger.error("  - Network connectivity issue")
            logger.error("  - Wait a few minutes and retry")
        
        # Final fallback to SQLite for development
        logger.warning("⚠️ Falling back to SQLite database for local development")
        DATABASE_URL = "sqlite:///./portfolio_analysis.db"
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        logger.info("✅ Fallback to SQLite database successful")
        return False

# Initialize the database engine
postgresql_success = create_database_engine()

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()

# Metadata for migrations
metadata = MetaData()

def get_db():
    """
    Database session dependency for FastAPI
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """
    Create all tables in the database
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        raise

def drop_tables():
    """
    Drop all tables in the database (for development/testing)
    """
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error(f"Failed to drop tables: {e}")
        raise
