import { useState, useEffect } from "react";
import { portfolioAPI, API_BASE_URL } from "../services/api";

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
  weighting_method?: string;
  portfolio_composition?: Record<string, number>;
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
  weighting_method?: string;
  portfolio_weights?: Record<string, number>;
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

  // Weighting state
  const [weightingMethod, setWeightingMethod] = useState<"equal" | "custom">(
    "equal"
  );
  const [portfolioWeights, setPortfolioWeights] = useState<
    Record<number, number>
  >({});

  // Analysis parameters
  const [startingCapital, setStartingCapital] = useState<number>(100000);

  // Force a fresh deployment with checkboxes

  useEffect(() => {
    fetchPortfolios();
  }, []);

  // Initialize weights when selected portfolios change
  useEffect(() => {
    if (selectedPortfolios.length > 0) {
      initializeWeights(selectedPortfolios);
    }
  }, [selectedPortfolios.length, weightingMethod]);

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

      if (response.success) {
        // Update the local state
        setPortfolios(
          portfolios.map((p) =>
            p.id === portfolioId ? { ...p, name: editingName.trim() } : p
          )
        );
        setEditingPortfolioId(null);
        setEditingName("");
      } else {
        alert(response.error || "Failed to rename portfolio");
      }
    } catch (err) {
      alert("Failed to rename portfolio");
      console.error("Error renaming portfolio:", err);
    }
  };

  const togglePortfolioSelection = (id: number) => {
    setSelectedPortfolios((prev) => {
      const newSelection = prev.includes(id)
        ? prev.filter((pid) => pid !== id)
        : [...prev, id];

      // Reset weights when selection changes
      initializeWeights(newSelection);
      return newSelection;
    });
  };

  const selectAllPortfolios = () => {
    const allIds = portfolios.map((p) => p.id);
    setSelectedPortfolios(allIds);
    initializeWeights(allIds);
  };

  const clearSelection = () => {
    setSelectedPortfolios([]);
    setPortfolioWeights({});
  };

  // Initialize multipliers for selected portfolios
  const initializeWeights = (portfolioIds: number[]) => {
    if (weightingMethod === "equal") {
      // Equal weighting now means 1.0x (full scale) for each portfolio
      const equalMultiplier = 1.0;
      const newWeights: Record<number, number> = {};
      portfolioIds.forEach((id) => {
        newWeights[id] = equalMultiplier;
      });
      setPortfolioWeights(newWeights);
    } else {
      // For custom multipliers, initialize with 1.0x if not already set
      setPortfolioWeights((prev) => {
        const newWeights = { ...prev };
        const defaultMultiplier = 1.0; // Default to full scale
        portfolioIds.forEach((id) => {
          if (!(id in newWeights)) {
            newWeights[id] = defaultMultiplier;
          }
        });
        // Remove multipliers for unselected portfolios
        Object.keys(newWeights).forEach((key) => {
          const id = parseInt(key);
          if (!portfolioIds.includes(id)) {
            delete newWeights[id];
          }
        });
        return newWeights;
      });
    }
  };

  // Handle weighting method change
  const handleWeightingMethodChange = (method: "equal" | "custom") => {
    setWeightingMethod(method);
    if (method === "equal") {
      initializeWeights(selectedPortfolios);
    }
  };

  // Handle individual multiplier change
  const handleWeightChange = (portfolioId: number, multiplier: number) => {
    setPortfolioWeights((prev) => ({
      ...prev,
      [portfolioId]: multiplier,
    }));
  };

  // Reset all multipliers to 1.0x (full scale)
  const resetMultipliers = () => {
    const resetWeights: Record<number, number> = {};
    Object.keys(portfolioWeights).forEach((key) => {
      resetWeights[parseInt(key)] = 1.0;
    });
    setPortfolioWeights(resetWeights);
  };

  // Get total portfolio scale for display
  const getTotalScale = () => {
    return Object.values(portfolioWeights).reduce(
      (sum, multiplier) => sum + multiplier,
      0
    );
  };

  const optimizePortfolioWeights = async () => {
    if (selectedPortfolios.length < 2) {
      alert("Please select at least 2 portfolios for weight optimization");
      return;
    }

    if (selectedPortfolios.length > 6) {
      alert(
        "Maximum 6 portfolios allowed for optimization to prevent performance issues"
      );
      return;
    }

    setAnalyzing(true);
    setAnalysisResults(null);

    try {
      const optimizeResponse = await fetch(
        `${API_BASE_URL}/api/optimize-weights`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            portfolio_ids: selectedPortfolios,
            method: "differential_evolution", // Can be 'scipy', 'differential_evolution', 'grid_search'
          }),
        }
      );

      if (optimizeResponse.ok) {
        const optimizationResult = await optimizeResponse.json();
        console.log("Optimization result:", optimizationResult);

        if (optimizationResult.success) {
          // Update the weights with the optimized values
          setWeightingMethod("custom");
          const optimizedWeights: Record<number, number> = {};
          selectedPortfolios.forEach((portfolioId, index) => {
            optimizedWeights[portfolioId] =
              optimizationResult.optimal_weights_array[index];
          });
          setPortfolioWeights(optimizedWeights);

          // Show optimization results to the user
          const message = `
Optimization completed successfully!

Optimal multipliers found:
${Object.entries(optimizationResult.optimal_weights)
  .map(([name, weight]) => `• ${name}: ${Number(weight).toFixed(2)}x`)
  .join("\n")}

Expected Performance:
• CAGR: ${(optimizationResult.metrics.cagr * 100).toFixed(2)}%
• Max Drawdown: ${(
            optimizationResult.metrics.max_drawdown_percent * 100
          ).toFixed(2)}%
• Return/Drawdown Ratio: ${optimizationResult.metrics.return_drawdown_ratio.toFixed(
            2
          )}
• Sharpe Ratio: ${optimizationResult.metrics.sharpe_ratio.toFixed(2)}

Method: ${optimizationResult.optimization_details.method}
Combinations explored: ${
            optimizationResult.optimization_details.combinations_explored
          }

The weights have been applied automatically. Click 'Analyze' to see the full results.
          `.trim();

          alert(message);
        } else {
          alert(`Weight optimization failed: ${optimizationResult.error}`);
        }
      } else {
        const errorData = await optimizeResponse.json();
        alert(
          `Weight optimization failed: ${errorData.error || "Unknown error"}`
        );
      }
    } catch (error) {
      console.error("Weight optimization failed:", error);
      alert(
        `Weight optimization failed: ${
          error instanceof Error ? error.message : "Unknown error"
        }`
      );
    } finally {
      setAnalyzing(false);
    }
  };

  const analyzeSelectedPortfolios = async () => {
    if (selectedPortfolios.length === 0) {
      alert("Please select at least one portfolio to analyze");
      return;
    }

    // Validate multipliers if using custom weighting
    if (weightingMethod === "custom" && selectedPortfolios.length > 1) {
      const multipliers = Object.values(portfolioWeights);
      // Check that all multipliers are positive
      const hasInvalidMultipliers = multipliers.some((m) => m <= 0);
      if (hasInvalidMultipliers) {
        alert(
          "All portfolio multipliers must be positive numbers (greater than 0)"
        );
        return;
      }
    }

    setAnalyzing(true);
    setAnalysisResults(null);

    try {
      // Determine which endpoint to use based on whether weighting is needed
      const useWeightedEndpoint =
        selectedPortfolios.length > 1 &&
        (weightingMethod === "custom" || weightingMethod === "equal");

      let endpoint = `${API_BASE_URL}/api/analyze-portfolios`;
      let requestBody: any = {
        portfolio_ids: selectedPortfolios,
        starting_capital: startingCapital,
      };

      // Add weighting parameters for multiple portfolios if using weighted endpoint
      if (useWeightedEndpoint) {
        endpoint = `${API_BASE_URL}/api/analyze-portfolios-weighted`;
        requestBody.weighting_method = weightingMethod;
        if (weightingMethod === "custom") {
          // Convert weights to array in the same order as portfolio_ids
          requestBody.weights = selectedPortfolios.map(
            (id) => portfolioWeights[id] || 0
          );
        }
      }

      console.log("Calling endpoint:", endpoint);
      console.log("Request body:", requestBody);

      // Call the backend API to analyze selected portfolios
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      console.log("Response status:", response.status);
      console.log("Response headers:", response.headers);

      if (!response.ok) {
        // If the weighted endpoint fails with 502/500, try the original endpoint as fallback
        if (
          useWeightedEndpoint &&
          (response.status === 502 || response.status === 500)
        ) {
          console.log(
            "Weighted endpoint failed, falling back to original endpoint"
          );

          const fallbackResponse = await fetch(
            `${API_BASE_URL}/api/analyze-portfolios`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                portfolio_ids: selectedPortfolios,
                starting_capital: startingCapital,
              }),
            }
          );

          if (!fallbackResponse.ok) {
            throw new Error(
              `Analysis failed on both endpoints: ${fallbackResponse.status} ${fallbackResponse.statusText}`
            );
          }

          const fallbackResults = await fallbackResponse.json();
          setAnalysisResults(fallbackResults);
          return;
        }

        throw new Error(
          `Analysis failed: ${response.status} ${response.statusText}`
        );
      }

      const results = await response.json();
      console.log("Analysis results:", results);
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
            {selectedPortfolios.length >= 2 && (
              <button
                onClick={optimizePortfolioWeights}
                disabled={analyzing || selectedPortfolios.length > 6}
                className="btn btn-success"
                style={{
                  padding: "0.5rem 1.5rem",
                  fontSize: "0.9rem",
                  marginRight: "0.5rem",
                  opacity: analyzing || selectedPortfolios.length > 6 ? 0.5 : 1,
                }}
                title="Find optimal weights to maximize return while minimizing drawdown"
              >
                {analyzing ? "Optimizing..." : "🎯 Optimize Weights"}
              </button>
            )}
            <button
              onClick={analyzeSelectedPortfolios}
              disabled={selectedPortfolios.length === 0 || analyzing}
              className="btn btn-primary"
              style={{
                padding: "0.5rem 1.5rem",
                fontSize: "0.9rem",
                marginLeft: selectedPortfolios.length >= 2 ? "0" : "auto",
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

          {/* Analysis Parameters */}
          {selectedPortfolios.length > 0 && (
            <div
              className="analysis-parameters"
              style={{
                marginBottom: "1.5rem",
                padding: "1.5rem",
                background: "#f8f9fa",
                borderRadius: "8px",
                border: "1px solid #e9ecef",
              }}
            >
              <h3 style={{ marginBottom: "1rem", color: "#495057" }}>
                ⚙️ Analysis Parameters
              </h3>

              <div style={{ marginBottom: "1rem" }}>
                <label
                  htmlFor="startingCapital"
                  style={{
                    display: "block",
                    marginBottom: "0.5rem",
                    fontWeight: "bold",
                    color: "#495057",
                  }}
                >
                  💰 Starting Capital ($)
                </label>
                <input
                  id="startingCapital"
                  type="number"
                  min="1000"
                  max="10000000"
                  step="1000"
                  value={startingCapital}
                  onChange={(e) => {
                    const value = parseFloat(e.target.value);
                    if (!isNaN(value) && value > 0) {
                      setStartingCapital(value);
                    }
                  }}
                  style={{
                    padding: "0.5rem",
                    border: "1px solid #ced4da",
                    borderRadius: "4px",
                    width: "200px",
                    fontSize: "1rem",
                  }}
                  placeholder="100000"
                />
                <div
                  style={{
                    fontSize: "0.85rem",
                    color: "#6c757d",
                    marginTop: "0.25rem",
                  }}
                >
                  The initial capital amount for portfolio analysis. Default is
                  $100,000.
                </div>
              </div>
            </div>
          )}

          {/* Weighting Controls */}
          {selectedPortfolios.length > 1 && (
            <div
              className="weighting-controls"
              style={{
                marginBottom: "1.5rem",
                padding: "1.5rem",
                background: "#f8f9fa",
                borderRadius: "8px",
                border: "1px solid #e9ecef",
              }}
            >
              <h3 style={{ marginBottom: "1rem", color: "#495057" }}>
                ⚖️ Portfolio Weighting
              </h3>

              <div
                style={{
                  marginBottom: "1rem",
                  padding: "0.75rem",
                  background: "#e8f5e8",
                  borderRadius: "6px",
                  border: "1px solid #c3e6cb",
                  fontSize: "0.9rem",
                  color: "#155724",
                }}
              >
                💡 <strong>Tip:</strong> Use the "🎯 Optimize Weights" button
                above to automatically find the best multipliers that maximize
                returns while minimizing drawdown. This uses advanced
                optimization algorithms to balance risk and reward.
              </div>

              {/* Portfolio Scaling Method Selection */}
              <div style={{ marginBottom: "1rem" }}>
                <label style={{ marginRight: "1rem" }}>
                  <input
                    type="radio"
                    name="weightingMethod"
                    value="equal"
                    checked={weightingMethod === "equal"}
                    onChange={() => handleWeightingMethodChange("equal")}
                    style={{ marginRight: "0.5rem" }}
                  />
                  Equal Scaling (1.0x each)
                </label>
                <label>
                  <input
                    type="radio"
                    name="weightingMethod"
                    value="custom"
                    checked={weightingMethod === "custom"}
                    onChange={() => handleWeightingMethodChange("custom")}
                    style={{ marginRight: "0.5rem" }}
                  />
                  Custom Multipliers
                </label>
              </div>

              {/* Multiplier Help Text */}
              {weightingMethod === "custom" && (
                <div
                  style={{
                    background: "#e7f3ff",
                    border: "1px solid #b3d7ff",
                    borderRadius: "4px",
                    padding: "0.75rem",
                    marginBottom: "1rem",
                    fontSize: "0.9rem",
                  }}
                >
                  <strong>Portfolio Multipliers:</strong>• 1.0 = Run portfolio
                  at full scale • 2.0 = Run portfolio at double scale • 0.5 =
                  Run portfolio at half scale • Any positive number works!
                </div>
              )}

              {/* Multiplier Display */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
                  gap: "1rem",
                  marginBottom: "1rem",
                }}
              >
                {selectedPortfolios.map((portfolioId) => {
                  const portfolio = portfolios.find(
                    (p) => p.id === portfolioId
                  );
                  const weight = portfolioWeights[portfolioId] || 0;
                  return (
                    <div
                      key={portfolioId}
                      style={{
                        padding: "1rem",
                        background: "#fff",
                        borderRadius: "6px",
                        border: "1px solid #dee2e6",
                      }}
                    >
                      <div
                        style={{ fontWeight: "bold", marginBottom: "0.5rem" }}
                      >
                        {portfolio?.name || `Portfolio ${portfolioId}`}
                      </div>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "0.5rem",
                        }}
                      >
                        <span style={{ minWidth: "80px" }}>Multiplier:</span>
                        <input
                          type="number"
                          min="0"
                          step="0.1"
                          value={weight.toFixed(2)}
                          disabled={weightingMethod === "equal"}
                          placeholder="1.0"
                          onChange={(e) =>
                            handleWeightChange(
                              portfolioId,
                              parseFloat(e.target.value) || 0
                            )
                          }
                          style={{
                            width: "80px",
                            padding: "0.25rem",
                            border: "1px solid #ced4da",
                            borderRadius: "4px",
                            backgroundColor:
                              weightingMethod === "equal" ? "#e9ecef" : "#fff",
                          }}
                        />
                        <span style={{ color: "#6c757d" }}>
                          ({weight.toFixed(2)}x)
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Weight Summary and Controls */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "0.75rem",
                  background: "#fff",
                  borderRadius: "6px",
                  border: "1px solid #dee2e6",
                }}
              >
                <div>
                  <span style={{ fontWeight: "bold" }}>Total Scale: </span>
                  <span
                    style={{
                      color: "#28a745",
                      fontWeight: "bold",
                    }}
                  >
                    {getTotalScale().toFixed(2)}x
                  </span>
                  <span style={{ color: "#6c757d", marginLeft: "0.5rem" }}>
                    (Sum of all multipliers)
                  </span>
                </div>
                {weightingMethod === "custom" && (
                  <button
                    onClick={resetMultipliers}
                    className="btn btn-secondary"
                    style={{ padding: "0.5rem 1rem", fontSize: "0.9rem" }}
                  >
                    Reset to 1.0x
                  </button>
                )}
              </div>
            </div>
          )}

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

                    {/* Portfolio Composition Display */}
                    {analysisResults.blended_result.weighting_method && (
                      <div
                        style={{
                          marginBottom: "1.5rem",
                          padding: "1rem",
                          background: "#e3f2fd",
                          borderRadius: "6px",
                          border: "1px solid #bbdefb",
                        }}
                      >
                        <h5
                          style={{ margin: "0 0 0.5rem 0", color: "#1976d2" }}
                        >
                          📊 Portfolio Composition
                        </h5>
                        <div
                          style={{ fontSize: "0.9rem", marginBottom: "0.5rem" }}
                        >
                          <strong>Weighting Method:</strong>{" "}
                          {analysisResults.blended_result.weighting_method ===
                          "equal"
                            ? "Equal Weighting"
                            : "Custom Weighting"}
                        </div>
                        {analysisResults.blended_result
                          .portfolio_composition && (
                          <div style={{ fontSize: "0.9rem" }}>
                            {Object.entries(
                              analysisResults.blended_result
                                .portfolio_composition
                            ).map(([name, weight]) => (
                              <div
                                key={name}
                                style={{ marginBottom: "0.25rem" }}
                              >
                                <strong>{name}:</strong>{" "}
                                {(weight as number).toFixed(2)}x
                                <span
                                  style={{
                                    color: "#666",
                                    marginLeft: "0.5rem",
                                  }}
                                >
                                  (multiplier: {(weight as number).toFixed(3)})
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

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
                                    gridTemplateColumns: "1fr",
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
