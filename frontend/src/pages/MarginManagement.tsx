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

interface MarginUploadResult {
  success: boolean;
  message: string;
  processed_files: number;
  failed_files: number;
  files_detail: {
    processed: Array<{
      filename: string;
      portfolio_id: number;
      portfolio_name: string;
      margin_records: number;
      date_range: {
        start: string;
        end: string;
      };
      margin_range: {
        min: number;
        max: number;
        average: number;
      };
      daily_stats?: {
        total_trading_days: number;
        records_per_day: number;
      };
    }>;
    failed: Array<{
      filename: string;
      error: string;
    }>;
  };
  aggregation_result?: any;
}

const MarginManagement: React.FC = () => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [messageType, setMessageType] = useState<"success" | "error" | "">("");
  const [uploadResult, setUploadResult] = useState<MarginUploadResult | null>(null);
  const [startingCapital, setStartingCapital] = useState<number>(1000000);
  const [maxMarginPercent, setMaxMarginPercent] = useState<number>(85);
  const [strategiesOverview, setStrategiesOverview] = useState<StrategiesOverviewResponse | null>(null);
  const [loadingOverview, setLoadingOverview] = useState<boolean>(true);
  const [collapsedStrategies, setCollapsedStrategies] = useState<string[]>([]);

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

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    if (files.length > 0) {
      const csvFiles = files.filter(
        (file) => file.type === "text/csv" || file.name.endsWith(".csv")
      );

      if (csvFiles.length !== files.length) {
        setMessage("Only CSV files are allowed. Non-CSV files have been removed.");
        setMessageType("error");
      } else {
        setMessage("");
      }

      setSelectedFiles(csvFiles);
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles((files) => files.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      setMessage("Please select at least one margin CSV file");
      setMessageType("error");
      return;
    }

    console.log("[Margin Upload] Starting upload process:", {
      fileCount: selectedFiles.length,
      startingCapital,
      maxMarginPercent,
    });

    setUploading(true);
    setMessage("");
    setUploadResult(null);

    try {
      const fileList = new DataTransfer();
      selectedFiles.forEach(file => fileList.items.add(file));

      const result = await api.margin.bulkUploadMargin(
        fileList.files,
        startingCapital,
        maxMarginPercent / 100
      );

      console.log("[Margin Upload] Upload result:", result);

      if (result.success) {
        setUploadResult(result);
        setMessage(`Successfully processed ${result.processed_files} of ${selectedFiles.length} margin files`);
        setMessageType("success");
        setSelectedFiles([]); // Clear files after successful upload
        
        // Clear the file input
        const fileInput = document.getElementById("file-input") as HTMLInputElement;
        if (fileInput) fileInput.value = "";

        // Refresh strategies overview
        loadStrategiesOverview();
      } else {
        setMessage(`Upload failed: ${result.message || "Unknown error"}`);
        setMessageType("error");
      }
    } catch (error: any) {
      console.error("[Margin Upload] Upload error:", error);
      setMessage(`Upload failed: ${error.message || "Network error"}`);
      setMessageType("error");
    } finally {
      setUploading(false);
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
          Upload margin requirement files for your trading strategies. Files will be automatically matched to existing portfolios by filename.
        </p>
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

      {/* Configuration Section */}
      <div className="upload-section">
        <h2>Configuration</h2>
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
      </div>

      {/* File Upload Section */}
      <div className="upload-section">
        <h2>Upload Margin Files</h2>
        <div className="upload-area">
          <div className="file-drop-zone">
            {selectedFiles.length > 0 ? (
              <div className="files-info">
                <h3>Selected Files ({selectedFiles.length}):</h3>
                <div className="files-list">
                  {selectedFiles.map((file, index) => (
                    <div key={index} className="file-item">
                      <div className="file-details">
                        <p className="file-name">{file.name}</p>
                        <p className="file-size">
                          Size: {(file.size / 1024).toFixed(2)} KB
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeFile(index)}
                        className="remove-file-btn"
                        title="Remove file"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="upload-text">
                <h3>Drag and drop your margin CSV files here</h3>
                <p>or click to select files (multiple selection supported)</p>
                <details style={{ fontSize: '14px', color: '#666', marginTop: '10px' }}>
                  <summary style={{ cursor: 'pointer', userSelect: 'none' }}>
                    ℹ️ Expected CSV Format (click to expand)
                  </summary>
                  <div style={{ marginTop: '10px', background: '#f8f9fa', padding: '10px', borderRadius: '4px', fontSize: '12px' }}>
                    <p><strong>Required columns (flexible naming):</strong></p>
                    <p>• <strong>Date:</strong> Date, Date Opened, Trade Date, Entry Date, etc.</p>
                    <p>• <strong>Margin:</strong> Margin, Margin Requirement, Initial Margin, Required Margin, etc.</p>
                    <p><strong>Example CSV content:</strong></p>
                    <pre style={{ background: '#fff', padding: '5px', border: '1px solid #ddd', fontSize: '11px' }}>
Date,Margin Requirement,Margin Type{'\n'}2024-01-01,15000,initial{'\n'}2024-01-02,18500,initial{'\n'}2024-01-03,22000,initial
                    </pre>
                    <p style={{ marginTop: '5px' }}><em>Note: Column matching is case-insensitive and flexible</em></p>
                  </div>
                </details>
              </div>
            )}
            <input
              id="file-input"
              type="file"
              accept=".csv"
              multiple
              onChange={handleFileSelect}
              className="file-input"
            />
          </div>
        </div>

        <div className="upload-actions">
          <button
            onClick={handleUpload}
            disabled={selectedFiles.length === 0 || uploading}
            className="upload-btn"
          >
            {uploading ? "Uploading..." : `Upload ${selectedFiles.length} File${selectedFiles.length === 1 ? "" : "s"}`}
          </button>
        </div>
      </div>

      {message && <div className={`message ${messageType}`}>{message}</div>}

      {/* Upload Results Display */}
      {uploadResult && (
        <div className="analysis-results">
          <h2>📊 Margin Upload Results</h2>

          {/* Summary Stats */}
          <div className="upload-summary" style={{ marginBottom: '20px' }}>
            <div className="summary-cards" style={{ display: 'flex', gap: '15px', flexWrap: 'wrap' }}>
              <div className="summary-card" style={{ 
                background: '#e8f5e8', 
                padding: '15px', 
                borderRadius: '8px',
                flex: 1,
                minWidth: '150px',
                textAlign: 'center'
              }}>
                <h3 style={{ margin: '0 0 5px 0', color: '#2e7d32' }}>{uploadResult.processed_files}</h3>
                <p style={{ margin: 0, fontSize: '14px' }}>Files Processed</p>
              </div>
              <div className="summary-card" style={{ 
                background: uploadResult.failed_files > 0 ? '#ffebee' : '#f5f5f5', 
                padding: '15px', 
                borderRadius: '8px',
                flex: 1,
                minWidth: '150px',
                textAlign: 'center'
              }}>
                <h3 style={{ 
                  margin: '0 0 5px 0', 
                  color: uploadResult.failed_files > 0 ? '#c62828' : '#666' 
                }}>{uploadResult.failed_files}</h3>
                <p style={{ margin: 0, fontSize: '14px' }}>Failed Files</p>
              </div>
            </div>
          </div>

          {/* Processed Files */}
          {uploadResult.files_detail.processed.length > 0 && (
            <div className="processed-files">
              <h3>✅ Successfully Processed Files</h3>
              <div className="results-grid">
                {uploadResult.files_detail.processed.map((file, index) => (
                  <div key={index} className="result-card">
                    <h4>{file.filename}</h4>
                    <div className="metrics">
                      <div className="metric">
                        <label>Portfolio:</label>
                        <span>{file.portfolio_name}</span>
                      </div>
                      <div className="metric">
                        <label>Margin Records:</label>
                        <span>{file.margin_records}</span>
                      </div>
                      <div className="metric">
                        <label>Date Range:</label>
                        <span>
                          {new Date(file.date_range.start).toLocaleDateString()} - {new Date(file.date_range.end).toLocaleDateString()}
                        </span>
                      </div>
                      <div className="metric">
                        <label>Avg Daily Margin:</label>
                        <span>{formatCurrency(file.margin_range.average)}</span>
                      </div>
                      <div className="metric">
                        <label>Max Daily Margin:</label>
                        <span>{formatCurrency(file.margin_range.max)}</span>
                      </div>
                      {file.daily_stats && (
                        <>
                          <div className="metric">
                            <label>Trading Days:</label>
                            <span>{file.daily_stats.total_trading_days}</span>
                          </div>
                          <div className="metric">
                            <label>Records/Day:</label>
                            <span>{file.daily_stats.records_per_day.toFixed(1)}</span>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Failed Files */}
          {uploadResult.files_detail.failed.length > 0 && (
            <div className="failed-files" style={{ marginTop: '20px' }}>
              <h3>❌ Failed Files</h3>
              <div className="failed-list">
                {uploadResult.files_detail.failed.map((file, index) => (
                  <div key={index} className="failed-item" style={{ 
                    background: '#ffebee', 
                    padding: '10px', 
                    marginBottom: '10px',
                    borderRadius: '4px',
                    border: '1px solid #ffcdd2'
                  }}>
                    <strong>{file.filename}</strong>
                    <p style={{ margin: '5px 0 0 0', color: '#c62828' }}>{file.error}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Aggregation Results */}
          {uploadResult.aggregation_result && uploadResult.aggregation_result.success && (
            <div className="aggregation-results" style={{ marginTop: '20px' }}>
              <h3>📈 Daily Margin Aggregation</h3>
              <div style={{ background: '#f8f9fa', padding: '15px', borderRadius: '8px' }}>
                <p><strong>Processed Days:</strong> {uploadResult.aggregation_result.processed_days}</p>
                <p><strong>Validation Failures:</strong> {uploadResult.aggregation_result.validation_failures}</p>
                <p><strong>Starting Capital:</strong> {formatCurrency(uploadResult.aggregation_result.starting_capital)}</p>
                <p><strong>Max Margin Allowed:</strong> {(uploadResult.aggregation_result.max_margin_percent * 100).toFixed(0)}%</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default MarginManagement;