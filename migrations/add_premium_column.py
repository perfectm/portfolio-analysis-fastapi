"""
Migration script to add the premium column to portfolio_data table
"""
import sqlite3
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DATABASE_URL

def migrate():
    """Add premium column to portfolio_data table"""
    db_url = DATABASE_URL
    
    if db_url.startswith('sqlite'):
        # Extract database path from sqlite URL
        db_path = db_url.replace('sqlite:///', '')
        
        print(f"Connecting to SQLite database: {db_path}")
        
        try:
            # Connect to SQLite database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if premium column already exists
            cursor.execute("PRAGMA table_info(portfolio_data);")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'premium' not in columns:
                print("Adding premium column to portfolio_data table...")
                cursor.execute("ALTER TABLE portfolio_data ADD COLUMN premium REAL;")
                conn.commit()
                print("✅ Successfully added premium column!")
            else:
                print("ℹ️  Premium column already exists")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"❌ Error during migration: {e}")
            return False
    else:
        print("This migration is only for SQLite databases")
        return False
    
    return True

if __name__ == "__main__":
    success = migrate()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")
        sys.exit(1)