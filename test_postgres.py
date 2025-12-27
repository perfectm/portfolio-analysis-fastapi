#!/usr/bin/env python3
"""
Quick test script to verify PostgreSQL connection
Usage: python test_postgres.py
"""
import os
import sys
from sqlalchemy import create_engine, text

# Get PostgreSQL URL from environment or use default
POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://cmtool:password@localhost:5432/portfolio_analysis")

print("=" * 60)
print("PostgreSQL Connection Test")
print("=" * 60)
print(f"\nTesting connection to:")
print(f"  {POSTGRES_URL.split('@')[0].split('://')[0]}://***@{POSTGRES_URL.split('@')[1]}")

try:
    engine = create_engine(POSTGRES_URL)

    with engine.connect() as conn:
        # Test basic query
        result = conn.execute(text("SELECT version();"))
        version = result.fetchone()[0]
        print(f"\n✅ Connection successful!")
        print(f"\nPostgreSQL version:")
        print(f"  {version.split(',')[0]}")

        # Test database
        result = conn.execute(text("SELECT current_database();"))
        db = result.fetchone()[0]
        print(f"\nCurrent database: {db}")

        # Test user
        result = conn.execute(text("SELECT current_user;"))
        user = result.fetchone()[0]
        print(f"Current user: {user}")

        # Test permissions
        result = conn.execute(text("SELECT has_database_privilege(current_user, current_database(), 'CREATE');"))
        can_create = result.fetchone()[0]
        print(f"Can create tables: {'Yes' if can_create else 'No'}")

        print("\n✅ All tests passed! Ready for migration.")
        sys.exit(0)

except Exception as e:
    print(f"\n❌ Connection failed: {e}")
    print("\nTroubleshooting steps:")
    print("1. Check PostgreSQL is running:")
    print("   sudo systemctl status postgresql")
    print("\n2. Verify database exists:")
    print("   sudo -u postgres psql -c '\\l' | grep portfolio_analysis")
    print("\n3. Verify user exists:")
    print("   sudo -u postgres psql -c '\\du' | grep cmtool")
    print("\n4. Test password:")
    print("   psql -U cmtool -d portfolio_analysis -c 'SELECT 1;'")
    print("\n5. Set DATABASE_URL environment variable:")
    print("   export DATABASE_URL='postgresql://cmtool:your_password@localhost:5432/portfolio_analysis'")
    sys.exit(1)
