import React, { useState, useEffect } from "react";
import { api } from "../services/api";
import "./Upload.css"; // Reuse the same CSS as Upload page

interface StrategyOverviewData {
  strategy_name: string;
  portfolios: Array<{
    id: number;
    name: string;
    filename: string;
    upload_date: string | null;
    margin_data: {
      has_margin_data: boolean;
      records_count: number;
      date_range: {
        start: string | null;
        end: string | null;
      };
      margin_range: {
        min: number | null;
        max: number | null;
        avg: number | null;
      };
    };
  }>;
  total_portfolios: number;
  portfolios_with_margin: number;
  total_margin_records: number;
  strategy_margin_range: {
    min: number | null;
    max: number | null;
    avg: number | null;
  };
}

interface StrategiesOverviewResponse {
  success: boolean;
  summary: {
    total_portfolios: number;
    portfolios_with_margin: number;
    strategies_count: number;
    coverage_percentage: number;
  };
  strategies: StrategyOverviewData[];
}


const MarginManagement: React.FC = () => {
  const [message, setMessage] = useState<string>("");
  const [messageType, setMessageType] = useState<"success" | "error" | "">("");
  const [startingCapital, setStartingCapital] = useState<number>(1000000);
  const [maxMarginPercent, setMaxMarginPercent] = useState<number>(85);
  const [strategiesOverview, setStrategiesOverview] = useState<StrategiesOverviewResponse | null>(null);
  const [loadingOverview, setLoadingOverview] = useState<boolean>(true);
  const [collapsedStrategies, setCollapsedStrategies] = useState<string[]>([]);
  const [calculatingAggregates, setCalculatingAggregates] = useState<boolean>(false);

  // Load strategies overview on component mount
  useEffect(() => {
    loadStrategiesOverview();
  }, []);

  const loadStrategiesOverview = async () => {
    try {
      setLoadingOverview(true);
      const response = await api.margin.getStrategiesOverview();
      if (response.success) {
        setStrategiesOverview(response);
      } else {
        console.error('Failed to load strategies overview:', response);
      }
    } catch (error) {
      console.error('Error loading strategies overview:', error);
    } finally {
      setLoadingOverview(false);
    }
  };

  const toggleStrategyCollapsed = (strategyName: string) => {
    setCollapsedStrategies(prev => 
      prev.includes(strategyName)
        ? prev.filter(name => name !== strategyName)
        : [...prev, strategyName]
    );
  };

  const handleRecalculateAggregates = async () => {
    try {
      setCalculatingAggregates(true);
      setMessage("");
      
      const result = await api.margin.recalculateMarginAggregates(
        startingCapital,
        maxMarginPercent / 100
      );

      if (result.success) {
        setMessage(`Successfully recalculated ${result.processed_days} daily aggregates with ${result.validation_failures} validation failures`);
        setMessageType("success");
        
        // Refresh strategies overview to show updated data
        loadStrategiesOverview();
      } else {
        setMessage(`Failed to recalculate aggregates: ${result.message || result.error || "Unknown error"}`);
        setMessageType("error");
      }
    } catch (error: any) {
      console.error("Error recalculating margin aggregates:", error);
      setMessage(`Failed to recalculate aggregates: ${error.message || "Network error"}`);
      setMessageType("error");
    } finally {
      setCalculatingAggregates(false);
    }
  };


  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  return (
    <div className="upload-container">
      <div className="header">
        <h1>📊 Margin Requirements Management</h1>
        <p>
          View and manage margin requirements that are automatically calculated from your portfolio uploads. Margin data is extracted from the 'Margin' or 'Margin Requirement' columns in your CSV files during portfolio upload.
        </p>
        <div style={{ 
          background: '#e3f2fd', 
          padding: '15px', 
          borderRadius: '8px', 
          marginBottom: '20px',
          border: '1px solid #bbdefb'
        }}>
          <h3 style={{ margin: '0 0 10px 0', color: '#1976d2' }}>💡 How Margin Data Works</h3>
          <ul style={{ margin: 0, paddingLeft: '20px' }}>
            <li>Margin requirements are automatically extracted during portfolio upload</li>
            <li>Include a 'Margin', 'Margin Requirement', or similar column in your CSV files</li>
            <li>No separate margin file upload needed - it's all integrated!</li>
            <li>Daily aggregates and validations are calculated automatically</li>
          </ul>
        </div>
      </div>

      {/* Strategies Overview Section */}
      <div className="upload-section">
        <h2>🎯 Strategies Overview</h2>
        {loadingOverview ? (
          <div style={{ textAlign: 'center', padding: '20px', color: '#666' }}>
            Loading strategies overview...
          </div>
        ) : strategiesOverview ? (
          <>
            {/* Summary Stats */}
            <div className="summary-stats" style={{ marginBottom: '20px' }}>
              <div style={{ display: 'flex', gap: '15px', flexWrap: 'wrap', marginBottom: '20px' }}>
                <div style={{ 
                  background: '#e3f2fd', 
                  padding: '15px', 
                  borderRadius: '8px',
                  flex: 1,
                  minWidth: '140px',
                  textAlign: 'center'
                }}>
                  <h3 style={{ margin: '0 0 5px 0', color: '#1565c0' }}>{strategiesOverview.summary.strategies_count}</h3>
                  <p style={{ margin: 0, fontSize: '14px' }}>Strategies</p>
                </div>
                <div style={{ 
                  background: '#f3e5f5', 
                  padding: '15px', 
                  borderRadius: '8px',
                  flex: 1,
                  minWidth: '140px',
                  textAlign: 'center'
                }}>
                  <h3 style={{ margin: '0 0 5px 0', color: '#7b1fa2' }}>{strategiesOverview.summary.total_portfolios}</h3>
                  <p style={{ margin: 0, fontSize: '14px' }}>Total Portfolios</p>
                </div>
                <div style={{ 
                  background: strategiesOverview.summary.portfolios_with_margin > 0 ? '#e8f5e8' : '#ffebee', 
                  padding: '15px', 
                  borderRadius: '8px',
                  flex: 1,
                  minWidth: '140px',
                  textAlign: 'center'
                }}>
                  <h3 style={{ 
                    margin: '0 0 5px 0', 
                    color: strategiesOverview.summary.portfolios_with_margin > 0 ? '#2e7d32' : '#c62828'
                  }}>{strategiesOverview.summary.portfolios_with_margin}</h3>
                  <p style={{ margin: 0, fontSize: '14px' }}>With Margin Data</p>
                </div>
                <div style={{ 
                  background: '#fff3e0', 
                  padding: '15px', 
                  borderRadius: '8px',
                  flex: 1,
                  minWidth: '140px',
                  textAlign: 'center'
                }}>
                  <h3 style={{ margin: '0 0 5px 0', color: '#ef6c00' }}>{strategiesOverview.summary.coverage_percentage.toFixed(1)}%</h3>
                  <p style={{ margin: 0, fontSize: '14px' }}>Coverage</p>
                </div>
              </div>
            </div>

            {/* Strategy Cards */}
            <div className="strategies-list">
              {strategiesOverview.strategies.map((strategy, index) => (
                <div key={strategy.strategy_name} style={{ 
                  background: '#f8f9fa', 
                  border: '1px solid #dee2e6',
                  borderRadius: '8px',
                  marginBottom: '15px'
                }}>
                  {/* Strategy Header */}
                  <div 
                    style={{ 
                      padding: '15px 20px',
                      background: strategy.portfolios_with_margin > 0 ? '#e8f5e8' : '#ffebee',
                      borderRadius: collapsedStrategies.includes(strategy.strategy_name) ? '8px' : '8px 8px 0 0',
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}
                    onClick={() => toggleStrategyCollapsed(strategy.strategy_name)}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                      <h3 style={{ margin: 0, color: '#333' }}>{strategy.strategy_name}</h3>
                      <span style={{
                        background: strategy.portfolios_with_margin > 0 ? '#4caf50' : '#f44336',
                        color: 'white',
                        padding: '4px 12px',
                        borderRadius: '12px',
                        fontSize: '12px',
                        fontWeight: '500'
                      }}>
                        {strategy.portfolios_with_margin}/{strategy.total_portfolios} portfolios
                      </span>
                      {strategy.portfolios_with_margin > 0 && strategy.strategy_margin_range.avg && (
                        <span style={{
                          background: '#2196f3',
                          color: 'white',
                          padding: '4px 12px',
                          borderRadius: '12px',
                          fontSize: '12px',
                          fontWeight: '500'
                        }}>
                          Avg: {formatCurrency(strategy.strategy_margin_range.avg)}
                        </span>
                      )}
                    </div>
                    <span style={{ fontSize: '18px', color: '#666' }}>
                      {collapsedStrategies.includes(strategy.strategy_name) ? '▶' : '▼'}
                    </span>
                  </div>

                  {/* Portfolio Details - shown by default, hidden when collapsed */}
                  {!collapsedStrategies.includes(strategy.strategy_name) && (
                    <div style={{ padding: '0 20px 20px 20px' }}>
                      <div style={{ display: 'grid', gap: '10px' }}>
                        {strategy.portfolios.map((portfolio) => (
                          <div key={portfolio.id} style={{
                            background: 'white',
                            padding: '12px',
                            borderRadius: '6px',
                            border: '1px solid #e9ecef',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center'
                          }}>
                            <div>
                              <div style={{ fontWeight: 'bold', color: '#333' }}>{portfolio.name}</div>
                              <div style={{ fontSize: '12px', color: '#666' }}>{portfolio.filename}</div>
                              {portfolio.upload_date && (
                                <div style={{ fontSize: '11px', color: '#999' }}>
                                  Uploaded: {new Date(portfolio.upload_date).toLocaleDateString()}
                                </div>
                              )}
                            </div>
                            <div style={{ textAlign: 'right' }}>
                              {portfolio.margin_data.has_margin_data ? (
                                <div>
                                  <div style={{ fontWeight: 'bold', color: '#2e7d32', fontSize: '14px' }}>
                                    {portfolio.margin_data.records_count} records
                                  </div>
                                  {portfolio.margin_data.margin_range.avg && (
                                    <div style={{ fontSize: '12px', color: '#666' }}>
                                      Avg: {formatCurrency(portfolio.margin_data.margin_range.avg)}
                                    </div>
                                  )}
                                  {portfolio.margin_data.date_range.start && portfolio.margin_data.date_range.end && (
                                    <div style={{ fontSize: '11px', color: '#999' }}>
                                      {new Date(portfolio.margin_data.date_range.start).toLocaleDateString()} - {new Date(portfolio.margin_data.date_range.end).toLocaleDateString()}
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <div style={{ 
                                  color: '#c62828',
                                  fontSize: '14px',
                                  fontStyle: 'italic'
                                }}>
                                  No margin data
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: '20px', color: '#999' }}>
            Failed to load strategies overview.
          </div>
        )}
      </div>

      {/* Configuration and Actions Section */}
      <div className="upload-section">
        <h2>📈 Margin Configuration & Actions</h2>
        <div className="config-row" style={{ display: 'flex', gap: '20px', marginBottom: '20px', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '200px' }}>
            <label htmlFor="starting-capital">Starting Capital ($):</label>
            <input
              id="starting-capital"
              type="number"
              value={startingCapital}
              onChange={(e) => setStartingCapital(Number(e.target.value))}
              style={{ 
                width: '100%', 
                padding: '8px', 
                marginTop: '5px',
                border: '1px solid #ddd',
                borderRadius: '4px'
              }}
            />
          </div>
          <div style={{ flex: 1, minWidth: '200px' }}>
            <label htmlFor="max-margin">Max Margin Percentage (%):</label>
            <input
              id="max-margin"
              type="number"
              min="0"
              max="100"
              step="1"
              value={maxMarginPercent}
              onChange={(e) => setMaxMarginPercent(Number(e.target.value))}
              style={{ 
                width: '100%', 
                padding: '8px', 
                marginTop: '5px',
                border: '1px solid #ddd',
                borderRadius: '4px'
              }}
            />
          </div>
        </div>
        
        <div style={{ 
          background: '#f8f9fa', 
          padding: '15px', 
          borderRadius: '8px', 
          marginTop: '20px',
          border: '1px solid #dee2e6'
        }}>
          <h3 style={{ margin: '0 0 15px 0', color: '#495057' }}>🔄 Recalculate Margin Aggregates</h3>
          <p style={{ margin: '0 0 15px 0', color: '#6c757d', fontSize: '14px' }}>
            Use the current configuration to recalculate daily margin aggregates for all portfolios with margin data.
            This will update validation results based on your current starting capital and margin percentage limits.
          </p>
          <button
            onClick={handleRecalculateAggregates}
            disabled={calculatingAggregates}
            style={{
              background: calculatingAggregates ? '#6c757d' : '#007bff',
              color: 'white',
              border: 'none',
              padding: '10px 20px',
              borderRadius: '6px',
              fontSize: '14px',
              cursor: calculatingAggregates ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            {calculatingAggregates ? (
              <>
                <span>🔄</span>
                Recalculating...
              </>
            ) : (
              <>
                <span>📊</span>
                Recalculate Aggregates
              </>
            )}
          </button>
        </div>
      </div>


      {message && <div className={`message ${messageType}`}>{message}</div>}
    </div>
  );
};

export default MarginManagement;