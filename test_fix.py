"""
Test script to verify the portfolio service date column fix
"""
import pandas as pd
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.append(os.getcwd())

from portfolio_service import PortfolioService
from database import get_db, create_tables
from sqlalchemy.orm import Session

# Test data with the actual column names from the CSV
test_data = {
    'Date Opened': ['2024-01-15', '2024-01-16', '2024-01-17'],
    'P/L': [150.50, -75.25, 225.75],
    'Premium': [500.00, 300.00, 800.00],
    'No. of Contracts': [2, 1, 3],
    'Strategy': ['Sample Strategy', 'Sample Strategy', 'Sample Strategy']
}

def test_portfolio_creation():
    """Test creating a portfolio with the correct column names"""
    try:
        # Create test DataFrame
        df = pd.DataFrame(test_data)
        print("Test DataFrame:")
        print(df)
        print(f"Columns: {df.columns.tolist()}")
        
        # Test file content (simulate CSV bytes)
        test_content = b"test content for hash"
        
        # Initialize database (this will use SQLite fallback)
        create_tables()
        
        # Get database session
        db_gen = get_db()
        db = next(db_gen)
        
        try:
            # Test portfolio creation
            print("\nTesting portfolio creation...")
            portfolio = PortfolioService.create_portfolio(
                db=db,
                name="Test Portfolio",
                filename="test_portfolio.csv",
                file_content=test_content,
                df=df
            )
            
            print(f"✅ Portfolio created successfully!")
            print(f"Portfolio ID: {portfolio.id}")
            print(f"Portfolio Name: {portfolio.name}")
            print(f"Date Range: {portfolio.date_range_start} to {portfolio.date_range_end}")
            
            # Test data storage
            print("\nTesting data storage...")
            data_records = PortfolioService.store_portfolio_data(
                db=db,
                portfolio_id=portfolio.id,
                df=df
            )
            
            print(f"✅ Data stored successfully!")
            print(f"Number of records: {len(data_records)}")
            
            # Show first record
            if data_records:
                first_record = data_records[0]
                print(f"First record - Date: {first_record.date}, P/L: {first_record.pl}")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_portfolio_creation()
