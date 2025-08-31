# Market Regime Data Backfill Scripts

This directory contains scripts to efficiently backfill market regime classifications from May 2022 to the present date.

## Files

### `backfill_regime_data.py`
Main backfill processing engine with the following features:

- **Efficient batch processing**: Processes data in configurable batches (default: 60 days)
- **Smart caching**: Avoids duplicates by checking existing database records
- **Robust error handling**: Continues processing even if individual batches fail
- **Memory optimization**: Cleans up large DataFrames and uses garbage collection
- **Historical accuracy**: Uses only data available up to each target date for regime classification
- **Comprehensive logging**: Detailed logs saved to `regime_backfill.log`

### `run_backfill.py` 
Simple command-line interface for running the backfill with various options.

## Usage

### Quick Start (Full Backfill)
```bash
python run_backfill.py
```
This will backfill all regime data from May 1, 2022 to today.

### Custom Date Range
```bash
python run_backfill.py --start 2023-01-01 --end 2024-08-30
```

### Test Before Running (Dry Run)
```bash
python run_backfill.py --dry-run
```

### Advanced Options
```bash
python run_backfill.py \
  --start 2022-05-01 \
  --end 2024-08-30 \
  --batch-size 30 \
  --symbol ^GSPC
```

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--start` | 2022-05-01 | Start date (YYYY-MM-DD format) |
| `--end` | Today | End date (YYYY-MM-DD format) |
| `--batch-size` | 60 | Number of days to process per batch |
| `--symbol` | ^GSPC | Market symbol to analyze (S&P 500) |
| `--dry-run` | False | Test run without storing data |

## How It Works

### 1. Data Fetching
- Fetches S&P 500 market data using `yfinance`
- Includes 100-day buffer for technical indicators
- Calculates returns, volatility, moving averages

### 2. Regime Classification
Uses the existing `MarketRegimeAnalyzer` with these indicators:
- **Volatility percentile** (60-day lookback)
- **Trend strength** (price and moving average momentum) 
- **Momentum score** (5-day vs 20-day returns)
- **Drawdown severity** (maximum drawdown)
- **Volume anomaly** (volatility-based proxy)

### 3. Regime Types
- **Bull**: Strong upward trends, low volatility
- **Bear**: Downward trends, high drawdowns
- **Volatile**: High volatility, unstable trends  
- **Transitioning**: Between other regime states

### 4. Database Storage
Stores classifications in `market_regime_history` table:
- Date and regime type
- Confidence score (0-1)
- All technical indicators
- Human-readable description

## Performance

### Batch Processing Benefits
- **Memory efficient**: Processes 60-day chunks instead of loading all data
- **Error resilient**: Individual batch failures don't stop the entire process
- **Progress tracking**: Real-time logging of completion percentage
- **Resumable**: Automatically skips already-processed dates

### Expected Processing Time
- **Full backfill** (May 2022 - present): ~5-10 minutes
- **Rate**: ~200-300 trading days per minute
- **Network dependent**: Speed varies with Yahoo Finance API responsiveness

## Database Schema

The script populates the `market_regime_history` table:

```sql
CREATE TABLE market_regime_history (
    id INTEGER PRIMARY KEY,
    date DATETIME NOT NULL,
    regime VARCHAR(20) NOT NULL,        -- bull, bear, volatile, transitioning
    confidence FLOAT NOT NULL,          -- 0.0 to 1.0
    volatility_percentile FLOAT,        -- Technical indicators
    trend_strength FLOAT,
    momentum_score FLOAT, 
    drawdown_severity FLOAT,
    volume_anomaly FLOAT,
    market_symbol VARCHAR(10) DEFAULT '^GSPC',
    description TEXT,                   -- Human readable summary
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Error Handling

### Common Issues
1. **Network errors**: Script retries and continues with next batch
2. **Insufficient data**: Skips dates without enough historical data
3. **Database errors**: Rolls back failed batches, continues processing
4. **Market holidays**: Automatically skips weekends and handles holidays

### Monitoring
- Check `regime_backfill.log` for detailed progress
- Failed batches are logged with specific error messages
- Success/failure summary provided at completion

## Integration

### With Existing Regime Analysis
The backfilled data integrates seamlessly with:
- `/api/regime/current` - Current regime detection
- `/api/regime/history` - Historical regime data
- `/api/regime/performance` - Strategy performance by regime
- Portfolio allocation recommendations

### Data Validation
After backfill, validate the data:
```sql
SELECT regime, COUNT(*) as count, 
       MIN(date) as earliest, MAX(date) as latest,
       AVG(confidence) as avg_confidence
FROM market_regime_history 
GROUP BY regime 
ORDER BY count DESC;
```

## Best Practices

### Before Running
1. **Test with dry run**: `python run_backfill.py --dry-run`
2. **Check database connectivity**: Ensure database is accessible
3. **Verify date range**: Confirm start/end dates are correct
4. **Monitor disk space**: Ensure adequate space for logs and data

### During Processing  
1. **Monitor logs**: Check `regime_backfill.log` for progress
2. **Allow interruption**: Script handles Ctrl+C gracefully
3. **Network stability**: Stable internet recommended for large backfills

### After Completion
1. **Validate results**: Check data completeness and accuracy
2. **Update regime cache**: Restart application to refresh cache
3. **Test regime endpoints**: Verify API endpoints work with new data
4. **Archive logs**: Save backfill logs for future reference

## Troubleshooting

### Common Error Solutions

**"Insufficient data" warnings**: Normal for early dates that need historical context

**Database connection errors**: Check database configuration in `database.py`

**Yahoo Finance rate limiting**: Add delays or reduce batch size

**Memory issues**: Reduce batch size (`--batch-size 30`)

**Partial failures**: Script continues; check logs for specific issues

### Manual Recovery
If the script fails partway through:
```bash
# Resume from specific date
python run_backfill.py --start 2023-06-15
```

The script automatically skips already-processed dates, making recovery seamless.