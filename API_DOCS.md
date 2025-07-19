# Portfolio Analysis FastAPI - API Documentation

## Endpoints

### GET /
**Description**: Serve the main upload form interface

**Response**: HTML form for file upload

---

### POST /upload
**Description**: Process uploaded CSV files and generate portfolio analysis

**Parameters**:
- `files`: List of CSV files (multipart/form-data)
- `rf_rate`: Risk-free rate (optional, default: 0.043)
- `starting_capital`: Initial capital amount (optional, default: 100000)

**Response**: HTML page with analysis results including:
- Performance metrics table
- Equity curve chart
- Drawdown analysis chart
- Correlation heatmap (for multiple files)
- Monte Carlo simulation (for blended portfolios)

**Example cURL**:
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "files=@portfolio1.csv" \
  -F "files=@portfolio2.csv" \
  -F "rf_rate=0.043" \
  -F "starting_capital=100000"
```

---

### GET /uploads/plots/{filename}
**Description**: Serve generated chart images

**Parameters**:
- `filename`: Name of the chart file

**Response**: Image file (PNG format)

## Data Format Requirements

### CSV File Structure
Your CSV files must contain the following columns (with flexible naming):

**Required Columns**:
- **Date Column**: One of: `Date Opened`, `Date`, `Trade Date`, `Entry Date`, `Open Date`
- **P/L Column**: One of: `P/L`, `PnL`, `Profit/Loss`, `Net P/L`, `Realized P/L`, `Total P/L`

**Optional Columns**:
- `Premium`: Premium amount for trades
- `No. of Contracts`: Number of contracts
- `Strategy`: Strategy name (auto-generated from filename if not present)

### Example CSV Format
```csv
Date Opened,P/L,Premium,No. of Contracts
2024-01-15,150.50,500.00,2
2024-01-16,-75.25,300.00,1
2024-01-17,225.75,800.00,3
```

## Response Objects

### Performance Metrics
```json
{
  "Total Profit ($)": 15420.75,
  "Total Return (%)": 15.42,
  "CAGR (%)": 8.45,
  "Sharpe Ratio": 1.23,
  "Max Drawdown (%)": 12.34,
  "Calmar Ratio": 0.69,
  "Win Rate (%)": 65.5,
  "Volatility (%)": 18.9
}
```

### Generated Charts
- `equity_curve.png`: Portfolio value over time
- `drawdown_chart.png`: Drawdown analysis with timeline
- `correlation_heatmap.png`: Strategy correlation matrix
- `monte_carlo_simulation.png`: Future path projections

## Error Handling

The API handles common errors gracefully:

- **Invalid CSV format**: Returns error message with format requirements
- **Missing required columns**: Provides list of acceptable column names
- **Empty files**: Returns appropriate error message
- **Processing errors**: Detailed error logging with user-friendly messages

## Configuration Options

### Default Settings
```python
rf_rate = 0.043  # 4.3% annual risk-free rate
starting_capital = 100000  # $100,000 initial capital
sma_window = 20  # 20-day moving average
use_trading_filter = True  # Enable SMA filtering
```

### Monte Carlo Parameters
```python
num_simulations = 1000  # Number of simulation paths
num_days = 252  # Trading days (1 year)
confidence_levels = [5, 50, 95]  # Percentile analysis
```
