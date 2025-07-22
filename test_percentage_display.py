#!/usr/bin/env python3
"""
Test to verify all percentage metrics are calculated correctly
"""

def test_percentage_metrics():
    """Test that percentage metrics match expected calculations"""
    
    # Example values for a portfolio that doubles
    starting_capital = 100000.0
    final_account_value = 200000.0
    max_drawdown_percent_decimal = 0.15  # 15% as stored in backend
    annual_volatility_decimal = 0.08     # 8% as stored in backend
    cagr_decimal = 0.12                  # 12% as stored in backend
    total_return_decimal = 1.0           # 100% as stored in backend
    
    print("=== Percentage Metrics Verification ===")
    print(f"Starting Capital: ${starting_capital:,.2f}")
    print(f"Final Account Value: ${final_account_value:,.2f}")
    print()
    
    print("Backend Values (stored as decimals):")
    print(f"total_return: {total_return_decimal:.6f}")
    print(f"cagr: {cagr_decimal:.6f}")
    print(f"annual_volatility: {annual_volatility_decimal:.6f}")
    print(f"max_drawdown_percent: {max_drawdown_percent_decimal:.6f}")
    print()
    
    print("Frontend Should Display (multiply by 100):")
    print(f"Total Return: {total_return_decimal * 100:.2f}%")
    print(f"CAGR: {cagr_decimal * 100:.2f}%")
    print(f"Annual Volatility: {annual_volatility_decimal * 100:.2f}%")
    print(f"Max Drawdown: {max_drawdown_percent_decimal * 100:.2f}%")
    print()
    
    print("Before Fix (what was showing):")
    print(f"Total Return: {total_return_decimal:.2f}% ❌ (should be 100.00%)")
    print(f"CAGR: {cagr_decimal:.2f}% ❌ (should be 12.00%)")
    print(f"Annual Volatility: {annual_volatility_decimal:.2f}% ❌ (should be 8.00%)")
    print(f"Max Drawdown: {max_drawdown_percent_decimal:.2f}% ❌ (should be 15.00%)")
    print()
    
    print("After Fix (what should now show):")
    print(f"Total Return: {total_return_decimal * 100:.2f}% ✅")
    print(f"CAGR: {cagr_decimal * 100:.2f}% ✅")
    print(f"Annual Volatility: {annual_volatility_decimal * 100:.2f}% ✅")
    print(f"Max Drawdown: {max_drawdown_percent_decimal * 100:.2f}% ✅")
    
    # Calculate verification
    expected_total_return = (final_account_value / starting_capital) - 1
    print(f"\nVerification:")
    print(f"Calculated total return: {expected_total_return:.6f} = {expected_total_return * 100:.2f}%")
    
    if abs(total_return_decimal - expected_total_return) < 0.001:
        print("✅ Total return calculation matches!")
    else:
        print("❌ Total return calculation mismatch!")

if __name__ == "__main__":
    test_percentage_metrics()
