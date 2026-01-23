"""
Configuration settings and constants for the Portfolio Analysis API
"""
import os
import logging
from logging.handlers import RotatingFileHandler
import sys

# Set up logging with both file and console handlers
def setup_logging():
    """Configure logging to write to both file and console"""
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # Create log file path
    log_file = os.path.join(log_dir, 'portfolio_analysis.log')

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler with rotation (10MB max, keep 5 backups)
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except (PermissionError, OSError) as e:
        # If we can't write to file, just log to console
        print(f"Warning: Could not create log file: {e}", file=sys.stderr)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    return root_logger

# Initialize logging
setup_logging()

# Directory settings - use environment variable for production
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
PLOTS_FOLDER = os.path.join(UPLOAD_FOLDER, 'plots')

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PLOTS_FOLDER, exist_ok=True)

# Default parameters
DEFAULT_RF_RATE = 0.041
DEFAULT_DAILY_RF_RATE = 0.000159  # (1.041)^(1/252) - 1
DEFAULT_SMA_WINDOW = 20
DEFAULT_STARTING_CAPITAL = 1000000.0

# Column name mappings
DATE_COLUMNS = ['Date Opened', 'Date', 'Trade Date', 'Entry Date', 'Open Date', 'OpenDate', 'FinalTradeClosedDate']
PL_COLUMNS = ['P/L', 'PnL', 'Profit/Loss', 'Net P/L', 'Realized P/L', 'Total P/L', 'TotalGrossProfitLoss', 'TotalNetProfitLoss']
PREMIUM_COLUMNS = ['Premium', 'Premium Collected', 'Premium Received', 'Initial Premium', 'Option Premium']
CONTRACTS_COLUMNS = ['No. of Contracts', 'Contracts', 'Contract Count', 'Number of Contracts', 'Qty', 'Quantity']

# Margin/Buying Power column mappings (for automatic extraction during upload)
MARGIN_COLUMNS = [
    'Buying Power', 'BuyingPower', 'Margin', 'Margin Requirement', 'MarginRequirement',
    'Initial Margin', 'InitialMargin', 'Required Margin', 'RequiredMargin',
    'Capital Required', 'CapitalRequired', 'Position Value', 'PositionValue',
    'Notional Value', 'NotionalValue', 'buying power', 'BUYING POWER'
]

# Vendor-specific column mappings
# Trade Steward format columns
TRADE_STEWARD_IDENTIFIER_COLUMNS = ['Backtick UID', 'Trade Number', 'Exit Date', 'Trade P/L']
TRADE_STEWARD_DATE_COLUMN = 'Exit Date'
TRADE_STEWARD_PL_COLUMN = 'Trade P/L'
TRADE_STEWARD_ENTRY_DATE_COLUMN = 'Entry Date'
TRADE_STEWARD_MARGIN_COLUMN = 'Buying Power'  # Trade Steward uses "Buying Power" for margin

# Monte Carlo simulation settings
DEFAULT_SIMULATIONS = 1000
DEFAULT_FORECAST_DAYS = 252

# Session configuration
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "dev-secret-key-change-in-production")

# Portfolio weighting settings
DEFAULT_EQUAL_WEIGHTING = True
DEFAULT_WEIGHTS = []  # Empty list means equal weighting
