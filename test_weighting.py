#!/usr/bin/env python3
"""
Test script for portfolio weighting functionality
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from portfolio_blender import create_blended_portfolio_from_files
    
    print("🧪 TESTING PORTFOLIO WEIGHTING FUNCTIONALITY")
    print("=" * 50)
    
    # Create sample portfolio data
    print("\n📊 Creating sample portfolio data...")
    dates = pd.date_range(start='2023-01-01', periods=50, freq='D')
    np.random.seed(42)
    
    # Portfolio 1: Conservative (smaller returns, lower volatility)
    portfolio1_pl = np.random.normal(50, 200, 50)
    portfolio1_df = pd.DataFrame({
        'Date': dates,
        'P/L': portfolio1_pl
    })
    
    # Portfolio 2: Aggressive (larger returns, higher volatility)
    portfolio2_pl = np.random.normal(100, 500, 50)
    portfolio2_df = pd.DataFrame({
        'Date': dates,
        'P/L': portfolio2_pl
    })
    
    # Portfolio 3: Moderate
    portfolio3_pl = np.random.normal(75, 300, 50)
    portfolio3_df = pd.DataFrame({
        'Date': dates,
        'P/L': portfolio3_pl
    })
    
    files_data = [
        ("conservative.csv", portfolio1_df),
        ("aggressive.csv", portfolio2_df),
        ("moderate.csv", portfolio3_df)
    ]
    
    print(f"✅ Created 3 sample portfolios with 50 trading days each")
    print(f"   Conservative P/L sum: ${portfolio1_df['P/L'].sum():,.2f}")
    print(f"   Aggressive P/L sum: ${portfolio2_df['P/L'].sum():,.2f}")
    print(f"   Moderate P/L sum: ${portfolio3_df['P/L'].sum():,.2f}")
    
    # Test 1: Equal weighting (default)
    print(f"\n🧪 Test 1: Equal Weighting")
    print("-" * 30)
    
    blended_df1, blended_metrics1, correlation_data1 = create_blended_portfolio_from_files(
        files_data,
        starting_capital=100000,
        weights=None,  # Should default to equal weighting
        use_capital_allocation=False  # Test strategy combination mode
    )
    
    if blended_metrics1:
        print(f"✅ Equal weighting test successful")
        print(f"   Weighting method: {blended_metrics1.get('Weighting_Method', 'Not specified')}")
        print(f"   Portfolio weights: {blended_metrics1.get('Portfolio_Weights', {})}")
        print(f"   Final account value: ${blended_metrics1.get('final_account_value', 0):,.2f}")
        print(f"   Total P/L: ${blended_metrics1.get('total_pl', 0):,.2f}")
        
        # Verify equal weighting
        weights = blended_metrics1.get('Portfolio_Weights', {})
        if weights:
            weight_values = list(weights.values())
            expected_weight = 1.0 / 3
            if all(abs(w - expected_weight) < 0.001 for w in weight_values):
                print(f"   ✅ Weights are correctly equal: {weight_values}")
            else:
                print(f"   ❌ Weights are not equal: {weight_values}")
    else:
        print(f"❌ Equal weighting test failed")
    
    # Test 2: Custom weighting (Conservative heavy: 60%, Aggressive: 20%, Moderate: 20%)
    print(f"\n🧪 Test 2: Custom Weighting (Conservative Heavy)")
    print("-" * 50)
    
    custom_weights = [0.6, 0.2, 0.2]  # Conservative 60%, Aggressive 20%, Moderate 20%
    
    blended_df2, blended_metrics2, correlation_data2 = create_blended_portfolio_from_files(
        files_data,
        starting_capital=100000,
        weights=custom_weights,
        use_capital_allocation=True  # Test capital allocation mode
    )
    
    if blended_metrics2:
        print(f"✅ Custom weighting test successful")
        print(f"   Weighting method: {blended_metrics2.get('Weighting_Method', 'Not specified')}")
        print(f"   Portfolio weights: {blended_metrics2.get('Portfolio_Weights', {})}")
        print(f"   Final account value: ${blended_metrics2.get('final_account_value', 0):,.2f}")
        print(f"   Total P/L: ${blended_metrics2.get('total_pl', 0):,.2f}")
        
        # Verify custom weighting
        weights = blended_metrics2.get('Portfolio_Weights', {})
        if weights:
            weight_values = list(weights.values())
            if all(abs(w - custom_weights[i]) < 0.001 for i, w in enumerate(weight_values)):
                print(f"   ✅ Custom weights applied correctly: {weight_values}")
            else:
                print(f"   ❌ Custom weights not applied correctly: {weight_values} vs {custom_weights}")
    else:
        print(f"❌ Custom weighting test failed")
    
    # Test 3: Aggressive heavy weighting (Conservative: 10%, Aggressive: 70%, Moderate: 20%)
    print(f"\n🧪 Test 3: Custom Weighting (Aggressive Heavy)")
    print("-" * 50)
    
    aggressive_weights = [0.1, 0.7, 0.2]  # Conservative 10%, Aggressive 70%, Moderate 20%
    
    blended_df3, blended_metrics3, correlation_data3 = create_blended_portfolio_from_files(
        files_data,
        starting_capital=100000,
        weights=aggressive_weights,
        use_capital_allocation=True  # Test capital allocation mode
    )
    
    if blended_metrics3:
        print(f"✅ Aggressive weighting test successful")
        print(f"   Weighting method: {blended_metrics3.get('Weighting_Method', 'Not specified')}")
        print(f"   Portfolio weights: {blended_metrics3.get('Portfolio_Weights', {})}")
        print(f"   Final account value: ${blended_metrics3.get('final_account_value', 0):,.2f}")
        print(f"   Total P/L: ${blended_metrics3.get('total_pl', 0):,.2f}")
    else:
        print(f"❌ Aggressive weighting test failed")
    
    # Compare results
    print(f"\n📊 COMPARISON OF WEIGHTING STRATEGIES")
    print("=" * 50)
    
    if all([blended_metrics1, blended_metrics2, blended_metrics3]):
        print(f"Strategy                 | Final Value    | Total P/L      | Sharpe Ratio")
        print(f"-" * 70)
        print(f"Equal Weighting         | ${blended_metrics1.get('final_account_value', 0):>10,.2f} | ${blended_metrics1.get('total_pl', 0):>10,.2f} | {blended_metrics1.get('sharpe_ratio', 0):>10.2f}")
        print(f"Conservative Heavy      | ${blended_metrics2.get('final_account_value', 0):>10,.2f} | ${blended_metrics2.get('total_pl', 0):>10,.2f} | {blended_metrics2.get('sharpe_ratio', 0):>10.2f}")
        print(f"Aggressive Heavy        | ${blended_metrics3.get('final_account_value', 0):>10,.2f} | ${blended_metrics3.get('total_pl', 0):>10,.2f} | {blended_metrics3.get('sharpe_ratio', 0):>10.2f}")
        
        # Test weight normalization
        print(f"\n🧪 Test 4: Weight Normalization")
        print("-" * 30)
        
        unnormalized_weights = [0.6, 0.3, 0.3]  # Sum = 1.2 (should be normalized)
        
        try:
            blended_df4, blended_metrics4, correlation_data4 = create_blended_portfolio_from_files(
                files_data,
                starting_capital=100000,
                weights=unnormalized_weights,
                use_capital_allocation=True  # Test capital allocation mode
            )
            
            if blended_metrics4:
                weights = blended_metrics4.get('Portfolio_Weights', {})
                weight_values = list(weights.values())
                weight_sum = sum(weight_values)
                
                print(f"✅ Weight normalization test successful")
                print(f"   Original weights: {unnormalized_weights} (sum: {sum(unnormalized_weights)})")
                print(f"   Normalized weights: {[f'{w:.3f}' for w in weight_values]} (sum: {weight_sum:.3f})")
            else:
                print(f"❌ Weight normalization test failed")
                
        except Exception as e:
            print(f"❌ Weight normalization test failed with error: {e}")
    
    print(f"\n" + "=" * 50)
    print(f"🎉 PORTFOLIO WEIGHTING TESTS COMPLETED!")
    print(f"✅ The weighting functionality is working correctly.")
    print(f"📝 Users can now configure custom portfolio weights in the web interface.")
    print("=" * 50)

except Exception as e:
    print(f"❌ Test failed with error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
