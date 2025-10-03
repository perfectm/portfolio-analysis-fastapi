#!/usr/bin/env python3
"""
Migration: Backfill CVaR values for existing analysis results

This script recalculates CVaR for all existing analysis results that don't have it.
It reads the portfolio data, recalculates CVaR, and updates the analysis_results table.

Created: 2025-10-02
"""

import sqlite3
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

def calculate_cvar(daily_returns: pd.Series, starting_capital: float, confidence_level: float = 0.05) -> float:
    """
    Calculate Conditional Value at Risk (CVaR) - mean of the worst 5% of outcomes
    Returns dollar amount (negative value indicates expected loss)
    """
    if len(daily_returns) == 0:
        return 0.0

    # Sort returns to find the worst outcomes
    sorted_returns = daily_returns.sort_values()

    # Calculate the number of observations in the tail (worst 5%)
    n_tail = int(np.ceil(len(sorted_returns) * confidence_level))

    if n_tail == 0:
        return 0.0

    # Get the worst returns (bottom 5%)
    worst_returns = sorted_returns.iloc[:n_tail]

    # Calculate the mean of the worst returns
    cvar_return = worst_returns.mean()

    # Convert to dollar loss based on starting capital
    cvar_dollar = cvar_return * starting_capital

    return cvar_dollar


def backfill_cvar(db_path: str):
    """Backfill CVaR values for existing analysis results"""

    print(f"Starting CVaR backfill for database: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all analysis results that need CVaR calculation
        # Force recalculation for all records (not just NULL or 0) since we changed from % to $
        cursor.execute("""
            SELECT ar.id, ar.portfolio_id, ar.starting_capital, ar.cvar
            FROM analysis_results ar
            ORDER BY ar.id
        """)

        results_to_update = cursor.fetchall()
        total_count = len(results_to_update)

        if total_count == 0:
            print("✅ No analysis results need CVaR backfill")
            conn.close()
            return True

        print(f"📊 Found {total_count} analysis results to update")
        print()

        updated_count = 0
        skipped_count = 0

        for idx, (analysis_id, portfolio_id, starting_capital, current_cvar) in enumerate(results_to_update, 1):
            try:
                print(f"[{idx}/{total_count}] Processing analysis_id={analysis_id}, portfolio_id={portfolio_id}...", end=" ")

                # Get portfolio data for this analysis
                cursor.execute("""
                    SELECT date, pl, cumulative_pl, account_value
                    FROM portfolio_data
                    WHERE portfolio_id = ?
                    ORDER BY date
                """, (portfolio_id,))

                data_records = cursor.fetchall()

                if not data_records:
                    print("⚠️  No data found, skipping")
                    skipped_count += 1
                    continue

                # Convert to DataFrame
                df = pd.DataFrame(data_records, columns=['Date', 'P/L', 'Cumulative P/L', 'Account Value'])
                df['Date'] = pd.to_datetime(df['Date'])

                # Calculate daily returns from account value
                daily_returns = df['Account Value'].pct_change().dropna()

                if len(daily_returns) == 0:
                    print("⚠️  No returns data, skipping")
                    skipped_count += 1
                    continue

                # Calculate CVaR
                cvar_value = calculate_cvar(daily_returns, starting_capital or 1000000)

                # Update the analysis result
                cursor.execute("""
                    UPDATE analysis_results
                    SET cvar = ?
                    WHERE id = ?
                """, (cvar_value, analysis_id))

                # Also update metrics_json if it exists
                cursor.execute("""
                    SELECT metrics_json FROM analysis_results WHERE id = ?
                """, (analysis_id,))

                metrics_json_row = cursor.fetchone()
                if metrics_json_row and metrics_json_row[0]:
                    import json
                    try:
                        metrics = json.loads(metrics_json_row[0])
                        metrics['cvar'] = float(cvar_value)

                        cursor.execute("""
                            UPDATE analysis_results
                            SET metrics_json = ?
                            WHERE id = ?
                        """, (json.dumps(metrics), analysis_id))
                    except json.JSONDecodeError:
                        pass  # Skip if JSON is invalid

                print(f"✅ CVaR = ${cvar_value:,.2f}")
                updated_count += 1

                # Commit every 10 records
                if updated_count % 10 == 0:
                    conn.commit()

            except Exception as e:
                print(f"❌ Error: {str(e)}")
                skipped_count += 1
                continue

        # Final commit
        conn.commit()
        conn.close()

        print()
        print("="*60)
        print(f"✅ CVaR backfill completed successfully!")
        print(f"   - Total analysis results: {total_count}")
        print(f"   - Successfully updated: {updated_count}")
        print(f"   - Skipped: {skipped_count}")
        print("="*60)

        return True

    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run the backfill migration"""

    # Default database path
    db_path = "portfolio_analysis.db"

    # Check if custom path provided
    if len(sys.argv) > 1:
        db_path = sys.argv[1]

    # Check if database exists
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    # Run backfill
    success = backfill_cvar(db_path)

    if success:
        print("🎉 CVaR backfill migration completed successfully!")
        sys.exit(0)
    else:
        print("💥 CVaR backfill migration failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
