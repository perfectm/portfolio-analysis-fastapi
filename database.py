"""
Database configuration and session management for PostgreSQL
"""
import os
from sqlalchemy import create_engine, MetaData
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
elif os.getenv("RENDER") or os.getenv("DB_HOST"):
    # Running on Render or with explicit database configuration
    # Try the internal hostname first (without .render.com), then external
    DB_HOST = os.getenv("DB_HOST", "dpg-d1u03gbipnbc73cqnl2g-a")
    if not DB_HOST.endswith('.render.com') and not DB_HOST.startswith('localhost'):
        # If it's just the database identifier, try both internal and external formats
        DB_HOST = "dpg-d1u03gbipnbc73cqnl2g-a"  # Internal hostname for Render
    
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "portanal")
    DB_USER = os.getenv("DB_USER", "portanal_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    logger.info(f"Using Render database configuration with host: {DB_HOST}")
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
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            echo=False,  # Set to True for SQL query logging
            connect_args={"connect_timeout": 10}  # 10 second timeout
        )
        
        # Test the connection
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        
        logger.info("Database engine created successfully with PostgreSQL")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create PostgreSQL engine: {e}")
        
        # If on Render and the external hostname failed, try internal hostname
        if os.getenv("RENDER") and "render.com" in DATABASE_URL:
            try:
                # Try with internal hostname (without .render.com)
                internal_host = DATABASE_URL.replace(".render.com", "")
                logger.info(f"Trying internal hostname: {internal_host}")
                
                engine = create_engine(
                    internal_host,
                    pool_pre_ping=True,
                    echo=False,
                    connect_args={"connect_timeout": 10}
                )
                
                # Test the connection
                with engine.connect() as conn:
                    conn.execute("SELECT 1")
                
                DATABASE_URL = internal_host
                logger.info("Database engine created successfully with internal hostname")
                return True
                
            except Exception as e2:
                logger.error(f"Internal hostname also failed: {e2}")
        
        # Final fallback to SQLite
        logger.warning("Falling back to SQLite database for local development")
        DATABASE_URL = "sqlite:///./portfolio_analysis.db"
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        logger.info("Fallback to SQLite database successful")
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
