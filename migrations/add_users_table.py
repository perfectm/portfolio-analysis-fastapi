#!/usr/bin/env python3
"""
Migration to add users table for authentication
"""
from sqlalchemy import text
from database import engine

def run_migration():
    """
    Add users table for authentication system
    """
    try:
        # SQL statements to create users table (SQLite compatible)
        create_table_sql = text("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            hashed_password VARCHAR(255) NOT NULL,
            full_name VARCHAR(255),
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME
        )
        """)
        
        create_username_index = text("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        create_email_index = text("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        
        # Run each SQL statement separately
        with engine.begin() as conn:
            conn.execute(create_table_sql)
            conn.execute(create_username_index) 
            conn.execute(create_email_index)
            
        print("✅ Users table migration completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        return False

def run_sync_migration(sql):
    """Run migration with sync engine"""
    with engine.begin() as conn:
        conn.execute(sql)

if __name__ == "__main__":
    print("🚀 Running users table migration...")
    success = run_migration()
    if not success:
        exit(1)