#!/usr/bin/env python3
"""
Migration: Add UPI (Ulcer Performance Index) column to analysis_results table

This migration adds the UPI column to store the Ulcer Performance Index metric
which measures risk-adjusted returns considering downside volatility.

UPI = Return / Ulcer Index
- Higher UPI values indicate better risk-adjusted performance
- Considers only negative deviations from running maximum (drawdowns)
- More sensitive to large drawdowns than Sharpe ratio

Created: 2024-01-20
"""

import sqlite3
import os
import sys
from datetime import datetime

def migrate_database(db_path: str):
    """Add UPI column to analysis_results table"""
    
    print(f"Starting UPI migration for database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if UPI column already exists
        cursor.execute("PRAGMA table_info(analysis_results)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'upi' in columns:
            print("✅ UPI column already exists, skipping migration")
            conn.close()
            return True
        
        # Add UPI column
        print("📊 Adding UPI (Ulcer Performance Index) column...")
        cursor.execute("""
            ALTER TABLE analysis_results 
            ADD COLUMN upi REAL DEFAULT 0.0
        """)
        
        # Update existing records with default UPI value (will be recalculated on next analysis)
        cursor.execute("""
            UPDATE analysis_results 
            SET upi = 0.0 
            WHERE upi IS NULL
        """)
        
        # Get count of updated records
        cursor.execute("SELECT COUNT(*) FROM analysis_results")
        total_records = cursor.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        print(f"✅ UPI migration completed successfully!")
        print(f"   - Added upi column to analysis_results table")
        print(f"   - Updated {total_records} existing records with default value")
        print(f"   - UPI values will be calculated on next portfolio analysis")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        return False

def main():
    """Run the migration"""
    
    # Default database path
    db_path = "portfolio_analysis.db"
    
    # Check if custom path provided
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    # Run migration
    success = migrate_database(db_path)
    
    if success:
        print("🎉 UPI migration completed successfully!")
        sys.exit(0)
    else:
        print("💥 UPI migration failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
