# Portfolio Analysis FastAPI Application

A comprehensive portfolio analysis tool built with FastAPI that provides advanced risk metrics, Monte Carlo simulations, and interactive visualizations for trading strategies.

## Features

- **Portfolio Analytics**: Calculate comprehensive performance metrics including Sharpe ratio, maximum drawdown, CAGR, and more
- **Monte Carlo Simulation**: Run 1000-scenario simulations to forecast potential portfolio paths with percentile analysis
- **Correlation Analysis**: Generate correlation heatmaps for multi-portfolio analysis
- **Interactive Charts**: Collapsible chart interface with professional formatting
- **CSV Upload**: Support for multiple CSV file uploads with automatic data processing
- **Blended Portfolio Analysis**: Combine multiple strategies into a single portfolio analysis

## Risk Metrics Calculated

- **Total Profit/Loss**: Absolute and percentage returns
- **CAGR**: Compound Annual Growth Rate
- **Sharpe Ratio**: Risk-adjusted return metric
- **Maximum Drawdown**: Largest peak-to-trough decline
- **Calmar Ratio**: CAGR divided by maximum drawdown
- **Win Rate**: Percentage of profitable trades
- **Volatility**: Annualized standard deviation
- **Value at Risk (VaR)**: Risk exposure at different confidence levels

## Monte Carlo Features

- **1000 Scenario Simulation**: Statistical forecasting over 252 trading days
- **Percentile Analysis**: 5th, 50th (median), and 95th percentile projections
- **Risk Assessment**: Probability analysis and worst-case scenarios
- **Visual Forecasting**: Interactive charts showing potential portfolio paths

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/portfolio-analysis-fastapi.git
cd portfolio-analysis-fastapi
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the application:

```bash
uvicorn app:app --reload
```

4. Open your browser and navigate to `http://localhost:8000`

## Usage

### Single Portfolio Analysis

1. Upload a CSV file containing your trading data
2. Ensure your CSV has columns for dates and P/L values
3. View comprehensive analytics including charts and risk metrics

### Multiple Portfolio Analysis

1. Upload multiple CSV files representing different strategies
2. Get individual analysis for each strategy
3. View correlation analysis between strategies
4. Analyze the blended portfolio with Monte Carlo simulation

### Required CSV Format

Your CSV files should contain at minimum:

- **Date column**: Date Opened, Date, Trade Date, etc.
- **P/L column**: P/L, PnL, Profit/Loss, etc.

Optional columns:

- Premium, No. of Contracts, Strategy names

## API Endpoints

- `GET /`: Upload form interface
- `POST /upload`: Process uploaded CSV files
- `GET /uploads/plots/{filename}`: Serve generated charts

## Technologies Used

- **FastAPI**: Modern Python web framework
- **Pandas**: Data manipulation and analysis
- **NumPy**: Numerical computing
- **Matplotlib/Seaborn**: Data visualization
- **Jinja2**: Template engine for HTML rendering

## Configuration

Default settings can be modified in the `process_portfolio_data` function:

- `rf_rate`: Risk-free rate (default: 4.3%)
- `starting_capital`: Initial capital (default: $100,000)
- `sma_window`: Simple moving average window (default: 20 days)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built for comprehensive portfolio risk analysis
- Designed for traders and portfolio managers
- Supports both individual and institutional use cases
