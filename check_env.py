#!/usr/bin/env python3
"""
Environment variable checker for database configuration
Run this to debug database connection issues
"""

import os

def check_environment():
    """Check all database-related environment variables"""
    print("🔍 Database Environment Variable Check")
    print("=" * 50)
    
    # Check for DATABASE_URL first
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        print(f"✅ DATABASE_URL: {database_url[:20]}...{database_url[-20:] if len(database_url) > 40 else database_url}")
        return
    
    # Check individual components
    print("📋 Individual Database Components:")
    
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    
    print(f"   DB_HOST: {'✅ ' + db_host if db_host else '❌ Not set'}")
    print(f"   DB_PORT: {'✅ ' + db_port if db_port else '❌ Not set (will default to 5432)'}")
    print(f"   DB_NAME: {'✅ ' + db_name if db_name else '❌ Not set'}")
    print(f"   DB_USER: {'✅ ' + db_user if db_user else '❌ Not set'}")
    print(f"   DB_PASSWORD: {'✅ Set (length: ' + str(len(db_password)) + ')' if db_password else '❌ NOT SET - THIS WILL CAUSE CONNECTION FAILURE'}")
    
    # Check other relevant environment variables
    print("\n🔧 Other Environment Variables:")
    render = os.getenv("RENDER")
    environment = os.getenv("ENVIRONMENT")
    
    print(f"   RENDER: {'✅ ' + render if render else '❌ Not set'}")
    print(f"   ENVIRONMENT: {'✅ ' + environment if environment else '❌ Not set'}")
    
    # Provide recommendations
    print("\n💡 Recommendations:")
    
    if not db_password:
        print("   🚨 CRITICAL: Set DB_PASSWORD environment variable")
        print("   Contact your database administrator for the correct password")
    
    if not db_host:
        print("   ⚠️  Set DB_HOST to: dpg-d1u03gbipnbc73cqnl2g-a")
    
    if not db_name:
        print("   ⚠️  Set DB_NAME to: portanal")
        
    if not db_user:
        print("   ⚠️  Set DB_USER to: portanal_user")
    
    if not render:
        print("   💡 Set RENDER=true for production deployment")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    check_environment()
