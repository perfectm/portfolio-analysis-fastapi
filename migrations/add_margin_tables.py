#!/usr/bin/env python3
"""
Database migration to add margin requirement tables
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from database import DATABASE_URL, Base
from models import PortfolioMarginData, DailyMarginAggregate, MarginValidationRule
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """
    Run the margin tables migration
    """
    try:
        logger.info("Starting margin tables migration...")
        
        # Get database URL
        logger.info(f"Using database: {DATABASE_URL}")
        
        # Create engine
        engine = create_engine(DATABASE_URL)
        
        # Create the new margin tables
        logger.info("Creating margin requirement tables...")
        
        # Import the models to ensure they're registered with Base
        from models import (
            PortfolioMarginData, 
            DailyMarginAggregate, 
            MarginValidationRule
        )
        
        # Create tables
        Base.metadata.create_all(engine, tables=[
            PortfolioMarginData.__table__,
            DailyMarginAggregate.__table__,
            MarginValidationRule.__table__
        ])
        
        logger.info("✅ Successfully created margin requirement tables:")
        logger.info("   - portfolio_margin_data")
        logger.info("   - daily_margin_aggregate") 
        logger.info("   - margin_validation_rules")
        
        # Initialize default validation rules
        logger.info("Initializing default validation rules...")
        
        with engine.connect() as conn:
            # Check if rules already exist
            result = conn.execute(text("SELECT COUNT(*) FROM margin_validation_rules"))
            count = result.scalar()
            
            if count == 0:
                # Insert default rules
                conn.execute(text("""
                    INSERT INTO margin_validation_rules (rule_name, rule_type, threshold_value, is_active, description)
                    VALUES 
                    ('max_margin_percentage', 'percentage_threshold', 85.0, true, 'Maximum percentage of starting capital that can be used for margin requirements'),
                    ('critical_margin_percentage', 'percentage_threshold', 95.0, true, 'Critical threshold where margin requirements become extremely risky')
                """))
                conn.commit()
                logger.info("✅ Initialized default margin validation rules")
            else:
                logger.info("✅ Margin validation rules already exist")
        
        logger.info("🎉 Margin tables migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise e

if __name__ == "__main__":
    try:
        success = run_migration()
        if success:
            print("✅ Migration completed successfully!")
        else:
            print("❌ Migration failed!")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Migration error: {e}")
        sys.exit(1)