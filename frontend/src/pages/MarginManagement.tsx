import React, { useState } from "react";
import { api } from "../services/api";
import "./Upload.css"; // Reuse the same CSS as Upload page

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