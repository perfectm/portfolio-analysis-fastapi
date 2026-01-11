# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a full-stack portfolio analysis application that provides Monte Carlo simulations, risk metrics calculation, and interactive visualizations for trading strategies. It consists of a FastAPI backend with a React frontend, featuring both individual portfolio analysis and multi-portfolio blending capabilities with custom weighting.

### Deployment Architecture

The application is deployed in two environments:

#### Production Server (Hostinger)
- **Production URL**: `https://portfolio.cottonmike.com`
- **Server**: Hostinger VPS (Linux, Ubuntu)
- **Installation Path**: `/opt/cmtool`
- **Service Name**: `cmtool` (systemd service)
- **Deployment User**: `deployuser` (owns git repo, runs git operations)
- **Runtime User**: `deployuser` (runs the application service)
- **Database**: PostgreSQL (`portfolio_analysis` database, user: `cmtool`)

**User/Permission Architecture:**
- `deployuser`: Owns `/opt/cmtool` directory and files, manages git operations
- `cmtool` (database user): PostgreSQL database access only
- Environment variables stored in `/opt/cmtool/.env` (600 permissions, owned by deployuser)
- Python virtual environment: `/opt/cmtool/venv` (owned by deployuser)

**Deployment Process:**
1. SSH to server: `ssh cotton@srv1173534`
2. Navigate to app: `cd /opt/cmtool`
3. Pull latest code: `sudo -u deployuser git pull`
4. Rebuild frontend (if needed): `cd frontend && npm run build && cd ..`
5. Restart service: `sudo systemctl restart cmtool`
6. Check status: `sudo systemctl status cmtool`
7. View logs: `tail -f logs/portfolio_analysis.log`

**PostgreSQL Migration (Completed):**
- Migrated from SQLite to PostgreSQL for improved performance
- 30-50% faster queries on large datasets (800K+ records)
- Database connection configured via `DATABASE_URL` in `/opt/cmtool/.env`
- Backup SQLite file kept at `/opt/cmtool/portfolio_analysis.db` (legacy)

**Important Hostinger Notes:**
- Service managed by systemd (not shell scripts)
- Logs written to `logs/portfolio_analysis.log` (automatic rotation at 10MB)
- **CRITICAL**: Always use `sudo -u deployuser` for git operations to maintain correct permissions
- After git pull conflicts: `sudo -u deployuser git fetch origin && sudo -u deployuser git reset --hard origin/main`
- yfinance cache stored in `/opt/cmtool/.cache/yfinance` (auto-created at runtime)
- Session data and uploads owned by `deployuser`

#### Local Development
- **Development**: Local machine, same codebase
- **Database**: SQLite (`portfolio_analysis.db`)
- **Server**: uvicorn instance via shell scripts
- **Changes immediately available after**:
  1. Rebuilding frontend: `cd frontend && npm run build`
  2. Restarting servers using scripts: `./stop.sh && ./start.sh`
  3. Hard refresh browser to clear cached assets (Cmd+Shift+R on Mac, Ctrl+F5 on Windows)

**Note**: The `render.yaml` and Docker files are legacy and not currently used for deployment.

### Server Management Best Practices

**ALWAYS use the provided shell scripts for server management:**

- **Start servers**: `./start.sh` (dev mode) or `./start.sh prod` (production mode)
- **Stop servers**: `./stop.sh` (dev mode) or `./stop.sh prod` (production mode)
- **Stop everything**: `./stop.sh all` (stops all services and cleans up)

**Why use scripts instead of manual commands?**
- Scripts handle PID tracking automatically (.backend.pid, .frontend.pid)
- Graceful shutdown with timeout and force kill if needed
- Automatic log rotation when logs exceed 50MB
- Port conflict detection before starting
- Proper cleanup of resources
- Consistent behavior across all environments

**NEVER manually kill processes with pkill or kill commands unless the scripts fail.**

## Development Commands

### Quick Start
- **First-time setup**: `./install.sh` (installs all dependencies and initializes database)
- **Start development**: `./start.sh` (starts both backend and frontend with log rotation)
- **Start production**: `./start.sh prod` (Docker-based production mode)
- **Stop all services**: `./stop.sh` (gracefully stops dev or prod services)
- **Stop everything**: `./stop.sh all` (stops all services and cleans up logs)
- **Sync production data**: `python sync_prod_to_dev.py` (import production data to local database for testing)

### Script Details

**start.sh Features:**
- Checks for port conflicts before starting (8000 for backend, 5173 for frontend)
- Validates dependencies are installed
- Rotates log files if they exceed 50MB (compresses with gzip)
- Stores PIDs in `.backend.pid` and `.frontend.pid` for tracking
- Waits for services to be ready before reporting success
- Logs output to `backend.log` and `frontend.log`

**stop.sh Features:**
- Stops processes using PID files first (graceful)
- Falls back to port-based process killing if needed
- Waits up to 10 seconds for graceful shutdown
- Force kills processes that don't respond
- Cleans up log files in dev mode
- Removes PID tracking files

### Manual Commands (fallback only - use scripts when possible)

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
- **Sync production to dev**: `python sync_prod_to_dev.py` (see SYNC_DATABASE.md for details)

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
- **favorites.py**: User favorite portfolio settings persistence

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
- **favorite_settings**: User-specific saved portfolio analysis configurations
- **users**: User authentication and profile data
- **regime_data**: Market regime analysis results (via yfinance S&P 500 data)
- **margin_requirements**: Portfolio margin requirement configurations
- **optimization_cache**: Cached optimization results for performance

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

### Favorites & User Preferences
- `POST /api/favorites/save`: Save current portfolio analysis settings as user favorites
- `GET /api/favorites/load`: Load user's saved favorite settings

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
- **Favorite Settings Persistence**: Save and restore portfolio analysis configurations per user
- **Date Preset Buttons**: Quick date range selection (1Y, 2Y, 3Y, 5Y, All, YTD) in Portfolios.tsx

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

## Database Synchronization (Production to Development)

For testing with real production data, use the `sync_prod_to_dev.py` script to safely import data from the Hostinger production PostgreSQL database to your local SQLite development database.

### Quick Start
```bash
# Step 1: Create SSH tunnel to production server
ssh -L 5433:localhost:5432 cotton@srv1173534

# Step 2: In another terminal, run sync
python sync_prod_to_dev.py "postgresql://cmtool:PASSWORD@localhost:5433/portfolio_analysis"
```

### Features
- ✅ **Read-only** connection to production (safe, no changes to prod)
- ✅ **Complete data sync** of all tables with foreign key relationships
- ✅ **Batch processing** for large datasets (100K+ rows)
- ✅ **Progress feedback** during sync
- ✅ **User confirmation** required before replacing local data
- ✅ **Automatic backup** recommendation

### What Gets Synced
All tables are synced in the correct order to preserve relationships:
- Users and authentication
- Portfolios and raw data
- Analysis results and plots
- Blended portfolio configurations
- Regime analysis data
- Margin requirements
- Optimization cache

### Documentation
See **SYNC_DATABASE.md** for:
- Detailed usage instructions
- SSH tunnel setup
- Troubleshooting guide
- Security best practices
- Performance tips

### Use Cases
- Testing with real production data
- Debugging issues reported by users
- Performance testing with large datasets
- Developing new features with actual data
- Validating migrations before production deployment

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

#### Full Optimization (Extensive Search)
These methods explore a wide range of weight combinations for optimal results:
- **Differential Evolution**: Global optimizer, best for complex landscapes (default)
- **Scipy SLSQP**: Local optimizer, faster but may find local optima
- **Grid Search**: Exhaustive search, thorough but slower
- **Objective Function**: Weighted combination of CAGR (60%) and inverse drawdown (40%)
- **Constraints**: Dynamic min/max weights based on portfolio count

#### Simple Optimization (Quick Refinement)
Fast optimization method that explores limited weight variations around current allocations:
- **Method Name**: `simple`
- **Strategy**: ±1 unit change around current ratios
- **Rules**:
  - If portfolio ratio is 1: try 1 and 2 only (cannot reduce to 0)
  - If portfolio ratio is N (where N > 1): try N-1, N, and N+1
  - All combinations are evaluated (exhaustive for ≤10 portfolios, random sampling for 11-20)
- **Objective Function**: 40% CAGR + 40% Sortino Ratio + 20% Sharpe Ratio
- **Portfolio Limits**:
  - **≤10 portfolios**: Exhaustive search (all combinations evaluated)
  - **>10 portfolios**: Greedy hill-climbing (iterative improvement, one portfolio at a time)
  - **Max change**: Each portfolio limited to ±2 units from starting position
  - **No upper limit**: Works efficiently even with 38+ portfolios
- **Use Case**: Quick refinement of existing allocations, faster than full optimization
- **Example**: For 3 portfolios with ratios [1, 2, 3]:
  - Portfolio 1: tries [1, 2] (2 options)
  - Portfolio 2: tries [1, 2, 3] (3 options)
  - Portfolio 3: tries [2, 3, 4] (3 options)
  - Total: 2 × 3 × 3 = 18 combinations evaluated

### Usage
1. Select 2 or more portfolios in the frontend
2. Click "🎯 Optimize Weights" button
3. Algorithm finds optimal weights based on selected method
4. Optimal weights are automatically applied
5. Click "Analyze" to see full results with optimized allocation

### API Usage
```python
# Full optimization (default)
POST /api/optimize-weights
{
  "portfolio_ids": [1, 2, 3],
  "method": "differential_evolution"  # or "scipy", "grid_search"
}

# Simple optimization (quick refinement)
POST /api/optimize-weights
{
  "portfolio_ids": [1, 2, 3],
  "method": "simple",
  "resume_from_weights": [0.2, 0.3, 0.5]  # optional starting weights
}
```

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

### Server Management Protocol
- **CRITICAL**: Always use `./start.sh` and `./stop.sh` scripts for server lifecycle management
- **Never Manually Kill**: Do not use `pkill -f uvicorn` or `kill` commands directly
- **Why Scripts Matter**:
  - Track PIDs in `.backend.pid` and `.frontend.pid` files for proper cleanup
  - Automatic log rotation prevents disk space issues
  - Port conflict detection prevents startup failures
  - Graceful shutdown prevents data corruption
  - Consistent environment across development and production
- **Emergency Only**: Manual process killing is acceptable only if scripts fail to work
- **After Code Changes**: Always restart with `./stop.sh && ./start.sh` to apply changes
- **Log Locations**: Check `backend.log` and `frontend.log` for debugging

### Maximum Drawdown Calculations
- **Standard Definition**: Calculated as percentage decline from highest peak value reached, not from starting capital
- **Formula**: `(Account Value - Rolling Peak) / Rolling Peak`
- **Financial Industry Standard**: This approach properly measures peak-to-trough decline as percentage of peak

### Drawdown Metrics Architecture
- **Days in Drawdown**: Total trading days where portfolio is below peak value (Drawdown Pct < 0)
- **Avg Drawdown Length**: Average duration of consecutive drawdown periods
- **Num Drawdown Periods**: Count of separate drawdown episodes
- **Calculation**: Identifies consecutive days in drawdown state, tracks individual periods
- **Backend Location**: `_calculate_drawdown_metrics()` in `portfolio_processor.py`
- **API Inclusion**: All three metrics included in every analysis response (individual and blended)

### Metrics Display Organization
- **Bottom Row Convention**: Portfolios.tsx displays metrics in final rows separated by horizontal divider:
  1. Max Drawdown % (red)
  2. Max Drawdown $ (red)
  3. Days in Drawdown (orange)
  4. Avg Drawdown Length (orange)
  5. Worst P/L Day (red)
  6. Worst P/L Date (gray)
  7. Days Loss > 0.5% of Current Net Liq (orange)
  8. Days Loss > 0.75% of Current Net Liq (orange)
  9. Days Loss > 1% of Current Net Liq (red)
  10. Days Loss > 0.5% of Starting Capital (orange)
  11. Days Loss > 0.75% of Starting Capital (orange)
  12. Days Loss > 1% of Starting Capital (red)
  13. Days Gain > 0.5% of Current Net Liq (green, highlighted)
  14. Days Gain > 0.75% of Current Net Liq (green, highlighted)
  15. Days Gain > 1% of Current Net Liq (green, highlighted)
  16. Days Gain > 0.5% of Starting Capital (green, highlighted)
  17. Days Gain > 0.75% of Starting Capital (green, highlighted)
  18. Days Gain > 1% of Starting Capital (green, highlighted)
  19. Largest Profit Day (green, highlighted)
  20. Largest Profit Date (gray, highlighted)
- **Visual Separator**: 2px horizontal divider (`theme.palette.divider`) before bottom row metrics
- **Consistent Layout**: Same organization for both blended and individual portfolio results
- **Removed Duplicates**: "Best P/L Day" and "Best P/L Date" duplicates removed from middle section, only "Largest Profit Day/Date" kept in bottom row

### Tail Risk Metrics
- **Current Net Liq Based**: Metrics calculated as percentage of account value on each day
  - Days Loss > 0.5%: Daily Return < -0.005
  - Days Loss > 0.75%: Daily Return < -0.0075
  - Days Loss > 1%: Daily Return < -0.01
  - Days Gain > 0.5%: Daily Return > 0.005
  - Days Gain > 0.75%: Daily Return > 0.0075
  - Days Gain > 1%: Daily Return > 0.01
- **Starting Capital Based**: Metrics calculated as fixed dollar thresholds based on initial capital
  - Days Loss > 0.5% of Starting Cap: P/L < -(starting_capital × 0.005)
  - Days Loss > 0.75% of Starting Cap: P/L < -(starting_capital × 0.0075)
  - Days Loss > 1% of Starting Cap: P/L < -(starting_capital × 0.01)
  - Days Gain > 0.5% of Starting Cap: P/L > (starting_capital × 0.005)
  - Days Gain > 0.75% of Starting Cap: P/L > (starting_capital × 0.0075)
  - Days Gain > 1% of Starting Cap: P/L > (starting_capital × 0.01)
- **Backend Location**: Calculated inline within `_calculate_drawdown_metrics()` in `portfolio_processor.py`
- **Purpose**: Provides tail risk assessment for extreme loss/gain scenarios with dual perspectives (dynamic vs fixed thresholds)

### Visualization Best Practices
- **Correlation Heatmaps**: Dynamic sizing based on portfolio count (0.5 × n portfolios, max 30 inches)
- **Adaptive Fonts**: Scale automatically based on matrix size (≤10: large, 11-20: medium, >20: small)
- **Annotation Control**: Hide correlation numbers for >20 portfolios (color-only)
- **Label Rotation**: 90° vertical for x-axis to prevent overlap
- **Alphabetical Sorting**: Portfolios sorted alphabetically on both axes for easier lookup
- **Module**: `plotting.py` - `create_correlation_heatmap()`

### Code Quality
- **TypeScript**: Strict type checking enabled for frontend components
- **Error Handling**: Comprehensive error boundaries and validation
- **Testing**: Pytest framework with modular test files for different components

## Database Migrations

The project uses manual SQLAlchemy migrations in the `/migrations/` directory:
- **add_users_table.py**: User authentication tables
- **add_regime_tables.py**: Market regime analysis tables
- **add_margin_tables.py**: Margin requirement tables
- **add_optimization_cache.py**: Optimization result caching
- **add_beta_columns.py**: Beta, alpha, and R-squared metrics
- **add_cvar_column.py**: Conditional Value at Risk (CVaR) metric
- **add_premium_column.py**: Premium data for options strategies
- **add_contracts_column.py**: Contract count tracking
- **add_upi_column.py**: Unique Portfolio Identifier
- **backfill_cvar_values.py**: Historical CVaR data population

**Running Migrations**: Execute migration files directly with `python migrations/filename.py`
# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.