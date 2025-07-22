#!/usr/bin/env python3

# Test the new multiplier-based blended portfolio calculation
import pandas as pd
import sys
import os

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from portfolio_blender import create_blended_portfolio

def test_multiplier_system():
    """Test the new multiplier-based blended portfolio calculation"""
    print("=== Testing Multiplier-Based Portfolio Blending ===\n")
    
    # Create sample data
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
    print(f"Individual P/L totals: {individual_totals}")
    
    # Test 1: Default multipliers (1.0x each) - should sum to 8100
    print("\n📋 Test 1: Default Multipliers (1.0x each)")
    print("-" * 50)
    
    try:
        blended_df, blended_metrics, _ = create_blended_portfolio(
            files_data,
            starting_capital=100000
        )
        
        if blended_metrics:
            actual_total = blended_metrics['total_pl']
            expected_total = sum(individual_totals)  # 8100
            print(f"   Multipliers: [1.0, 1.0, 1.0]")
            print(f"   Expected total: ${expected_total:,.2f}")
            print(f"   Actual total: ${actual_total:,.2f}")
            print(f"   Match: {'✅ YES' if abs(actual_total - expected_total) < 1 else '❌ NO'}")
            print(f"   Total scale: {blended_metrics.get('Total_Portfolio_Scale', 'N/A'):.1f}x")
        else:
            print("❌ Test failed")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Custom multipliers [2.0, 1.0, 0.5]
    print("\n📋 Test 2: Custom Multipliers [2.0, 1.0, 0.5]")
    print("-" * 50)
    
    custom_multipliers = [2.0, 1.0, 0.5]
    expected_scaled = [
        individual_totals[0] * 2.0,  # 3500 * 2.0 = 7000
        individual_totals[1] * 1.0,  # 2600 * 1.0 = 2600  
        individual_totals[2] * 0.5   # 2000 * 0.5 = 1000
    ]
    expected_total = sum(expected_scaled)  # 10600
    
    try:
        blended_df2, blended_metrics2, _ = create_blended_portfolio(
            files_data,
            starting_capital=100000,
            weights=custom_multipliers
        )
        
        if blended_metrics2:
            actual_total = blended_metrics2['total_pl']
            print(f"   Multipliers: {custom_multipliers}")
            print(f"   Expected scaled: {expected_scaled}")
            print(f"   Expected total: ${expected_total:,.2f}")
            print(f"   Actual total: ${actual_total:,.2f}")
            print(f"   Match: {'✅ YES' if abs(actual_total - expected_total) < 1 else '❌ NO'}")
            print(f"   Total scale: {blended_metrics2.get('Total_Portfolio_Scale', 'N/A'):.1f}x")
        else:
            print("❌ Test failed")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: Half scale all [0.5, 0.5, 0.5]
    print("\n📋 Test 3: Half Scale All [0.5, 0.5, 0.5]")
    print("-" * 50)
    
    half_multipliers = [0.5, 0.5, 0.5]
    expected_half_total = sum(individual_totals) * 0.5  # 8100 * 0.5 = 4050
    
    try:
        blended_df3, blended_metrics3, _ = create_blended_portfolio(
            files_data,
            starting_capital=100000,
            weights=half_multipliers
        )
        
        if blended_metrics3:
            actual_total = blended_metrics3['total_pl']
            print(f"   Multipliers: {half_multipliers}")
            print(f"   Expected total: ${expected_half_total:,.2f}")
            print(f"   Actual total: ${actual_total:,.2f}")
            print(f"   Match: {'✅ YES' if abs(actual_total - expected_half_total) < 1 else '❌ NO'}")
            print(f"   Total scale: {blended_metrics3.get('Total_Portfolio_Scale', 'N/A'):.1f}x")
        else:
            print("❌ Test failed")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_multiplier_system()
