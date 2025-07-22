"""
Database models for portfolio analysis application
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import uuid

class Portfolio(Base):
    """
    Model for storing portfolio metadata
    """
    __tablename__ = "portfolios"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    file_size = Column(Integer)  # File size in bytes
    row_count = Column(Integer)  # Number of data rows
    date_range_start = Column(DateTime)  # First date in the data
    date_range_end = Column(DateTime)    # Last date in the data
    file_hash = Column(String(64), index=True)  # SHA-256 hash for duplicate detection
    strategy = Column(String(255), nullable=True)  # Trading strategy description
    
    # Relationships
    raw_data = relationship("PortfolioData", back_populates="portfolio", cascade="all, delete-orphan")
    analysis_results = relationship("AnalysisResult", back_populates="portfolio", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Portfolio(id={self.id}, name='{self.name}', filename='{self.filename}')>"

class PortfolioData(Base):
    """
    Model for storing raw CSV data from uploaded files
    """
    __tablename__ = "portfolio_data"
    
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    pl = Column(Float, nullable=False)  # Profit/Loss value
    cumulative_pl = Column(Float)       # Cumulative P/L (calculated)
    account_value = Column(Float)       # Account value (calculated)
    daily_return = Column(Float)        # Daily return percentage
    row_number = Column(Integer)        # Original row number from CSV
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    portfolio = relationship("Portfolio", back_populates="raw_data")
    
    # Create composite index for efficient querying
    __table_args__ = (
        Index('idx_portfolio_date', 'portfolio_id', 'date'),
        Index('idx_portfolio_row', 'portfolio_id', 'row_number'),
    )
    
    def __repr__(self):
        return f"<PortfolioData(id={self.id}, portfolio_id={self.portfolio_id}, date='{self.date}', pl={self.pl})>"

class AnalysisResult(Base):
    """
    Model for storing calculated analysis results
    """
    __tablename__ = "analysis_results"
    
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    analysis_type = Column(String(50), nullable=False)  # 'individual', 'blended', 'correlation', etc.
    
    # Analysis parameters
    rf_rate = Column(Float)
    daily_rf_rate = Column(Float)
    sma_window = Column(Integer)
    use_trading_filter = Column(Boolean)
    starting_capital = Column(Float)
    
    # Calculated metrics (stored as JSON-like text for flexibility)
    metrics_json = Column(Text)  # JSON string of all calculated metrics
    
    # Key metrics (for easy querying)
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    ulcer_index = Column(Float)
    mar_ratio = Column(Float)
    cagr = Column(Float)
    annual_volatility = Column(Float)
    total_return = Column(Float)
    total_pl = Column(Float)
    final_account_value = Column(Float)
    max_drawdown = Column(Float)
    max_drawdown_percent = Column(Float)
    max_drawdown_date = Column(String(20))  # Date when max drawdown occurred
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    portfolio = relationship("Portfolio", back_populates="analysis_results")
    plots = relationship("AnalysisPlot", back_populates="analysis_result", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<AnalysisResult(id={self.id}, portfolio_id={self.portfolio_id}, type='{self.analysis_type}')>"

class AnalysisPlot(Base):
    """
    Model for storing generated plot file information
    """
    __tablename__ = "analysis_plots"
    
    id = Column(Integer, primary_key=True, index=True)
    analysis_result_id = Column(Integer, ForeignKey("analysis_results.id"), nullable=False)
    plot_type = Column(String(50), nullable=False)  # 'combined_analysis', 'correlation_heatmap', etc.
    file_path = Column(String(500), nullable=False)
    file_url = Column(String(500), nullable=False)
    file_size = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    analysis_result = relationship("AnalysisResult", back_populates="plots")
    
    def __repr__(self):
        return f"<AnalysisPlot(id={self.id}, plot_type='{self.plot_type}', file_path='{self.file_path}')>"

class BlendedPortfolio(Base):
    """
    Model for storing blended portfolio configurations and results
    """
    __tablename__ = "blended_portfolios"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    weighting_method = Column(String(20), nullable=False)  # 'equal', 'custom'
    weights_json = Column(Text)  # JSON string of portfolio weights
    
    # Analysis parameters
    rf_rate = Column(Float)
    daily_rf_rate = Column(Float)
    sma_window = Column(Integer)
    use_trading_filter = Column(Boolean)
    starting_capital = Column(Float)
    
    # Results
    analysis_result_id = Column(Integer, ForeignKey("analysis_results.id"))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    analysis_result = relationship("AnalysisResult")
    portfolio_mappings = relationship("BlendedPortfolioMapping", back_populates="blended_portfolio", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<BlendedPortfolio(id={self.id}, name='{self.name}', method='{self.weighting_method}')>"

class BlendedPortfolioMapping(Base):
    """
    Model for mapping individual portfolios to blended portfolios with weights
    """
    __tablename__ = "blended_portfolio_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    blended_portfolio_id = Column(Integer, ForeignKey("blended_portfolios.id"), nullable=False)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    weight = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    blended_portfolio = relationship("BlendedPortfolio", back_populates="portfolio_mappings")
    portfolio = relationship("Portfolio")
    
    # Unique constraint
    __table_args__ = (
        Index('idx_blended_portfolio_unique', 'blended_portfolio_id', 'portfolio_id', unique=True),
    )
    
    def __repr__(self):
        return f"<BlendedPortfolioMapping(blended_id={self.blended_portfolio_id}, portfolio_id={self.portfolio_id}, weight={self.weight})>"
