#!/usr/bin/env python3
"""
Test to verify MAR ratio is being calculated and included in metrics
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from portfolio_processor import _calculate_drawdown_metrics, _calculate_cagr_from_df
import pandas as pd
import numpy as np

def test_mar_ratio_calculation():
    """Test that MAR ratio is calculated correctly"""
    
    # Create sample data that should produce a MAR ratio
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    
    # Create account values with some growth and a drawdown
    np.random.seed(42)  # For reproducible results
    daily_returns = np.random.normal(0.001, 0.01, len(dates))  # ~10% annual return with volatility
    
    # Add a significant drawdown period
    drawdown_start = len(dates) // 3
    drawdown_end = drawdown_start + 30
    daily_returns[drawdown_start:drawdown_end] = -0.02  # 20% drawdown over 30 days
    
    # Calculate cumulative returns and account values
    cumulative_returns = np.cumprod(1 + daily_returns)
    account_values = 100000 * cumulative_returns
    
    # Create DataFrame
    df = pd.DataFrame({
        'Date': dates,
        'Account Value': account_values,
        'Daily Return': daily_returns,
        'Cumulative P/L': account_values - 100000
    })
    
    # Calculate rolling peak for drawdown calculation
    df['Rolling Peak'] = df['Account Value'].expanding().max()
    df['Drawdown Amount'] = df['Account Value'] - df['Rolling Peak']  # Changed from 'Drawdown'
    df['Drawdown Pct'] = (df['Drawdown Amount'] / df['Rolling Peak']) * 100
    
    print("=== MAR Ratio Calculation Test ===")
    print(f"Starting Account Value: ${df['Account Value'].iloc[0]:,.2f}")
    print(f"Final Account Value: ${df['Account Value'].iloc[-1]:,.2f}")
    print(f"Total Return: {((df['Account Value'].iloc[-1] / df['Account Value'].iloc[0]) - 1) * 100:.2f}%")
    print(f"Max Drawdown: {df['Drawdown Amount'].min():,.2f}")
    print(f"Max Drawdown %: {df['Drawdown Pct'].min():.2f}%")
    print()
    
    # Calculate CAGR
    cagr = _calculate_cagr_from_df(df)
    print(f"CAGR: {cagr * 100:.2f}%")
    
    # Calculate drawdown metrics including MAR ratio
    drawdown_metrics = _calculate_drawdown_metrics(df)
    
    print("\n=== Drawdown Metrics ===")
    for key, value in drawdown_metrics.items():
        if isinstance(value, float):
            if 'ratio' in key.lower():
                print(f"{key}: {value:.4f}")
            elif 'percent' in key.lower():
                print(f"{key}: {value:.2f}%")
            elif '$' in str(value) or 'value' in key.lower():
                print(f"{key}: ${value:,.2f}")
            else:
                print(f"{key}: {value}")
        else:
            print(f"{key}: {value}")
    
    # Verify MAR ratio is present and reasonable
    if 'mar_ratio' in drawdown_metrics:
        mar_ratio = drawdown_metrics['mar_ratio']
        print(f"\n✅ MAR Ratio found: {mar_ratio:.4f}")
        
        # MAR ratio should be CAGR / abs(max_drawdown_percent)
        expected_mar = abs(cagr) / abs(drawdown_metrics['max_drawdown_percent']) if drawdown_metrics['max_drawdown_percent'] != 0 else 0
        print(f"Expected MAR Ratio: {expected_mar:.4f}")
        
        if abs(mar_ratio - expected_mar) < 0.001:
            print("✅ MAR Ratio calculation is correct!")
        else:
            print("❌ MAR Ratio calculation mismatch!")
    else:
        print("❌ MAR Ratio not found in metrics!")
    
    return drawdown_metrics

if __name__ == "__main__":
    test_mar_ratio_calculation()
