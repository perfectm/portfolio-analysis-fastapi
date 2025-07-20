import React, { useState } from "react";
import { portfolioAPI } from "../services/api";
import "./Upload.css";

interface AnalysisResult {
  filename: string;
  metrics: {
    sharpe_ratio: number;
    total_return: number;
    total_pl: number;
    final_account_value: number;
    max_drawdown: number;
    max_drawdown_percent: number;
    cagr: number;
    annual_volatility: number;
    [key: string]: any;
  };
  plots: Array<{
    filename: string;
    url: string;
  }>;
}

interface UploadResult {
  success: boolean;
  message: string;
  portfolio_ids: number[];
  individual_results: AnalysisResult[];
  blended_result: AnalysisResult | null;
  multiple_portfolios: boolean;
}

const Upload: React.FC = () => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [messageType, setMessageType] = useState<"success" | "error" | "">("");
  const [analysisResults, setAnalysisResults] = useState<UploadResult | null>(
    null
  );

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    if (files.length > 0) {
      const csvFiles = files.filter(
        (file) => file.type === "text/csv" || file.name.endsWith(".csv")
      );

      if (csvFiles.length !== files.length) {
        setMessage(
          "Only CSV files are allowed. Non-CSV files have been removed."
        );
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
      setMessage("Please select at least one CSV file");
      setMessageType("error");
      return;
    }

    console.log("[Upload] Starting upload process:", {
      fileCount: selectedFiles.length,
      files: selectedFiles.map((f) => ({
        name: f.name,
        size: f.size,
        type: f.type,
      })),
    });

    setUploading(true);
    setMessage("");

    try {
      let result;

      if (selectedFiles.length === 1) {
        // Single file upload
        console.log("[Upload] Performing single file upload");
        result = await portfolioAPI.uploadPortfolio(selectedFiles[0]);
        console.log("[Upload] Single file upload result:", result);

        // Check if we got analysis results
        if (result.individual_results || result.blended_result) {
          setAnalysisResults(result as UploadResult);
          setMessage(
            `Upload and analysis completed! Portfolio ID: ${result.portfolio_id}`
          );
        } else {
          setMessage(`Upload successful! Portfolio ID: ${result.portfolio_id}`);
        }
        setMessageType("success");
      } else {
        // Multiple file upload
        console.log("[Upload] Performing multiple file upload");
        result = await portfolioAPI.uploadMultiplePortfolios(selectedFiles);
        console.log("[Upload] Multiple file upload result:", result);

        // Check if we got analysis results
        if (result.individual_results || result.blended_result) {
          setAnalysisResults(result as UploadResult);
          setMessage(
            `Upload and analysis completed! Uploaded ${selectedFiles.length} portfolios with full analysis.`
          );
        } else {
          setMessage(
            `Upload successful! Uploaded ${selectedFiles.length} portfolios.`
          );
        }
        setMessageType("success");
      }

      setSelectedFiles([]);
      // Reset file input
      const fileInput = document.getElementById(
        "file-input"
      ) as HTMLInputElement;
      if (fileInput) fileInput.value = "";
    } catch (error) {
      console.error("[Upload] Upload failed with error:", error);

      // Extract more detailed error information
      let errorMessage = "Unknown error";
      if (error instanceof Error) {
        errorMessage = error.message;
        console.error("[Upload] Error details:", {
          name: error.name,
          message: error.message,
          stack: error.stack,
        });
      } else {
        console.error("[Upload] Non-Error object thrown:", error);
        errorMessage = String(error);
      }

      setMessage(`Upload failed: ${errorMessage}`);
      setMessageType("error");
    } finally {
      setUploading(false);
    }
  };

  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault();
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) {
      const csvFiles = files.filter(
        (file) => file.type === "text/csv" || file.name.endsWith(".csv")
      );

      if (csvFiles.length !== files.length) {
        setMessage(
          "Only CSV files are allowed. Non-CSV files have been removed."
        );
        setMessageType("error");
      } else {
        setMessage("");
      }

      setSelectedFiles((prev) => [...prev, ...csvFiles]);
    }
  };

  return (
    <div className="upload">
      <div className="upload-container">
        <h1>Upload Portfolio CSV Files</h1>
        <p className="upload-description">
          Upload one or more trading portfolio CSV files to get detailed
          analytics and insights. Multiple files will be analyzed individually
          and can be blended together for comparison.
        </p>

        <div
          className={`upload-area ${
            selectedFiles.length > 0 ? "has-file" : ""
          }`}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <div className="upload-content">
            <div className="upload-icon">📁</div>
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
                <h3>Drag and drop your CSV files here</h3>
                <p>or click to select files (multiple selection supported)</p>
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

        {message && <div className={`message ${messageType}`}>{message}</div>}

        {/* Analysis Results Display */}
        {analysisResults && (
          <div className="analysis-results">
            <h2>📊 Analysis Results</h2>

            {/* Individual Portfolio Results */}
            {analysisResults.individual_results &&
              analysisResults.individual_results.length > 0 && (
                <div className="individual-results">
                  <h3>Individual Portfolio Analysis</h3>
                  <div className="results-grid">
                    {analysisResults.individual_results.map((result, index) => (
                      <div key={index} className="result-card">
                        <h4>{result.filename}</h4>
                        <div className="metrics">
                          <div className="metric">
                            <label>Total Return:</label>
                            <span>
                              {(result.metrics.total_return * 100).toFixed(2)}%
                            </span>
                          </div>
                          <div className="metric">
                            <label>Total P&L:</label>
                            <span>
                              $
                              {result.metrics.total_pl?.toLocaleString() ||
                                "N/A"}
                            </span>
                          </div>
                          <div className="metric">
                            <label>Sharpe Ratio:</label>
                            <span>
                              {result.metrics.sharpe_ratio?.toFixed(3) || "N/A"}
                            </span>
                          </div>
                          <div className="metric">
                            <label>Max Drawdown:</label>
                            <span>
                              {(
                                result.metrics.max_drawdown_percent * 100
                              ).toFixed(2)}
                              %
                            </span>
                          </div>
                          <div className="metric">
                            <label>CAGR:</label>
                            <span>
                              {(result.metrics.cagr * 100).toFixed(2)}%
                            </span>
                          </div>
                          <div className="metric">
                            <label>Final Account Value:</label>
                            <span>
                              $
                              {result.metrics.final_account_value?.toLocaleString() ||
                                "N/A"}
                            </span>
                          </div>
                        </div>

                        {/* Display plots if available */}
                        {result.plots && result.plots.length > 0 && (
                          <div className="plots">
                            <h5>Charts:</h5>
                            <div className="plots-grid">
                              {result.plots.map((plot, plotIndex) => (
                                <div key={plotIndex} className="plot-item">
                                  <img
                                    src={plot.url}
                                    alt={plot.filename}
                                    onError={(e) => {
                                      e.currentTarget.style.display = "none";
                                    }}
                                  />
                                  <p>{plot.filename}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

            {/* Blended Portfolio Results */}
            {analysisResults.blended_result && (
              <div className="blended-results">
                <h3>🔀 Blended Portfolio Analysis</h3>
                <div className="result-card blended">
                  <h4>{analysisResults.blended_result.filename}</h4>
                  <div className="metrics">
                    <div className="metric">
                      <label>Total Return:</label>
                      <span>
                        {(
                          analysisResults.blended_result.metrics.total_return *
                          100
                        ).toFixed(2)}
                        %
                      </span>
                    </div>
                    <div className="metric">
                      <label>Total P&L:</label>
                      <span>
                        $
                        {analysisResults.blended_result.metrics.total_pl?.toLocaleString() ||
                          "N/A"}
                      </span>
                    </div>
                    <div className="metric">
                      <label>Sharpe Ratio:</label>
                      <span>
                        {analysisResults.blended_result.metrics.sharpe_ratio?.toFixed(
                          3
                        ) || "N/A"}
                      </span>
                    </div>
                    <div className="metric">
                      <label>Max Drawdown:</label>
                      <span>
                        {(
                          analysisResults.blended_result.metrics
                            .max_drawdown_percent * 100
                        ).toFixed(2)}
                        %
                      </span>
                    </div>
                    <div className="metric">
                      <label>CAGR:</label>
                      <span>
                        {(
                          analysisResults.blended_result.metrics.cagr * 100
                        ).toFixed(2)}
                        %
                      </span>
                    </div>
                    <div className="metric">
                      <label>Final Account Value:</label>
                      <span>
                        $
                        {analysisResults.blended_result.metrics.final_account_value?.toLocaleString() ||
                          "N/A"}
                      </span>
                    </div>
                  </div>

                  {/* Display blended portfolio plots */}
                  {analysisResults.blended_result.plots &&
                    analysisResults.blended_result.plots.length > 0 && (
                      <div className="plots">
                        <h5>Charts:</h5>
                        <div className="plots-grid">
                          {analysisResults.blended_result.plots.map(
                            (plot, plotIndex) => (
                              <div key={plotIndex} className="plot-item">
                                <img
                                  src={plot.url}
                                  alt={plot.filename}
                                  onError={(e) => {
                                    e.currentTarget.style.display = "none";
                                  }}
                                />
                                <p>{plot.filename}</p>
                              </div>
                            )
                          )}
                        </div>
                      </div>
                    )}
                </div>
              </div>
            )}

            {/* Clear Results Button */}
            <div className="results-actions">
              <button
                onClick={() => setAnalysisResults(null)}
                className="btn btn-secondary"
              >
                Clear Results
              </button>
            </div>
          </div>
        )}

        <div className="upload-actions">
          <button
            onClick={handleUpload}
            disabled={selectedFiles.length === 0 || uploading}
            className={`btn btn-primary ${uploading ? "loading" : ""}`}
          >
            {uploading
              ? "Uploading..."
              : selectedFiles.length === 1
              ? "Upload Portfolio"
              : `Upload ${selectedFiles.length} Portfolios`}
          </button>
        </div>

        <div className="upload-info">
          <h3>CSV Format Requirements:</h3>
          <ul>
            <li>Files must be in CSV format (.csv)</li>
            <li>
              Should contain trading data with columns for dates, trades, P&L,
              etc.
            </li>
            <li>Maximum file size per file: 10MB</li>
            <li>
              Multiple files will be analyzed individually and can be blended
              for comparison
            </li>
            <li>Ensure data is properly formatted for accurate analysis</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default Upload;
