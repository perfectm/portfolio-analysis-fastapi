#!/usr/bin/env python3

# Test the fixed blended portfolio calculation
import pandas as pd
import sys
import os

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from portfolio_blender import create_blended_portfolio

def test_blended_calculation():
    """Test the corrected blended portfolio calculation"""
    print("=== Testing Blended Portfolio Calculation ===\n")
    
    # Create sample data that matches your results
    data1 = pd.DataFrame({
        'Date': ['2024-01-01', '2024-01-02', '2024-01-03'],
        'P/L': [1000, 2000, 500],  # Total: 3500
    })
    
    data2 = pd.DataFrame({
        'Date': ['2024-01-01', '2024-01-02', '2024-01-03'],
        'P/L': [800, 1500, 300],   # Total: 2600
    })
    
    data3 = pd.DataFrame({
        'Date': ['2024-01-01', '2024-01-02', '2024-01-03'],
        'P/L': [600, 1200, 200],   # Total: 2000
    })
    
    files_data = [
        ('Portfolio1.csv', data1),
        ('Portfolio2.csv', data2), 
        ('Portfolio3.csv', data3)
    ]
    
    # Expected individual totals
    individual_totals = [3500, 2600, 2000]
    expected_combined = sum(individual_totals)  # 8100
    
    print(f"Individual P/L totals: {individual_totals}")
    print(f"Expected combined total: ${expected_combined:,.2f}")
    
    # Test strategy combination mode (new default)
    try:
        blended_df, blended_metrics, _ = create_blended_portfolio(
            files_data,
            starting_capital=100000,
            use_capital_allocation=False  # Strategy combination mode
        )
        
        if blended_metrics:
            actual_total = blended_metrics['total_pl']
            print(f"\n✅ Strategy Combination Mode:")
            print(f"   Actual blended total: ${actual_total:,.2f}")
            print(f"   Expected: ${expected_combined:,.2f}")
            print(f"   Match: {'✅ YES' if abs(actual_total - expected_combined) < 1 else '❌ NO'}")
        else:
            print("❌ Strategy combination mode failed")
            
    except Exception as e:
        print(f"❌ Error in strategy combination mode: {e}")
    
    # Test capital allocation mode (old behavior)
    try:
        blended_df2, blended_metrics2, _ = create_blended_portfolio(
            files_data,
            starting_capital=100000,
            use_capital_allocation=True  # Capital allocation mode
        )
        
        if blended_metrics2:
            actual_total2 = blended_metrics2['total_pl']
            expected_weighted = expected_combined / 3  # Each gets 1/3
            print(f"\n📊 Capital Allocation Mode:")
            print(f"   Actual blended total: ${actual_total2:,.2f}")
            print(f"   Expected (1/3 each): ${expected_weighted:,.2f}")
            print(f"   Match: {'✅ YES' if abs(actual_total2 - expected_weighted) < 1 else '❌ NO'}")
        else:
            print("❌ Capital allocation mode failed")
            
    except Exception as e:
        print(f"❌ Error in capital allocation mode: {e}")

if __name__ == "__main__":
    test_blended_calculation()
