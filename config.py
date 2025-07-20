"""
Configuration settings and constants for the Portfolio Analysis API
"""
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Directory settings - use environment variable for production
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
PLOTS_FOLDER = os.path.join(UPLOAD_FOLDER, 'plots')

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PLOTS_FOLDER, exist_ok=True)

# Default parameters
DEFAULT_RF_RATE = 0.043
DEFAULT_DAILY_RF_RATE = 0.000171
DEFAULT_SMA_WINDOW = 20
DEFAULT_STARTING_CAPITAL = 100000.0

# Column name mappings
DATE_COLUMNS = ['Date Opened', 'Date', 'Trade Date', 'Entry Date', 'Open Date']
PL_COLUMNS = ['P/L', 'PnL', 'Profit/Loss', 'Net P/L', 'Realized P/L', 'Total P/L']

# Monte Carlo simulation settings
DEFAULT_SIMULATIONS = 1000
DEFAULT_FORECAST_DAYS = 252

# Session configuration
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "dev-secret-key-change-in-production")

# Portfolio weighting settings
DEFAULT_EQUAL_WEIGHTING = True
DEFAULT_WEIGHTS = []  # Empty list means equal weighting
