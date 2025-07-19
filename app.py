import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import json
from typing import List, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# Create plots directory if it doesn't exist
os.makedirs(os.path.join(UPLOAD_FOLDER, 'plots'), exist_ok=True)

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/uploads", StaticFiles(directory=UPLOAD_FOLDER), name="uploads")

# Add session middleware with a secret key
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")

def process_portfolio_data(df, rf_rate=0.043, daily_rf_rate=0.000171, sma_window=20, use_trading_filter=True, starting_capital=100000, is_blended=False):
    logger = logging.getLogger(__name__)
    
    # Log original columns for debugging
    logger.info(f"Original columns in CSV: {df.columns.tolist()}")
    
    # For blended portfolio, we already have the correct columns
    if is_blended:
        clean_df = df.copy()
        logger.info("Processing as blended portfolio with pre-cleaned data")
    else:
        # List of possible date column names
        date_columns = ['Date Opened', 'Date', 'Trade Date', 'Entry Date', 'Open Date']
        # List of possible P/L column names
        pl_columns = ['P/L', 'PnL', 'Profit/Loss', 'Net P/L', 'Realized P/L', 'Total P/L']
        
        # Find the date column
        date_column = None
        for col in date_columns:
            if col in df.columns:
                date_column = col
                break
                
        if date_column is None:
            logger.error(f"No date column found. Looking for any of: {date_columns}")
            logger.error(f"Available columns are: {df.columns.tolist()}")
            raise ValueError(f"No date column found. Expected one of: {date_columns}")
        
        logger.info(f"Using '{date_column}' as date column")
        
        # Find the P/L column
        pl_column = None
        for col in pl_columns:
            if col in df.columns:
                pl_column = col
                break
                
        if pl_column is None:
            logger.error(f"No P/L column found. Looking for any of: {pl_columns}")
            logger.error(f"Available columns are: {df.columns.tolist()}")
            raise ValueError(f"No P/L column found. Expected one of: {pl_columns}")
        
        logger.info(f"Using '{pl_column}' as P/L column")
        
        # Create a clean DataFrame with standardized column names
        clean_df = pd.DataFrame()
        clean_df['Date'] = pd.to_datetime(df[date_column])
        
        # Clean P/L data - remove any currency symbols and convert to float
        clean_df['P/L'] = df[pl_column].astype(str).str.replace('$', '').str.replace(',', '').str.replace('(', '-').str.replace(')', '').astype(float)
    
    # Sort by date
    clean_df = clean_df.sort_values('Date')
    
    # Show sample of data after cleaning
    logger.info("\nSample of cleaned data:")
    logger.info(clean_df.head().to_string())
    logger.info(f"\nData shape after cleaning: {clean_df.shape}")
    logger.info(f"Date range: {clean_df['Date'].min()} to {clean_df['Date'].max()}")
    logger.info(f"Total P/L sum: ${clean_df['P/L'].sum():,.2f}")
    
    # Calculate cumulative P/L and account value
    clean_df['Cumulative P/L'] = clean_df['P/L'].cumsum()
    clean_df['Account Value'] = starting_capital + clean_df['Cumulative P/L']
    
    # Calculate returns based on account value
    clean_df['Daily Return'] = clean_df['Account Value'].pct_change()
    
    # Replace infinite values with NaN
    clean_df['Daily Return'] = clean_df['Daily Return'].replace([np.inf, -np.inf], np.nan)
    
    # Calculate SMA if using trading filter
    if use_trading_filter:
        clean_df['SMA'] = clean_df['Account Value'].rolling(window=sma_window, min_periods=1).mean()
        clean_df['Position'] = np.where(clean_df['Account Value'] > clean_df['SMA'], 1, 0)
        clean_df['Strategy Return'] = clean_df['Daily Return'] * clean_df['Position'].shift(1).fillna(0)
    else:
        clean_df['Strategy Return'] = clean_df['Daily Return']
    
    # Keep track of only days with actual trades
    clean_df['Has_Trade'] = clean_df['P/L'] != 0
    
    # For Sharpe calculation, we'll only use days with trades
    clean_df['Strategy Return'] = clean_df['Strategy Return'].where(clean_df['Has_Trade'])
    
    # Initialize variables with default values
    strategy_mean_return = 0
    strategy_std = 0
    sharpe_ratio = 0
    total_return = 0
    num_years = 0
    
    # Rest of the function remains the same, just use clean_df instead of df
    try:
        # Calculate strategy metrics with error handling - only use days with trades
        valid_returns = clean_df['Strategy Return'][clean_df['Has_Trade']]
        
        if len(valid_returns) > 0:
            # Calculate total return based on account value
            total_return = (clean_df['Account Value'].iloc[-1] / starting_capital) - 1
            
            # Calculate number of years (exactly matching YEARFRAC actual/actual basis)
            start_date = clean_df['Date'].min()
            end_date = clean_df['Date'].max()
            
            def days_in_month(year, month):
                if month in [4, 6, 9, 11]:
                    return 30
                elif month == 2:
                    if pd.Timestamp(f"{year}-12-31").is_leap_year:
                        return 29
                    return 28
                else:
                    return 31
            
            if start_date.year == end_date.year:
                # If same year, use actual days and actual year length
                days_in_year = 366 if pd.Timestamp(f"{start_date.year}-12-31").is_leap_year else 365
                num_years = (end_date - start_date).days / days_in_year
            else:
                # Calculate days in first partial year
                days_in_start_year = 366 if pd.Timestamp(f"{start_date.year}-12-31").is_leap_year else 365
                remaining_days_start = (pd.Timestamp(f"{start_date.year}-12-31") - start_date).days + 1
                first_year_fraction = remaining_days_start / days_in_start_year
                
                # Calculate days in last partial year
                days_in_end_year = 366 if pd.Timestamp(f"{end_date.year}-12-31").is_leap_year else 365
                days_in_end = (end_date - pd.Timestamp(f"{end_date.year}-01-01")).days + 1
                last_year_fraction = days_in_end / days_in_end_year
                
                # Add up complete years in between
                full_years = end_date.year - start_date.year - 1
                
                num_years = first_year_fraction + full_years + last_year_fraction
            
            # Calculate annualized return
            if num_years > 0:
                strategy_mean_return = (1 + total_return) ** (1/num_years) - 1
            else:
                strategy_mean_return = total_return
            
            # Exactly matching Google Sheet calculations with detailed logging:
            # Calculate normalized returns (P/L divided by starting capital)
            # Important: Filter to only market trading days and match Google Sheet range
            clean_df_sorted = clean_df.sort_values('Date')
            
            # Create a series of business days from start to end of data
            start_date = clean_df_sorted['Date'].min()
            end_date = clean_df_sorted['Date'].max()
            business_days = pd.bdate_range(start=start_date, end=end_date)
            
            # Create a DataFrame with all business days and merge with our data
            market_days_df = pd.DataFrame({'Date': business_days})
            market_days_df['Date'] = pd.to_datetime(market_days_df['Date']).dt.normalize()
            
            # Merge with our clean data
            clean_df_sorted['Date'] = pd.to_datetime(clean_df_sorted['Date']).dt.normalize()
            market_data = market_days_df.merge(clean_df_sorted[['Date', 'P/L']], on='Date', how='left')
            market_data['P/L'] = market_data['P/L'].fillna(0)  # Fill non-trading days with 0
            
            # Calculate normalized returns for market days only
            normalized_returns = market_data['P/L'] / starting_capital
            
            # Take only the first 742 rows to match Google Sheet range BO4:BO745
            normalized_returns = normalized_returns[:742]
            
            # Calculate dates with trades for validation
            trade_dates = clean_df[clean_df['Has_Trade']]['Date']
            logger.info("\nFirst and last trade dates:")
            logger.info(f"First trade: {trade_dates.min()}")
            logger.info(f"Last trade: {trade_dates.max()}")
            logger.info(f"Number of calendar days: {(trade_dates.max() - trade_dates.min()).days}")
            
            # Log the first few normalized returns for verification and validation
            logger.info("\nFirst 5 normalized returns:")
            logger.info(normalized_returns.head().to_string())
            logger.info("\nLast 5 normalized returns:")
            logger.info(normalized_returns.tail().to_string())
            
            mean_return = normalized_returns.mean()
            logger.info(f"\nMean daily return calculation:")
            logger.info(f"Sum of normalized returns: {normalized_returns.sum():.10f}")
            logger.info(f"Count of returns: {len(normalized_returns)}")
            logger.info(f"Mean daily return: {mean_return:.10f}")
            
            # Calculate mean differently to validate
            alt_mean = normalized_returns.sum() / len(normalized_returns)
            logger.info(f"Alternative mean calculation: {alt_mean:.10f}")
            
            # BS2 = AVERAGE(BO4:BO745)-daily_rf_rate
            daily_excess_returns = mean_return - daily_rf_rate
            logger.info(f"\nExcess return calculation:")
            logger.info(f"Mean daily return: {mean_return:.10f}")
            logger.info(f"Risk-free daily rate: {daily_rf_rate}")
            logger.info(f"Daily excess return (BS2) calculated: {daily_excess_returns:.10f}")
            logger.info(f"Daily excess return (BS2) target from Google: 0.0007816134771")
            logger.info(f"Difference from target: {daily_excess_returns - 0.0007816134771:.10f}")
            
            # BS1 = STDEV.P(BO4:BO745)
            # Calculate standard deviation exactly like Excel's STDEV.P
            mean_for_std = normalized_returns.mean()  # Ensure we use the same mean for std calculation
            
            # Log values for comparison with Google Sheet
            logger.info("\nFirst few values for comparison with BO column:")
            sample_values = normalized_returns.head(20)
            for idx, val in sample_values.items():
                logger.info(f"{val:.7f}")
            
            # Calculate variance exactly like STDEV.P in Excel
            squared_diff_sum = ((normalized_returns - mean_for_std)**2).sum()
            count = len(normalized_returns)  # This should match your BO column length
            variance = squared_diff_sum / count
            daily_std = np.sqrt(variance)
            
            # Count zero vs non-zero values
            zero_count = (normalized_returns == 0).sum()
            nonzero_count = (normalized_returns != 0).sum()
            logger.info(f"\nValue distribution:")
            logger.info(f"Zero values: {zero_count}")
            logger.info(f"Non-zero values: {nonzero_count}")
            logger.info(f"Total values: {len(normalized_returns)}")
            
            # Calculate std dev both ways for comparison
            std_with_zeros = daily_std
            std_without_zeros = normalized_returns[normalized_returns != 0].std(ddof=0)
            logger.info(f"\nStandard deviation comparison:")
            logger.info(f"Std dev with zeros: {std_with_zeros:.10f}")
            logger.info(f"Std dev without zeros: {std_without_zeros:.10f}")
            
            # Also calculate using alternative methods for validation
            pandas_std = normalized_returns.std(ddof=0)
            numpy_std = np.std(normalized_returns, ddof=0)
            
            logger.info(f"\nDetailed standard deviation calculation:")
            logger.info(f"Target std dev from Google: 0.006252802845")
            logger.info(f"Mean used for calculation: {mean_for_std:.10f}")
            logger.info(f"Squared differences calculation:")
            logger.info(f"  Sum of squared deviations: {squared_diff_sum:.10f}")
            logger.info(f"  Count (n): {count}")
            logger.info(f"  Variance (sum/n): {variance:.10f}")
            logger.info(f"Standard deviation results:")
            logger.info(f"  Our STDEV.P calculation: {daily_std:.10f}")
            logger.info(f"  Google Sheet STDEV.P: 0.00619301214")
            logger.info(f"  Difference: {daily_std - 0.00619301214:.10f}")
            logger.info(f"Validation with other methods:")
            logger.info(f"  Pandas std (ddof=0): {pandas_std:.10f}")
            logger.info(f"  Numpy std (ddof=0): {numpy_std:.10f}")
            
            # Log more details about the distribution
            logger.info("\nDetailed return distribution:")
            percentiles = normalized_returns.quantile([0, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 1])
            logger.info(percentiles.to_string())
            logger.info(f"\nFirst few normalized returns:")
            logger.info(normalized_returns.head().to_string())
            logger.info(f"\nDescriptive statistics:")
            logger.info(normalized_returns.describe().to_string())
            
            # Standard Sharpe Ratio Calculation (Best Practice)
            # Use portfolio returns (not just trading days) and calculate properly
            
            # Method 1: Using account value returns (most common for portfolio analysis)
            portfolio_returns = clean_df['Account Value'].pct_change().dropna()
            
            # Convert annual risk-free rate to daily
            daily_rf_for_sharpe = (1 + rf_rate) ** (1/252) - 1
            
            # Calculate excess returns
            excess_returns = portfolio_returns - daily_rf_for_sharpe
            
            # Calculate Sharpe ratio components
            mean_excess_return = excess_returns.mean()
            volatility = excess_returns.std()
            
            # Annualized Sharpe ratio
            sharpe_ratio = (mean_excess_return / volatility) * np.sqrt(252) if volatility != 0 else 0
            
            # Alternative Method 2: Using P/L returns on trading days only
            trading_returns = clean_df[clean_df['Has_Trade']]['P/L'] / starting_capital
            trading_excess_returns = trading_returns - daily_rf_for_sharpe
            alt_sharpe = (trading_excess_returns.mean() / trading_excess_returns.std()) * np.sqrt(252) if trading_excess_returns.std() != 0 else 0
            
            logger.info(f"\nStandard Sharpe Ratio Calculation:")
            logger.info(f"Annual risk-free rate: {rf_rate:.4f}")
            logger.info(f"Daily risk-free rate: {daily_rf_for_sharpe:.6f}")
            logger.info(f"Mean daily excess return: {mean_excess_return:.6f}")
            logger.info(f"Daily volatility: {volatility:.6f}")
            logger.info(f"Annualized Sharpe Ratio (Method 1 - Portfolio): {sharpe_ratio:.4f}")
            logger.info(f"Annualized Sharpe Ratio (Method 2 - Trading days): {alt_sharpe:.4f}")
            
            # Use the portfolio-based Sharpe ratio as it's more standard
            strategy_std = volatility * np.sqrt(252)
            
            # Additional validation
            logger.info(f"\nValidation:")
            logger.info(f"Number of valid returns: {len(normalized_returns)}")
            logger.info(f"Date range: {clean_df['Date'].min()} to {clean_df['Date'].max()}")
            logger.info(f"Trading days: {len(clean_df[clean_df['Has_Trade']])}")
            logger.info(f"Returns range: Min={normalized_returns.min():.6f}, Max={normalized_returns.max():.6f}")
            
            # Also log the number of valid returns we're using
            logger.info(f"Number of valid returns: {len(valid_returns)}")
            logger.info(f"Any NaN values in returns: {valid_returns.isna().any()}")
            logger.info(f"Returns range: {valid_returns.min():.6f} to {valid_returns.max():.6f}")
        else:
            logger.warning("No valid returns found for strategy metrics calculation")
            return clean_df, {
                'Sharpe Ratio': 0,
                'MAR Ratio': 0,
                'CAGR': 0,
                'Annual Volatility': 0,
                'Total Return': 0,
                'Total P/L': 0,
                'Final Account Value': starting_capital,
                'Peak Value': starting_capital,
                'Max Drawdown': 0,
                'Max Drawdown %': 0,
                'Number of Trading Days': 0,
                'Time Period (Years)': 0,
                'Recovery Days': 0,
                'Has Recovered': False
            }
    except Exception as e:
        logger.error(f"Error calculating metrics: {str(e)}")
        return clean_df, {
            'Sharpe Ratio': 0,
            'MAR Ratio': 0,
            'Annual Return': 0,
            'Annual Volatility': 0,
            'Total Return': 0,
            'Total P/L': float(clean_df['Cumulative P/L'].iloc[-1]),
            'Final Account Value': float(clean_df['Account Value'].iloc[-1]),
            'Peak Value': float(clean_df['Account Value'].max()),
            'Max Drawdown': 0,
            'Max Drawdown %': 0,
            'Number of Trading Days': len(clean_df[clean_df['P/L'] != 0]) if 'P/L' in clean_df.columns else len(clean_df),
            'Time Period (Years)': 0,
            'Recovery Days': 0,
            'Has Recovered': False
        }
    
    # Calculate drawdown using clean_df
    clean_df['Rolling Peak'] = clean_df['Account Value'].expanding().max()
    clean_df['Drawdown Amount'] = clean_df['Account Value'] - clean_df['Rolling Peak']
    clean_df['Drawdown Pct'] = clean_df['Drawdown Amount'] / clean_df['Rolling Peak']
    
    # Get maximum drawdown info
    max_drawdown_idx = clean_df['Drawdown Pct'].idxmin()
    max_drawdown = clean_df.loc[max_drawdown_idx, 'Drawdown Amount']
    max_drawdown_pct = clean_df.loc[max_drawdown_idx, 'Drawdown Pct']
    peak_value = clean_df['Account Value'].max()  # Use the actual peak account value
    
    # Get detailed drawdown information
    max_drawdown_date = clean_df.loc[max_drawdown_idx, 'Date']
    max_drawdown_account_value = clean_df.loc[max_drawdown_idx, 'Account Value']
    drawdown_peak_value = clean_df.loc[max_drawdown_idx, 'Rolling Peak']
    
    # Find the date when the drawdown began (when account value last equaled the rolling peak before max drawdown)
    pre_drawdown_data = clean_df.loc[:max_drawdown_idx]
    drawdown_peak_idx = pre_drawdown_data[pre_drawdown_data['Account Value'] == drawdown_peak_value].index[-1]
    drawdown_start_date = clean_df.loc[drawdown_peak_idx, 'Date']
    
    # Find date of peak before max drawdown
    peak_idx = clean_df.loc[:max_drawdown_idx]['Account Value'].idxmax()
    
    # Find date of peak before max drawdown
    peak_idx = clean_df.loc[:max_drawdown_idx]['Account Value'].idxmax()
    
    # Calculate recovery info
    recovery_days = None
    if max_drawdown_idx < len(clean_df) - 1:
        recovery_series = clean_df.loc[max_drawdown_idx:, 'Account Value']
        drawdown_peak_value = clean_df.loc[max_drawdown_idx, 'Rolling Peak']
        recovered_points = recovery_series[recovery_series >= drawdown_peak_value]
        if not recovered_points.empty:
            recovery_idx = recovered_points.index[0]
            recovery_days = (clean_df.loc[recovery_idx, 'Date'] - clean_df.loc[max_drawdown_idx, 'Date']).days

    # Calculate MAR ratio (Annualized Return / Maximum Drawdown)
    mar_ratio = abs(strategy_mean_return / abs(max_drawdown_pct)) if max_drawdown_pct != 0 else 0

    metrics = {
        'Sharpe Ratio': float(sharpe_ratio),
        'MAR Ratio': float(mar_ratio), 
        'CAGR': float(strategy_mean_return * 100),  # Convert to percentage
        'Annual Volatility': float(strategy_std * 100),  # Convert to percentage
        'Total Return': float(total_return * 100),  # Convert to percentage
        'Total P/L': float(clean_df['Cumulative P/L'].iloc[-1]),
        'Final Account Value': float(clean_df['Account Value'].iloc[-1]),
        'Peak Value': float(peak_value),
        'Max Drawdown': float(max_drawdown),
        'Max Drawdown %': float(abs(max_drawdown_pct) * 100),  # Convert to positive percentage
        'Max Drawdown Date': max_drawdown_date.strftime('%Y-%m-%d'),
        'Drawdown Start Date': drawdown_start_date.strftime('%Y-%m-%d'),
        'Account Value at Drawdown Start': float(drawdown_peak_value),
        'Account Value at Max Drawdown': float(max_drawdown_account_value),
        'Number of Trading Days': len(clean_df[clean_df['Has_Trade']]),  # Only days with actual trades
        'Time Period (Years)': float(num_years),
        'Recovery Days': float(recovery_days) if recovery_days is not None else 0.0,  # Convert None to 0.0
        'Has Recovered': recovery_days is not None  # Add boolean flag for recovery status
    }
    
    logger.info(f"Processed {len(clean_df):,} trades")
    logger.info(f"Date range: {clean_df['Date'].min()} to {clean_df['Date'].max()} ({num_years:.1f} years)")
    logger.info(f"Starting Capital: ${starting_capital:,.2f}")
    logger.info(f"Final Account Value: ${metrics['Final Account Value']:,.2f}")
    logger.info(f"Total P/L: ${metrics['Total P/L']:,.2f}")
    logger.info(f"Total Return: {metrics['Total Return']:.2f}%")
    logger.info(f"CAGR: {metrics['CAGR']:.2f}%")
    logger.info(f"Annual Volatility: {metrics['Annual Volatility']:.2f}%")
    logger.info(f"Sharpe Ratio: {metrics['Sharpe Ratio']:.2f}")
    logger.info(f"Maximum Drawdown: ${abs(max_drawdown):,.2f} ({metrics['Max Drawdown %']:.2f}%)")
    logger.info(f"Drawdown Start Date: {metrics['Drawdown Start Date']}")
    logger.info(f"Max Drawdown Date: {metrics['Max Drawdown Date']}")
    logger.info(f"Account Value at Drawdown Start: ${metrics['Account Value at Drawdown Start']:,.2f}")
    logger.info(f"Account Value at Max Drawdown: ${metrics['Account Value at Max Drawdown']:,.2f}")
    logger.info(f"MAR Ratio: {metrics['MAR Ratio']:.2f}")
    if recovery_days is not None:
        logger.info(f"Recovery Time: {recovery_days} days")
    else:
        logger.info("Drawdown not yet recovered")
    
    return clean_df, metrics

def create_plots(df, metrics, filename_prefix, sma_window=20):
    # Create plots directory if it doesn't exist
    plots_dir = os.path.join(UPLOAD_FOLDER, 'plots')
    os.makedirs(plots_dir, exist_ok=True)
    
    # Create a 2x2 subplot grid
    fig = plt.figure(figsize=(20, 16))
    
    # Plot 1: Cumulative P/L (top left)
    ax1 = plt.subplot(2, 2, 1)
    ax1.plot(df['Date'], df['Cumulative P/L'])
    ax1.set_title('Cumulative P/L Over Time')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Cumulative P/L')
    ax1.grid(True)
    ax1.tick_params(axis='x', rotation=45)
    # Format y-axis as currency
    ax1.yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter('${x:,.0f}'))

    # Plot 2: Drawdown (top right)
    ax2 = plt.subplot(2, 2, 2)
    ax2.plot(df['Date'], df['Drawdown Pct'] * 100)
    ax2.set_title('Drawdown Over Time')
    ax2.set_xlabel('Date')
    ax2.set_ylabel('Drawdown (%)')
    ax2.grid(True)
    ax2.tick_params(axis='x', rotation=45)

    # Plot 3: Daily Returns Distribution (bottom left)
    ax3 = plt.subplot(2, 2, 3)
    dollar_returns = df['Daily Return'].dropna() * df['Account Value'].shift(1)
    sns.histplot(data=dollar_returns, bins=20, kde=True, ax=ax3)
    ax3.set_title('Distribution of Daily Returns')
    ax3.set_xlabel('Daily Return ($)')
    ax3.set_ylabel('Frequency')
    # Format x-axis as currency
    current_values = ax3.get_xticks()
    ax3.set_xticks(current_values)  # Set the tick positions first
    ax3.set_xticklabels(['${:,.0f}'.format(x) for x in current_values])
    ax3.grid(True)

    # Plot 4: Account Value vs SMA (bottom right)
    ax4 = plt.subplot(2, 2, 4)
    if 'SMA' in df.columns:
        ax4.plot(df['Date'], df['Account Value'], label='Account Value', alpha=0.7)
        ax4.plot(df['Date'], df['SMA'], label=f'{sma_window}-day SMA', linewidth=2)
        ax4.set_title('Account Value vs SMA')
        ax4.set_xlabel('Date')
        ax4.set_ylabel('Value ($)')
        ax4.legend()
        ax4.grid(True)
        ax4.tick_params(axis='x', rotation=45)
        # Format y-axis as currency
        ax4.yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter('${x:,.0f}'))
    else:
        ax4.set_title('SMA Analysis Not Available')
        ax4.text(0.5, 0.5, 'Trading Filter Disabled', 
                horizontalalignment='center', verticalalignment='center',
                transform=ax4.transAxes)

    # Adjust layout to prevent overlap
    plt.tight_layout()
    
    # Save the combined plot
    plot_path = os.path.join(plots_dir, f'{filename_prefix}_combined_analysis.png')
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()

    return [plot_path]

def create_correlation_heatmap(correlation_data, portfolio_names):
    """Create a correlation heatmap for multiple portfolios"""
    try:
        # Create plots directory if it doesn't exist
        plots_dir = os.path.join(UPLOAD_FOLDER, 'plots')
        os.makedirs(plots_dir, exist_ok=True)
        
        # Fill NaN values with 0 for correlation calculation
        correlation_data_filled = correlation_data.fillna(0)
        
        # Calculate correlation matrix
        correlation_matrix = correlation_data_filled.corr()
        
        # Create the heatmap
        plt.figure(figsize=(10, 8))
        
        # Create a mask for the upper triangle to show only lower triangle + diagonal
        mask = np.triu(np.ones_like(correlation_matrix, dtype=bool), k=1)
        
        # Generate the heatmap
        sns.heatmap(correlation_matrix, 
                   annot=True, 
                   cmap='RdYlBu_r', 
                   vmin=-1, 
                   vmax=1,
                   center=0,
                   square=True, 
                   fmt='.3f',
                   cbar_kws={"shrink": .8},
                   mask=mask)
        
        plt.title('Portfolio Correlation Matrix\n(Daily Returns)', fontsize=16, pad=20)
        plt.xlabel('Portfolios', fontsize=12)
        plt.ylabel('Portfolios', fontsize=12)
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        
        # Adjust layout
        plt.tight_layout()
        
        # Save the heatmap
        heatmap_path = os.path.join(plots_dir, 'portfolio_correlation_heatmap.png')
        plt.savefig(heatmap_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return heatmap_path
        
    except Exception as e:
        logger.error(f"Error creating correlation heatmap: {str(e)}")
        return None

def create_monte_carlo_simulation(blended_df, metrics, num_simulations=1000, forecast_days=252):
    """Create a Monte Carlo simulation for the blended portfolio"""
    try:
        # Create plots directory if it doesn't exist
        plots_dir = os.path.join(UPLOAD_FOLDER, 'plots')
        os.makedirs(plots_dir, exist_ok=True)
        
        # Calculate daily returns from the blended portfolio
        daily_returns = blended_df['Daily Return'].dropna()
        
        if len(daily_returns) < 30:  # Need sufficient data
            logger.warning("Insufficient data for Monte Carlo simulation")
            return None
            
        # Calculate mean and standard deviation of daily returns
        mean_return = daily_returns.mean()
        std_return = daily_returns.std()
        
        # Current account value (starting point for simulation)
        current_value = metrics['Final Account Value']
        
        # Create random return scenarios
        np.random.seed(42)  # For reproducible results
        random_returns = np.random.normal(mean_return, std_return, (num_simulations, forecast_days))
        
        # Calculate portfolio value paths
        portfolio_paths = np.zeros((num_simulations, forecast_days + 1))
        portfolio_paths[:, 0] = current_value
        
        for i in range(forecast_days):
            portfolio_paths[:, i + 1] = portfolio_paths[:, i] * (1 + random_returns[:, i])
        
        # Create the Monte Carlo plot
        plt.figure(figsize=(12, 8))
        
        # Plot all simulation paths (with transparency)
        time_axis = np.arange(forecast_days + 1)
        for i in range(min(100, num_simulations)):  # Only plot first 100 for visibility
            plt.plot(time_axis, portfolio_paths[i], alpha=0.1, color='lightblue', linewidth=0.5)
        
        # Calculate and plot percentiles
        percentiles = [5, 25, 50, 75, 95]
        percentile_paths = np.percentile(portfolio_paths, percentiles, axis=0)
        
        colors = ['red', 'orange', 'green', 'orange', 'red']
        labels = ['5th Percentile', '25th Percentile', 'Median', '75th Percentile', '95th Percentile']
        
        for i, (percentile, color, label) in enumerate(zip(percentile_paths, colors, labels)):
            plt.plot(time_axis, percentile, color=color, linewidth=2, label=label)
        
        # Add current value line
        plt.axhline(y=current_value, color='black', linestyle='--', linewidth=2, label='Current Value')
        
        plt.title(f'Monte Carlo Simulation - Blended Portfolio\n({num_simulations:,} simulations, {forecast_days} trading days forecast)', fontsize=14)
        plt.xlabel('Trading Days')
        plt.ylabel('Portfolio Value ($)')
        plt.legend(loc='upper left')
        plt.grid(True, alpha=0.3)
        
        # Format y-axis as currency
        plt.gca().yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter('${x:,.0f}'))
        
        # Add statistics text box
        final_values = portfolio_paths[:, -1]
        stats_text = f"""Forecast Statistics (1 Year):
Expected Value: ${np.mean(final_values):,.0f}
5th Percentile: ${np.percentile(final_values, 5):,.0f}
95th Percentile: ${np.percentile(final_values, 95):,.0f}
Probability of Loss: {(final_values < current_value).mean() * 100:.1f}%"""
        
        plt.text(0.02, 0.98, stats_text, transform=plt.gca().transAxes, 
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        plt.tight_layout()
        
        # Save the Monte Carlo plot
        mc_path = os.path.join(plots_dir, 'monte_carlo_simulation.png')
        plt.savefig(mc_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return mc_path
        
    except Exception as e:
        logger.error(f"Error creating Monte Carlo simulation: {str(e)}")
        return None

@app.get("/", response_class=HTMLResponse)
async def main(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@app.post("/upload")
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    rf_rate: float = Form(0.043),  # Annual risk-free rate
    daily_rf_rate: float = Form(0.000163),  # Daily risk-free rate matching Google Sheet
    sma_window: int = Form(20),
    use_trading_filter: bool = Form(True),
    starting_capital: float = Form(100000.0)
):
    results = []
    logger.info(f"Received {len(files)} files for processing")
    logger.info(f"Parameters: rf_rate={rf_rate}, sma_window={sma_window}, use_trading_filter={use_trading_filter}, starting_capital={starting_capital}")
    
    # First, collect all trade data to create a blended portfolio
    blended_trades = pd.DataFrame()
    total_pl = 0  # Track total P/L for validation
    total_trades = 0  # Track total number of trades
    all_portfolios_recovered = True  # Track if all portfolios have recovered
    
    # Store daily returns for correlation analysis
    correlation_data = pd.DataFrame()
    portfolio_names = []
    
    for file in files:
        try:
            logger.info(f"Reading file for blended portfolio: {file.filename}")
            contents = await file.read()
            df = pd.read_csv(pd.io.common.BytesIO(contents))
            
            # Process individual file to get clean trade data
            clean_df, individual_metrics = process_portfolio_data(
                df,
                rf_rate=rf_rate,
                sma_window=sma_window,
                use_trading_filter=use_trading_filter,
                starting_capital=starting_capital
            )
            
            # Create individual portfolio result
            individual_result = {
                'filename': file.filename,
                'metrics': individual_metrics,
                'type': 'file',
                'plots': []
            }

            # Create plots for individual portfolio
            plot_paths = create_plots(clean_df, individual_metrics, filename_prefix=f"portfolio_{len(results)}", sma_window=sma_window)
            
            # Add plot paths to the results
            for plot_path in plot_paths:
                filename = os.path.basename(plot_path)
                plot_url = f"/uploads/plots/{filename}"
                individual_result['plots'].append({
                    'filename': filename,
                    'url': plot_url
                })

            # Add individual result to results list
            results.append(individual_result)
            
            # Store daily returns for correlation analysis
            portfolio_name = file.filename.replace('.csv', '')
            portfolio_names.append(portfolio_name)
            
            # Get daily account returns for correlation
            daily_returns = clean_df.set_index('Date')['Daily Return'].fillna(0)
            if correlation_data.empty:
                correlation_data = daily_returns.to_frame(portfolio_name)
            else:
                correlation_data = correlation_data.join(daily_returns.to_frame(portfolio_name), how='outer')
            
            # Add to total P/L and trades count for validation
            total_pl += individual_metrics['Total P/L']
            total_trades += individual_metrics['Number of Trading Days']
            # Update recovery status
            if not individual_metrics['Has Recovered']:
                all_portfolios_recovered = False
            
            # Add trades to blended portfolio
            # First, group the clean_df by date to get daily P/L
            daily_pl = clean_df.groupby('Date')['P/L'].sum().reset_index()
            
            if blended_trades.empty:
                blended_trades = daily_pl.copy()
            else:
                # Merge on date and sum P/L
                blended_trades = pd.merge(blended_trades, daily_pl, on='Date', how='outer', suffixes=('', '_new'))
                # Sum P/L columns, treating NaN as 0
                blended_trades['P/L'] = blended_trades['P/L'].fillna(0) + blended_trades['P/L_new'].fillna(0)
                blended_trades = blended_trades.drop('P/L_new', axis=1)
            
            # Reset file pointer for individual processing
            await file.seek(0)
            
        except Exception as e:
            logger.error(f"Error processing {file.filename} for blended portfolio: {str(e)}", exc_info=True)
            continue
    
    # Process blended portfolio if we have data
    blended_result = None
    if not blended_trades.empty and len(files) > 1:
        try:
            logger.info("Processing blended portfolio")
            logger.info(f"Initial total P/L in blended trades: {blended_trades['P/L'].sum():.2f}")
            
            # Ensure Date is datetime type and normalize to midnight
            blended_trades['Date'] = pd.to_datetime(blended_trades['Date']).dt.normalize()
            
            # Sort by date (no need to group since we've already done daily aggregation)
            blended_trades = blended_trades.sort_values('Date').reset_index(drop=True)
            
            logger.info(f"Total P/L after grouping by date: {blended_trades['P/L'].sum():.2f}")
            
            # Log P/L values for debugging
            logger.info(f"Raw blended P/L sum: {blended_trades['P/L'].sum():.2f}")
            logger.info(f"Expected total P/L (sum of individuals): {total_pl:.2f}")
            
            # Process the blended portfolio using the existing function
            blended_df, blended_metrics = process_portfolio_data(
                blended_trades,
                rf_rate=rf_rate,
                sma_window=sma_window,
                use_trading_filter=use_trading_filter,
                starting_capital=starting_capital,
                is_blended=True  # Important flag to indicate this is a blended portfolio
            )
            
            # Store the result
            blended_result = {
                'filename': 'Blended Portfolio',
                'metrics': blended_metrics,
                'type': 'file',
                'plots': []
            }

            # Create plots for blended portfolio
            plot_paths = create_plots(blended_df, blended_metrics, filename_prefix="blended_portfolio", sma_window=sma_window)
            
            # Add plot paths to the results
            for plot_path in plot_paths:
                filename = os.path.basename(plot_path)
                plot_url = f"/uploads/plots/{filename}"
                blended_result['plots'].append({
                    'filename': filename,
                    'url': plot_url
                })

            # Add blended result to results list
            results.append(blended_result)

        except Exception as e:
            logger.error(f"Error processing blended portfolio: {str(e)}")
            blended_result = None
            
            logger.info(f"Total P/L after grouping by date: {blended_trades['P/L'].sum():.2f}")
            
            # Log P/L values for debugging
            logger.info(f"Raw blended P/L sum: {blended_trades['P/L'].sum():.2f}")
            logger.info(f"Expected total P/L (sum of individuals): {total_pl:.2f}")
            
            # Process the blended portfolio using the existing function
            blended_df, blended_metrics = process_portfolio_data(
                blended_trades,
                rf_rate=rf_rate,
                sma_window=sma_window,
                use_trading_filter=use_trading_filter,
                starting_capital=starting_capital,
                is_blended=True  # Important flag to indicate this is a blended portfolio
            )
            
            # Use the processed data
            processed_blended = blended_df.copy()
            total_pl_blended = processed_blended['P/L'].sum()
            final_account_value = processed_blended['Account Value'].iloc[-1]
            total_return = (final_account_value / starting_capital) - 1
            
            # Calculate other metrics as before
            num_years = (processed_blended['Date'].max() - processed_blended['Date'].min()).days / 365.25
            # Calculate annualized return properly
            strategy_mean_return = (1 + total_return) ** (1/num_years) - 1 if num_years > 0 else total_return
            
            # Calculate daily returns and other metrics
            processed_blended['Daily Return'] = processed_blended['Account Value'].pct_change()
            processed_blended['Daily Return'] = processed_blended['Daily Return'].replace([np.inf, -np.inf], np.nan)
            
            if use_trading_filter:
                processed_blended['SMA'] = processed_blended['Account Value'].rolling(window=sma_window, min_periods=1).mean()
                processed_blended['Position'] = np.where(processed_blended['Account Value'] > processed_blended['SMA'], 1, 0)
                processed_blended['Strategy Return'] = processed_blended['Daily Return'] * processed_blended['Position'].shift(1).fillna(0)
            else:
                processed_blended['Strategy Return'] = processed_blended['Daily Return']
            
            processed_blended['Strategy Return'] = processed_blended['Strategy Return'].fillna(0)
            
            # Calculate drawdown
            processed_blended['Rolling Peak'] = processed_blended['Account Value'].expanding().max()
            processed_blended['Drawdown Amount'] = processed_blended['Account Value'] - processed_blended['Rolling Peak']
            processed_blended['Drawdown Pct'] = processed_blended['Drawdown Amount'] / processed_blended['Rolling Peak']
            
            # Get maximum drawdown info
            max_drawdown_idx = processed_blended['Drawdown Pct'].idxmin()
            max_drawdown = processed_blended.loc[max_drawdown_idx, 'Drawdown Amount']
            max_drawdown_pct = processed_blended.loc[max_drawdown_idx, 'Drawdown Pct']
            peak_value = processed_blended['Account Value'].max()  # Use the actual peak account value
            drawdown_date = processed_blended.loc[max_drawdown_idx, 'Date']
            
            # Calculate recovery info
            recovery_days = None
            if max_drawdown_idx < len(processed_blended) - 1:
                recovery_series = processed_blended.loc[max_drawdown_idx:, 'Account Value']
                drawdown_peak_value = processed_blended.loc[max_drawdown_idx, 'Rolling Peak']
                recovered_points = recovery_series[recovery_series >= drawdown_peak_value]
                if not recovered_points.empty:
                    recovery_idx = recovered_points.index[0]
                    recovery_days = (processed_blended.loc[recovery_idx, 'Date'] - processed_blended.loc[max_drawdown_idx, 'Date']).days

            # Calculate volatility and Sharpe ratio
            valid_returns = processed_blended['Strategy Return'].dropna()
            strategy_std = valid_returns.std() * np.sqrt(252) if len(valid_returns) > 1 else 0

    # Create correlation analysis if we have multiple portfolios
    heatmap_url = None
    monte_carlo_url = None
    
    if len(files) > 1 and not correlation_data.empty:
        try:
            logger.info("Creating correlation analysis for multiple portfolios")
            heatmap_path = create_correlation_heatmap(correlation_data, portfolio_names)
            if heatmap_path:
                heatmap_filename = os.path.basename(heatmap_path)
                heatmap_url = f"/uploads/plots/{heatmap_filename}"
                logger.info(f"Correlation heatmap created: {heatmap_url}")
        except Exception as e:
            logger.error(f"Error creating correlation analysis: {str(e)}")
            heatmap_url = None
    
    # Create Monte Carlo simulation for blended portfolio if we have one
    if blended_result is not None:
        try:
            logger.info("Creating Monte Carlo simulation for blended portfolio")
            mc_path = create_monte_carlo_simulation(blended_df, blended_result['metrics'])
            if mc_path:
                mc_filename = os.path.basename(mc_path)
                monte_carlo_url = f"/uploads/plots/{mc_filename}"
                logger.info(f"Monte Carlo simulation created: {monte_carlo_url}")
        except Exception as e:
            logger.error(f"Error creating Monte Carlo simulation: {str(e)}")
            monte_carlo_url = None

    # Return the results
    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "results": results,
            "blended_result": blended_result,
            "multiple_portfolios": len(files) > 1,
            "heatmap_url": heatmap_url,
            "monte_carlo_url": monte_carlo_url
        }
    )
