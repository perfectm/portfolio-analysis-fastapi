# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a full-stack portfolio analysis application that provides Monte Carlo simulations, risk metrics calculation, and interactive visualizations for trading strategies. It consists of a FastAPI backend with a React frontend, featuring both individual portfolio analysis and multi-portfolio blending capabilities with custom weighting.

## Development Commands

### Backend (FastAPI)
- **Start development server**: `uvicorn app:app --reload`
- **Run tests**: `pytest` (uses pytest framework)
- **Check specific test files**: `pytest test_app.py`, `pytest test_weighting.py`, etc.

### Frontend (React/TypeScript)
- **Navigate to frontend**: `cd frontend`
- **Install dependencies**: `npm ci`
- **Development server**: `npm run dev` (runs on Vite)
- **Build production**: `npm run build`
- **Lint**: `npm run lint` (ESLint configuration)
- **Preview build**: `npm run preview`

### Database Operations
- **Initialize database**: `python init_db.py` (creates tables)
- **Check database connection**: Use the `/api/debug/database` endpoint
- **Database migrations**: Uses SQLAlchemy with automatic table creation

### Docker & Deployment
- **Local Docker**: `docker-compose up` (builds and runs the full stack)
- **Build for production**: `bash build.sh` (Render deployment script)
- **Dockerfile**: Multi-stage build (Node.js for frontend, Python for backend)

## Architecture Overview

### Backend Structure
- **app.py**: Main FastAPI application with all API endpoints
- **database.py**: Database configuration with PostgreSQL/SQLite fallback
- **models.py**: SQLAlchemy ORM models for portfolios, analysis results, and plots
- **portfolio_service.py**: Service layer for database operations
- **config.py**: Configuration constants and environment settings
- **portfolio_processor.py**: Core data processing logic
- **portfolio_blender.py**: Multi-portfolio blending and weighting logic
- **plotting.py**: Matplotlib/Seaborn chart generation

### Frontend Structure (React + TypeScript + Vite)
- **src/components/**: Reusable UI components (Navigation)
- **src/pages/**: Main application pages (Home, Upload, Portfolios, Analysis)
- **src/services/api.ts**: Axios-based API client
- **Frontend routes**: Handled by React Router with catch-all backend route

### Database Schema
- **portfolios**: Portfolio metadata, file info, date ranges
- **portfolio_data**: Raw CSV data with calculated metrics
- **analysis_results**: Computed risk metrics and parameters
- **analysis_plots**: Generated chart file references
- **blended_portfolios**: Multi-portfolio configurations

## Key Features & Endpoints

### Portfolio Management
- `POST /api/upload`: Upload and analyze CSV files
- `GET /api/strategies`: List all portfolios with analysis summaries
- `DELETE /api/portfolio/{id}`: Delete portfolio and associated data
- `PUT /api/portfolio/{id}/name`: Update portfolio name

### Analysis Endpoints
- `POST /api/analyze-portfolios`: Analyze selected portfolios (equal weighting)
- `POST /api/analyze-portfolios-weighted`: Advanced analysis with custom weights
- `GET /api/strategies/{id}/analysis`: Get analysis history for a portfolio

### File Processing
- **Supported formats**: CSV files with date and P/L columns
- **Date columns**: 'Date Opened', 'Date', 'Trade Date', 'Entry Date', 'Open Date'
- **P/L columns**: 'P/L', 'PnL', 'Profit/Loss', 'Net P/L', 'Realized P/L', 'Total P/L'
- **Charts generated**: Combined analysis plots, correlation heatmaps, Monte Carlo simulations

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
1. Select 2-6 portfolios in the frontend
2. Click "🎯 Optimize Weights" button
3. Algorithm finds weights that maximize return/drawdown ratio
4. Optimal weights are automatically applied
5. Click "Analyze" to see full results with optimized allocation

### Optimization Objective
- **Primary Goal**: Maximize return while minimizing maximum drawdown
- **Objective Function**: Weighted combination of CAGR and inverse drawdown
- **Constraints**: Min weight 5%, Max weight 60% per portfolio
- **Bonus**: Additional scoring for high Sharpe ratios