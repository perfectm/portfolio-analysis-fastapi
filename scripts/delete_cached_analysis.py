import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import AnalysisResult, Base

DATABASE_URL = "sqlite:///portfolio_analysis.db"  # Update if using a different DB
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

if len(sys.argv) < 2:
    print("Usage: python delete_cached_analysis.py <portfolio_id>")
    sys.exit(1)
portfolio_id = int(sys.argv[1])

session = Session()
results = session.query(AnalysisResult).filter(AnalysisResult.portfolio_id == portfolio_id).all()
if not results:
    print(f"No cached analysis results found for portfolio_id={portfolio_id}")
else:
    for result in results:
        session.delete(result)
    session.commit()
    print(f"Deleted {len(results)} cached analysis results for portfolio_id={portfolio_id}")
session.close() 