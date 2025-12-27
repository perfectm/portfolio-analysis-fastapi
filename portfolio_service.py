"""
Database service layer for portfolio operations
"""
import hashlib
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
import pandas as pd
import logging
import os
import psutil

from models import Portfolio, PortfolioData, AnalysisResult, AnalysisPlot, BlendedPortfolio, BlendedPortfolioMapping, PortfolioMarginData
from config import (
    DATE_COLUMNS, PL_COLUMNS, PREMIUM_COLUMNS, CONTRACTS_COLUMNS,
    TRADE_STEWARD_IDENTIFIER_COLUMNS, TRADE_STEWARD_DATE_COLUMN,
    TRADE_STEWARD_PL_COLUMN, TRADE_STEWARD_ENTRY_DATE_COLUMN
)
from margin_service import MarginService, MARGIN_COLUMNS
from portfolio_processor import process_portfolio_data, _detect_vendor

logger = logging.getLogger(__name__)

class PortfolioService:
    """
    Service class for portfolio database operations
    """
    
    @staticmethod
    def calculate_file_hash(content: bytes) -> str:
        """Calculate SHA-256 hash of file content"""
        return hashlib.sha256(content).hexdigest()
    
    @staticmethod
    def get_parquet_path(portfolio_id: int) -> str:
        return os.path.join('uploads', 'portfolios', f'{portfolio_id}.parquet')

    @staticmethod
    def save_portfolio_parquet(db: Session, portfolio_id: int, df: pd.DataFrame):
        # Always save the fully processed DataFrame
        processed_df, _ = process_portfolio_data(
            df,
            rf_rate=0.05,  # Use default or pass as needed
            sma_window=20,
            use_trading_filter=True,
            starting_capital=1000000.0
        )
        parquet_path = PortfolioService.get_parquet_path(portfolio_id)
        os.makedirs(os.path.dirname(parquet_path), exist_ok=True)
        
        # Try parquet first, fallback to pickle if parquet fails
        try:
            processed_df.to_parquet(parquet_path, index=False)
            logger.info(f"Saved portfolio {portfolio_id} as parquet file")
        except Exception as parquet_error:
            logger.warning(f"Parquet save failed for portfolio {portfolio_id}: {parquet_error}")
            # Use pickle as fallback
            pickle_path = parquet_path.replace('.parquet', '.pkl')
            processed_df.to_pickle(pickle_path)
            parquet_path = pickle_path
            logger.info(f"Saved portfolio {portfolio_id} as pickle file instead")
        
        # Update the portfolio record
        portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if portfolio:
            portfolio.parquet_path = parquet_path
            db.commit()

    @staticmethod
    def load_portfolio_parquet(db: Session, portfolio_id: int, columns: list = None) -> pd.DataFrame:
        portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if portfolio and portfolio.parquet_path and os.path.exists(portfolio.parquet_path):
            try:
                # Try to load as parquet first
                if portfolio.parquet_path.endswith('.parquet'):
                    # Read parquet - if columns specified, try to read them, but handle missing columns gracefully
                    if columns:
                        # First, read without column filter to see what's available
                        try:
                            df = pd.read_parquet(portfolio.parquet_path, columns=columns)
                        except (KeyError, ValueError):
                            # If some columns don't exist, load all and filter
                            df = pd.read_parquet(portfolio.parquet_path)
                            df = df[[col for col in columns if col in df.columns]]
                    else:
                        df = pd.read_parquet(portfolio.parquet_path)
                elif portfolio.parquet_path.endswith('.pkl'):
                    df = pd.read_pickle(portfolio.parquet_path)
                    if columns:
                        # Only select columns that exist
                        df = df[[col for col in columns if col in df.columns]]
                else:
                    # Fallback: try both formats
                    try:
                        if columns:
                            try:
                                df = pd.read_parquet(portfolio.parquet_path, columns=columns)
                            except (KeyError, ValueError):
                                df = pd.read_parquet(portfolio.parquet_path)
                                df = df[[col for col in columns if col in df.columns]]
                        else:
                            df = pd.read_parquet(portfolio.parquet_path)
                    except:
                        df = pd.read_pickle(portfolio.parquet_path)
                        if columns:
                            df = df[[col for col in columns if col in df.columns]]
                return df
            except Exception as e:
                logger.error(f"Failed to load portfolio data for {portfolio_id}: {e}")
                return None
        return None

    @staticmethod
    def create_portfolio(
        db: Session,
        name: str,
        filename: str,
        file_content: bytes,
        df: pd.DataFrame
    ) -> Portfolio:
        """
        Create a new portfolio record
        """
        try:
            # Calculate file hash for tracking (but always create new portfolio)
            file_hash = PortfolioService.calculate_file_hash(file_content)
            logger.info(f"Creating new portfolio with hash {file_hash} (duplicate detection disabled)")
            
            # Find the date column using the same logic as portfolio_processor
            date_column = None
            for col in DATE_COLUMNS:
                if col in df.columns:
                    date_column = col
                    break
            
            # Extract date range from dataframe
            date_range_start = None
            date_range_end = None
            if date_column and not df.empty:
                try:
                    # Convert to datetime and get min/max
                    date_series = pd.to_datetime(df[date_column])
                    date_range_start = date_series.min()
                    date_range_end = date_series.max()
                except Exception as date_error:
                    logger.warning(f"Could not parse dates from column '{date_column}': {date_error}")
                    # Continue without date range if parsing fails
            
            # Create portfolio record
            portfolio = Portfolio(
                name=name,
                filename=filename,
                file_size=len(file_content),
                row_count=len(df),
                date_range_start=date_range_start,
                date_range_end=date_range_end,
                file_hash=file_hash
            )
            
            db.add(portfolio)
            db.commit()
            db.refresh(portfolio)
            
            # Save Parquet file
            PortfolioService.save_portfolio_parquet(db, portfolio.id, df)
            logger.info(f"Created portfolio: {portfolio.name} (ID: {portfolio.id})")
            return portfolio
            
        except Exception as e:
            logger.error(f"Error creating portfolio: {e}")
            db.rollback()
            raise
    
    @staticmethod
    def store_portfolio_data(
        db: Session,
        portfolio_id: int,
        df: pd.DataFrame
    ) -> List[PortfolioData]:
        """
        Store raw portfolio data from CSV
        """
        try:
            # Check if data already exists for this portfolio
            existing_count = db.query(PortfolioData).filter(
                PortfolioData.portfolio_id == portfolio_id
            ).count()
            
            if existing_count > 0:
                logger.info(f"Data already exists for portfolio {portfolio_id}")
                return db.query(PortfolioData).filter(
                    PortfolioData.portfolio_id == portfolio_id
                ).order_by(PortfolioData.date).all()
            
            # Detect vendor format
            vendor = _detect_vendor(df)
            logger.info(f"Detected vendor format: {vendor}")

            # Set column names based on vendor
            if vendor == 'trade_steward':
                # For Trade Steward, we'll store aggregated data by Exit Date
                # Filter to only closed trades (rows with Exit Date)
                df_closed = df[df[TRADE_STEWARD_DATE_COLUMN].notna() & (df[TRADE_STEWARD_DATE_COLUMN] != '')]
                logger.info(f"Trade Steward format: filtered to {len(df_closed)} closed trades from {len(df)} total rows")

                if len(df_closed) == 0:
                    raise ValueError("No closed trades found in Trade Steward file")

                # Use Trade Steward columns
                date_column = TRADE_STEWARD_DATE_COLUMN
                pl_column = TRADE_STEWARD_PL_COLUMN
                df = df_closed  # Use only closed trades
            else:
                # Standard Option Omega format
                date_column = None
                for col in DATE_COLUMNS:
                    if col in df.columns:
                        date_column = col
                        break

                if date_column is None:
                    logger.error(f"No date column found. Looking for any of: {DATE_COLUMNS}")
                    logger.error(f"Available columns are: {df.columns.tolist()}")
                    raise ValueError(f"No date column found. Expected one of: {DATE_COLUMNS}")

                # Find the P/L column
                pl_column = None
                for col in PL_COLUMNS:
                    if col in df.columns:
                        pl_column = col
                        break

                if pl_column is None:
                    logger.error(f"No P/L column found. Looking for any of: {PL_COLUMNS}")
                    logger.error(f"Available columns are: {df.columns.tolist()}")
                    raise ValueError(f"No P/L column found. Expected one of: {PL_COLUMNS}")
            
            # Find the Premium column (optional)
            premium_column = None
            for col in PREMIUM_COLUMNS:
                if col in df.columns:
                    premium_column = col
                    break
            
            # Find the Margin column (optional)
            margin_column = None
            logger.info(f"[MARGIN DEBUG] Available columns in CSV: {list(df.columns)}")
            
            for col in MARGIN_COLUMNS:
                if col in df.columns:
                    margin_column = col
                    logger.info(f"[MARGIN DEBUG] Found margin column: {col}")
                    break
            
            # Find the Contracts column (optional)
            contracts_column = None
            for col in CONTRACTS_COLUMNS:
                if col in df.columns:
                    contracts_column = col
                    logger.info(f"Found contracts column: {col}")
                    break
            
            if margin_column is None:
                logger.warning(f"[MARGIN DEBUG] No margin column found. Searched for: {MARGIN_COLUMNS[:10]}...")
            
            logger.info(f"Using '{date_column}' as date column and '{pl_column}' as P/L column")
            if premium_column:
                logger.info(f"Using '{premium_column}' as premium column")
            else:
                logger.info("No premium column found in CSV - PCR calculation will be unavailable")
                
            if margin_column:
                logger.info(f"Using '{margin_column}' as margin column")
            else:
                logger.info("No margin column found in CSV - margin calculations will be unavailable")
            
            # Prepare data for bulk insert
            data_records = []
            margin_records = []  # For storing margin data separately
            cumulative_pl = 0
            starting_capital = 1000000  # Default starting capital
            
            for idx, row in df.iterrows():
                # Clean P/L data - remove any currency symbols and convert to float
                try:
                    pl_value = str(row[pl_column]).replace('$', '').replace(',', '').replace('(', '-').replace(')', '')
                    pl_value = float(pl_value)
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse P/L value: {row[pl_column]}, skipping row {idx}")
                    continue
                
                # Parse date
                try:
                    date_value = pd.to_datetime(row[date_column])
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse date value: {row[date_column]}, skipping row {idx}")
                    continue
                
                # Parse premium value (optional)
                premium_value = None
                if premium_column and pd.notna(row[premium_column]):
                    try:
                        premium_str = str(row[premium_column]).replace('$', '').replace(',', '').replace('(', '-').replace(')', '')
                        premium_value = float(premium_str)
                    except (ValueError, TypeError):
                        logger.warning(f"Could not parse premium value: {row[premium_column]}, using None for row {idx}")
                
                # Parse margin value (optional)
                margin_value = None
                if margin_column and pd.notna(row[margin_column]):
                    try:
                        margin_str = str(row[margin_column]).replace('$', '').replace(',', '').replace('(', '-').replace(')', '')
                        margin_value = float(abs(float(margin_str)))  # Ensure positive value for margin requirements
                    except (ValueError, TypeError):
                        logger.warning(f"Could not parse margin value: {row[margin_column]}, using None for row {idx}")
                
                # Parse contracts value (optional)
                contracts_value = None
                if contracts_column and pd.notna(row[contracts_column]):
                    try:
                        contracts_value = int(float(row[contracts_column]))  # Convert to int for number of contracts
                    except (ValueError, TypeError):
                        logger.warning(f"Could not parse contracts value: {row[contracts_column]}, using None for row {idx}")
                
                cumulative_pl += pl_value
                account_value = starting_capital + cumulative_pl
                
                # Calculate daily return
                daily_return = None
                if idx > 0:
                    prev_value = starting_capital + (cumulative_pl - pl_value)
                    daily_return = (pl_value / prev_value) * 100 if prev_value != 0 else 0
                
                data_record = PortfolioData(
                    portfolio_id=portfolio_id,
                    date=date_value,
                    pl=pl_value,
                    premium=premium_value,
                    contracts=contracts_value,
                    cumulative_pl=cumulative_pl,
                    account_value=account_value,
                    daily_return=daily_return,
                    row_number=idx + 1
                )
                data_records.append(data_record)
                
                # Create margin record if margin data exists
                if margin_value is not None:
                    margin_record = PortfolioMarginData(
                        portfolio_id=portfolio_id,
                        date=date_value,
                        margin_requirement=margin_value,
                        margin_type='initial',  # Default type
                        row_number=idx + 1
                    )
                    margin_records.append(margin_record)
            
            # Bulk insert portfolio data
            db.bulk_save_objects(data_records)
            
            # Bulk insert margin data if available
            if margin_records:
                db.bulk_save_objects(margin_records)
                logger.info(f"Stored {len(margin_records)} margin records for portfolio {portfolio_id}")
                
                # Calculate and store daily margin aggregates
                try:
                    MarginService.calculate_daily_aggregates(db, starting_capital)
                    logger.info("Updated daily margin aggregates")
                except Exception as e:
                    logger.warning(f"Error calculating margin aggregates: {e}")
            
            db.commit()
            
            # Save Parquet file after storing data
            PortfolioService.save_portfolio_parquet(db, portfolio_id, df)
            logger.info(f"Stored {len(data_records)} data records for portfolio {portfolio_id}")
            return data_records
            
        except Exception as e:
            logger.error(f"Error storing portfolio data: {e}")
            db.rollback()
            raise
    
    @staticmethod
    def get_portfolio_data(
        db: Session,
        portfolio_id: int,
        limit: Optional[int] = None
    ) -> List[PortfolioData]:
        """
        Retrieve portfolio data from database
        """
        query = db.query(PortfolioData).filter(
            PortfolioData.portfolio_id == portfolio_id
        ).order_by(PortfolioData.date)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    @staticmethod
    def get_portfolio_dataframe(db: Session, portfolio_id: int, columns: list = None) -> pd.DataFrame:
        """Get portfolio data as DataFrame with memory-efficient processing"""
        import psutil
        process = psutil.Process()
        logger.info(f"[MEMORY] Before loading portfolio - RSS: {process.memory_info().rss / 1024 / 1024:.2f} MB")
        
        # Try to load from Parquet first with specific columns
        if columns:
            required_cols = list({'Date'} | set(columns))  # Ensure we have Date column, convert to list
        else:
            required_cols = None

        df = PortfolioService.load_portfolio_parquet(db, portfolio_id, columns=required_cols)
        
        if df is not None:
            logger.info(f"[MEMORY] After parquet load - RSS: {process.memory_info().rss / 1024 / 1024:.2f} MB")
            logger.info(f"[MEMORY] DataFrame size: {df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")
            
            # Optimize memory usage
            for col in df.select_dtypes(include=['float64']).columns:
                df[col] = pd.to_numeric(df[col], downcast='float')
            for col in df.select_dtypes(include=['int64']).columns:
                df[col] = pd.to_numeric(df[col], downcast='integer')
                
            # Defensive renaming
            if 'Cumulative_PL' in df.columns:
                df = df.rename(columns={'Cumulative_PL': 'Cumulative P/L'})
                
            # Check if processing is needed
            required_metrics = {'Cumulative P/L', 'Account_Value', 'Drawdown Pct'}
            if not required_metrics.issubset(df.columns):
                logger.info("Processing DataFrame for required metrics")
                df, _ = process_portfolio_data(
                    df,
                    rf_rate=0.05,
                    sma_window=20,
                    use_trading_filter=True,
                    starting_capital=1000000.0
                )
                
            if columns:
                df = df[[col for col in columns if col in df.columns]]
                
            logger.info(f"[MEMORY] Final DataFrame - RSS: {process.memory_info().rss / 1024 / 1024:.2f} MB")
            return df
            
        # Fallback to DB with chunked processing
        logger.info("Falling back to database with chunked processing")
        chunk_size = 10000
        chunks = []
        
        # Get total count
        total_count = db.query(PortfolioData).filter(
            PortfolioData.portfolio_id == portfolio_id
        ).count()
        
        for offset in range(0, total_count, chunk_size):
            chunk_data = db.query(PortfolioData).filter(
                PortfolioData.portfolio_id == portfolio_id
            ).order_by(PortfolioData.date).offset(offset).limit(chunk_size).all()
            
            chunk_df = pd.DataFrame([{
                'Date': record.date,
                'P/L': record.pl,
                'Premium': record.premium,
                'Cumulative P/L': record.cumulative_pl,
                'Account_Value': record.account_value,
                'Daily_Return': record.daily_return
            } for record in chunk_data])
            
            if columns:
                chunk_df = chunk_df[[col for col in columns if col in chunk_df.columns]]
                
            chunks.append(chunk_df)
            logger.info(f"[MEMORY] Processed chunk {offset//chunk_size + 1} - RSS: {process.memory_info().rss / 1024 / 1024:.2f} MB")
        
        if not chunks:
            return pd.DataFrame()
            
        df = pd.concat(chunks, ignore_index=True)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            
        # Process if needed
        required_cols = {'Cumulative P/L', 'Account_Value', 'Drawdown Pct'}
        if not required_cols.issubset(df.columns):
            df, _ = process_portfolio_data(
                df,
                rf_rate=0.05,
                sma_window=20,
                use_trading_filter=True,
                starting_capital=1000000.0
            )
            
        logger.info(f"[MEMORY] Final DataFrame from DB - RSS: {process.memory_info().rss / 1024 / 1024:.2f} MB")
        return df
    
    @staticmethod
    def store_analysis_result(
        db: Session,
        portfolio_id: int,
        analysis_type: str,
        metrics: Dict[str, Any],
        analysis_params: Dict[str, Any]
    ) -> AnalysisResult:
        """
        Store analysis results in database
        """
        try:
            logger.debug(f"[store_analysis_result] Attempting to store analysis result for portfolio_id={portfolio_id}, analysis_type={analysis_type}")
            logger.debug(f"[store_analysis_result] Metrics to save: {metrics}")
            logger.debug(f"[store_analysis_result] Analysis params: {analysis_params}")
            analysis_result = AnalysisResult(
                portfolio_id=portfolio_id,
                analysis_type=analysis_type,
                rf_rate=analysis_params.get('rf_rate'),
                daily_rf_rate=analysis_params.get('daily_rf_rate'),
                sma_window=analysis_params.get('sma_window'),
                use_trading_filter=analysis_params.get('use_trading_filter'),
                starting_capital=analysis_params.get('starting_capital'),
                metrics_json=json.dumps(metrics),
                sharpe_ratio=metrics.get('sharpe_ratio'),
                sortino_ratio=metrics.get('sortino_ratio'),
                ulcer_index=metrics.get('ulcer_index'),
                upi=metrics.get('upi'),
                kelly_criterion=metrics.get('kelly_criterion'),
                mar_ratio=metrics.get('mar_ratio'),
                cvar=metrics.get('cvar'),
                cagr=metrics.get('cagr'),
                annual_volatility=metrics.get('annual_volatility'),
                total_return=metrics.get('total_return'),
                total_pl=metrics.get('total_pl'),
                final_account_value=metrics.get('final_account_value'),
                max_drawdown=metrics.get('max_drawdown'),
                max_drawdown_percent=metrics.get('max_drawdown_percent'),
                max_drawdown_date=metrics.get('max_drawdown_date'),
                beta=metrics.get('beta'),
                alpha=metrics.get('alpha'),
                r_squared=metrics.get('r_squared'),
                beta_observation_count=metrics.get('beta_observation_count')
            )
            
            db.add(analysis_result)
            db.commit()
            db.refresh(analysis_result)
            
            logger.info(f"Stored analysis result for portfolio {portfolio_id}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"[store_analysis_result] ERROR: Exception occurred while storing analysis result for portfolio_id={portfolio_id}, analysis_type={analysis_type}")
            logger.error(f"[store_analysis_result] ERROR: Metrics: {metrics}")
            logger.error(f"[store_analysis_result] ERROR: Analysis params: {analysis_params}")
            logger.error(f"[store_analysis_result] ERROR: Exception: {e}", exc_info=True)
            db.rollback()
            raise
    
    @staticmethod
    def store_analysis_plot(
        db: Session,
        analysis_result_id: int,
        plot_type: str,
        file_path: str,
        file_url: str,
        file_size: int = 0
    ) -> AnalysisPlot:
        """
        Store analysis plot information
        """
        try:
            plot = AnalysisPlot(
                analysis_result_id=analysis_result_id,
                plot_type=plot_type,
                file_path=file_path,
                file_url=file_url,
                file_size=file_size
            )
            
            db.add(plot)
            db.commit()
            db.refresh(plot)
            
            return plot
            
        except Exception as e:
            logger.error(f"Error storing analysis plot: {e}")
            db.rollback()
            raise
    
    @staticmethod
    def get_portfolios(db: Session, limit: int = 100) -> List[Portfolio]:
        """
        Get list of portfolios
        """
        return db.query(Portfolio).order_by(desc(Portfolio.upload_date)).limit(limit).all()
    
    @staticmethod
    def get_portfolio_by_id(db: Session, portfolio_id: int) -> Optional[Portfolio]:
        """
        Get portfolio by ID
        """
        return db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    
    @staticmethod
    def delete_portfolio(db: Session, portfolio_id: int) -> bool:
        """
        Delete a portfolio and all associated data
        """
        try:
            portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
            if not portfolio:
                return False
            
            db.delete(portfolio)
            db.commit()
            
            logger.info(f"Deleted portfolio {portfolio_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting portfolio: {e}")
            db.rollback()
            raise
    
    @staticmethod
    def update_portfolio_name(db: Session, portfolio_id: int, new_name: str) -> bool:
        """
        Update portfolio name
        """
        try:
            portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
            if not portfolio:
                return False
            
            old_name = portfolio.name
            portfolio.name = new_name
            db.commit()
            
            logger.info(f"Updated portfolio {portfolio_id} name from '{old_name}' to '{new_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error updating portfolio name: {e}")
            db.rollback()
            raise
    
    @staticmethod
    def update_portfolio_strategy(db: Session, portfolio_id: int, new_strategy: str) -> bool:
        """
        Update portfolio strategy
        """
        try:
            portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
            if not portfolio:
                return False
            
            old_strategy = portfolio.strategy
            portfolio.strategy = new_strategy.strip() if new_strategy else None
            db.commit()
            
            logger.info(f"Updated portfolio {portfolio_id} strategy from '{old_strategy}' to '{new_strategy}'")
            return True
            
        except Exception as e:
            logger.error(f"Error updating portfolio strategy: {e}")
            db.rollback()
            raise
    
    @staticmethod
    def get_recent_analysis_results(
        db: Session,
        portfolio_id: Optional[int] = None,
        limit: int = 10
    ) -> List[AnalysisResult]:
        """
        Get recent analysis results
        """
        query = db.query(AnalysisResult).order_by(desc(AnalysisResult.created_at))
        
        if portfolio_id:
            query = query.filter(AnalysisResult.portfolio_id == portfolio_id)
        
        return query.limit(limit).all()
    
    @staticmethod
    def get_all_portfolios(db: Session) -> List[Portfolio]:
        """
        Get all portfolios from the database
        """
        try:
            portfolios = db.query(Portfolio).order_by(desc(Portfolio.upload_date)).all()
            logger.info(f"Retrieved {len(portfolios)} portfolios from database")
            return portfolios
        except Exception as e:
            logger.error(f"Error fetching all portfolios: {e}")
            raise
    
    @staticmethod
    def get_latest_analysis_result(db: Session, portfolio_id: int) -> Optional[AnalysisResult]:
        """
        Get the latest analysis result for a specific portfolio
        """
        try:
            result = (db.query(AnalysisResult)
                     .filter(AnalysisResult.portfolio_id == portfolio_id)
                     .order_by(desc(AnalysisResult.created_at))
                     .first())
            return result
        except Exception as e:
            logger.error(f"Error fetching latest analysis result for portfolio {portfolio_id}: {e}")
            raise
