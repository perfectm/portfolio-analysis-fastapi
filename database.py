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
elif os.getenv("RENDER"):
    # Running on Render - construct URL from Render environment variables
    DB_HOST = os.getenv("DB_HOST", "dpg-d1u03gbipnbc73cqnl2g-a.render.com")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "portanal")
    DB_USER = os.getenv("DB_USER", "portanal_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    # Local development fallback
    DATABASE_URL = "postgresql://postgres:password@localhost:5432/portfolio_analysis"

logger.info(f"Database URL configured: {DATABASE_URL.replace(DATABASE_URL.split('@')[0].split('://')[-1], '***')}")  # Hide credentials in logs

# Create SQLAlchemy engine
try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        echo=False,  # Set to True for SQL query logging
    )
    logger.info("Database engine created successfully")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    # Fallback to SQLite for development
    DATABASE_URL = "sqlite:///./portfolio_analysis.db"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    logger.info("Fallback to SQLite database")

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
