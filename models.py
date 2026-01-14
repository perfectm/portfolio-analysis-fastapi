"""
Database models for portfolio analysis application
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import uuid

class User(Base):
    """
    Model for storing user authentication information
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"

class FavoriteSettings(Base):
    """
    Model for storing user's favorite portfolio analysis settings
    """
    __tablename__ = "favorite_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False, default="My Favorite Settings")

    # Portfolio selection and weights
    portfolio_ids_json = Column(Text, nullable=False)  # JSON array of portfolio IDs
    weights_json = Column(Text, nullable=False)  # JSON array of weights

    # Analysis parameters
    starting_capital = Column(Float, nullable=False, default=500000.0)
    risk_free_rate = Column(Float, nullable=False, default=0.043)
    sma_window = Column(Integer, nullable=False, default=20)
    use_trading_filter = Column(Boolean, nullable=False, default=True)

    # Date range (optional - null means use all data)
    date_range_start = Column(DateTime, nullable=True)
    date_range_end = Column(DateTime, nullable=True)

    # Optimization tracking
    last_optimized = Column(DateTime(timezone=True), nullable=True)  # When last optimization ran
    optimized_weights_json = Column(Text, nullable=True)  # JSON array of optimized weights
    optimization_method = Column(String(50), nullable=True)  # Method used for optimization
    has_new_optimization = Column(Boolean, default=False)  # Flag for UI alert

    # Multiple favorites support
    is_default = Column(Boolean, default=False, nullable=False)  # Is this the default favorite for the user
    tags = Column(Text, nullable=True)  # JSON array of tags for categorization (e.g., ["Experimental", "Production"])

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Unique constraint: one favorite name per user
    __table_args__ = (
        Index('idx_user_name_unique', 'user_id', 'name', unique=True),
    )

    def __repr__(self):
        return f"<FavoriteSettings(id={self.id}, user_id={self.user_id}, name='{self.name}')>"

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
    parquet_path = Column(String(500), nullable=True)  # Path to Parquet file
    # Relationships
    raw_data = relationship("PortfolioData", back_populates="portfolio", cascade="all, delete-orphan")
    analysis_results = relationship("AnalysisResult", back_populates="portfolio", cascade="all, delete-orphan")
    margin_data = relationship("PortfolioMarginData", back_populates="portfolio", cascade="all, delete-orphan")
    regime_performance = relationship("RegimePerformance", back_populates="portfolio", cascade="all, delete-orphan")
    blended_mappings = relationship("BlendedPortfolioMapping", back_populates="portfolio", cascade="all, delete-orphan")
    
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
    premium = Column(Float)             # Premium collected (from CSV)
    contracts = Column(Integer)         # Number of contracts (from CSV)
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
    upi = Column(Float)  # Ulcer Performance Index
    kelly_criterion = Column(Float)
    mar_ratio = Column(Float)
    cvar = Column(Float)  # Conditional Value at Risk (mean of worst 5%)
    cagr = Column(Float)
    annual_volatility = Column(Float)
    total_return = Column(Float)
    total_pl = Column(Float)
    final_account_value = Column(Float)
    max_drawdown = Column(Float)
    max_drawdown_percent = Column(Float)
    max_drawdown_date = Column(String(20))  # Date when max drawdown occurred

    # Beta metrics (Portfolio vs S&P 500)
    beta = Column(Float)  # Beta coefficient vs SPX
    alpha = Column(Float)  # Alpha (excess return vs expected return based on beta)
    r_squared = Column(Float)  # R-squared (correlation strength)
    beta_observation_count = Column(Integer)  # Number of observations used in beta calculation
    
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
    portfolio = relationship("Portfolio", back_populates="blended_mappings")
    
    # Unique constraint
    __table_args__ = (
        Index('idx_blended_portfolio_unique', 'blended_portfolio_id', 'portfolio_id', unique=True),
    )
    
    def __repr__(self):
        return f"<BlendedPortfolioMapping(blended_id={self.blended_portfolio_id}, portfolio_id={self.portfolio_id}, weight={self.weight})>"


class MarketRegimeHistory(Base):
    """
    Model for storing historical market regime classifications
    """
    __tablename__ = "market_regime_history"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False, index=True)
    regime = Column(String(20), nullable=False)  # bull, bear, volatile, transitioning
    confidence = Column(Float, nullable=False)  # 0-1 confidence score
    
    # Regime indicators (stored for analysis)
    volatility_percentile = Column(Float)
    trend_strength = Column(Float)
    momentum_score = Column(Float)
    drawdown_severity = Column(Float)
    volume_anomaly = Column(Float)
    
    # Market data used
    market_symbol = Column(String(10), nullable=False, default="^GSPC")
    
    # Metadata
    regime_start_date = Column(DateTime)  # When this regime began
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<MarketRegimeHistory(date='{self.date}', regime='{self.regime}', confidence={self.confidence})>"


class RegimePerformance(Base):
    """
    Model for storing strategy performance by market regime
    """
    __tablename__ = "regime_performance"
    
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    regime = Column(String(20), nullable=False)  # bull, bear, volatile, transitioning
    
    # Performance metrics for this regime
    total_return = Column(Float)
    avg_daily_return = Column(Float)  
    volatility = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    win_rate = Column(Float)
    
    # Analysis parameters
    analysis_period_start = Column(DateTime)
    analysis_period_end = Column(DateTime)
    total_trading_days = Column(Integer)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    portfolio = relationship("Portfolio", back_populates="regime_performance")
    
    # Unique constraint per portfolio/regime combination
    __table_args__ = (
        Index('idx_portfolio_regime', 'portfolio_id', 'regime', unique=True),
    )
    
    def __repr__(self):
        return f"<RegimePerformance(portfolio_id={self.portfolio_id}, regime='{self.regime}', return={self.total_return})>"


class RegimeAlert(Base):
    """
    Model for storing regime change alerts and recommendations
    """
    __tablename__ = "regime_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String(30), nullable=False)  # regime_change, rebalance_recommendation
    
    # Regime information
    previous_regime = Column(String(20))
    new_regime = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False)
    
    # Alert details
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False, default="info")  # info, warning, critical
    
    # Recommendations (JSON format)
    recommended_allocations = Column(Text)  # JSON string of allocation recommendations
    projected_impact = Column(Text)  # JSON string of projected impact metrics
    
    # Status tracking
    is_active = Column(Boolean, default=True)
    acknowledged_at = Column(DateTime)
    dismissed_at = Column(DateTime)
    
    # Timestamps  
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime)  # When alert becomes inactive
    
    def __repr__(self):
        return f"<RegimeAlert(type='{self.alert_type}', regime='{self.new_regime}', active={self.is_active})>"


class OptimizationCache(Base):
    """
    Model for caching portfolio weight optimization results
    """
    __tablename__ = "optimization_cache"
    
    id = Column(Integer, primary_key=True, index=True)

    # User-defined name for this optimization (optional)
    name = Column(String(200), nullable=True)  # e.g., "Conservative Mix", "High Growth Strategy"

    # Portfolio combination identifier (sorted portfolio IDs as comma-separated string)
    portfolio_ids_hash = Column(String(64), nullable=False, index=True)  # SHA-256 hash of sorted portfolio IDs
    portfolio_ids = Column(String(500), nullable=False)  # Comma-separated sorted portfolio IDs (e.g., "1,3,5")
    portfolio_count = Column(Integer, nullable=False, index=True)  # Number of portfolios in this optimization
    
    # Optimization parameters (for cache invalidation)
    rf_rate = Column(Float, nullable=False)
    sma_window = Column(Integer, nullable=False)
    use_trading_filter = Column(Boolean, nullable=False)
    starting_capital = Column(Float, nullable=False)
    min_weight = Column(Float, nullable=False)
    max_weight = Column(Float, nullable=False)
    
    # Optimization results
    optimization_method = Column(String(50), nullable=False)
    optimal_weights = Column(Text, nullable=False)  # JSON string of optimal weights
    optimal_ratios = Column(Text, nullable=False)   # JSON string of optimal ratios
    iterations = Column(Integer, nullable=False)
    success = Column(Boolean, nullable=False)
    
    # Performance metrics
    optimal_cagr = Column(Float, nullable=False)
    optimal_max_drawdown = Column(Float, nullable=False)
    optimal_return_drawdown_ratio = Column(Float, nullable=False)
    optimal_sharpe_ratio = Column(Float, nullable=False)
    
    # Additional metadata
    execution_time_seconds = Column(Float)  # How long optimization took
    explored_combinations_count = Column(Integer)  # Number of combinations explored
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_accessed_at = Column(DateTime(timezone=True), server_default=func.now())
    access_count = Column(Integer, default=1)  # Track cache hit frequency
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_portfolio_hash_params', 'portfolio_ids_hash', 'rf_rate', 'sma_window', 'use_trading_filter'),
        Index('idx_portfolio_count', 'portfolio_count'),
        Index('idx_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<OptimizationCache(id={self.id}, portfolio_ids='{self.portfolio_ids}', method='{self.optimization_method}')>"


class PortfolioMarginData(Base):
    """
    Model for storing raw margin requirement data from uploaded files
    """
    __tablename__ = "portfolio_margin_data"
    
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    margin_requirement = Column(Float, nullable=False)  # Margin required for this date/trade
    margin_type = Column(String(50), nullable=True)  # Optional: type of margin (initial, maintenance, etc.)
    row_number = Column(Integer)  # Original row number from CSV
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    portfolio = relationship("Portfolio", back_populates="margin_data")
    
    # Create composite index for efficient querying
    __table_args__ = (
        Index('idx_portfolio_margin_date', 'portfolio_id', 'date'),
        Index('idx_portfolio_margin_row', 'portfolio_id', 'row_number'),
    )
    
    def __repr__(self):
        return f"<PortfolioMarginData(id={self.id}, portfolio_id={self.portfolio_id}, date='{self.date}', margin={self.margin_requirement})>"


class DailyMarginAggregate(Base):
    """
    Model for storing daily aggregated margin requirements across all portfolios
    """
    __tablename__ = "daily_margin_aggregate"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False, index=True, unique=True)
    total_margin_required = Column(Float, nullable=False)  # Total margin across all active portfolios
    portfolio_count = Column(Integer, nullable=False)  # Number of portfolios with margin requirements on this date
    starting_capital = Column(Float, nullable=False)  # Starting capital used for validation
    margin_utilization_percent = Column(Float, nullable=False)  # Percentage of starting capital used for margin
    is_valid = Column(Boolean, nullable=False, default=True)  # Whether this date's margin is within acceptable limits
    validation_message = Column(Text)  # Optional validation message
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<DailyMarginAggregate(date='{self.date}', total_margin={self.total_margin_required}, valid={self.is_valid})>"


class MarginValidationRule(Base):
    """
    Model for storing margin validation rules and thresholds
    """
    __tablename__ = "margin_validation_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String(100), nullable=False, unique=True)
    rule_type = Column(String(50), nullable=False)  # 'percentage_threshold', 'absolute_limit', etc.
    threshold_value = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<MarginValidationRule(name='{self.rule_name}', type='{self.rule_type}', threshold={self.threshold_value})>"


class RobustnessTest(Base):
    """
    Model for storing robustness test configurations and overall results
    """
    __tablename__ = "robustness_tests"
    
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    test_date = Column(DateTime(timezone=True), server_default=func.now())
    num_periods = Column(Integer, nullable=False, default=10)
    min_period_length_days = Column(Integer, nullable=False, default=252)
    overall_robustness_score = Column(Float)
    
    # Analysis parameters used
    rf_rate = Column(Float)
    daily_rf_rate = Column(Float)
    sma_window = Column(Integer)
    use_trading_filter = Column(Boolean)
    starting_capital = Column(Float)
    
    # Status tracking
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed
    progress = Column(Integer, default=0)  # Progress percentage
    error_message = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    portfolio = relationship("Portfolio")
    periods = relationship("RobustnessPeriod", back_populates="robustness_test", cascade="all, delete-orphan")
    statistics = relationship("RobustnessStatistic", back_populates="robustness_test", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<RobustnessTest(id={self.id}, portfolio_id={self.portfolio_id}, num_periods={self.num_periods}, score={self.overall_robustness_score})>"


class RobustnessPeriod(Base):
    """
    Model for storing individual robustness test period results
    """
    __tablename__ = "robustness_periods"
    
    id = Column(Integer, primary_key=True, index=True)
    robustness_test_id = Column(Integer, ForeignKey("robustness_tests.id"), nullable=False)
    period_number = Column(Integer, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    
    # Performance metrics for this period
    cagr = Column(Float)
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    max_drawdown = Column(Float)
    max_drawdown_percent = Column(Float)
    volatility = Column(Float)
    win_rate = Column(Float)
    profit_factor = Column(Float)
    avg_trade_return = Column(Float)
    total_return = Column(Float)
    total_pl = Column(Float)
    final_account_value = Column(Float)
    ulcer_index = Column(Float)
    upi = Column(Float)  # Ulcer Performance Index
    kelly_criterion = Column(Float)
    mar_ratio = Column(Float)
    pcr = Column(Float)  # Premium Capture Rate
    cvar = Column(Float)  # Conditional Value at Risk (mean of worst 5%)
    
    # Additional metrics
    trade_count = Column(Integer)
    winning_trades = Column(Integer)
    losing_trades = Column(Integer)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    robustness_test = relationship("RobustnessTest", back_populates="periods")
    
    # Indexes
    __table_args__ = (
        Index('idx_robustness_test_period', 'robustness_test_id', 'period_number'),
    )
    
    def __repr__(self):
        return f"<RobustnessPeriod(id={self.id}, test_id={self.robustness_test_id}, period={self.period_number}, cagr={self.cagr})>"


class RobustnessStatistic(Base):
    """
    Model for storing descriptive statistics for robustness test metrics
    """
    __tablename__ = "robustness_statistics"
    
    id = Column(Integer, primary_key=True, index=True)
    robustness_test_id = Column(Integer, ForeignKey("robustness_tests.id"), nullable=False)
    metric_name = Column(String(50), nullable=False)
    
    # Descriptive statistics
    max_value = Column(Float)
    min_value = Column(Float)
    mean_value = Column(Float)
    median_value = Column(Float)
    std_deviation = Column(Float)
    q1_value = Column(Float)  # 25th percentile
    q3_value = Column(Float)  # 75th percentile
    
    # Comparison with full dataset
    full_dataset_value = Column(Float)
    robustness_component_score = Column(Float)
    relative_deviation = Column(Float)  # (mean_value - full_dataset_value) / full_dataset_value
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    robustness_test = relationship("RobustnessTest", back_populates="statistics")
    
    # Indexes
    __table_args__ = (
        Index('idx_robustness_test_metric', 'robustness_test_id', 'metric_name'),
    )
    
    def __repr__(self):
        return f"<RobustnessStatistic(id={self.id}, test_id={self.robustness_test_id}, metric='{self.metric_name}', score={self.robustness_component_score})>"
