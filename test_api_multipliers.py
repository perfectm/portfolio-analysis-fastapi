#!/usr/bin/env python3
"""
Quick test of the new multiplier-based API system
"""
import tempfile
import os
import pandas as pd
from portfolio_blender import create_blended_portfolio

def test_api_multiplier_system():
    """Test that the portfolio blender works with multiplier system"""
    print("🧪 Testing API Multiplier System")
    print("=" * 50)
    
    # Create test data as DataFrames
    test_data = {
        "Portfolio1.csv": pd.DataFrame({
            "Date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "P/L": [1000, 2000, 500]
        }),
        "Portfolio2.csv": pd.DataFrame({
            "Date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "P/L": [800, 1500, 300]
        }),
        "Portfolio3.csv": pd.DataFrame({
            "Date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "P/L": [600, 1200, 200]
        })
    }
    
    # Convert to files_data format
    files_data = [(filename, df) for filename, df in test_data.items()]
    
    print(f"Individual P/L totals: [3500, 2600, 2000] = {3500 + 2600 + 2000}")
    
    # Test 1: Custom multipliers [2.0, 1.0, 0.5]
    print("\n📋 Test 1: Custom Multipliers [2.0, 1.0, 0.5]")
    print("-" * 50)
    multipliers = [2.0, 1.0, 0.5]
    expected_total = (3500 * 2.0) + (2600 * 1.0) + (2000 * 0.5)
    print(f"Expected: (3500×2.0) + (2600×1.0) + (2000×0.5) = {expected_total}")
    
    try:
        blended_df, metrics, correlation_data = create_blended_portfolio(
            files_data=files_data,
            weights=multipliers
        )
        
        actual_total = metrics['total_pl']
        print(f"Actual result: ${actual_total:,.2f}")
        if abs(actual_total - expected_total) < 0.01:
            print("✅ Multiplier system working correctly!")
        else:
            print(f"❌ Mismatch! Expected ${expected_total}, got ${actual_total}")
                
    except Exception as e:
        print(f"❌ Error testing multiplier system: {e}")
    
    # Test 2: Default multipliers (1.0 each)
    print("\n📋 Test 2: Default Multipliers (1.0 each)")
    print("-" * 50)
    expected_total = 3500 + 2600 + 2000
    print(f"Expected: 3500 + 2600 + 2000 = {expected_total}")
    
    try:
        blended_df, metrics, correlation_data = create_blended_portfolio(
            files_data=files_data,
            weights=None  # Should default to [1.0, 1.0, 1.0]
        )
        
        actual_total = metrics['total_pl']
        print(f"Actual result: ${actual_total:,.2f}")
        if abs(actual_total - expected_total) < 0.01:
            print("✅ Default multipliers working correctly!")
        else:
            print(f"❌ Mismatch! Expected ${expected_total}, got ${actual_total}")
            
    except Exception as e:
        print(f"❌ Error testing default multipliers: {e}")

if __name__ == "__main__":
    test_api_multiplier_system()
