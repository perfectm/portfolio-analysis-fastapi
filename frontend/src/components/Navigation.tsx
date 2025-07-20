import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import './Navigation.css';

const Navigation: React.FC = () => {
  const location = useLocation();

  const isActive = (path: string) => {
    return location.pathname === path ? 'nav-link active' : 'nav-link';
  };

  return (
    <nav className="navigation">
      <div className="nav-container">
        <Link to="/" className="nav-brand">
          Portfolio Analysis
        </Link>
        <ul className="nav-menu">
          <li className="nav-item">
            <Link to="/" className={isActive('/')}>
              Home
            </Link>
          </li>
          <li className="nav-item">
            <Link to="/upload" className={isActive('/upload')}>
              Upload
            </Link>
          </li>
          <li className="nav-item">
            <Link to="/portfolios" className={isActive('/portfolios')}>
              Portfolios
            </Link>
          </li>
        </ul>
      </div>
    </nav>
  );
};

export default Navigation;
