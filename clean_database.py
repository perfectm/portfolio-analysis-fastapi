#!/usr/bin/env python3
"""
Database cleanup script for portfolio analysis application.
This script will completely wipe all data from the database and remove uploaded files.
"""

import os
import shutil
import sqlite3
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def delete_database_file():
    """Remove the SQLite database file completely."""
    db_path = "portfolio_analysis.db"
    
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            logger.info(f"✅ Deleted database file: {db_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete database file: {e}")
            return False
    else:
        logger.info(f"ℹ️ Database file {db_path} does not exist")
        return True

def truncate_all_tables():
    """Clear all data from tables while preserving schema."""
    db_path = "portfolio_analysis.db"
    
    if not os.path.exists(db_path):
        logger.info(f"ℹ️ Database file {db_path} does not exist")
        return True
    
    # List of tables in order (respecting foreign key constraints)
    tables_to_clear = [
        # Child tables first (those with foreign keys)
        'robustness_statistics',
        'robustness_periods', 
        'robustness_tests',
        'daily_margin_aggregate',
        'portfolio_margin_data',
        'regime_alerts',
        'regime_performance',
        'market_regime_history',
        'optimization_cache',
        'blended_portfolio_mappings',
        'blended_portfolios',
        'analysis_plots',
        'analysis_results',
        'portfolio_data',
        'portfolios',
        'margin_validation_rules',
        'users'
    ]
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Disable foreign key constraints temporarily
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        deleted_count = 0
        for table in tables_to_clear:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                if count > 0:
                    cursor.execute(f"DELETE FROM {table}")
                    logger.info(f"✅ Cleared {count} rows from {table}")
                    deleted_count += count
                else:
                    logger.info(f"ℹ️ Table {table} is already empty")
            except sqlite3.OperationalError as e:
                if "no such table" in str(e):
                    logger.info(f"ℹ️ Table {table} does not exist")
                else:
                    logger.warning(f"⚠️ Error clearing table {table}: {e}")
        
        # Reset auto-increment counters (if table exists)
        try:
            cursor.execute("DELETE FROM sqlite_sequence")
            logger.info("✅ Reset all auto-increment counters")
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                logger.info("ℹ️ No auto-increment counters to reset")
            else:
                logger.warning(f"⚠️ Error resetting auto-increment counters: {e}")
        
        # Re-enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Successfully cleared {deleted_count} total rows from database")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to truncate tables: {e}")
        return False

def clean_uploaded_files():
    """Remove all uploaded portfolio files and generated plots."""
    directories_to_clean = [
        "uploads/portfolios",
        "uploads/plots", 
        "uploads",
        "plots"
    ]
    
    for directory in directories_to_clean:
        if os.path.exists(directory):
            try:
                shutil.rmtree(directory)
                logger.info(f"✅ Deleted directory: {directory}")
            except Exception as e:
                logger.error(f"❌ Failed to delete directory {directory}: {e}")
        else:
            logger.info(f"ℹ️ Directory {directory} does not exist")

def recreate_upload_directories():
    """Recreate the necessary upload directories."""
    directories_to_create = [
        "uploads",
        "uploads/portfolios",
        "uploads/plots"
    ]
    
    for directory in directories_to_create:
        try:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"✅ Created directory: {directory}")
        except Exception as e:
            logger.error(f"❌ Failed to create directory {directory}: {e}")

def main():
    """Main cleanup function."""
    logger.info("🧹 Starting database cleanup...")
    
    # Ask user to choose cleanup method
    print("\n" + "="*70)
    print("⚠️  WARNING: This will permanently delete ALL data!")
    print("="*70)
    print("Choose cleanup method:")
    print()
    print("1. TRUNCATE TABLES (Recommended)")
    print("   • Deletes all data from tables")
    print("   • Preserves database schema and structure")
    print("   • Faster startup (no table recreation needed)")
    print("   • Resets auto-increment counters")
    print()
    print("2. DELETE DATABASE FILE")
    print("   • Completely removes database file")
    print("   • Schema will be recreated on next startup")
    print("   • Slower startup (full table recreation)")
    print()
    print("Both options will also:")
    print("• Remove all uploaded portfolio CSV files")  
    print("• Remove all generated analysis plots")
    print("• Remove all cached analysis results")
    print("• Remove all user accounts and authentication data")
    print("• Remove all robustness test data")
    print("• Remove all margin data and validation rules")
    print("• Remove all market regime analysis data")
    print("="*70)
    
    # Get user choice
    while True:
        choice = input("\nChoose option (1 or 2): ").strip()
        if choice in ['1', '2']:
            break
        print("❌ Please enter 1 or 2")
    
    method_name = "TRUNCATE TABLES" if choice == '1' else "DELETE DATABASE FILE"
    
    # Ask for confirmation
    confirmation = input(f"\nType 'CONFIRM {method_name}' to proceed: ")
    expected = f"CONFIRM {method_name}"
    if confirmation != expected:
        print("❌ Cleanup cancelled.")
        return
    
    print(f"\n🧹 Proceeding with {method_name.lower()}...")
    
    # 1. Clean database based on choice
    if choice == '1':
        success = truncate_all_tables()
    else:
        success = delete_database_file()
    
    if not success:
        print("❌ Database cleanup failed!")
        return
    
    # 2. Clean uploaded files and plots
    clean_uploaded_files()
    
    # 3. Recreate necessary directories
    recreate_upload_directories()
    
    logger.info("✅ Database cleanup completed successfully!")
    
    # Show completion message based on method
    print("\n" + "="*70)
    if choice == '1':
        print("🎉 Table truncation complete! The application now has:")
        print("• Empty database tables with preserved schema")
        print("• Fast startup (no table recreation needed)")
    else:
        print("🎉 Database deletion complete! The application now has:")
        print("• No database file (will be recreated on next startup)")
        print("• Slower first startup (full schema recreation)")
    
    print("• Clean file system with empty upload directories")
    print("• No user accounts (you'll need to register again)")
    print("• No portfolio or analysis data")
    print("="*70)
    print("\nTo use the application:")
    print("1. Start the server with: ./start.sh")
    print("2. Register a new user account")
    print("3. Upload fresh portfolio CSV files")

if __name__ == "__main__":
    main()