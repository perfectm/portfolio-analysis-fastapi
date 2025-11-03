"""
Plotting and visualization utilities for portfolio analysis
"""
import os
import time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
import logging
import warnings
from typing import List, Optional, Dict, Any
import gc
import psutil

from config import UPLOAD_FOLDER
from correlation_utils import calculate_correlation_matrix_from_dataframe

# Suppress common warnings
warnings.filterwarnings('ignore', message='use_inf_as_na option is deprecated')
warnings.filterwarnings('ignore', message='Unable to import Axes3D')
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib.projections')
warnings.filterwarnings('ignore', message='Format strings passed to MaskedConstant are ignored')
warnings.filterwarnings('ignore', category=FutureWarning, module='seaborn.matrix')

logger = logging.getLogger(__name__)


def log_memory_usage(context: str):
    process = psutil.Process()
    mem_mb = process.memory_info().rss / 1024 ** 2
    logger.info(f"[MEMORY] {context}: {mem_mb:.2f} MB RSS")


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
    log_memory_usage(f"[create_plots] BEFORE plotting {filename_prefix}")
    try:
        logger.info(f"[create_plots] Starting plot creation for {filename_prefix}")
        logger.info(f"[create_plots] DataFrame shape: {df.shape}")
        logger.info(f"[create_plots] DataFrame columns: {list(df.columns)}")
        
        # Defensive column renaming for compatibility
        if 'Cumulative_PL' in df.columns and 'Cumulative P/L' not in df.columns:
            df = df.rename(columns={'Cumulative_PL': 'Cumulative P/L'})
        
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

        # Use pre-calculated drawdown percentage if available
        if 'Drawdown Pct' in df.columns:
            drawdown_pct = df['Drawdown Pct'] * 100
            logger.info(f"[create_plots] Using pre-calculated Drawdown Pct column (min: {df['Drawdown Pct'].min():.4%})")
        else:
            # Fallback: calculate from account value
            rolling_peak = df['Account Value'].expanding().max()
            drawdown_pct = ((df['Account Value'] - rolling_peak) / rolling_peak) * 100
            logger.info(f"[create_plots] Calculated drawdown percentage (min: {(drawdown_pct/100).min():.4%})")

        ax2.plot(df['Date'], drawdown_pct)
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

        # Plot 4: Drawdown in Dollars (bottom right)
        logger.info(f"[create_plots] Creating dollar drawdown plot")
        logger.info(f"[create_plots] DataFrame shape: {df.shape}")
        logger.info(f"[create_plots] DataFrame date range: {df['Date'].min()} to {df['Date'].max()}")
        logger.info(f"[create_plots] Available columns: {df.columns.tolist()}")

        ax4 = plt.subplot(2, 2, 4)

        # Use pre-calculated drawdown amount if available, otherwise calculate it
        if 'Drawdown Amount' in df.columns:
            drawdown_amount = df['Drawdown Amount']
            logger.info(f"[create_plots] Using pre-calculated Drawdown Amount column")
            logger.info(f"[create_plots] Drawdown Amount range: ${drawdown_amount.min():,.2f} to ${drawdown_amount.max():,.2f}")
        else:
            # Fallback: calculate rolling peak and drawdown amount for plotting
            logger.info(f"[create_plots] 'Drawdown Amount' column not found, calculating from Account Value")
            rolling_peak = df['Account Value'].expanding().max()
            drawdown_amount = df['Account Value'] - rolling_peak
            logger.info(f"[create_plots] Calculated drawdown range: ${drawdown_amount.min():,.2f} to ${drawdown_amount.max():,.2f}")

        ax4.plot(df['Date'], drawdown_amount, color='red', linewidth=1.5)
        ax4.fill_between(df['Date'], drawdown_amount, 0, alpha=0.3, color='red')
        ax4.set_title('Drawdown Over Time')
        ax4.set_xlabel('Date')
        ax4.set_ylabel('Drawdown ($)')
        ax4.grid(True)
        ax4.tick_params(axis='x', rotation=45)
        # Format y-axis as currency
        ax4.yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter('${x:,.0f}'))

        # Set y-axis to show drawdowns properly with zero at top
        ax4.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        # Set y-axis limits to ensure zero is at top and negatives go down
        min_drawdown = drawdown_amount.min()
        logger.info(f"[create_plots] Setting y-axis limits: {min_drawdown * 1.1:.2f} to 0")
        ax4.set_ylim(min_drawdown * 1.1, 0)  # Extend bottom slightly, zero at top

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
            del df
            gc.collect()
            log_memory_usage(f"[create_plots] AFTER cleanup {filename_prefix}")
            return [plot_path]
        else:
            logger.error(f"[create_plots] Plot file was not created: {plot_path}")
            del df
            gc.collect()
            log_memory_usage(f"[create_plots] AFTER cleanup {filename_prefix}")
            return []
            
    except Exception as plot_error:
        logger.error(f"[create_plots] Error creating plots: {str(plot_error)}")
        # Close any open figures to prevent memory leaks
        plt.close('all')
        del df
        gc.collect()
        log_memory_usage(f"[create_plots] AFTER EXCEPTION cleanup {filename_prefix}")
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
    log_memory_usage("[create_correlation_heatmap] BEFORE plotting")
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
        
        # Calculate correlation matrix using zero-excluding method
        value_columns = list(correlation_data.columns)
        correlation_matrix = calculate_correlation_matrix_from_dataframe(correlation_data, value_columns)
        logger.info(f"[Correlation Heatmap] Correlation matrix shape: {correlation_matrix.shape}")
        logger.info(f"[Correlation Heatmap] Correlation matrix columns: {list(correlation_matrix.columns)}")
        logger.info(f"[Correlation Heatmap] Using zero-excluding correlation calculation")

        # Dynamic sizing based on number of portfolios
        n_portfolios = len(correlation_matrix)

        # Scale figure size with number of portfolios (min 10, max 30)
        base_size = max(10, min(30, 0.5 * n_portfolios))
        fig_width = base_size
        fig_height = base_size * 0.9  # Slightly rectangular for better label spacing

        # Dynamic font sizes based on portfolio count
        if n_portfolios <= 10:
            title_size = 18
            label_size = 14
            tick_size = 12
            annot_size = 10
            show_annotations = True
        elif n_portfolios <= 20:
            title_size = 16
            label_size = 12
            tick_size = 10
            annot_size = 8
            show_annotations = True
        else:
            title_size = 14
            label_size = 10
            tick_size = 8
            annot_size = 6
            show_annotations = False  # Hide numbers for large matrices

        logger.info(f"[Correlation Heatmap] Using figure size: {fig_width}x{fig_height}, show_annotations={show_annotations}")

        # Create the heatmap with dynamic figure size
        plt.figure(figsize=(fig_width, fig_height), dpi=100)

        # Create a mask for the upper triangle to show only lower triangle + diagonal
        mask = np.triu(np.ones_like(correlation_matrix, dtype=bool), k=1)

        # Clean correlation matrix for seaborn - replace infinite values with NaN
        correlation_matrix_clean = correlation_matrix.replace([np.inf, -np.inf], np.nan)

        # Fill NaN values in correlation matrix with 0 for display
        correlation_matrix_display = correlation_matrix_clean.fillna(0)

        # Create custom colormap: Green at -1, Blue at 0, Red at 1
        colors = ['green', 'blue', 'red']  # -1 = green, 0 = blue, 1 = red
        n_bins = 256  # Smooth gradient
        custom_cmap = mcolors.LinearSegmentedColormap.from_list('correlation', colors, N=n_bins)

        # Prepare annotations if needed
        if show_annotations:
            # Create custom annotation array with better number formatting
            def format_correlation(x):
                if abs(x) < 0.001:  # Very small correlations show as 0
                    return "0"
                return f"{x:.2f}"  # Show 2 decimal places for all other values

            annotations = np.vectorize(format_correlation)(correlation_matrix_display)
            annot_kws = {'size': annot_size, 'weight': 'normal'}
        else:
            annotations = False
            annot_kws = {}

        # Generate the heatmap with custom colormap
        sns.heatmap(correlation_matrix_display,
                   annot=annotations,
                   fmt='' if show_annotations else None,
                   cmap=custom_cmap,
                   vmin=-1,
                   vmax=1,
                   center=0,
                   square=True,
                   linewidths=0.5 if n_portfolios <= 15 else 0,  # Remove gridlines for large matrices
                   cbar_kws={"shrink": .8, "label": "Correlation"},
                   mask=mask,
                   annot_kws=annot_kws
                   )

        plt.title('Portfolio Correlation Matrix\n(Daily Returns)', fontsize=title_size, pad=20)
        plt.xlabel('Portfolios', fontsize=label_size, labelpad=10)
        plt.ylabel('Portfolios', fontsize=label_size, labelpad=10)
        plt.xticks(rotation=90, ha='center', fontsize=tick_size)  # Vertical rotation for better readability
        plt.yticks(rotation=0, fontsize=tick_size)
        
        # Adjust layout to ensure all labels are visible
        plt.tight_layout()
        
        # Create unique filename based on portfolio names and timestamp
        portfolio_hash = str(hash(tuple(sorted(correlation_data.columns))))[-8:]  # Last 8 chars of hash
        timestamp = str(int(time.time()))[-6:]  # Last 6 chars of timestamp
        heatmap_filename = f'correlation_heatmap_{len(correlation_data.columns)}portfolios_{portfolio_hash}_{timestamp}.png'
        
        # Save the heatmap with appropriate DPI (higher for larger matrices)
        save_dpi = 200 if n_portfolios > 15 else 150
        heatmap_path = os.path.join(plots_dir, heatmap_filename)
        plt.savefig(heatmap_path, dpi=save_dpi, bbox_inches='tight')
        plt.close()  # Explicitly close figure to free memory
        logger.info(f"[Correlation Heatmap] Saved with DPI={save_dpi}")
        
        logger.info(f"[Correlation Heatmap] Successfully created heatmap: {heatmap_path}")
        # Clean up memory
        del correlation_matrix, correlation_matrix_clean, correlation_matrix_display, mask
        if show_annotations and annotations is not False:
            del annotations
        gc.collect()
        log_memory_usage("[create_correlation_heatmap] AFTER plotting")
        return heatmap_path
        
    except Exception as e:
        logger.error(f"[Correlation Heatmap] Error creating correlation heatmap: {str(e)}", exc_info=True)
        # Clean up memory on exception
        gc.collect()
        log_memory_usage("[create_correlation_heatmap] AFTER EXCEPTION cleanup")
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
    log_memory_usage("[create_monte_carlo_simulation] BEFORE plotting")
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
        
        # Create unique filename based on portfolio metrics and timestamp
        portfolio_id = str(hash(str(metrics.get('sharpe_ratio', 0)) + str(metrics.get('total_return', 0))))[-8:]
        timestamp = str(int(time.time()))[-6:]
        mc_filename = f'monte_carlo_{num_simulations}sims_{portfolio_id}_{timestamp}.png'
        
        # Save the Monte Carlo plot with reduced DPI
        mc_path = os.path.join(plots_dir, mc_filename)
        plt.savefig(mc_path, dpi=150, bbox_inches='tight')  # Reduced from 300 DPI
        plt.close()  # Explicitly close figure to free memory
        
        logger.info(f"Monte Carlo simulation plot saved: {mc_path}")
        del blended_df, daily_returns, random_returns, portfolio_paths, percentile_paths, percentiles, colors, labels, time_axis, final_values, stats_text
        gc.collect()
        log_memory_usage("[create_monte_carlo_simulation] AFTER plotting")
        return mc_path
        
    except Exception as e:
        logger.error(f"Error creating Monte Carlo simulation: {str(e)}")
        del blended_df
        gc.collect()
        log_memory_usage("[create_monte_carlo_simulation] AFTER EXCEPTION cleanup")
        return None
