#!/usr/bin/env python3

import sys
import os
sys.path.append('.')

import pandas as pd
from portfolio_processor import process_portfolio_data

def test_portfolio_calculation():
    # Load test data
    df = pd.read_csv('realistic_test.csv')
    
    print("=== Testing Portfolio Calculation ===")
    print(f"Loaded {len(df)} rows of data")
    print(f"Date range: {df['Date'].iloc[0]} to {df['Date'].iloc[-1]}")
    print(f"Total P/L sum: ${df['P/L'].sum():,.2f}")
    
    # Process the data
    processed_df, metrics = process_portfolio_data(
        df, 
        starting_capital=100000,
        rf_rate=0.043,
        daily_rf_rate=0.000171,
        sma_window=20,
        use_trading_filter=True
    )
    
    print("\n=== Backend Calculation Results ===")
    print(f"Total Return: {metrics['total_return']:.6f}")
    print(f"CAGR: {metrics['cagr']:.6f}")
    print(f"Final Account Value: ${metrics['final_account_value']:,.2f}")
    print(f"Total P/L: ${metrics['total_pl']:,.2f}")
    
    print("\n=== Expected Frontend Display ===")
    print(f"Total Return: {metrics['total_return'] * 100:.2f}%")
    print(f"CAGR: {metrics['cagr'] * 100:.2f}%")
    
    # Manual verification
    print("\n=== Manual Verification ===")
    expected_total_return = (metrics['final_account_value'] / 100000) - 1
    print(f"Expected total return: {expected_total_return:.6f} = {expected_total_return*100:.2f}%")
    
    if abs(metrics['total_return'] - expected_total_return) < 0.001:
        print("✅ Total return calculation is correct")
    else:
        print("❌ Total return calculation is incorrect")
        print(f"   Backend returned: {metrics['total_return']}")
        print(f"   Expected: {expected_total_return}")

if __name__ == "__main__":
    test_portfolio_calculation()
