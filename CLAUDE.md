# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a full-stack portfolio analysis application that provides Monte Carlo simulations, risk metrics calculation, and interactive visualizations for trading strategies. It consists of a FastAPI backend with a React frontend, featuring both individual portfolio analysis and multi-portfolio blending capabilities with custom weighting.

### Deployment Architecture

**IMPORTANT**: Both development and production environments are hosted on the same local machine.

- **Production URL**: `https://portfolio.cottonmike.com`
- **Development**: Same codebase, same database (`portfolio_analysis.db`)
- **Server**: Single uvicorn instance serves both environments
- **No separate deployment needed**: Changes made locally are immediately available in production after:
  1. Rebuilding frontend: `cd frontend && npm run build`
  2. Restarting backend server: `pkill -f uvicorn && uvicorn app:app --reload --host 0.0.0.0 --port 8000`
  3. Hard refresh browser to clear cached assets (Cmd+Shift+R on Mac, Ctrl+F5 on Windows)

**Note**: The `render.yaml` and Docker files are legacy and not currently used for deployment.

## Development Commands

### Quick Start
- **First-time setup**: `./install.sh` (installs all dependencies and initializes database)
- **Start development**: `./start.sh` (lightweight startup - starts both backend and frontend)
- **Start production**: `./start.sh prod` (Docker-based production mode)
- **Stop all services**: `./stop.sh` (stops dev or prod services)

### Manual Commands (if needed)

#### Backend (FastAPI)
- **Start development server**: `uvicorn app:app --reload`
- **Run tests**: `pytest` (uses pytest framework)
- **Check specific test files**: `pytest test_app.py`, `pytest test_weighting.py`, `pytest test_regime_analysis.py`

#### Frontend (React/TypeScript)
- **Navigate to frontend**: `cd frontend`
- **Install dependencies**: `npm ci`
- **Development server**: `npm run dev` (runs on Vite)
- **Build production**: `npm run build`
- **Lint**: `npm run lint` (ESLint configuration)
- **Preview build**: `npm run preview`

#### Database Operations
- **Initialize database**: `python init_db.py` (creates tables)
- **Run regime tables migration**: `python migrations/add_regime_tables.py`
- **Check database connection**: Use the `/api/debug/database` endpoint
- **Database migrations**: Uses SQLAlchemy with automatic table creation

#### Docker & Deployment (Legacy - Not Currently Used)
- **Local Docker**: `docker-compose up` (builds and runs the full stack)
- **Build for production**: `bash build.sh` (Render deployment script - legacy)
- **Dockerfile**: Multi-stage build (Node.js for frontend, Python for backend - legacy)

**Note**: These Docker/Render deployment files are legacy and not actively used. The application runs directly on the local machine and serves both dev and production.

## Architecture Overview

### Backend Structure (Modular Router Design)
The backend uses FastAPI with a modular router architecture for better code organization:

- **app.py**: Main FastAPI application with middleware and router registration
- **database.py**: Database configuration with PostgreSQL/SQLite fallback
- **models.py**: SQLAlchemy ORM models for portfolios, analysis results, and plots
- **portfolio_service.py**: Service layer for database operations
- **config.py**: Configuration constants and environment settings

#### Core Processing Modules
- **portfolio_processor.py**: Core data processing logic
- **portfolio_blender.py**: Multi-portfolio blending and weighting logic
- **portfolio_optimizer.py**: Advanced weight optimization algorithms
- **plotting.py**: Matplotlib/Seaborn chart generation
- **correlation_utils.py**: Zero-excluding correlation calculations for financial time series
- **robustness_service.py**: Background robustness testing service and data models
- **profit_optimizer.py**: Profit optimization and contract sizing algorithms
- **beta_calculator.py**: Beta, alpha, and R-squared calculations vs S&P 500
- **margin_service.py**: Margin requirement processing and validation

#### Router Modules (`/routers/`)
- **auth.py**: User authentication and registration
- **upload.py**: File upload and processing endpoints
- **portfolio.py**: Portfolio management operations
- **strategies.py**: Strategy listing and analysis
- **optimization.py**: Portfolio weight optimization and analysis endpoints
- **regime.py**: Market regime analysis
- **margin.py**: Margin management functionality
- **robustness.py**: Portfolio robustness testing with random period analysis
- **profit_optimization.py**: Profit optimization and contract sizing endpoints

### Frontend Structure (React + TypeScript + Vite + Material-UI)
Modern React application with Material-UI components and Recharts for data visualization:

- **src/components/**: Reusable UI components (Navigation, theme providers)
- **src/pages/**: Main application pages with advanced features
  - **Home.tsx**: Landing page and overview
  - **Upload.tsx**: File upload interface
  - **Portfolios.tsx**: Interactive portfolio analysis with date range sliders and strategy editing
  - **Analysis.tsx**: Comprehensive analysis results with beta metrics
  - **RegimeAnalysis.tsx**: Market regime analysis interface
  - **MarginManagement.tsx**: Margin calculation and management with automatic extraction from CSV
  - **RobustnessTest.tsx**: Portfolio robustness testing with random period analysis
  - **ProfitOptimization.tsx**: Profit optimization and contract sizing interface
  - **OptimizationHistory.tsx**: Historical optimization results and tracking
- **src/services/api.ts**: Axios-based API client with authentication
- **Frontend routes**: React Router with protected routes and catch-all backend routing

### Database Schema
- **portfolios**: Portfolio metadata, file info, date ranges
- **portfolio_data**: Raw CSV data with calculated metrics
- **analysis_results**: Computed risk metrics and parameters
- **analysis_plots**: Generated chart file references
- **blended_portfolios**: Multi-portfolio configurations

## Key Features & Endpoints

### Authentication & User Management
- `POST /api/register`: User registration with full name and email validation
- `POST /api/login`: User authentication and session management
- `POST /api/logout`: Session termination
- `GET /api/me`: Get current user information

### Portfolio Management
- `POST /api/upload`: Upload and analyze CSV files
- `GET /api/strategies`: List all portfolios with analysis summaries
- `DELETE /api/portfolio/{id}`: Delete portfolio and associated data
- `PUT /api/portfolio/{id}/name`: Update portfolio name
- `GET /api/portfolios`: Get all portfolios with metadata

### Analysis Endpoints
- `POST /api/analyze-portfolios`: Analyze selected portfolios (equal weighting)
- `POST /api/analyze-portfolios-weighted`: Advanced analysis with custom weights
- `GET /api/strategies/{id}/analysis`: Get analysis history for a portfolio
- `POST /api/optimize-weights`: Intelligent portfolio weight optimization

### Market Regime Analysis
- `POST /api/regime/analyze`: Analyze market regime periods and transitions
- `GET /api/regime/data`: Retrieve regime analysis results

### Margin Management
- `POST /api/margin/calculate`: Calculate margin requirements and portfolio multipliers
- `GET /api/margin/requirements`: Get margin requirement configurations

### Robustness Testing
- `POST /api/robustness/test`: Create new robustness test with random period analysis
- `GET /api/robustness/test/{test_id}`: Get robustness test results and status
- `GET /api/robustness/tests`: List all robustness tests for user

### Profit Optimization
- `POST /api/profit-optimization/optimize`: Optimize portfolio for maximum profit with contract sizing
- `GET /api/profit-optimization/history`: Get historical optimization results
- `GET /api/profit-optimization/{optimization_id}`: Get specific optimization result

### File Processing
- **Supported formats**: CSV files with date and P/L columns
- **Date columns**: 'Date Opened', 'Date', 'Trade Date', 'Entry Date', 'Open Date'
- **P/L columns**: 'P/L', 'PnL', 'Profit/Loss', 'Net P/L', 'Realized P/L', 'Total P/L'
- **Premium columns**: 'Premium', 'Premium Collected', 'Premium Received', 'Initial Premium'
- **Contracts columns**: 'No. of Contracts', 'Contracts', 'Contract Count', 'Quantity'
- **Margin columns**: 'Margin', 'Margin Requirement', 'Initial Margin', 'Required Margin'
- **Charts generated**: Combined analysis plots, correlation heatmaps, Monte Carlo simulations

## Interactive UI Features

### Advanced Portfolio Analysis Interface
- **Interactive Date Range Slider**: Dual-handle slider for filtering analysis periods (May 2022 - current date)
- **Logarithmic Scale Toggle**: Switch between linear and log scale for Daily Net Liquidity charts
- **Persistent User Preferences**: localStorage-based persistence for portfolio selections and analysis parameters
- **Material-UI Dark/Light Theme**: Responsive theme switching with proper contrast ratios
- **Real-time Chart Updates**: Recharts integration with dynamic data filtering
- **Strategy Editing**: Direct inline editing of portfolio strategy/category names in table view
- **URL-based State Management**: Query parameters for deep linking to specific portfolios and date ranges

### Portfolio Selection & Weighting
- **Checkbox-based Portfolio Selection**: Multi-select interface with visual feedback
- **Custom Weight Assignment**: Manual weight input with validation and normalization
- **Intelligent Weight Optimization**: One-click optimization using multiple algorithms
- **Weight Constraint Validation**: Real-time validation with min/max weight enforcement

### User Experience Enhancements
- **Session-based Authentication**: Secure user sessions with automatic logout
- **Cross-device Network Access**: Configured for 0.0.0.0 binding with CORS support
- **Responsive Design**: Mobile-friendly interface with Material-UI breakpoints
- **Error Handling**: Comprehensive error messaging and validation feedback

## Configuration & Environment

### Environment Variables
- `DATABASE_URL`: PostgreSQL connection string (falls back to SQLite)
- `SESSION_SECRET_KEY`: For session middleware
- `RENDER`: Set to "true" for Render.com deployment
- `PORT`: Server port (default: 8000)

### Default Parameters
- Risk-free rate: 4.3% annual (0.0171% daily)
- SMA window: 20 days
- Starting capital: $100,000
- Monte Carlo: 1000 simulations, 252 days forecast

## Testing Strategy

The project includes comprehensive test files:
- **test_app.py**: FastAPI endpoint testing
- **test_weighting.py**: Portfolio weighting logic tests
- **test_modules.py**: Module-level testing
- **test_fix.py**: Bug fix validation

## Deployment

- **Production platform**: Render.com
- **Database**: PostgreSQL (managed service)
- **Build process**: Multi-stage Docker with frontend compilation
- **Static assets**: React build served by FastAPI
- **File storage**: Local filesystem with `/uploads` mount

## Memory Management

The application includes garbage collection optimizations for cloud deployment, especially for Monte Carlo simulations and multi-portfolio analysis. Large DataFrame operations are cleaned up immediately after use.

## Portfolio Weight Optimization

### New Feature: Intelligent Weight Optimization
- **Endpoint**: `POST /api/optimize-weights`
- **Purpose**: Automatically finds optimal portfolio weights to maximize return while minimizing drawdown
- **Algorithms**: Scipy optimization, Differential Evolution, Grid Search
- **Module**: `portfolio_optimizer.py` (requires scipy>=1.10.0)

### Optimization Methods
- **Differential Evolution**: Global optimizer, best for complex landscapes (default)
- **Scipy SLSQP**: Local optimizer, faster but may find local optima
- **Grid Search**: Exhaustive search, thorough but slower

### Usage
1. Select 2 or more portfolios in the frontend
2. Click "🎯 Optimize Weights" button
3. Algorithm finds weights that maximize return/drawdown ratio
4. Optimal weights are automatically applied
5. Click "Analyze" to see full results with optimized allocation

### Optimization Objective
- **Primary Goal**: Maximize return while minimizing maximum drawdown
- **Objective Function**: Weighted combination of CAGR and inverse drawdown
- **Constraints**: Min weight 5%, Max weight 60% per portfolio
- **Bonus**: Additional scoring for high Sharpe ratios

## Important Development Notes

### Starting Capital Parameter Flow
- **Critical**: Both individual and blended portfolio analysis respect user-provided starting capital from UI
- **Backend Logic**: User starting capital takes precedence over margin-based calculations
- **Function Signatures**: All portfolio processing functions accept `starting_capital` parameter
- **Default Fallback**: System defaults to margin-based capital calculation only when user input is invalid

### Correlation Analysis Architecture
- **Zero-Exclusion**: Custom correlation calculations exclude zero P&L values (non-trading days)
- **Module**: `correlation_utils.py` provides specialized financial correlation functions
- **Implementation**: Uses `calculate_correlation_excluding_zeros()` instead of pandas `.corr()`
- **Color Scheme**: Correlation heatmaps use Red=1, Blue=0, Green=-1 color mapping

### React Component Performance
- **Slider Components**: Use cached calculations for `maxSliderValue` to prevent render loops
- **State Management**: Avoid stale closures by capturing DOM element references immediately in event handlers
- **Chart Optimization**: Recharts components benefit from memoized data props to prevent unnecessary re-renders

### Database & Authentication
- **Pydantic Schemas**: Use `str | None = None` for nullable fields, not `str = None`
- **User Management**: Full name field is optional and properly handles null values
- **Session Management**: FastAPI session middleware handles authentication state

### Network Configuration
- **Development**: Configured for 0.0.0.0 binding to support cross-device access
- **CORS**: Includes closet.local domain for local network testing
- **Frontend**: Vite dev server configured with proper host and allowed origins

### Performance Considerations
- **Memory Management**: Explicit garbage collection for large DataFrame operations
- **File Uploads**: Streaming file processing for large CSV files
- **Monte Carlo**: Optimized simulation algorithms with progress tracking
- **Background Jobs**: Robustness testing runs asynchronously with progress tracking

### Maximum Drawdown Calculations
- **Standard Definition**: Calculated as percentage decline from highest peak value reached, not from starting capital
- **Formula**: `(Account Value - Rolling Peak) / Rolling Peak`
- **Financial Industry Standard**: This approach properly measures peak-to-trough decline as percentage of peak

### Code Quality
- **TypeScript**: Strict type checking enabled for frontend components
- **Error Handling**: Comprehensive error boundaries and validation
- **Testing**: Pytest framework with modular test files for different components
# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.