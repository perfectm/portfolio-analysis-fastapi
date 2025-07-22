#!/usr/bin/env python3
"""
Test script to verify that the new metrics calculations are working correctly
"""
import pandas as pd
from portfolio_processor import process_portfolio_data

def test_metrics():
    print("Testing portfolio metrics calculations...")
    
    # Read the sample data
    try:
        df = pd.read_csv('sample_data.csv')
        print(f"Sample data loaded: {len(df)} rows")
        print(f"Columns: {list(df.columns)}")
        print(f"Date range: {df['Date Opened'].min()} to {df['Date Opened'].max()}")
        
        # Process the portfolio data
        clean_df, metrics = process_portfolio_data(df, starting_capital=100000)
        
        print("\n" + "="*50)
        print("CALCULATED METRICS:")
        print("="*50)
        
        # Check key metrics
        key_metrics = [
            'sharpe_ratio', 'sortino_ratio', 'ulcer_index', 
            'max_drawdown_date', 'cagr', 'annual_volatility', 
            'total_return', 'max_drawdown', 'max_drawdown_percent'
        ]
        
        for metric in key_metrics:
            value = metrics.get(metric, "NOT FOUND")
            print(f"{metric:20}: {value}")
        
        print("\n" + "="*50)
        print("ALL METRICS:")
        print("="*50)
        for key in sorted(metrics.keys()):
            print(f"{key:25}: {metrics[key]}")
            
        # Check if the problematic metrics are present and not None/empty
        issues = []
        if not metrics.get('sortino_ratio') or metrics.get('sortino_ratio') == 0:
            issues.append('sortino_ratio is missing or zero')
        if not metrics.get('ulcer_index') or metrics.get('ulcer_index') == 0:
            issues.append('ulcer_index is missing or zero')
        if not metrics.get('max_drawdown_date'):
            issues.append('max_drawdown_date is missing or empty')
            
        if issues:
            print("\n" + "!"*50)
            print("ISSUES FOUND:")
            for issue in issues:
                print(f"  - {issue}")
            print("!"*50)
        else:
            print("\n" + "✓"*50)
            print("ALL METRICS LOOK GOOD!")
            print("✓"*50)
            
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_metrics()
