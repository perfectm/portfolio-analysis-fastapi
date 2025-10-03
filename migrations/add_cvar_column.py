#!/usr/bin/env python3
"""
Migration: Add CVaR (Conditional Value at Risk) column to analysis_results and robustness_periods tables

This migration adds the CVaR column to store the Conditional Value at Risk metric
which measures the expected loss in the worst 5% of scenarios.

CVaR (Expected Shortfall):
- Measures the mean of the worst 5% of daily returns
- Provides a more comprehensive risk measure than VaR alone
- Captures tail risk and extreme loss scenarios
- Expressed as a percentage of starting capital (negative values indicate expected loss)

Created: 2025-10-02
"""

import sqlite3
import os
import sys
from datetime import datetime

def migrate_database(db_path: str):
    """Add CVaR column to analysis_results and robustness_periods tables"""

    print(f"Starting CVaR migration for database: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if CVaR column already exists in analysis_results
        cursor.execute("PRAGMA table_info(analysis_results)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'cvar' in columns:
            print("✅ CVaR column already exists in analysis_results, skipping that table")
        else:
            # Add CVaR column to analysis_results
            print("📊 Adding CVaR (Conditional Value at Risk) column to analysis_results...")
            cursor.execute("""
                ALTER TABLE analysis_results
                ADD COLUMN cvar REAL DEFAULT 0.0
            """)

            # Update existing records with default CVaR value (will be recalculated on next analysis)
            cursor.execute("""
                UPDATE analysis_results
                SET cvar = 0.0
                WHERE cvar IS NULL
            """)

            # Get count of updated records
            cursor.execute("SELECT COUNT(*) FROM analysis_results")
            total_records = cursor.fetchone()[0]

            print(f"   - Added cvar column to analysis_results table")
            print(f"   - Updated {total_records} existing records with default value")

        # Check if robustness_periods table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='robustness_periods'
        """)

        if cursor.fetchone():
            # Check if CVaR column already exists in robustness_periods
            cursor.execute("PRAGMA table_info(robustness_periods)")
            robustness_columns = [column[1] for column in cursor.fetchall()]

            if 'cvar' in robustness_columns:
                print("✅ CVaR column already exists in robustness_periods, skipping that table")
            else:
                # Add CVaR column to robustness_periods
                print("📊 Adding CVaR column to robustness_periods...")
                cursor.execute("""
                    ALTER TABLE robustness_periods
                    ADD COLUMN cvar REAL DEFAULT 0.0
                """)

                # Update existing records
                cursor.execute("""
                    UPDATE robustness_periods
                    SET cvar = 0.0
                    WHERE cvar IS NULL
                """)

                # Get count of updated records
                cursor.execute("SELECT COUNT(*) FROM robustness_periods")
                robustness_records = cursor.fetchone()[0]

                print(f"   - Added cvar column to robustness_periods table")
                print(f"   - Updated {robustness_records} existing records with default value")
        else:
            print("ℹ️  robustness_periods table does not exist, skipping")

        conn.commit()
        conn.close()

        print(f"✅ CVaR migration completed successfully!")
        print(f"   - CVaR values will be calculated on next portfolio analysis")

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
        print("🎉 CVaR migration completed successfully!")
        sys.exit(0)
    else:
        print("💥 CVaR migration failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
