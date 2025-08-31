#!/usr/bin/env python3
"""
Regime Analysis Backfill Script

Efficiently backfills market regime classifications from May 2022 to present day.
Processes data in batches to optimize performance and memory usage.
"""

import logging
import sys
from datetime import datetime, timedelta, date
from typing import List, Optional
import pandas as pd
import yfinance as yf
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func

# Import project modules
from database import engine, get_db
from models import MarketRegimeHistory
from market_regime_analyzer import MarketRegimeAnalyzer, RegimeClassification
from regime_service import RegimeService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('regime_backfill.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class RegimeBackfillProcessor:
    """Efficiently process regime backfill in batches"""
    
    def __init__(self, batch_size_days: int = 30):
        """
        Initialize the backfill processor
        
        Args:
            batch_size_days: Number of days to process in each batch
        """
        self.batch_size_days = batch_size_days
        self.analyzer = MarketRegimeAnalyzer(
            volatility_lookback=60,
            trend_lookback=20,
            regime_confirmation_days=5
        )
        self.regime_service = RegimeService()
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Track processed dates to avoid duplicates
        self.processed_dates = set()
        
    def get_existing_regime_dates(self, symbol: str = "^GSPC") -> set:
        """Get dates that already have regime classifications"""
        try:
            with self.SessionLocal() as db:
                existing_records = db.query(MarketRegimeHistory.date).filter(
                    MarketRegimeHistory.market_symbol == symbol
                ).all()
                
                return {record.date.date() for record in existing_records}
                
        except Exception as e:
            logger.error(f"Failed to get existing regime dates: {e}")
            return set()
    
    def get_market_data_batch(self, start_date: date, end_date: date, symbol: str = "^GSPC") -> Optional[pd.DataFrame]:
        """
        Fetch market data for a specific date range with error handling
        
        Args:
            start_date: Start date for data
            end_date: End date for data
            symbol: Market symbol to fetch
            
        Returns:
            DataFrame with market data or None if failed
        """
        try:
            logger.info(f"Fetching market data for {symbol} from {start_date} to {end_date}")
            
            # Fetch data with some buffer for technical indicators
            buffer_start = start_date - timedelta(days=100)  # Larger buffer for 60-day lookback plus safety
            
            ticker = yf.Ticker(symbol)
            data = ticker.history(start=buffer_start, end=end_date + timedelta(days=1))
            
            if data.empty:
                logger.warning(f"No data retrieved for {symbol} in range {start_date} to {end_date}")
                return None
            
            # Calculate technical indicators
            data['Returns'] = data['Close'].pct_change()
            data['Volatility'] = data['Returns'].rolling(window=20).std() * (252 ** 0.5)
            data['SMA_20'] = data['Close'].rolling(window=20).mean()
            data['SMA_50'] = data['Close'].rolling(window=50).mean()
            
            # Don't filter the data here - return all data with buffer for calculations
            logger.info(f"Retrieved {len(data)} days of market data (including buffer)")
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch market data for {start_date} to {end_date}: {e}")
            return None
    
    def classify_regime_for_date(self, target_date: date, market_data: pd.DataFrame) -> Optional[RegimeClassification]:
        """
        Classify market regime for a specific date using historical data
        
        Args:
            target_date: Date to classify regime for
            market_data: Historical market data up to and including target_date
            
        Returns:
            RegimeClassification or None if not enough data
        """
        try:
            # Get data up to target date
            date_data = market_data[market_data.index.date <= target_date]
            
            if len(date_data) < self.analyzer.volatility_lookback:
                logger.warning(f"Insufficient data for {target_date}: only {len(date_data)} days available")
                return None
            
            # Calculate metrics using data available up to target date
            metrics = self.analyzer.calculate_regime_metrics(date_data)
            
            # Classify regime
            classification = self.analyzer.classify_regime(metrics)
            
            # Set the detection date to the target date
            classification.detected_at = datetime.combine(target_date, datetime.min.time())
            
            return classification
            
        except Exception as e:
            logger.error(f"Failed to classify regime for {target_date}: {e}")
            return None
    
    def store_regime_classifications(self, classifications: List[tuple], symbol: str = "^GSPC") -> int:
        """
        Store regime classifications in database
        
        Args:
            classifications: List of (date, RegimeClassification) tuples
            symbol: Market symbol
            
        Returns:
            Number of records stored
        """
        if not classifications:
            return 0
        
        stored_count = 0
        
        try:
            with self.SessionLocal() as db:
                for target_date, classification in classifications:
                    # Check if record already exists
                    existing = db.query(MarketRegimeHistory).filter(
                        func.date(MarketRegimeHistory.date) == target_date,
                        MarketRegimeHistory.market_symbol == symbol
                    ).first()
                    
                    if existing:
                        logger.debug(f"Regime classification already exists for {target_date}, skipping")
                        continue
                    
                    # Create new record
                    regime_record = MarketRegimeHistory(
                        date=classification.detected_at,
                        regime=classification.regime.value,
                        confidence=classification.confidence,
                        volatility_percentile=classification.indicators.get('volatility_percentile'),
                        trend_strength=classification.indicators.get('trend_strength'),
                        momentum_score=classification.indicators.get('momentum_score'),
                        drawdown_severity=classification.indicators.get('drawdown_severity'),
                        volume_anomaly=classification.indicators.get('volume_anomaly'),
                        market_symbol=symbol,
                        description=classification.description
                    )
                    
                    db.add(regime_record)
                    stored_count += 1
                
                db.commit()
                logger.info(f"Stored {stored_count} new regime classifications")
                
        except Exception as e:
            logger.error(f"Failed to store regime classifications: {e}")
            
        return stored_count
    
    def process_date_range(self, start_date: date, end_date: date, symbol: str = "^GSPC") -> int:
        """
        Process regime classification for a date range
        
        Args:
            start_date: Start date
            end_date: End date  
            symbol: Market symbol
            
        Returns:
            Number of classifications processed
        """
        logger.info(f"Processing regime data from {start_date} to {end_date}")
        
        # Get existing regime dates to avoid duplicates
        existing_dates = self.get_existing_regime_dates(symbol)
        logger.info(f"Found {len(existing_dates)} existing regime classifications")
        
        # Get market data for the entire range (with buffer)
        market_data = self.get_market_data_batch(start_date, end_date, symbol)
        
        if market_data is None:
            logger.error(f"No market data available for range {start_date} to {end_date}")
            return 0
        
        # Process each trading day in the range
        classifications = []
        current_date = start_date
        processed_count = 0
        
        while current_date <= end_date:
            # Skip weekends (market is closed)
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            # Skip if already processed
            if current_date in existing_dates:
                logger.debug(f"Skipping {current_date} - already processed")
                current_date += timedelta(days=1)
                continue
            
            # Check if we have market data for this date
            available_data = market_data[market_data.index.date <= current_date]
            if len(available_data) < self.analyzer.volatility_lookback:
                logger.debug(f"Skipping {current_date} - insufficient historical data")
                current_date += timedelta(days=1)
                continue
            
            # Classify regime for this date
            classification = self.classify_regime_for_date(current_date, market_data)
            
            if classification:
                classifications.append((current_date, classification))
                processed_count += 1
                
                if processed_count % 10 == 0:
                    logger.info(f"Processed {processed_count} dates, current: {current_date}")
            
            current_date += timedelta(days=1)
        
        # Store classifications in batch
        stored_count = self.store_regime_classifications(classifications, symbol)
        
        logger.info(f"Completed processing {processed_count} dates, stored {stored_count} new records")
        return stored_count
    
    def backfill_regime_data(self, start_date: date, end_date: Optional[date] = None, symbol: str = "^GSPC") -> int:
        """
        Main method to backfill regime data efficiently
        
        Args:
            start_date: Start date for backfill
            end_date: End date for backfill (defaults to today)
            symbol: Market symbol to analyze
            
        Returns:
            Total number of records processed
        """
        if end_date is None:
            end_date = date.today()
        
        logger.info(f"Starting regime data backfill from {start_date} to {end_date}")
        
        total_processed = 0
        current_batch_start = start_date
        
        # Process in batches to manage memory and handle errors
        while current_batch_start <= end_date:
            batch_end = min(current_batch_start + timedelta(days=self.batch_size_days - 1), end_date)
            
            try:
                logger.info(f"Processing batch: {current_batch_start} to {batch_end}")
                batch_processed = self.process_date_range(current_batch_start, batch_end, symbol)
                total_processed += batch_processed
                
                # Log progress
                progress = ((current_batch_start - start_date).days / (end_date - start_date).days) * 100
                logger.info(f"Batch completed. Progress: {progress:.1f}% ({total_processed} total records)")
                
            except Exception as e:
                logger.error(f"Error processing batch {current_batch_start} to {batch_end}: {e}")
                logger.info("Continuing with next batch...")
            
            # Move to next batch
            current_batch_start = batch_end + timedelta(days=1)
        
        logger.info(f"Backfill completed! Total records processed: {total_processed}")
        return total_processed


def main():
    """Main execution function"""
    try:
        # Initialize processor
        processor = RegimeBackfillProcessor(batch_size_days=60)  # 2-month batches
        
        # Define backfill period (May 1, 2022 to present)
        start_date = date(2022, 5, 1)
        end_date = date.today()
        
        logger.info(f"Starting regime data backfill from {start_date} to {end_date}")
        logger.info(f"Total period: {(end_date - start_date).days} days")
        
        # Run backfill
        total_records = processor.backfill_regime_data(start_date, end_date)
        
        print(f"\n✅ Backfill completed successfully!")
        print(f"📊 Total records processed: {total_records}")
        print(f"📅 Period covered: {start_date} to {end_date}")
        print(f"📋 Log file: regime_backfill.log")
        
    except KeyboardInterrupt:
        logger.info("Backfill interrupted by user")
        print("\n⚠️ Backfill interrupted by user")
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        print(f"\n❌ Backfill failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()