"""
Margin Service for handling portfolio margin requirements
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Portfolio, PortfolioMarginData, DailyMarginAggregate, MarginValidationRule
from config import DATE_COLUMNS
import logging
from datetime import datetime
import hashlib
import os

logger = logging.getLogger(__name__)

# Margin requirement column mappings - expanded to handle various formats
MARGIN_COLUMNS = [
    # Standard formats
    'Margin Requirement', 'Margin', 'Initial Margin', 'Required Margin', 
    'MarginRequirement', 'InitialMargin', 'RequiredMargin', 'TotalMargin',
    # Common trading platform variations
    'Maintenance Margin', 'MaintenanceMargin', 'Margin Req', 'MarginReq', 'margin req', 'Margin Req.',
    'Buying Power Used', 'BuyingPowerUsed', 'Capital Required', 'CapitalRequired',
    'Position Value', 'PositionValue', 'Notional Value', 'NotionalValue',
    'Risk Requirement', 'RiskRequirement', 'Portfolio Margin', 'PortfolioMargin',
    # Broker-specific variations
    'Day Trading Buying Power', 'DayTradingBuyingPower', 'DTBP',
    'Overnight Buying Power', 'OvernightBuyingPower', 'ONBP',
    'Excess Liquidity', 'ExcessLiquidity', 'Available Funds', 'AvailableFunds',
    # Case-insensitive matches will be handled separately
    'margin', 'MARGIN', 'Margin_Requirement', 'margin_requirement',
    'initial_margin', 'INITIAL_MARGIN', 'required_margin', 'REQUIRED_MARGIN'
]

class MarginService:
    
    @staticmethod
    def _clean_margin_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean margin data CSV similar to portfolio data cleaning
        """
        logger.info(f"[MARGIN] Starting to clean data with shape {df.shape}")
        
        # Find date column
        date_col = None
        for col_name in DATE_COLUMNS:
            if col_name in df.columns:
                date_col = col_name
                break
        
        if date_col is None:
            raise ValueError(f"No recognized date column found. Expected one of: {DATE_COLUMNS}")
        
        # Find margin requirement column with flexible matching
        margin_col = None
        
        # First try exact match
        for col_name in MARGIN_COLUMNS:
            if col_name in df.columns:
                margin_col = col_name
                break
        
        # If no exact match, try case-insensitive matching
        if margin_col is None:
            df_columns_lower = [col.lower() for col in df.columns]
            margin_columns_lower = [col.lower() for col in MARGIN_COLUMNS]
            
            for i, col_lower in enumerate(df_columns_lower):
                if col_lower in margin_columns_lower:
                    margin_col = df.columns[i]
                    break
        
        # If still no match, try partial matching for common terms
        if margin_col is None:
            common_margin_terms = ['margin', 'requirement', 'buying', 'power', 'capital', 'notional', 'position']
            for col in df.columns:
                col_lower = col.lower().replace('_', ' ').replace('-', ' ')
                if any(term in col_lower for term in common_margin_terms):
                    # Check if this looks like a margin-related column
                    if 'margin' in col_lower or 'requirement' in col_lower or 'capital' in col_lower:
                        margin_col = col
                        logger.info(f"[MARGIN] Using fuzzy match for margin column: {col}")
                        break
        
        if margin_col is None:
            available_columns = list(df.columns)
            raise ValueError(
                f"No recognized margin column found in file. "
                f"Available columns: {available_columns}. "
                f"Expected one of: {MARGIN_COLUMNS[:10]}... "  # Show first 10 to avoid overwhelming
                f"Please ensure your CSV has a column containing margin requirements."
            )
        
        logger.info(f"[MARGIN] Using date column: {date_col}, margin column: {margin_col}")
        
        # Create clean DataFrame
        clean_df = pd.DataFrame()
        clean_df['Date'] = pd.to_datetime(df[date_col])
        clean_df['Margin Requirement'] = pd.to_numeric(df[margin_col], errors='coerce')
        
        # Add margin type if available
        if 'Margin Type' in df.columns:
            clean_df['Margin Type'] = df['Margin Type']
        else:
            clean_df['Margin Type'] = 'initial'  # Default margin type
        
        # Remove rows with invalid data
        initial_count = len(clean_df)
        clean_df = clean_df.dropna(subset=['Date', 'Margin Requirement'])
        final_count = len(clean_df)
        
        if final_count < initial_count:
            logger.warning(f"[MARGIN] Removed {initial_count - final_count} rows with invalid date or margin data")
        
        if len(clean_df) == 0:
            raise ValueError("No valid margin data found after cleaning")
        
        # Sort by date
        clean_df = clean_df.sort_values('Date').reset_index(drop=True)
        
        # Calculate daily aggregated statistics for reporting
        daily_totals = clean_df.groupby('Date')['Margin Requirement'].sum()
        daily_avg = daily_totals.mean()
        daily_max = daily_totals.max()
        daily_min = daily_totals.min()
        
        logger.info(f"[MARGIN] Cleaned data shape: {clean_df.shape}")
        logger.info(f"[MARGIN] Date range: {clean_df['Date'].min()} to {clean_df['Date'].max()}")
        logger.info(f"[MARGIN] Individual margin range: ${clean_df['Margin Requirement'].min():,.2f} to ${clean_df['Margin Requirement'].max():,.2f}")
        logger.info(f"[MARGIN] Daily aggregated margins - Avg: ${daily_avg:,.2f}, Max: ${daily_max:,.2f}, Min: ${daily_min:,.2f}")
        
        return clean_df
    
    @staticmethod
    def store_margin_data(db: Session, portfolio_id: int, margin_df: pd.DataFrame) -> bool:
        """
        Store margin requirement data for a portfolio
        """
        try:
            logger.info(f"[MARGIN] Storing {len(margin_df)} margin records for portfolio {portfolio_id}")
            
            # Clear existing margin data for this portfolio
            db.query(PortfolioMarginData).filter(
                PortfolioMarginData.portfolio_id == portfolio_id
            ).delete()
            
            # Store new margin data
            for idx, row in margin_df.iterrows():
                margin_record = PortfolioMarginData(
                    portfolio_id=portfolio_id,
                    date=row['Date'],
                    margin_requirement=row['Margin Requirement'],
                    margin_type=row.get('Margin Type', 'initial'),
                    row_number=idx + 1
                )
                db.add(margin_record)
            
            db.commit()
            logger.info(f"[MARGIN] Successfully stored margin data for portfolio {portfolio_id}")
            return True
            
        except Exception as e:
            logger.error(f"[MARGIN] Error storing margin data for portfolio {portfolio_id}: {e}")
            db.rollback()
            return False
    
    @staticmethod
    def get_portfolio_margin_data(db: Session, portfolio_id: int, limit: Optional[int] = None) -> List[PortfolioMarginData]:
        """
        Get margin data for a specific portfolio
        """
        query = db.query(PortfolioMarginData).filter(
            PortfolioMarginData.portfolio_id == portfolio_id
        ).order_by(PortfolioMarginData.date)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    @staticmethod
    def calculate_daily_margin_aggregates(db: Session, starting_capital: float = 1000000.0, max_margin_percent: float = 0.85) -> Dict[str, Any]:
        """
        Calculate daily aggregated margin requirements across all portfolios
        """
        try:
            logger.info(f"[MARGIN] Calculating daily margin aggregates with starting capital: ${starting_capital:,.2f}")
            
            # Get all margin data grouped by date
            query = db.query(
                PortfolioMarginData.date,
                func.sum(PortfolioMarginData.margin_requirement).label('total_margin'),
                func.count(func.distinct(PortfolioMarginData.portfolio_id)).label('portfolio_count')
            ).group_by(PortfolioMarginData.date).order_by(PortfolioMarginData.date)
            
            results = query.all()
            
            if not results:
                logger.warning("[MARGIN] No margin data found for aggregation")
                return {"success": False, "message": "No margin data found"}
            
            # Clear existing aggregates
            db.query(DailyMarginAggregate).delete()
            
            processed_count = 0
            validation_failures = 0
            
            for result in results:
                date = result.date
                total_margin = float(result.total_margin)
                portfolio_count = result.portfolio_count
                
                # Calculate margin utilization percentage
                margin_utilization = (total_margin / starting_capital) * 100
                
                # Validate against margin limits
                is_valid = total_margin <= (starting_capital * max_margin_percent)
                validation_message = None
                
                if not is_valid:
                    validation_failures += 1
                    validation_message = f"Margin requirement (${total_margin:,.2f}) exceeds {max_margin_percent*100}% of starting capital (${starting_capital * max_margin_percent:,.2f})"
                    logger.warning(f"[MARGIN] Validation failure for {date}: {validation_message}")
                
                # Store aggregate record
                aggregate = DailyMarginAggregate(
                    date=date,
                    total_margin_required=total_margin,
                    portfolio_count=portfolio_count,
                    starting_capital=starting_capital,
                    margin_utilization_percent=margin_utilization,
                    is_valid=is_valid,
                    validation_message=validation_message
                )
                db.add(aggregate)
                processed_count += 1
            
            db.commit()
            
            logger.info(f"[MARGIN] Processed {processed_count} daily aggregates, {validation_failures} validation failures")
            
            # Get summary statistics
            summary_stats = MarginService.get_margin_summary_stats(db)
            
            return {
                "success": True,
                "processed_days": processed_count,
                "validation_failures": validation_failures,
                "starting_capital": starting_capital,
                "max_margin_percent": max_margin_percent,
                "summary": summary_stats
            }
            
        except Exception as e:
            logger.error(f"[MARGIN] Error calculating daily margin aggregates: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_margin_summary_stats(db: Session) -> Dict[str, Any]:
        """
        Get summary statistics for margin requirements
        """
        try:
            # Get aggregate statistics
            stats_query = db.query(
                func.count(DailyMarginAggregate.id).label('total_days'),
                func.sum(func.case([(DailyMarginAggregate.is_valid == True, 1)], else_=0)).label('valid_days'),
                func.avg(DailyMarginAggregate.total_margin_required).label('avg_margin'),
                func.max(DailyMarginAggregate.total_margin_required).label('max_margin'),
                func.min(DailyMarginAggregate.total_margin_required).label('min_margin'),
                func.avg(DailyMarginAggregate.margin_utilization_percent).label('avg_utilization'),
                func.max(DailyMarginAggregate.margin_utilization_percent).label('max_utilization')
            ).first()
            
            if not stats_query or stats_query.total_days == 0:
                return {"message": "No margin aggregate data available"}
            
            return {
                "total_days": stats_query.total_days,
                "valid_days": stats_query.valid_days or 0,
                "invalid_days": (stats_query.total_days or 0) - (stats_query.valid_days or 0),
                "average_margin_required": float(stats_query.avg_margin or 0),
                "maximum_margin_required": float(stats_query.max_margin or 0),
                "minimum_margin_required": float(stats_query.min_margin or 0),
                "average_utilization_percent": float(stats_query.avg_utilization or 0),
                "maximum_utilization_percent": float(stats_query.max_utilization or 0),
                "validation_success_rate": ((stats_query.valid_days or 0) / (stats_query.total_days or 1)) * 100
            }
            
        except Exception as e:
            logger.error(f"[MARGIN] Error getting margin summary stats: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def get_margin_violations(db: Session, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get dates with margin requirement violations
        """
        violations = db.query(DailyMarginAggregate).filter(
            DailyMarginAggregate.is_valid == False
        ).order_by(DailyMarginAggregate.date.desc()).limit(limit).all()
        
        return [
            {
                "date": violation.date.isoformat(),
                "total_margin_required": violation.total_margin_required,
                "margin_utilization_percent": violation.margin_utilization_percent,
                "portfolio_count": violation.portfolio_count,
                "validation_message": violation.validation_message
            }
            for violation in violations
        ]
    
    @staticmethod
    def match_portfolio_by_filename(db: Session, margin_filename: str) -> Optional[Portfolio]:
        """
        Match a margin file to an existing portfolio by filename pattern
        """
        # Try exact filename match first (without .csv extension)
        base_name = margin_filename.replace('.csv', '').replace('_margin', '').replace('-margin', '')
        
        # Try various matching patterns
        patterns = [
            base_name,
            base_name.replace('-', '_'),
            base_name.replace('_', '-'),
            base_name.replace(' ', '_'),
            base_name.replace(' ', '-')
        ]
        
        for pattern in patterns:
            portfolio = db.query(Portfolio).filter(
                Portfolio.filename.ilike(f"%{pattern}%")
            ).first()
            
            if portfolio:
                logger.info(f"[MARGIN] Matched margin file '{margin_filename}' to portfolio '{portfolio.name}' (ID: {portfolio.id})")
                return portfolio
        
        logger.warning(f"[MARGIN] Could not match margin file '{margin_filename}' to any existing portfolio")
        return None
    
    @staticmethod
    def initialize_default_validation_rules(db: Session) -> bool:
        """
        Initialize default margin validation rules
        """
        try:
            # Check if rules already exist
            existing_rules = db.query(MarginValidationRule).count()
            if existing_rules > 0:
                logger.info("[MARGIN] Validation rules already initialized")
                return True
            
            default_rules = [
                {
                    "rule_name": "max_margin_percentage",
                    "rule_type": "percentage_threshold", 
                    "threshold_value": 85.0,
                    "description": "Maximum percentage of starting capital that can be used for margin requirements"
                },
                {
                    "rule_name": "critical_margin_percentage",
                    "rule_type": "percentage_threshold",
                    "threshold_value": 95.0,
                    "description": "Critical threshold where margin requirements become extremely risky"
                }
            ]
            
            for rule_data in default_rules:
                rule = MarginValidationRule(**rule_data)
                db.add(rule)
            
            db.commit()
            logger.info(f"[MARGIN] Initialized {len(default_rules)} default validation rules")
            return True
            
        except Exception as e:
            logger.error(f"[MARGIN] Error initializing validation rules: {e}")
            db.rollback()
            return False