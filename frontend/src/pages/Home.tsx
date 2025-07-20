import React from "react";
import { Link } from "react-router-dom";
import "./Home.css";

const Home: React.FC = () => {
  return (
    <div className="home">
      <div className="hero-section">
        <h1>Portfolio Analysis Dashboard</h1>
        <p className="hero-description">
          Analyze your trading portfolios with comprehensive metrics,
          visualizations, and insights. Upload your CSV files and get detailed
          performance analytics.
        </p>
        <div className="hero-actions">
          <Link to="/upload" className="btn btn-primary">
            Upload Portfolio
          </Link>
          <Link to="/portfolios" className="btn btn-secondary">
            View Portfolios
          </Link>
        </div>
      </div>

      <div className="features-section">
        <h2>Features</h2>
        <div className="features-grid">
          <div className="feature-card">
            <h3>📊 Performance Analytics</h3>
            <p>
              Comprehensive analysis of your trading performance including P&L,
              win rates, and Sharpe ratios.
            </p>
          </div>
          <div className="feature-card">
            <h3>📈 Visualizations</h3>
            <p>
              Interactive charts and graphs to visualize your portfolio
              performance over time.
            </p>
          </div>
          <div className="feature-card">
            <h3>📋 Portfolio Management</h3>
            <p>
              Upload, manage, and compare multiple portfolios in one centralized
              dashboard.
            </p>
          </div>
          <div className="feature-card">
            <h3>🔍 Risk Analysis</h3>
            <p>
              Detailed risk metrics including maximum drawdown and trade
              distribution analysis.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Home;
