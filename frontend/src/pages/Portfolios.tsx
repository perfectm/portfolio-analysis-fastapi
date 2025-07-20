import { useState, useEffect } from 'react';
import { portfolioAPI } from '../services/api';

interface Portfolio {
  id: number;
  name: string;
  filename: string;
  upload_date: string;
  row_count: number;
  date_range_start?: string;
  date_range_end?: string;
}

export default function Portfolios() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPortfolios();
  }, []);

  const fetchPortfolios = async () => {
    try {
      setLoading(true);
      const response = await portfolioAPI.getStrategiesList();
      if (response.success) {
        setPortfolios(response.strategies);
      } else {
        setError(response.error || 'Failed to fetch portfolios');
      }
    } catch (err) {
      setError('Failed to fetch portfolios');
      console.error('Error fetching portfolios:', err);
    } finally {
      setLoading(false);
    }
  };

  const deletePortfolio = async (id: number) => {
    if (!confirm('Are you sure you want to delete this portfolio?')) return;
    
    try {
      const response = await portfolioAPI.deletePortfolio(id);
      if (response.success) {
        setPortfolios(portfolios.filter(p => p.id !== id));
      } else {
        alert(response.error || 'Failed to delete portfolio');
      }
    } catch (err) {
      alert('Failed to delete portfolio');
      console.error('Error deleting portfolio:', err);
    }
  };

  if (loading) return <div className="loading">Loading portfolios...</div>;
  if (error) return <div className="error">Error: {error}</div>;

  return (
    <div className="portfolios-page">
      <h1>Portfolio Management</h1>
      
      {portfolios.length === 0 ? (
        <div className="no-portfolios">
          <p>No portfolios found. Upload a portfolio to get started.</p>
        </div>
      ) : (
        <div className="portfolios-grid">
          {portfolios.map((portfolio) => (
            <div key={portfolio.id} className="portfolio-card">
              <h3>{portfolio.name}</h3>
              <p><strong>File:</strong> {portfolio.filename}</p>
              <p><strong>Uploaded:</strong> {new Date(portfolio.upload_date).toLocaleDateString()}</p>
              <p><strong>Records:</strong> {portfolio.row_count}</p>
              {portfolio.date_range_start && portfolio.date_range_end && (
                <p><strong>Date Range:</strong> {new Date(portfolio.date_range_start).toLocaleDateString()} - {new Date(portfolio.date_range_end).toLocaleDateString()}</p>
              )}
              
              <div className="portfolio-actions">
                <button 
                  onClick={() => window.open(`/portfolio/${portfolio.id}`, '_blank')}
                  className="btn-primary"
                >
                  View Data
                </button>
                <button 
                  onClick={() => deletePortfolio(portfolio.id)}
                  className="btn-danger"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
