from sqlalchemy import Column, String, text
from sqlalchemy import create_engine, MetaData, Table

DATABASE_URL = "sqlite:///portfolio_analysis.db"  # Update if using a different DB
engine = create_engine(DATABASE_URL)
metadata = MetaData()
metadata.reflect(bind=engine)

portfolios = Table('portfolios', metadata, autoload_with=engine)

if not hasattr(portfolios.c, 'parquet_path'):
    with engine.connect() as conn:
        conn.execute(text('ALTER TABLE portfolios ADD COLUMN parquet_path VARCHAR(500)'))
        print("Added 'parquet_path' column to portfolios table.")
else:
    print("'parquet_path' column already exists.") 