# Portfolio Robustness Testing Feature

## Overview

A comprehensive feature to evaluate portfolio performance consistency across multiple time periods through statistical robustness testing. This feature will allow users to select any portfolio from the database and analyze its performance stability using randomly sampled 1-year periods.

## Core Functionality

### Portfolio Selection Interface
- **Dropdown Menu**: List all portfolios in the database with portfolio names and date ranges
- **Portfolio Overview**: Display full dataset metrics for the selected portfolio
  - Total return period
  - Overall CAGR, Sharpe ratio, max drawdown, volatility
  - Total trades, win rate, profit factor

### Robustness Testing Engine
- **Random Period Selection**: Generate random start dates with constraints:
  - Minimum 1 year from the end date of the dataset
  - Default: 10 random periods (scalable to 50+)
  - Each period spans exactly 1 year (252 trading days)
- **Metrics Calculation**: Calculate all standard portfolio metrics for each 1-year period:
  - CAGR (Compound Annual Growth Rate)
  - Sharpe Ratio
  - Maximum Drawdown
  - Volatility (Standard Deviation)
  - Win Rate
  - Profit Factor
  - Average Trade Return
  - Total Return

### Statistical Analysis
- **Descriptive Statistics**: For each metric, calculate:
  - Maximum value
  - Minimum value
  - Average (mean) value
  - Median value
  - Standard deviation
  - 25th percentile (Q1)
  - 75th percentile (Q3)
- **Distribution Analysis**: Provide insights into metric consistency and variability

### Robustness Scoring
- **Comparison Framework**: Compare average results from random periods against full dataset results
- **Robustness Score Calculation**: 
  - Score based on consistency between subset averages and full dataset metrics
  - Higher scores indicate more robust/consistent performance
  - Scoring methodology: Weighted average of metric deviations
- **Performance Stability Index**: Overall measure of how consistent the strategy performs across different time periods

## Technical Implementation

### Database Schema Extensions

#### New Tables

**robustness_tests**
```sql
- id (Primary Key)
- portfolio_id (Foreign Key to portfolios)
- test_date (Timestamp)
- num_periods (Integer, default 10)
- min_period_length_days (Integer, default 252)
- overall_robustness_score (Float)
- created_at (Timestamp)
```

**robustness_periods**
```sql
- id (Primary Key) 
- robustness_test_id (Foreign Key)
- period_number (Integer)
- start_date (Date)
- end_date (Date)
- cagr (Float)
- sharpe_ratio (Float)
- max_drawdown (Float)
- volatility (Float)
- win_rate (Float)
- profit_factor (Float)
- avg_trade_return (Float)
- total_return (Float)
- created_at (Timestamp)
```

**robustness_statistics**
```sql
- id (Primary Key)
- robustness_test_id (Foreign Key)
- metric_name (String)
- max_value (Float)
- min_value (Float)
- mean_value (Float)
- median_value (Float)
- std_deviation (Float)
- q1_value (Float)
- q3_value (Float)
- full_dataset_value (Float)
- robustness_component_score (Float)
```

### Backend Implementation

#### New API Endpoints

**GET /api/robustness/portfolios**
- List all portfolios available for robustness testing
- Return portfolio metadata and overall metrics

**POST /api/robustness/test/{portfolio_id}**
- Request body: `{num_periods: int, period_length_days: int}`
- Execute robustness test for specified portfolio
- Return test ID and initial results

**GET /api/robustness/test/{test_id}/results**
- Retrieve complete robustness test results
- Include statistical analysis and robustness scores

**GET /api/robustness/test/{test_id}/periods**
- Get individual period results for detailed analysis

**DELETE /api/robustness/test/{test_id}**
- Delete robustness test and associated data

#### New Backend Modules

**robustness_service.py**
- Core business logic for robustness testing
- Random period generation with validation
- Statistical calculations and scoring algorithms

**robustness_processor.py**  
- Portfolio data processing for random periods
- Metric calculations for individual time periods
- Database persistence operations

**routers/robustness.py**
- FastAPI router for robustness testing endpoints
- Request validation and response formatting

### Frontend Implementation

#### New React Components

**RobustnessTestPage.tsx**
- Main interface for robustness testing
- Portfolio selection dropdown
- Test configuration (number of periods)
- Results visualization

**RobustnessResults.tsx**
- Statistical summary tables
- Performance comparison charts
- Robustness score visualization
- Individual period analysis

**RobustnessCharts.tsx**
- Box plots for metric distributions
- Scatter plots comparing periods
- Robustness score visualization
- Historical comparison charts

#### New Frontend Routes
- `/robustness` - Main robustness testing interface
- `/robustness/results/{testId}` - Detailed results page

### Data Processing Logic

#### Random Period Selection Algorithm
1. Load portfolio date range from database
2. Calculate valid start date range (end_date - min_period_length - 1 year)
3. Generate N random start dates within valid range
4. Ensure no overlapping periods (optional constraint)
5. Validate each period has sufficient data

#### Metrics Calculation Pipeline
1. Extract portfolio data for each random period
2. Apply same calculation logic as existing portfolio analysis
3. Store individual period results
4. Calculate descriptive statistics across all periods
5. Compute robustness scores

#### Robustness Scoring Methodology
```python
def calculate_robustness_score(period_metrics, full_dataset_metrics):
    """
    Calculate robustness score based on consistency between 
    random period averages and full dataset metrics
    """
    weights = {
        'cagr': 0.25,
        'sharpe_ratio': 0.20, 
        'max_drawdown': 0.25,
        'volatility': 0.15,
        'win_rate': 0.15
    }
    
    component_scores = {}
    for metric, weight in weights.items():
        period_avg = np.mean([p[metric] for p in period_metrics])
        full_value = full_dataset_metrics[metric]
        
        # Calculate relative deviation (lower is better)
        deviation = abs(period_avg - full_value) / abs(full_value)
        component_score = max(0, 100 - (deviation * 100))
        component_scores[metric] = component_score
    
    # Weighted average of component scores
    overall_score = sum(score * weights[metric] 
                       for metric, score in component_scores.items())
    
    return overall_score, component_scores
```

## User Experience Flow

1. **Portfolio Selection**: User selects portfolio from dropdown
2. **Overview Display**: Show full dataset metrics for context
3. **Test Configuration**: Choose number of random periods (10-50)
4. **Execution**: Run robustness test (progress indicator)
5. **Results Display**: 
   - Statistical summary tables
   - Robustness score with interpretation
   - Distribution visualizations
   - Comparison with full dataset
6. **Historical Tests**: View previous robustness tests for the portfolio

## Success Metrics

- **Performance Consistency**: Identify strategies with stable performance across time periods
- **Risk Assessment**: Evaluate if risk metrics remain consistent
- **Strategy Validation**: Confirm strategy effectiveness isn't due to specific market conditions
- **Comparative Analysis**: Rank portfolios by robustness scores

## Future Enhancements

- **Custom Period Lengths**: Allow testing with different time horizons (6 months, 2 years)
- **Monte Carlo Integration**: Combine with existing Monte Carlo simulations
- **Regime-Aware Testing**: Sample periods from different market regimes
- **Rolling Window Testing**: Systematic testing of consecutive periods
- **Benchmark Comparison**: Compare robustness against market indices

## Implementation Priority

1. **Phase 1**: Database schema and basic backend endpoints
2. **Phase 2**: Core robustness testing algorithm and statistics
3. **Phase 3**: Frontend interface and basic visualizations  
4. **Phase 4**: Advanced scoring and comparison features
5. **Phase 5**: Enhanced visualizations and reporting

## Technical Considerations

- **Performance**: Optimize for large datasets and multiple period calculations
- **Memory Management**: Efficient handling of portfolio data subsets
- **Caching**: Store intermediate calculations for faster re-runs
- **Validation**: Ensure sufficient data availability for all random periods
- **Error Handling**: Graceful handling of insufficient data or calculation errors