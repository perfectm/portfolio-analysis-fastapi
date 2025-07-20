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
  advanced_plots?: {
    correlation_heatmap?: string | null;
    monte_carlo_simulation?: string | null;
  };
}

export default function Portfolios() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPortfolios, setSelectedPortfolios] = useState<number[]>([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResults, setAnalysisResults] =
    useState<AnalysisResults | null>(null);
  const [editingPortfolioId, setEditingPortfolioId] = useState<number | null>(
    null
  );
  const [editingName, setEditingName] = useState<string>("");

  // Force a fresh deployment with checkboxes

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

  const startRenaming = (portfolio: Portfolio) => {
    setEditingPortfolioId(portfolio.id);
    setEditingName(portfolio.name);
  };

  const cancelRenaming = () => {
    setEditingPortfolioId(null);
    setEditingName("");
  };

  const saveRename = async (portfolioId: number) => {
    if (!editingName.trim()) {
      alert("Portfolio name cannot be empty");
      return;
    }

    try {
      const response = await portfolioAPI.updatePortfolioName(
        portfolioId,
        editingName.trim()
      );
      if (response.message) {
        // Update the local state
        setPortfolios(
          portfolios.map((p) =>
            p.id === portfolioId ? { ...p, name: editingName.trim() } : p
          )
        );
        setEditingPortfolioId(null);
        setEditingName("");
      } else {
        alert("Failed to rename portfolio");
      }
    } catch (err) {
      alert("Failed to rename portfolio");
      console.error("Error renaming portfolio:", err);
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

          {/* Analysis Results */}
          {analysisResults && (
            <div
              className="analysis-results"
              style={{
                marginTop: "1.5rem",
                marginBottom: "2rem",
                padding: "1.5rem",
                background: "#f8f9fa",
                borderRadius: "8px",
                border: "1px solid #e9ecef",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "1rem",
                }}
              >
                <h2 style={{ margin: 0 }}>📊 Analysis Results</h2>
                <button
                  onClick={() => setAnalysisResults(null)}
                  className="btn btn-secondary"
                  style={{ padding: "0.5rem 1rem", fontSize: "0.9rem" }}
                >
                  Clear Results
                </button>
              </div>

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
                              border: "1px solid #e9ecef",
                              boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
                            }}
                          >
                            <h4 style={{ marginBottom: "1rem" }}>
                              {result.filename}
                            </h4>

                            {/* Key Metrics */}
                            <div
                              className="metrics-grid"
                              style={{
                                display: "grid",
                                gridTemplateColumns: "1fr 1fr",
                                gap: "0.75rem",
                                marginBottom: "1rem",
                              }}
                            >
                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: "#666",
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  Total Return
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color:
                                      result.metrics.total_return >= 0
                                        ? "#28a745"
                                        : "#dc3545",
                                  }}
                                >
                                  {result.metrics.total_return?.toFixed(2)}%
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: "#666",
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  Sharpe Ratio
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color:
                                      result.metrics.sharpe_ratio >= 1
                                        ? "#28a745"
                                        : result.metrics.sharpe_ratio >= 0.5
                                        ? "#ffc107"
                                        : "#dc3545",
                                  }}
                                >
                                  {result.metrics.sharpe_ratio?.toFixed(2)}
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: "#666",
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  Max Drawdown
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: "#dc3545",
                                  }}
                                >
                                  {result.metrics.max_drawdown_percent?.toFixed(
                                    2
                                  )}
                                  %
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: "#666",
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  CAGR
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color:
                                      result.metrics.cagr >= 0
                                        ? "#28a745"
                                        : "#dc3545",
                                  }}
                                >
                                  {result.metrics.cagr?.toFixed(2)}%
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: "#666",
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  Total P/L
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color:
                                      result.metrics.total_pl >= 0
                                        ? "#28a745"
                                        : "#dc3545",
                                  }}
                                >
                                  $
                                  {result.metrics.total_pl?.toLocaleString(
                                    undefined,
                                    {
                                      minimumFractionDigits: 2,
                                      maximumFractionDigits: 2,
                                    }
                                  )}
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: "#666",
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  Final Account Value
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: "#007bff",
                                  }}
                                >
                                  $
                                  {result.metrics.final_account_value?.toLocaleString(
                                    undefined,
                                    {
                                      minimumFractionDigits: 2,
                                      maximumFractionDigits: 2,
                                    }
                                  )}
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: "#666",
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  Max Drawdown ($)
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: "#dc3545",
                                  }}
                                >
                                  $
                                  {Math.abs(
                                    result.metrics.max_drawdown || 0
                                  ).toLocaleString(undefined, {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2,
                                  })}
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: "#666",
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  Annual Volatility
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color:
                                      (result.metrics.annual_volatility || 0) <=
                                      15
                                        ? "#28a745"
                                        : (result.metrics.annual_volatility ||
                                            0) <= 25
                                        ? "#ffc107"
                                        : "#dc3545",
                                  }}
                                >
                                  {result.metrics.annual_volatility?.toFixed(2)}
                                  %
                                </div>
                              </div>
                            </div>

                            {/* Portfolio Plots */}
                            {result.plots && result.plots.length > 0 && (
                              <div className="plots-section">
                                <h5 style={{ marginBottom: "0.75rem" }}>
                                  Visualizations
                                </h5>
                                <div
                                  className="plots-grid"
                                  style={{
                                    display: "grid",
                                    gridTemplateColumns: "1fr 1fr",
                                    gap: "0.5rem",
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
                                          border: "1px solid #e9ecef",
                                        }}
                                        onError={(e) => {
                                          e.currentTarget.style.display =
                                            "none";
                                        }}
                                      />
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
                  <h3>🔗 Blended Portfolio Analysis</h3>
                  <div
                    className="blended-card"
                    style={{
                      background: "#fff",
                      padding: "1.5rem",
                      borderRadius: "8px",
                      border: "2px solid #007bff",
                      boxShadow: "0 4px 8px rgba(0,0,0,0.1)",
                      marginBottom: "2rem",
                    }}
                  >
                    <h4 style={{ marginBottom: "1rem", color: "#007bff" }}>
                      Combined Portfolio Performance
                    </h4>

                    {/* Blended Metrics */}
                    <div
                      className="blended-metrics"
                      style={{
                        display: "grid",
                        gridTemplateColumns:
                          "repeat(auto-fit, minmax(200px, 1fr))",
                        gap: "1rem",
                        marginBottom: "1.5rem",
                      }}
                    >
                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: "#f8f9fa",
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: "#666",
                            marginBottom: "0.5rem",
                          }}
                        >
                          Total Return
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color:
                              analysisResults.blended_result.metrics
                                .total_return >= 0
                                ? "#28a745"
                                : "#dc3545",
                          }}
                        >
                          {analysisResults.blended_result.metrics.total_return?.toFixed(
                            2
                          )}
                          %
                        </div>
                      </div>

                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: "#f8f9fa",
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: "#666",
                            marginBottom: "0.5rem",
                          }}
                        >
                          Sharpe Ratio
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color:
                              analysisResults.blended_result.metrics
                                .sharpe_ratio >= 1
                                ? "#28a745"
                                : analysisResults.blended_result.metrics
                                    .sharpe_ratio >= 0.5
                                ? "#ffc107"
                                : "#dc3545",
                          }}
                        >
                          {analysisResults.blended_result.metrics.sharpe_ratio?.toFixed(
                            2
                          )}
                        </div>
                      </div>

                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: "#f8f9fa",
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: "#666",
                            marginBottom: "0.5rem",
                          }}
                        >
                          Max Drawdown
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color: "#dc3545",
                          }}
                        >
                          {analysisResults.blended_result.metrics.max_drawdown_percent?.toFixed(
                            2
                          )}
                          %
                        </div>
                      </div>

                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: "#f8f9fa",
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: "#666",
                            marginBottom: "0.5rem",
                          }}
                        >
                          CAGR
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color:
                              analysisResults.blended_result.metrics.cagr >= 0
                                ? "#28a745"
                                : "#dc3545",
                          }}
                        >
                          {analysisResults.blended_result.metrics.cagr?.toFixed(
                            2
                          )}
                          %
                        </div>
                      </div>

                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: "#f8f9fa",
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: "#666",
                            marginBottom: "0.5rem",
                          }}
                        >
                          Total P/L
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color:
                              analysisResults.blended_result.metrics.total_pl >=
                              0
                                ? "#28a745"
                                : "#dc3545",
                          }}
                        >
                          $
                          {analysisResults.blended_result.metrics.total_pl?.toLocaleString(
                            undefined,
                            {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2,
                            }
                          )}
                        </div>
                      </div>

                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: "#f8f9fa",
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: "#666",
                            marginBottom: "0.5rem",
                          }}
                        >
                          Final Account Value
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color: "#007bff",
                          }}
                        >
                          $
                          {analysisResults.blended_result.metrics.final_account_value?.toLocaleString(
                            undefined,
                            {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2,
                            }
                          )}
                        </div>
                      </div>

                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: "#f8f9fa",
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: "#666",
                            marginBottom: "0.5rem",
                          }}
                        >
                          Max Drawdown ($)
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color: "#dc3545",
                          }}
                        >
                          $
                          {Math.abs(
                            analysisResults.blended_result.metrics
                              .max_drawdown || 0
                          ).toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </div>
                      </div>

                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: "#f8f9fa",
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: "#666",
                            marginBottom: "0.5rem",
                          }}
                        >
                          Annual Volatility
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color:
                              (analysisResults.blended_result.metrics
                                .annual_volatility || 0) <= 15
                                ? "#28a745"
                                : (analysisResults.blended_result.metrics
                                    .annual_volatility || 0) <= 25
                                ? "#ffc107"
                                : "#dc3545",
                          }}
                        >
                          {analysisResults.blended_result.metrics.annual_volatility?.toFixed(
                            2
                          )}
                          %
                        </div>
                      </div>
                    </div>

                    {/* Blended Portfolio Plots */}
                    {analysisResults.blended_result.plots &&
                      analysisResults.blended_result.plots.length > 0 && (
                        <div className="blended-plots">
                          <h5 style={{ marginBottom: "1rem" }}>
                            Combined Portfolio Visualizations
                          </h5>
                          <div
                            className="plots-grid"
                            style={{
                              display: "grid",
                              gridTemplateColumns:
                                "repeat(auto-fit, minmax(300px, 1fr))",
                              gap: "1rem",
                            }}
                          >
                            {analysisResults.blended_result.plots.map(
                              (plot, plotIndex) => (
                                <div key={plotIndex} className="plot-container">
                                  <img
                                    src={plot.url}
                                    alt={plot.filename}
                                    style={{
                                      width: "100%",
                                      height: "auto",
                                      borderRadius: "4px",
                                      border: "1px solid #e9ecef",
                                    }}
                                    onError={(e) => {
                                      e.currentTarget.style.display = "none";
                                    }}
                                  />
                                </div>
                              )
                            )}
                          </div>
                        </div>
                      )}
                  </div>
                </div>
              )}

              {/* Advanced Plots Section */}
              {analysisResults.advanced_plots &&
                analysisResults.multiple_portfolios &&
                (analysisResults.advanced_plots.correlation_heatmap ||
                  analysisResults.advanced_plots.monte_carlo_simulation) && (
                  <div className="advanced-plots-section">
                    <h3>🔬 Advanced Portfolio Analysis</h3>
                    <p
                      style={{
                        color: "#666",
                        fontSize: "0.95rem",
                        marginBottom: "1.5rem",
                      }}
                    >
                      Advanced statistical analysis for multiple portfolio
                      comparison and risk assessment.
                    </p>
                    <div
                      className="plots-grid"
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr",
                        gap: "2rem",
                      }}
                    >
                      {analysisResults.advanced_plots.correlation_heatmap && (
                        <div className="advanced-plot-card">
                          <h4 style={{ marginBottom: "0.5rem" }}>
                            📊 Portfolio Correlation Heatmap
                          </h4>
                          <p
                            style={{
                              color: "#666",
                              fontSize: "0.9rem",
                              marginBottom: "1rem",
                            }}
                          >
                            Shows correlation coefficients between portfolio
                            returns. Values closer to 1 indicate higher positive
                            correlation, while values closer to -1 indicate
                            negative correlation.
                          </p>
                          <div className="plot-container">
                            <img
                              src={
                                analysisResults.advanced_plots
                                  .correlation_heatmap
                              }
                              alt="Correlation Heatmap"
                              style={{
                                width: "100%",
                                height: "auto",
                                borderRadius: "4px",
                                border: "1px solid #e9ecef",
                              }}
                              onError={(e) => {
                                e.currentTarget.style.display = "none";
                              }}
                            />
                          </div>
                        </div>
                      )}

                      {analysisResults.advanced_plots
                        .monte_carlo_simulation && (
                        <div className="advanced-plot-card">
                          <h4 style={{ marginBottom: "0.5rem" }}>
                            🎲 Monte Carlo Simulation
                          </h4>
                          <p
                            style={{
                              color: "#666",
                              fontSize: "0.9rem",
                              marginBottom: "1rem",
                            }}
                          >
                            1-year forecast based on 1,000 simulations using
                            historical return patterns. Shows expected portfolio
                            value range and confidence intervals.
                          </p>
                          <div className="plot-container">
                            <img
                              src={
                                analysisResults.advanced_plots
                                  .monte_carlo_simulation
                              }
                              alt="Monte Carlo Simulation"
                              style={{
                                width: "100%",
                                height: "auto",
                                borderRadius: "4px",
                                border: "1px solid #e9ecef",
                              }}
                              onError={(e) => {
                                e.currentTarget.style.display = "none";
                              }}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
            </div>
          )}

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
                  {editingPortfolioId === portfolio.id ? (
                    <div
                      style={{
                        flex: 1,
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5rem",
                      }}
                    >
                      <input
                        type="text"
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            saveRename(portfolio.id);
                          } else if (e.key === "Escape") {
                            cancelRenaming();
                          }
                        }}
                        style={{
                          flex: 1,
                          padding: "0.25rem 0.5rem",
                          border: "1px solid #ccc",
                          borderRadius: "4px",
                          fontSize: "1.1rem",
                          fontWeight: "bold",
                        }}
                        autoFocus
                      />
                      <button
                        onClick={() => saveRename(portfolio.id)}
                        style={{
                          padding: "0.25rem 0.5rem",
                          background: "#28a745",
                          color: "white",
                          border: "none",
                          borderRadius: "4px",
                          cursor: "pointer",
                          fontSize: "0.8rem",
                        }}
                        title="Save (Enter)"
                      >
                        ✓
                      </button>
                      <button
                        onClick={cancelRenaming}
                        style={{
                          padding: "0.25rem 0.5rem",
                          background: "#dc3545",
                          color: "white",
                          border: "none",
                          borderRadius: "4px",
                          cursor: "pointer",
                          fontSize: "0.8rem",
                        }}
                        title="Cancel (Escape)"
                      >
                        ✕
                      </button>
                    </div>
                  ) : (
                    <div
                      style={{
                        flex: 1,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                      }}
                    >
                      <h3 style={{ margin: 0 }}>{portfolio.name}</h3>
                      <button
                        onClick={() => startRenaming(portfolio)}
                        style={{
                          padding: "0.25rem 0.5rem",
                          background: "#007bff",
                          color: "white",
                          border: "none",
                          borderRadius: "4px",
                          cursor: "pointer",
                          fontSize: "0.8rem",
                          marginLeft: "0.5rem",
                        }}
                        title="Rename portfolio"
                      >
                        ✏️
                      </button>
                    </div>
                  )}
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
        </>
      )}
    </div>
  );
}
