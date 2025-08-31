#!/usr/bin/env python3
"""
Simple direct test of the optimization caching system using database session
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, engine, Base
from portfolio_optimizer import PortfolioOptimizer, OptimizationObjective
from portfolio_service import PortfolioService
import time

def test_direct_caching():
    """Test optimization caching directly through the database"""
    print("🔬 Direct Cache Testing")
    print("=" * 40)
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Create all tables (including our new optimization_cache table)
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables ensured")
        
        # List available portfolios
        portfolios = PortfolioService.get_all_portfolios(db)
        print(f"📊 Found {len(portfolios)} portfolios:")
        for p in portfolios[:5]:  # Show first 5
            print(f"   - ID {p.id}: {p.name}")
        
        if len(portfolios) < 2:
            print("❌ Need at least 2 portfolios for testing")
            return
        
        # Test with first few portfolios
        test_portfolio_ids = [p.id for p in portfolios[:min(3, len(portfolios))]]
        print(f"\n🧪 Testing with portfolio IDs: {test_portfolio_ids}")
        
        # Create optimizer
        optimizer = PortfolioOptimizer(
            objective=OptimizationObjective(),
            rf_rate=0.043,
            sma_window=20,
            use_trading_filter=True,
            starting_capital=1000000.0
        )
        
        # First optimization (should not be cached)
        print("\n🏃‍♂️ First optimization run...")
        start_time = time.time()
        result1 = optimizer.optimize_weights_from_ids(
            db, test_portfolio_ids, method='differential_evolution'
        )
        time1 = time.time() - start_time
        
        print(f"   Time: {time1:.2f}s")
        print(f"   Success: {result1.success}")
        print(f"   Method: {result1.optimization_method}")
        if result1.success:
            print(f"   Weights: {result1.optimal_weights}")
        
        # Second optimization (should hit cache)
        print("\n🏃‍♂️ Second optimization run (should hit cache)...")
        start_time = time.time()
        result2 = optimizer.optimize_weights_from_ids(
            db, test_portfolio_ids, method='differential_evolution'
        )
        time2 = time.time() - start_time
        
        print(f"   Time: {time2:.2f}s")
        print(f"   Success: {result2.success}")
        print(f"   Method: {result2.optimization_method}")
        print(f"   Cached: {'(cached)' in result2.optimization_method}")
        if result2.success:
            print(f"   Weights: {result2.optimal_weights}")
        
        # Performance comparison
        if result1.success and result2.success:
            speedup = time1 / time2 if time2 > 0 else float('inf')
            print(f"\n📈 Performance:")
            print(f"   First run:  {time1:.2f}s")
            print(f"   Second run: {time2:.2f}s") 
            print(f"   Speedup:    {speedup:.1f}x")
            
            weights_match = (
                abs(sum(result1.optimal_weights) - sum(result2.optimal_weights)) < 0.001
                if result1.optimal_weights and result2.optimal_weights
                else False
            )
            print(f"   Weights consistent: {weights_match}")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()

if __name__ == "__main__":
    test_direct_caching()