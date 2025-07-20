import { useState, useEffect } from "react";
import { portfolioAPI } from "../services/api";

interface Portfolio {
  id: number;
  name: string;
  filename: string;
  upload_date: string;
  row_count: number;
  date_range_start?: string;
  date_range_end?: string;
}

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

interface AnalysisResults {
  success: boolean;
  message: string;
  individual_results?: AnalysisResult[];
  blended_result?: AnalysisResult | null;
  multiple_portfolios?: boolean;
}

export default function Portfolios() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPortfolios, setSelectedPortfolios] = useState<number[]>([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResults, setAnalysisResults] =
    useState<AnalysisResults | null>(null);

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
        setError(response.error || "Failed to fetch portfolios");
      }
    } catch (err) {
      setError("Failed to fetch portfolios");
      console.error("Error fetching portfolios:", err);
    } finally {
      setLoading(false);
    }
  };

  const deletePortfolio = async (id: number) => {
    if (!confirm("Are you sure you want to delete this portfolio?")) return;

    try {
      const response = await portfolioAPI.deletePortfolio(id);
      if (response.success) {
        setPortfolios(portfolios.filter((p) => p.id !== id));
        // Remove from selected portfolios if it was selected
        setSelectedPortfolios(selectedPortfolios.filter((pid) => pid !== id));
      } else {
        alert(response.error || "Failed to delete portfolio");
      }
    } catch (err) {
      alert("Failed to delete portfolio");
      console.error("Error deleting portfolio:", err);
    }
  };

  const togglePortfolioSelection = (id: number) => {
    setSelectedPortfolios((prev) =>
      prev.includes(id) ? prev.filter((pid) => pid !== id) : [...prev, id]
    );
  };

  const selectAllPortfolios = () => {
    setSelectedPortfolios(portfolios.map((p) => p.id));
  };

  const clearSelection = () => {
    setSelectedPortfolios([]);
  };

  const analyzeSelectedPortfolios = async () => {
    if (selectedPortfolios.length === 0) {
      alert("Please select at least one portfolio to analyze");
      return;
    }

    setAnalyzing(true);
    setAnalysisResults(null);

    try {
      // Call the backend API to analyze selected portfolios
      const response = await fetch(
        `${
          import.meta.env.VITE_API_URL || window.location.origin
        }/api/analyze-portfolios`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            portfolio_ids: selectedPortfolios,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          `Analysis failed: ${response.status} ${response.statusText}`
        );
      }

      const results = await response.json();
      setAnalysisResults(results);
    } catch (error) {
      console.error("Analysis failed:", error);
      alert(
        `Analysis failed: ${
          error instanceof Error ? error.message : "Unknown error"
        }`
      );
    } finally {
      setAnalyzing(false);
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
        <>
          {/* Selection Controls */}
          <div
            className="selection-controls"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "1rem",
              marginBottom: "1.5rem",
              padding: "1rem",
              background: "#f8f9fa",
              borderRadius: "8px",
              border: "1px solid #e9ecef",
            }}
          >
            <div
              style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}
            >
              <strong>
                Selected: {selectedPortfolios.length} / {portfolios.length}
              </strong>
            </div>
            <button
              onClick={selectAllPortfolios}
              className="btn btn-secondary"
              style={{ padding: "0.5rem 1rem", fontSize: "0.9rem" }}
            >
              Select All
            </button>
            <button
              onClick={clearSelection}
              className="btn btn-secondary"
              style={{ padding: "0.5rem 1rem", fontSize: "0.9rem" }}
            >
              Clear Selection
            </button>
            <button
              onClick={analyzeSelectedPortfolios}
              disabled={selectedPortfolios.length === 0 || analyzing}
              className="btn btn-primary"
              style={{
                padding: "0.5rem 1.5rem",
                fontSize: "0.9rem",
                marginLeft: "auto",
                opacity: selectedPortfolios.length === 0 ? 0.5 : 1,
              }}
            >
              {analyzing
                ? "Analyzing..."
                : `Analyze ${selectedPortfolios.length} Portfolio${
                    selectedPortfolios.length !== 1 ? "s" : ""
                  }`}
            </button>
          </div>

          <div className="portfolios-grid">
            {portfolios.map((portfolio) => (
              <div
                key={portfolio.id}
                className="portfolio-card"
                style={{
                  border: selectedPortfolios.includes(portfolio.id)
                    ? "2px solid #007bff"
                    : "1px solid #e9ecef",
                  background: selectedPortfolios.includes(portfolio.id)
                    ? "#f0f8ff"
                    : "#fff",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    marginBottom: "1rem",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selectedPortfolios.includes(portfolio.id)}
                    onChange={() => togglePortfolioSelection(portfolio.id)}
                    style={{
                      marginRight: "0.75rem",
                      transform: "scale(1.2)",
                      cursor: "pointer",
                    }}
                  />
                  <h3 style={{ margin: 0, flex: 1 }}>{portfolio.name}</h3>
                </div>
                <p>
                  <strong>File:</strong> {portfolio.filename}
                </p>
                <p>
                  <strong>Uploaded:</strong>{" "}
                  {new Date(portfolio.upload_date).toLocaleDateString()}
                </p>
                <p>
                  <strong>Records:</strong> {portfolio.row_count}
                </p>
                {portfolio.date_range_start && portfolio.date_range_end && (
                  <p>
                    <strong>Date Range:</strong>{" "}
                    {new Date(portfolio.date_range_start).toLocaleDateString()}{" "}
                    - {new Date(portfolio.date_range_end).toLocaleDateString()}
                  </p>
                )}

                <div className="portfolio-actions">
                  <button
                    onClick={() =>
                      window.open(`/portfolio/${portfolio.id}`, "_blank")
                    }
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

          {/* Analysis Results */}
          {analysisResults && (
            <div
              className="analysis-results"
              style={{
                marginTop: "2rem",
                padding: "1.5rem",
                background: "#f8f9fa",
                borderRadius: "8px",
                border: "1px solid #e9ecef",
              }}
            >
              <h2>📊 Analysis Results</h2>

              {/* Individual Portfolio Results */}
              {analysisResults.individual_results &&
                analysisResults.individual_results.length > 0 && (
                  <div className="individual-results">
                    <h3>Individual Portfolio Analysis</h3>
                    <div
                      className="results-grid"
                      style={{
                        display: "grid",
                        gridTemplateColumns:
                          "repeat(auto-fit, minmax(350px, 1fr))",
                        gap: "1.5rem",
                        marginBottom: "2rem",
                      }}
                    >
                      {analysisResults.individual_results.map(
                        (result, index) => (
                          <div
                            key={index}
                            className="result-card"
                            style={{
                              background: "#fff",
                              padding: "1.5rem",
                              borderRadius: "8px",
                              boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                              border: "1px solid #e9ecef",
                            }}
                          >
                            <h4>{result.filename}</h4>
                            <div
                              className="metrics"
                              style={{
                                display: "grid",
                                gridTemplateColumns:
                                  "repeat(auto-fit, minmax(150px, 1fr))",
                                gap: "0.75rem",
                                marginBottom: "1rem",
                              }}
                            >
                              <div className="metric">
                                <label>Total Return:</label>
                                <span>
                                  {(result.metrics.total_return * 100).toFixed(
                                    2
                                  )}
                                  %
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
                                  {result.metrics.sharpe_ratio?.toFixed(3) ||
                                    "N/A"}
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
                                <div
                                  className="plots-grid"
                                  style={{
                                    display: "grid",
                                    gridTemplateColumns:
                                      "repeat(auto-fit, minmax(200px, 1fr))",
                                    gap: "1rem",
                                  }}
                                >
                                  {result.plots.map((plot, plotIndex) => (
                                    <div key={plotIndex} className="plot-item">
                                      <img
                                        src={plot.url}
                                        alt={plot.filename}
                                        style={{
                                          width: "100%",
                                          height: "auto",
                                          borderRadius: "4px",
                                        }}
                                        onError={(e) => {
                                          e.currentTarget.style.display =
                                            "none";
                                        }}
                                      />
                                      <p
                                        style={{
                                          margin: "0.5rem 0 0 0",
                                          fontSize: "0.9rem",
                                          color: "#666",
                                        }}
                                      >
                                        {plot.filename}
                                      </p>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        )
                      )}
                    </div>
                  </div>
                )}

              {/* Blended Portfolio Results */}
              {analysisResults.blended_result && (
                <div className="blended-results">
                  <h3>🔀 Blended Portfolio Analysis</h3>
                  <div
                    className="result-card blended"
                    style={{
                      background: "#fff",
                      padding: "1.5rem",
                      borderRadius: "8px",
                      boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                      border: "2px solid #28a745",
                    }}
                  >
                    <h4>{analysisResults.blended_result.filename}</h4>
                    <div
                      className="metrics"
                      style={{
                        display: "grid",
                        gridTemplateColumns:
                          "repeat(auto-fit, minmax(150px, 1fr))",
                        gap: "0.75rem",
                        marginBottom: "1rem",
                      }}
                    >
                      <div className="metric">
                        <label>Total Return:</label>
                        <span>
                          {(
                            analysisResults.blended_result.metrics
                              .total_return * 100
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
                          <div
                            className="plots-grid"
                            style={{
                              display: "grid",
                              gridTemplateColumns:
                                "repeat(auto-fit, minmax(200px, 1fr))",
                              gap: "1rem",
                            }}
                          >
                            {analysisResults.blended_result.plots.map(
                              (plot, plotIndex) => (
                                <div key={plotIndex} className="plot-item">
                                  <img
                                    src={plot.url}
                                    alt={plot.filename}
                                    style={{
                                      width: "100%",
                                      height: "auto",
                                      borderRadius: "4px",
                                    }}
                                    onError={(e) => {
                                      e.currentTarget.style.display = "none";
                                    }}
                                  />
                                  <p
                                    style={{
                                      margin: "0.5rem 0 0 0",
                                      fontSize: "0.9rem",
                                      color: "#666",
                                    }}
                                  >
                                    {plot.filename}
                                  </p>
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
              <div className="results-actions" style={{ marginTop: "1.5rem" }}>
                <button
                  onClick={() => setAnalysisResults(null)}
                  className="btn btn-secondary"
                >
                  Clear Results
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
