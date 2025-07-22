#!/usr/bin/env python3
"""
Test to verify total return calculation is correct
"""

def test_total_return_calculation():
    """Test that total return calculation matches expected math"""
    
    starting_capital = 100000.0
    final_account_value = 295397.64
    
    # Expected calculation: (final / initial) - 1
    expected_total_return = (final_account_value / starting_capital) - 1
    expected_percentage = expected_total_return * 100
    
    print("=== Total Return Calculation Test ===")
    print(f"Starting Capital: ${starting_capital:,.2f}")
    print(f"Final Account Value: ${final_account_value:,.2f}")
    print(f"Expected Total Return (decimal): {expected_total_return:.6f}")
    print(f"Expected Total Return (percentage): {expected_percentage:.2f}%")
    print()
    
    # Verify the math
    profit = final_account_value - starting_capital
    print(f"Total Profit: ${profit:,.2f}")
    print(f"Profit as % of starting capital: {(profit/starting_capital)*100:.2f}%")
    print()
    
    # Show what 1.95% would actually be
    wrong_percentage = 1.95
    wrong_final_value = starting_capital * (1 + wrong_percentage/100)
    print(f"If total return was actually {wrong_percentage}%:")
    print(f"Final value would be: ${wrong_final_value:,.2f}")
    print(f"Difference from actual: ${final_account_value - wrong_final_value:,.2f}")
    
    return expected_total_return

if __name__ == "__main__":
    test_total_return_calculation()
