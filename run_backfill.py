#!/usr/bin/env python3
"""
Simple script to run the regime data backfill

Usage examples:
    python run_backfill.py                    # Full backfill from May 2022 to present
    python run_backfill.py --start 2023-01-01 # Backfill from specific date
    python run_backfill.py --start 2024-01-01 --end 2024-08-30 # Specific date range
    python run_backfill.py --dry-run          # Test run without storing data
"""

import argparse
import sys
from datetime import date, datetime, timedelta
from backfill_regime_data import RegimeBackfillProcessor


def parse_date(date_string: str) -> date:
    """Parse date string in YYYY-MM-DD format"""
    try:
        return datetime.strptime(date_string, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_string}. Use YYYY-MM-DD")


def main():
    parser = argparse.ArgumentParser(
        description="Backfill market regime data from May 2022 to present",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--start", 
        type=parse_date,
        default=date(2022, 5, 1),
        help="Start date (YYYY-MM-DD, default: 2022-05-01)"
    )
    
    parser.add_argument(
        "--end",
        type=parse_date, 
        default=date.today(),
        help="End date (YYYY-MM-DD, default: today)"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=60,
        help="Batch size in days (default: 60)"
    )
    
    parser.add_argument(
        "--symbol",
        type=str,
        default="^GSPC",
        help="Market symbol to analyze (default: ^GSPC)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test run without storing data to database"
    )
    
    args = parser.parse_args()
    
    # Validate date range
    if args.start >= args.end:
        print("❌ Error: Start date must be before end date")
        sys.exit(1)
    
    # Show configuration
    print(f"🔧 Configuration:")
    print(f"   Start date: {args.start}")
    print(f"   End date: {args.end}")
    print(f"   Batch size: {args.batch_size} days")
    print(f"   Symbol: {args.symbol}")
    print(f"   Dry run: {args.dry_run}")
    print(f"   Total period: {(args.end - args.start).days} days")
    
    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No data will be stored")
    
    print("\n🚀 Starting regime data backfill...")
    
    try:
        # Initialize processor
        processor = RegimeBackfillProcessor(batch_size_days=args.batch_size)
        
        if args.dry_run:
            # Test a small sample
            print("Running test with 5-day sample...")
            test_end = min(args.start + timedelta(days=4), args.end)
            market_data = processor.get_market_data_batch(args.start, test_end, args.symbol)
            
            if market_data is not None:
                print(f"✅ Market data available: {len(market_data)} rows")
                
                # Test classification
                classification = processor.classify_regime_for_date(test_end, market_data)
                if classification:
                    print(f"✅ Regime classification works: {classification.regime.value} ({classification.confidence:.2f})")
                    print(f"   Sample description: {classification.description}")
                    print("✅ Dry run successful - backfill should work properly")
                else:
                    print("❌ Regime classification failed")
            else:
                print("❌ Market data fetch failed")
        else:
            # Run actual backfill
            total_records = processor.backfill_regime_data(args.start, args.end, args.symbol)
            
            print(f"\n✅ Backfill completed successfully!")
            print(f"📊 Total records processed: {total_records}")
            print(f"📅 Period covered: {args.start} to {args.end}")
            print(f"📋 Log file: regime_backfill.log")
    
    except KeyboardInterrupt:
        print("\n⚠️ Backfill interrupted by user")
    except Exception as e:
        print(f"\n❌ Backfill failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()