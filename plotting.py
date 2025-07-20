"""
Plotting and visualization utilities for portfolio analysis
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import logging
import warnings
from typing import List, Optional, Dict, Any

from config import UPLOAD_FOLDER

# Suppress common warnings
warnings.filterwarnings('ignore', message='use_inf_as_na option is deprecated')
warnings.filterwarnings('ignore', message='Unable to import Axes3D')
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib.projections')
warnings.filterwarnings('ignore', message='Format strings passed to MaskedConstant are ignored')
warnings.filterwarnings('ignore', category=FutureWarning, module='seaborn.matrix')

logger = logging.getLogger(__name__)


def create_plots(df: pd.DataFrame, metrics: Dict[str, Any], filename_prefix: str, sma_window: int = 20) -> List[str]:
    """
    Create comprehensive portfolio analysis plots
    
    Args:
        df: Portfolio DataFrame with calculated metrics
        metrics: Dictionary of portfolio metrics
        filename_prefix: Prefix for saved plot files
        sma_window: SMA window for plotting
        
    Returns:
        List of plot file paths
    """
    try:
        logger.info(f"[create_plots] Starting plot creation for {filename_prefix}")
        logger.info(f"[create_plots] DataFrame shape: {df.shape}")
        logger.info(f"[create_plots] DataFrame columns: {list(df.columns)}")
        
        # Create plots directory if it doesn't exist
        plots_dir = os.path.join(UPLOAD_FOLDER, 'plots')
        logger.info(f"[create_plots] Creating plots directory: {plots_dir}")
        os.makedirs(plots_dir, exist_ok=True)
        
        # Verify directory was created
        if not os.path.exists(plots_dir):
            logger.error(f"[create_plots] Failed to create plots directory: {plots_dir}")
            return []
        logger.info(f"[create_plots] Plots directory verified: {plots_dir}")
        
    except Exception as setup_error:
        logger.error(f"[create_plots] Setup error: {str(setup_error)}")
        return []
    
    try:
        logger.info(f"[create_plots] Creating matplotlib figure")
        # Create a 2x2 subplot grid with reduced figure size to save memory
        # Use smaller size for better memory efficiency
        fig = plt.figure(figsize=(12, 9), dpi=100)  # Further reduced from 16x12
        
        # Plot 1: Cumulative P/L (top left)
        logger.info(f"[create_plots] Creating cumulative P/L plot")
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
        logger.info(f"[create_plots] Creating drawdown plot")
        ax2 = plt.subplot(2, 2, 2)
        ax2.plot(df['Date'], df['Drawdown Pct'] * 100)
        ax2.set_title('Drawdown Over Time')
        ax2.set_xlabel('Date')
        ax2.set_ylabel('Drawdown (%)')
        ax2.grid(True)
        ax2.tick_params(axis='x', rotation=45)

        # Plot 3: Daily Returns Distribution (bottom left)
        logger.info(f"[create_plots] Creating returns distribution plot")
        ax3 = plt.subplot(2, 2, 3)
        dollar_returns = df['Daily Return'].dropna() * df['Account Value'].shift(1)
        # Clean data for seaborn - remove infinite values and NaNs
        dollar_returns_clean = dollar_returns.replace([np.inf, -np.inf], np.nan).dropna()
        if len(dollar_returns_clean) > 0:
            sns.histplot(data=dollar_returns_clean, bins=20, kde=True, ax=ax3)
        else:
            # Fallback if no valid data
            ax3.text(0.5, 0.5, 'No valid return data', ha='center', va='center', transform=ax3.transAxes)
        ax3.set_title('Distribution of Daily Returns')
        ax3.set_xlabel('Daily Return ($)')
        ax3.set_ylabel('Frequency')
        # Format x-axis as currency
        current_values = ax3.get_xticks()
        ax3.set_xticks(current_values)  # Set the tick positions first
        ax3.set_xticklabels(['${:,.0f}'.format(x) for x in current_values])
        ax3.grid(True)

        # Plot 4: Account Value vs SMA (bottom right)
        logger.info(f"[create_plots] Creating SMA plot")
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
        logger.info(f"[create_plots] Finalizing plot layout")
        plt.tight_layout()
        
        # Save the combined plot with reduced DPI to save memory and disk space
        plot_path = os.path.join(plots_dir, f'{filename_prefix}_combined_analysis.png')
        logger.info(f"[create_plots] Saving plot to: {plot_path}")
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')  # Reduced from 300 DPI
        plt.close(fig)  # Explicitly close the figure to free memory
        
        # Verify file was created
        if os.path.exists(plot_path):
            file_size = os.path.getsize(plot_path)
            logger.info(f"[create_plots] Plot saved successfully: {plot_path} (size: {file_size} bytes)")
            return [plot_path]
        else:
            logger.error(f"[create_plots] Plot file was not created: {plot_path}")
            return []
            
    except Exception as plot_error:
        logger.error(f"[create_plots] Error creating plots: {str(plot_error)}")
        # Close any open figures to prevent memory leaks
        plt.close('all')
        return []


def create_correlation_heatmap(correlation_data: pd.DataFrame, portfolio_names: List[str]) -> Optional[str]:
    """
    Create a correlation heatmap for multiple portfolios
    
    Args:
        correlation_data: DataFrame with portfolio returns for correlation analysis
        portfolio_names: List of portfolio names
        
    Returns:
        Path to saved heatmap file or None if failed
    """
    try:
        logger.info(f"[Correlation Heatmap] Input data shape: {correlation_data.shape}")
        logger.info(f"[Correlation Heatmap] Input columns: {list(correlation_data.columns)}")
        logger.info(f"[Correlation Heatmap] Portfolio names provided: {portfolio_names}")
        
        # Create plots directory if it doesn't exist
        plots_dir = os.path.join(UPLOAD_FOLDER, 'plots')
        os.makedirs(plots_dir, exist_ok=True)
        
        # Check if we have enough data for correlation
        if correlation_data.shape[1] < 2:
            logger.warning(f"[Correlation Heatmap] Insufficient columns for correlation: {correlation_data.shape[1]}")
            return None
            
        if correlation_data.shape[0] < 2:
            logger.warning(f"[Correlation Heatmap] Insufficient rows for correlation: {correlation_data.shape[0]}")
            return None
        
        # Fill NaN values with 0 for correlation calculation
        correlation_data_filled = correlation_data.fillna(0)
        logger.info(f"[Correlation Heatmap] Data after filling NaN: shape {correlation_data_filled.shape}")
        
        # Calculate correlation matrix
        correlation_matrix = correlation_data_filled.corr()
        logger.info(f"[Correlation Heatmap] Correlation matrix shape: {correlation_matrix.shape}")
        logger.info(f"[Correlation Heatmap] Correlation matrix columns: {list(correlation_matrix.columns)}")
        
        # Create the heatmap with reduced figure size
        plt.figure(figsize=(8, 6), dpi=100)  # Reduced from 10x8
        
        # Create a mask for the upper triangle to show only lower triangle + diagonal
        mask = np.triu(np.ones_like(correlation_matrix, dtype=bool), k=1)
        
        # Clean correlation matrix for seaborn - replace infinite values with NaN
        correlation_matrix_clean = correlation_matrix.replace([np.inf, -np.inf], np.nan)
        
        # Fill NaN values in correlation matrix with 0 for display
        correlation_matrix_display = correlation_matrix_clean.fillna(0)
        
        # Create custom annotation array to handle NaN values properly
        annotations = correlation_matrix_display.round(3).astype(str)
        
        # Generate the heatmap without automatic annotations first
        sns.heatmap(correlation_matrix_display, 
                   annot=annotations,
                   fmt='',  # Use empty format since we're providing custom annotations
                   cmap='RdYlBu_r', 
                   vmin=-1, 
                   vmax=1,
                   center=0,
                   square=True, 
                   cbar_kws={"shrink": .8},
                   mask=mask)
        
        plt.title('Portfolio Correlation Matrix\n(Daily Returns)', fontsize=16, pad=20)
        plt.xlabel('Portfolios', fontsize=12)
        plt.ylabel('Portfolios', fontsize=12)
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        
        # Adjust layout
        plt.tight_layout()
        
        # Save the heatmap with reduced DPI
        heatmap_path = os.path.join(plots_dir, 'portfolio_correlation_heatmap.png')
        plt.savefig(heatmap_path, dpi=150, bbox_inches='tight')  # Reduced from 300 DPI
        plt.close()  # Explicitly close figure to free memory
        
        logger.info(f"[Correlation Heatmap] Successfully created heatmap: {heatmap_path}")
        return heatmap_path
        
    except Exception as e:
        logger.error(f"[Correlation Heatmap] Error creating correlation heatmap: {str(e)}", exc_info=True)
        return None


def create_monte_carlo_simulation(
    blended_df: pd.DataFrame, 
    metrics: Dict[str, Any], 
    num_simulations: int = 250,  # Reduced from 500 to 250 for better memory management
    forecast_days: int = 252
) -> Optional[str]:
    """
    Create a Monte Carlo simulation for the blended portfolio
    
    Args:
        blended_df: DataFrame with blended portfolio data
        metrics: Portfolio metrics dictionary
        num_simulations: Number of simulation runs
        forecast_days: Number of days to forecast
        
    Returns:
        Path to saved Monte Carlo plot or None if failed
    """
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
        current_value = metrics.get('final_account_value', metrics.get('Final Account Value', 100000))
        
        # Create random return scenarios
        np.random.seed(42)  # For reproducible results
        random_returns = np.random.normal(mean_return, std_return, (num_simulations, forecast_days))
        
        # Calculate portfolio value paths
        portfolio_paths = np.zeros((num_simulations, forecast_days + 1))
        portfolio_paths[:, 0] = current_value
        
        for i in range(forecast_days):
            portfolio_paths[:, i + 1] = portfolio_paths[:, i] * (1 + random_returns[:, i])
        
        # Create the Monte Carlo plot with reduced figure size
        plt.figure(figsize=(10, 6), dpi=100)  # Reduced from 12x8
        
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
        
        # Save the Monte Carlo plot with reduced DPI
        mc_path = os.path.join(plots_dir, 'monte_carlo_simulation.png')
        plt.savefig(mc_path, dpi=150, bbox_inches='tight')  # Reduced from 300 DPI
        plt.close()  # Explicitly close figure to free memory
        
        return mc_path
        
    except Exception as e:
        logger.error(f"Error creating Monte Carlo simulation: {str(e)}")
        return None
