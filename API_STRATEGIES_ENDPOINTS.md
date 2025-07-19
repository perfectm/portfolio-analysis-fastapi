# Strategies API Endpoints

This document describes the new API endpoints for retrieving existing strategies (portfolios) from the database.

## Endpoints

### 1. GET /api/strategies
Get all existing strategies with detailed information and optional analysis summary.

**Parameters:**
- `limit` (int, optional): Maximum number of strategies to return (default: 100)
- `include_summary` (bool, optional): Whether to include latest analysis summary (default: true)

**Response:**
```json
{
  "success": true,
  "count": 5,
  "total_available": 5,
  "strategies": [
    {
      "id": 1,
      "name": "My Strategy",
      "filename": "portfolio_data.csv",
      "upload_date": "2025-07-19T10:30:00",
      "file_size": 15432,
      "row_count": 250,
      "date_range_start": "2024-01-01T00:00:00",
      "date_range_end": "2024-12-31T00:00:00",
      "file_hash": "a1b2c3d4e5f6...",
      "latest_analysis": {
        "analysis_type": "portfolio_analysis",
        "created_at": "2025-07-19T11:00:00",
        "sharpe_ratio": 1.25,
        "mar_ratio": 0.85,
        "cagr": 12.5,
        "annual_volatility": 18.2,
        "total_return": 15.8,
        "max_drawdown": -5.2,
        "max_drawdown_percent": -8.5,
        "final_account_value": 115800
      }
    }
  ],
  "metadata": {
    "limit_applied": 100,
    "include_summary": true,
    "generated_at": "2025-07-19T12:00:00"
  }
}
```

### 2. GET /api/strategies/list
Get a lightweight list of strategy names and IDs for quick reference.

**Response:**
```json
{
  "success": true,
  "count": 5,
  "strategies": [
    {
      "id": 1,
      "name": "My Strategy",
      "filename": "portfolio_data.csv",
      "upload_date": "2025-07-19T10:30:00",
      "row_count": 250
    }
  ]
}
```

### 3. GET /api/strategies/{strategy_id}/analysis
Get detailed analysis history for a specific strategy.

**Parameters:**
- `strategy_id` (int): ID of the strategy/portfolio
- `limit` (int, optional): Maximum number of analysis results to return (default: 10)

**Response:**
```json
{
  "success": true,
  "strategy": {
    "id": 1,
    "name": "My Strategy",
    "filename": "portfolio_data.csv"
  },
  "analysis_count": 3,
  "analysis_results": [
    {
      "id": 15,
      "analysis_type": "portfolio_analysis",
      "created_at": "2025-07-19T11:00:00",
      "parameters": {
        "rf_rate": 0.04,
        "daily_rf_rate": 0.000157,
        "sma_window": 50,
        "use_trading_filter": true,
        "starting_capital": 100000
      },
      "metrics": {
        "sharpe_ratio": 1.25,
        "mar_ratio": 0.85,
        "cagr": 12.5,
        "annual_volatility": 18.2,
        "total_return": 15.8,
        "total_pl": 15800,
        "final_account_value": 115800,
        "max_drawdown": -5200,
        "max_drawdown_percent": -8.5
      },
      "plots": [
        {
          "plot_type": "combined_analysis",
          "file_url": "/uploads/plots/strategy_1_combined_analysis.png",
          "file_size": 125648,
          "created_at": "2025-07-19T11:01:00"
        }
      ]
    }
  ]
}
```

## Usage Examples

### Get all strategies with summary
```bash
curl "http://localhost:8000/api/strategies"
```

### Get strategies without analysis summary
```bash
curl "http://localhost:8000/api/strategies?include_summary=false"
```

### Get limited number of strategies
```bash
curl "http://localhost:8000/api/strategies?limit=10"
```

### Get lightweight strategies list
```bash
curl "http://localhost:8000/api/strategies/list"
```

### Get analysis history for strategy ID 1
```bash
curl "http://localhost:8000/api/strategies/1/analysis"
```

### Get last 5 analysis results for strategy ID 1
```bash
curl "http://localhost:8000/api/strategies/1/analysis?limit=5"
```

## Error Responses

All endpoints return consistent error responses:

```json
{
  "success": false,
  "error": "Error description",
  "strategies": [],
  "count": 0
}
```

For strategy-specific endpoints, if strategy not found:
```json
{
  "success": false,
  "error": "Strategy with ID 123 not found",
  "analysis_results": []
}
```

## Integration with Existing Endpoints

These new endpoints complement the existing endpoints:
- `/portfolios` - HTML page listing portfolios
- `/portfolio/{portfolio_id}` - JSON data for specific portfolio
- `/upload` - Upload and process new portfolios

The new API endpoints provide programmatic access to the same data with enhanced filtering and analysis information.
