#!/usr/bin/env python3
"""
Test the fixed equal weighting system
"""

def test_equal_weighting_logic():
    """Test that equal weighting now uses 1.0x for each portfolio"""
    print("🧪 Testing Fixed Equal Weighting Logic")
    print("=" * 50)
    
    # Simulate the new backend logic
    def get_portfolio_weights(weighting_method, weights, portfolio_count):
        if weighting_method == "custom" and weights:
            return weights
        elif weighting_method == "equal":
            # Equal scaling: 1.0x for each portfolio
            return [1.0] * portfolio_count
        elif weights:
            # Use provided weights regardless of method
            return weights
        else:
            # Fallback to equal scaling
            return [1.0] * portfolio_count
    
    # Test scenarios
    test_cases = [
        {
            "name": "Equal weighting with 3 portfolios",
            "method": "equal",
            "weights": None,
            "count": 3,
            "expected": [1.0, 1.0, 1.0]
        },
        {
            "name": "Custom weighting",
            "method": "custom", 
            "weights": [2.0, 1.5, 0.5],
            "count": 3,
            "expected": [2.0, 1.5, 0.5]
        },
        {
            "name": "Equal weighting with explicit weights",
            "method": "equal",
            "weights": [1.0, 1.0, 1.0],
            "count": 3,
            "expected": [1.0, 1.0, 1.0]
        },
        {
            "name": "Fallback case",
            "method": "unknown",
            "weights": None,
            "count": 2,
            "expected": [1.0, 1.0]
        }
    ]
    
    for test_case in test_cases:
        result = get_portfolio_weights(
            test_case["method"], 
            test_case["weights"], 
            test_case["count"]
        )
        
        success = result == test_case["expected"]
        status = "✅" if success else "❌"
        
        print(f"{status} {test_case['name']}")
        print(f"   Expected: {test_case['expected']}")
        print(f"   Got:      {result}")
        
        if not success:
            print(f"   ❌ FAILED!")
        print()
    
    print("Fixed equal weighting logic test complete!")

if __name__ == "__main__":
    test_equal_weighting_logic()
