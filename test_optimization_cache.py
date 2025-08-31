#!/usr/bin/env python3
"""
Test script for optimization caching system
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_optimization_caching():
    """Test the optimization caching functionality"""
    
    print("🧪 Testing Portfolio Optimization Caching System")
    print("=" * 50)
    
    # Test data - using portfolio IDs that should exist
    test_cases = [
        {
            "name": "Test Case 1: Two portfolios (1, 2)",
            "portfolio_ids": [1, 2],
            "method": "differential_evolution"
        },
        {
            "name": "Test Case 2: Three portfolios (1, 2, 3)", 
            "portfolio_ids": [1, 2, 3],
            "method": "differential_evolution"
        },
        {
            "name": "Test Case 3: Repeat first case (should hit cache)",
            "portfolio_ids": [1, 2],
            "method": "differential_evolution"
        },
        {
            "name": "Test Case 4: Four portfolios including subset (1, 2, 3, 4)",
            "portfolio_ids": [1, 2, 3, 4],
            "method": "differential_evolution"
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔍 {test_case['name']}")
        print(f"   Portfolio IDs: {test_case['portfolio_ids']}")
        print(f"   Method: {test_case['method']}")
        
        # Record start time
        start_time = time.time()
        
        # Make the API request
        try:
            response = requests.post(
                f"{BASE_URL}/api/optimize-weights",
                json={
                    "portfolio_ids": test_case['portfolio_ids'],
                    "method": test_case['method']
                },
                timeout=30
            )
            
            execution_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("success"):
                    optimization_method = data.get("optimization_details", {}).get("method", "unknown")
                    is_cached = "(cached)" in optimization_method
                    
                    print(f"   ✅ Success: {data['message']}")
                    print(f"   ⏱️  Execution time: {execution_time:.2f} seconds")
                    print(f"   🎯 Cached result: {'Yes' if is_cached else 'No'}")
                    print(f"   📊 Method: {optimization_method}")
                    
                    if data.get("optimal_weights"):
                        print(f"   📈 Optimal weights: {data['optimal_weights']}")
                        
                    results.append({
                        "test_case": test_case['name'],
                        "success": True,
                        "cached": is_cached,
                        "execution_time": execution_time,
                        "method": optimization_method,
                        "portfolio_count": len(test_case['portfolio_ids'])
                    })
                else:
                    print(f"   ❌ Failed: {data.get('error', 'Unknown error')}")
                    results.append({
                        "test_case": test_case['name'],
                        "success": False,
                        "error": data.get('error'),
                        "execution_time": execution_time
                    })
            else:
                print(f"   ❌ HTTP Error: {response.status_code}")
                print(f"   Response: {response.text}")
                results.append({
                    "test_case": test_case['name'],
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "execution_time": execution_time
                })
                
        except requests.exceptions.Timeout:
            execution_time = time.time() - start_time
            print(f"   ⏰ Timeout after {execution_time:.2f} seconds")
            results.append({
                "test_case": test_case['name'],
                "success": False,
                "error": "Timeout",
                "execution_time": execution_time
            })
        except Exception as e:
            execution_time = time.time() - start_time
            print(f"   💥 Exception: {str(e)}")
            results.append({
                "test_case": test_case['name'],
                "success": False,
                "error": str(e),
                "execution_time": execution_time
            })
        
        # Add a small delay between requests
        time.sleep(1)
    
    # Print summary
    print(f"\n📋 TEST SUMMARY")
    print("=" * 50)
    
    successful_tests = [r for r in results if r.get("success")]
    cached_tests = [r for r in results if r.get("cached")]
    
    print(f"Total tests: {len(results)}")
    print(f"Successful: {len(successful_tests)}")
    print(f"Cached results: {len(cached_tests)}")
    
    if successful_tests:
        avg_time = sum(r["execution_time"] for r in successful_tests) / len(successful_tests)
        print(f"Average execution time: {avg_time:.2f} seconds")
        
        if cached_tests:
            cached_avg_time = sum(r["execution_time"] for r in cached_tests) / len(cached_tests)
            non_cached = [r for r in successful_tests if not r.get("cached")]
            if non_cached:
                non_cached_avg_time = sum(r["execution_time"] for r in non_cached) / len(non_cached)
                speedup = non_cached_avg_time / cached_avg_time if cached_avg_time > 0 else 0
                print(f"Cache speedup: {speedup:.1f}x faster")
    
    print(f"\n🎉 Cache testing completed!")
    return results

if __name__ == "__main__":
    test_results = test_optimization_caching()