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

from models import Portfolio, PortfolioData, AnalysisResult, AnalysisPlot, BlendedPortfolio, BlendedPortfolioMapping
from config import DATE_COLUMNS, PL_COLUMNS

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
            # Calculate file hash for duplicate detection
            file_hash = PortfolioService.calculate_file_hash(file_content)
            
            # Check if portfolio with same hash already exists
            existing = db.query(Portfolio).filter(Portfolio.file_hash == file_hash).first()
            if existing:
                logger.info(f"Portfolio with hash {file_hash} already exists: {existing.name}")
                return existing
            
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
            
            # Find the date column using the same logic as portfolio_processor
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
            
            logger.info(f"Using '{date_column}' as date column and '{pl_column}' as P/L column")
            
            # Prepare data for bulk insert
            data_records = []
            cumulative_pl = 0
            starting_capital = 100000  # Default starting capital
            
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
                    cumulative_pl=cumulative_pl,
                    account_value=account_value,
                    daily_return=daily_return,
                    row_number=idx + 1
                )
                data_records.append(data_record)
            
            # Bulk insert
            db.bulk_save_objects(data_records)
            db.commit()
            
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
    def get_portfolio_dataframe(db: Session, portfolio_id: int) -> pd.DataFrame:
        """
        Get portfolio data as pandas DataFrame
        """
        data = PortfolioService.get_portfolio_data(db, portfolio_id)
        
        if not data:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df_data = []
        for record in data:
            df_data.append({
                'Date': record.date,
                'P/L': record.pl,
                'Cumulative_PL': record.cumulative_pl,
                'Account_Value': record.account_value,
                'Daily_Return': record.daily_return
            })
        
        df = pd.DataFrame(df_data)
        df['Date'] = pd.to_datetime(df['Date'])
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
                kelly_criterion=metrics.get('kelly_criterion'),
                mar_ratio=metrics.get('mar_ratio'),
                cagr=metrics.get('cagr'),
                annual_volatility=metrics.get('annual_volatility'),
                total_return=metrics.get('total_return'),
                total_pl=metrics.get('total_pl'),
                final_account_value=metrics.get('final_account_value'),
                max_drawdown=metrics.get('max_drawdown'),
                max_drawdown_percent=metrics.get('max_drawdown_percent'),
                max_drawdown_date=metrics.get('max_drawdown_date')
            )
            
            db.add(analysis_result)
            db.commit()
            db.refresh(analysis_result)
            
            logger.info(f"Stored analysis result for portfolio {portfolio_id}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error storing analysis result: {e}")
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
