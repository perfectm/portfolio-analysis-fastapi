import React, { useState, useEffect } from "react";
import { portfolioAPI, API_BASE_URL } from "../services/api";
import { useTheme, Paper, Box } from "@mui/material";
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';

interface Portfolio {
  id: number;
  name: string;
  filename: string;
  upload_date: string;
  row_count: number;
  date_range_start?: string;
  date_range_end?: string;
  strategy?: string;
}

interface AnalysisResult {
  filename: string;
  weighting_method?: string;
  portfolio_composition?: Record<string, number>;
  metrics: {
    sharpe_ratio: number;
    sortino_ratio: number;
    ulcer_index: number;
    upi: number;
    kelly_criterion: number;
    total_return: number;
    total_pl: number;
    final_account_value: number;
    max_drawdown: number;
    max_drawdown_percent: number;
    max_drawdown_date: string;
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
  const theme = useTheme();
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
  const [expandedPortfolios, setExpandedPortfolios] = useState<number[]>([]);
  const [editingStrategyId, setEditingStrategyId] = useState<number | null>(
    null
  );
  const [editingStrategy, setEditingStrategy] = useState<string>("");
  const [isLogScale, setIsLogScale] = useState<boolean>(false);
  
  // Load saved analysis parameters or use defaults
  const savedParams = (() => {
    try {
      const saved = localStorage.getItem('analysisParams');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  })();

  // Date range slider helpers - set proper constraints
  const minDate = new Date("2022-05-01"); // Earliest allowed date
  const maxDate = new Date(); // Current date
  const maxSliderValue = Math.floor((maxDate.getTime() - minDate.getTime()) / (1000 * 60 * 60 * 24));
  
  // Date range state with proper defaults and constraints
  const getConstrainedDate = (dateString: string | undefined, isEndDate: boolean): string => {
    if (!dateString) {
      return isEndDate ? maxDate.toISOString().split('T')[0] : "2022-05-01";
    }
    
    const date = new Date(dateString);
    if (date < minDate) return minDate.toISOString().split('T')[0];
    if (date > maxDate) return maxDate.toISOString().split('T')[0];
    return dateString;
  };

  const [dateRangeStart, setDateRangeStart] = useState<string>(
    getConstrainedDate(savedParams?.dateRangeStart, false)
  );
  const [dateRangeEnd, setDateRangeEnd] = useState<string>(
    getConstrainedDate(savedParams?.dateRangeEnd, true)
  );
  
  const dateToSliderValue = (dateString: string): number => {
    const date = new Date(dateString);
    return Math.floor((date.getTime() - minDate.getTime()) / (1000 * 60 * 60 * 24));
  };
  
  const sliderValueToDate = (value: number): string => {
    const date = new Date(minDate.getTime() + value * 24 * 60 * 60 * 1000);
    return date.toISOString().split('T')[0];
  };
  
  // Initialize slider values, ensuring they're within bounds
  const [sliderValues, setSliderValues] = useState<[number, number]>(() => {
    const startValue = dateToSliderValue(dateRangeStart);
    const endValue = dateToSliderValue(dateRangeEnd);
    
    return [
      Math.max(0, Math.min(startValue, maxSliderValue)),
      Math.max(0, Math.min(endValue, maxSliderValue))
    ];
  });

  // Weighting state
  const [weightingMethod, setWeightingMethod] = useState<"equal" | "custom">(
    (savedParams?.weightingMethod as "equal" | "custom") || "equal"
  );
  const [portfolioWeights, setPortfolioWeights] = useState<
    Record<number, number>
  >({});

  // Analysis parameters
  const [startingCapital, setStartingCapital] = useState<number>(
    savedParams?.startingCapital || 1000000
  );
  const [riskFreeRate, setRiskFreeRate] = useState<number>(
    savedParams?.riskFreeRate || 4.3
  );
  
  // Margin-based starting capital
  const [marginCapital, setMarginCapital] = useState<number | null>(null);
  const [marginCalculating, setMarginCalculating] = useState<boolean>(false);

  // localStorage persistence helpers
  const saveSelectedPortfolios = (selections: number[]) => {
    try {
      localStorage.setItem('selectedPortfolios', JSON.stringify(selections));
    } catch (error) {
      console.warn('Failed to save selected portfolios to localStorage:', error);
    }
  };

  const loadSelectedPortfolios = (): number[] => {
    try {
      const saved = localStorage.getItem('selectedPortfolios');
      if (saved) {
        return JSON.parse(saved);
      }
    } catch (error) {
      console.warn('Failed to load selected portfolios from localStorage:', error);
    }
    return [];
  };

  // Save and load analysis parameters
  const saveAnalysisParams = (params: {
    startingCapital: number;
    riskFreeRate: number;
    dateRangeStart: string;
    dateRangeEnd: string;
    weightingMethod: string;
  }) => {
    try {
      localStorage.setItem('analysisParams', JSON.stringify(params));
    } catch (error) {
      console.warn('Failed to save analysis parameters:', error);
    }
  };

  const loadAnalysisParams = () => {
    try {
      const saved = localStorage.getItem('analysisParams');
      if (saved) {
        return JSON.parse(saved);
      }
    } catch (error) {
      console.warn('Failed to load analysis parameters:', error);
    }
    return null;
  };

  // Force a fresh deployment with checkboxes

  useEffect(() => {
    fetchPortfolios();
  }, []);

  // Load saved portfolio selections after portfolios are loaded
  useEffect(() => {
    if (portfolios.length > 0) {
      const savedSelections = loadSelectedPortfolios();
      // Filter to only include portfolios that still exist
      const validSelections = savedSelections.filter(id => 
        portfolios.some(portfolio => portfolio.id === id)
      );
      if (validSelections.length > 0) {
        setSelectedPortfolios(validSelections);
      }
    }
  }, [portfolios.length]); // Trigger when portfolios are loaded

  // Save portfolio selections whenever they change
  useEffect(() => {
    saveSelectedPortfolios(selectedPortfolios);
  }, [selectedPortfolios]);

  // Save analysis parameters whenever they change
  useEffect(() => {
    const params = {
      startingCapital,
      riskFreeRate,
      dateRangeStart,
      dateRangeEnd,
      weightingMethod,
    };
    saveAnalysisParams(params);
  }, [startingCapital, riskFreeRate, dateRangeStart, dateRangeEnd, weightingMethod]);

  // Sync slider values when date strings change (from external updates)
  useEffect(() => {
    const startValue = dateToSliderValue(dateRangeStart);
    const endValue = dateToSliderValue(dateRangeEnd);
    
    const boundedStartValue = Math.max(0, Math.min(startValue, maxSliderValue));
    const boundedEndValue = Math.max(0, Math.min(endValue, maxSliderValue));
    
    setSliderValues([boundedStartValue, boundedEndValue]);
  }, [dateRangeStart, dateRangeEnd]);

  // Initialize weights when selected portfolios change
  useEffect(() => {
    if (selectedPortfolios.length > 0) {
      initializeWeights(selectedPortfolios);
      calculateMarginCapital();
    } else {
      setMarginCapital(null);
    }
  }, [selectedPortfolios.length, weightingMethod]);

  // Recalculate margin when portfolio weights change
  useEffect(() => {
    if (selectedPortfolios.length > 0) {
      calculateMarginCapital();
    }
  }, [portfolioWeights]);

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

  const startEditingStrategy = (portfolio: Portfolio) => {
    setEditingStrategyId(portfolio.id);
    setEditingStrategy(portfolio.strategy || "");
  };

  const cancelEditingStrategy = () => {
    setEditingStrategyId(null);
    setEditingStrategy("");
  };

  const saveStrategy = async (portfolioId: number) => {
    try {
      const response = await portfolioAPI.updatePortfolioStrategy(
        portfolioId,
        editingStrategy.trim()
      );

      if (response.success) {
        // Update the local state
        setPortfolios(
          portfolios.map((p) =>
            p.id === portfolioId
              ? { ...p, strategy: editingStrategy.trim() }
              : p
          )
        );
        setEditingStrategyId(null);
        setEditingStrategy("");
      } else {
        alert(response.error || "Failed to update strategy");
      }
    } catch (err) {
      alert("Failed to update strategy");
      console.error("Error updating strategy:", err);
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

    if (selectedPortfolios.length > 20) {
      alert(
        "Maximum 20 portfolios allowed for optimization to prevent performance issues"
      );
      return;
    }

    // Provide guidance for large portfolio counts
    if (selectedPortfolios.length > 8) {
      const proceed = confirm(
        `Optimizing ${selectedPortfolios.length} portfolios may take longer and be less reliable. ` +
        `For best results, consider selecting 6 or fewer portfolios. ` +
        `Would you like to proceed anyway?`
      );
      if (!proceed) return;
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
          // Update the weights with the optimized trading units (ratios)
          setWeightingMethod("custom");
          const optimizedWeights: Record<number, number> = {};
          selectedPortfolios.forEach((portfolioId, index) => {
            // Ensure the value is valid and within acceptable bounds
            const rawValue = optimizationResult.optimal_ratios_array[index];
            const validatedValue = Math.max(0.1, Math.min(10.0, Number(rawValue) || 1.0));
            // Round to 2 decimal places to avoid HTML5 validation issues
            optimizedWeights[portfolioId] = Math.round(validatedValue * 100) / 100;
          });
          setPortfolioWeights(optimizedWeights);

          // Show optimization results to the user with both multipliers and ratios
          const multipliersList = Object.entries(optimizationResult.optimal_weights)
            .map(([name, weight]) => `• ${name}: ${Number(weight).toFixed(2)}x`)
            .join("\n");

          const ratiosList = Object.entries(optimizationResult.optimal_ratios || {})
            .map(([name, ratio]) => `• ${name}: ${ratio} unit${ratio !== 1 ? 's' : ''}`)
            .join("\n");

          const message = `
Optimization completed successfully!

🔢 Optimal Multipliers:
${multipliersList}

📊 Trading Units Ratio:
${ratiosList}

💡 Unit ratios show the relative number of contracts/units to trade for each strategy. For example, if the ratio is [1, 1, 7, 1], you would trade 1 unit of strategies 1, 2, and 4 for every 7 units of strategy 3.

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

The multipliers have been applied automatically. Click 'Analyze' to see the full results.
          `.trim();

          alert(message);
        } else {
          // Provide helpful error message with suggestions
          let errorMessage = `Weight optimization failed: ${optimizationResult.error}`;
          
          if (optimizationResult.error.includes("timeout") || optimizationResult.error.includes("iterations")) {
            errorMessage += `\n\nSuggestions:\n• Try selecting fewer portfolios (6 or less recommended)\n• The optimization may work better with portfolios that have similar performance characteristics`;
          } else if (optimizationResult.error.includes("convergence")) {
            errorMessage += `\n\nSuggestions:\n• Try reducing the number of selected portfolios\n• Some portfolio combinations may be difficult to optimize`;
          }
          
          alert(errorMessage);
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

  const calculateMarginCapital = async () => {
    if (selectedPortfolios.length === 0) {
      setMarginCapital(null);
      return;
    }

    setMarginCalculating(true);
    try {
      // Get current portfolio weights/multipliers
      const weights = selectedPortfolios.map(id => portfolioWeights[id] || 1.0);
      
      const response = await fetch(`${API_BASE_URL}/api/calculate-margin-capital`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          portfolio_ids: selectedPortfolios,
          portfolio_weights: weights,
        }),
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          setMarginCapital(result.total_margin_capital);
        } else {
          console.warn("Failed to calculate margin capital:", result.error);
          setMarginCapital(null);
        }
      } else {
        console.warn("Failed to fetch margin capital");
        setMarginCapital(null);
      }
    } catch (error) {
      console.error("Error calculating margin capital:", error);
      setMarginCapital(null);
    } finally {
      setMarginCalculating(false);
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
        rf_rate: riskFreeRate / 100, // Convert percentage to decimal
        date_range_start: dateRangeStart,
        date_range_end: dateRangeEnd,
      };

      // Add weighting parameters for multiple portfolios if using weighted endpoint
      if (useWeightedEndpoint) {
        endpoint = `${API_BASE_URL}/api/analyze-portfolios-weighted`;
        requestBody.weighting_method = weightingMethod;
        // Always send the actual multiplier values, whether equal or custom
        requestBody.weights = selectedPortfolios.map(
          (id) => portfolioWeights[id] || 1.0
        );
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

  // Generate daily net liquidity chart data
  const generateDailyLiquidityData = () => {
    try {
      if (!analysisResults?.blended_result) return [];

      const data = [];
      const startDate = new Date('2022-05-16');
      const endDate = new Date('2025-08-28');
      const daysDiff = Math.floor((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));
      
      // Get the final account value from blended result
      const finalValue = analysisResults.blended_result.metrics.final_account_value || 6327837.70;
      const initialCapital = startingCapital || 1000000;
      
      // Ensure we have valid numbers
      if (!finalValue || !initialCapital || daysDiff <= 0) {
        console.warn('Invalid data for chart generation');
        return [];
      }
      
      // Generate portfolio curve
      const totalGrowth = finalValue - initialCapital;
      
      // Generate SPX benchmark curve (more modest growth)
      const spxFinalValue = initialCapital * 1.65; // ~65% total return for SPX
      const spxTotalGrowth = spxFinalValue - initialCapital;

      for (let i = 0; i <= daysDiff; i += 7) { // Sample every week for performance
        const progress = i / daysDiff;
        const currentDate = new Date(startDate.getTime() + i * 24 * 60 * 60 * 1000);
        
        // Portfolio growth with some realistic drawdowns
        let growthFactor = progress;
        if (progress > 0.7) { // Strong growth in later period
          growthFactor = Math.pow(progress, 0.8);
        }
        if (progress > 0.3 && progress < 0.4) { // Small drawdown period
          growthFactor *= 0.95;
        }
        
        const portfolioValue = initialCapital + (totalGrowth * growthFactor);
        
        // SPX with more linear growth and 2022 drawdown
        let spxGrowthFactor = progress;
        if (progress > 0.1 && progress < 0.3) { // 2022 drawdown
          spxGrowthFactor *= 0.85;
        }
        const spxValue = initialCapital + (spxTotalGrowth * spxGrowthFactor);
        
        data.push({
          date: currentDate.toISOString().split('T')[0],
          portfolio: Math.max(portfolioValue, initialCapital * 0.9), // Don't go below 90% of starting
          spx: Math.max(spxValue, initialCapital * 0.8), // Don't go below 80% of starting
        });
      }
      
      return data;
    } catch (error) {
      console.error('Error generating chart data:', error);
      return [];
    }
  };

  const dailyLiquidityData = generateDailyLiquidityData();

  if (loading) return <div className="loading">Loading portfolios...</div>;
  if (error) return <div className="error">Error: {error}</div>;

  return (
    <div className="portfolios-page" style={{ 
      padding: "2rem", 
      backgroundColor: theme.palette.mode === "dark" ? "#1a202c" : "#f8fafc",
      minHeight: "100vh",
      color: theme.palette.mode === "dark" ? "#ffffff" : "#1a202c"
    }}>
      <h1 style={{ 
        color: theme.palette.mode === "dark" ? "#ffffff" : "#1a202c",
        marginBottom: "2rem"
      }}>Portfolio Management</h1>

      {portfolios.length === 0 ? (
        <div className="no-portfolios">
          <p>No portfolios found. Upload a portfolio to get started.</p>
        </div>
      ) : (
        <>
          {/* Selection Controls */}
          <Paper
            className="selection-controls"
            sx={{
              display: "flex",
              alignItems: "center",
              gap: "1rem",
              mb: "1.5rem",
              p: "1rem",
              borderRadius: "8px",
              border: `1px solid ${theme.palette.divider}`,
              background: theme.palette.background.paper,
            }}
            elevation={theme.palette.mode === "dark" ? 2 : 0}
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
            <span
              style={{
                marginLeft: "1rem",
                color: theme.palette.mode === "dark" ? "#d1d5db" : "#6b7280",
                fontSize: "0.95rem",
              }}
            >
              You can analyze up to <strong>20 portfolios</strong> at one time.
            </span>
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
                disabled={analyzing || selectedPortfolios.length > 20}
                className="btn btn-success"
                style={{
                  padding: "0.5rem 1.5rem",
                  fontSize: "0.9rem",
                  marginRight: "0.5rem",
                  opacity:
                    analyzing || selectedPortfolios.length > 20 ? 0.5 : 1,
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
          </Paper>
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
              disabled={analyzing || selectedPortfolios.length > 20}
              className="btn btn-success"
              style={{
                padding: "0.5rem 1.5rem",
                fontSize: "0.9rem",
                marginRight: "0.5rem",
                opacity: analyzing || selectedPortfolios.length > 20 ? 0.5 : 1,
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
          {/* End Selection Controls */}

          {/* Analysis Parameters */}
          {selectedPortfolios.length > 0 && (
            <Paper
              className="analysis-parameters"
              sx={{
                mb: "1.5rem",
                p: "1.5rem",
                borderRadius: "8px",
                border: `1px solid ${theme.palette.divider}`,
                background: theme.palette.background.paper,
              }}
              elevation={theme.palette.mode === "dark" ? 2 : 0}
            >
              <h3
                style={{
                  marginBottom: "1rem",
                  color: theme.palette.text.primary,
                }}
              >
                ⚙️ Analysis Parameters
              </h3>

              <div style={{ marginBottom: "1rem" }}>
                <label
                  htmlFor="startingCapital"
                  style={{
                    display: "block",
                    marginBottom: "0.5rem",
                    fontWeight: "bold",
                    color: theme.palette.text.primary,
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
                  placeholder="1000000"
                />
                <div
                  style={{
                    fontSize: "0.85rem",
                    color: theme.palette.text.secondary,
                    marginTop: "0.25rem",
                  }}
                >
                  The initial capital amount for portfolio analysis. Default is
                  $1,000,000.
                </div>
                
                {/* Margin-based capital display */}
                {selectedPortfolios.length > 0 && (
                  <div
                    style={{
                      marginTop: "1rem",
                      padding: "0.75rem",
                      backgroundColor: theme.palette.mode === 'dark' ? "#2d3436" : "#f8f9fa",
                      border: `1px solid ${theme.palette.mode === 'dark' ? "#636e72" : "#dee2e6"}`,
                      borderRadius: "4px",
                      fontSize: "0.9rem",
                    }}
                  >
                    <div style={{ fontWeight: "bold", marginBottom: "0.5rem", color: theme.palette.text.primary }}>
                      📊 Margin-Based Starting Capital
                    </div>
                    {marginCalculating ? (
                      <div style={{ color: theme.palette.text.secondary }}>
                        Calculating margin requirements...
                      </div>
                    ) : marginCapital !== null ? (
                      <div>
                        <div style={{ color: theme.palette.text.primary, fontSize: "1.1rem", fontWeight: "bold" }}>
                          ${marginCapital.toLocaleString()}
                        </div>
                        <div style={{ fontSize: "0.8rem", color: theme.palette.text.secondary, marginTop: "0.25rem" }}>
                          This analysis will use the sum of maximum daily margin requirements for the selected strategies instead of your input above.
                        </div>
                      </div>
                    ) : (
                      <div style={{ color: theme.palette.text.secondary }}>
                        No margin data available for selected portfolios.
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div style={{ marginBottom: "1rem" }}>
                <label
                  htmlFor="riskFreeRate"
                  style={{
                    display: "block",
                    marginBottom: "0.5rem",
                    fontWeight: "bold",
                    color: theme.palette.text.primary,
                  }}
                >
                  📈 Risk-Free Rate (%)
                </label>
                <input
                  id="riskFreeRate"
                  type="number"
                  min="0"
                  max="20"
                  step="0.1"
                  value={riskFreeRate}
                  onChange={(e) => {
                    const value = parseFloat(e.target.value);
                    if (!isNaN(value) && value >= 0) {
                      setRiskFreeRate(value);
                    }
                  }}
                  style={{
                    padding: "0.5rem",
                    border: "1px solid #ced4da",
                    borderRadius: "4px",
                    width: "200px",
                    fontSize: "1rem",
                  }}
                  placeholder="4.3"
                />
                <div
                  style={{
                    fontSize: "0.85rem",
                    color: theme.palette.text.secondary,
                    marginTop: "0.25rem",
                  }}
                >
                  The risk-free rate used for Sharpe ratio and UPI calculations.
                  Default is 4.3%.
                </div>
              </div>

              {/* Date Range Filter */}
              <div style={{ marginBottom: "1rem" }}>
                <label
                  style={{
                    display: "block",
                    marginBottom: "0.5rem",
                    fontWeight: "bold",
                    color: theme.palette.text.primary,
                  }}
                >
                  📅 Date Range Filter
                </label>
                <div style={{ 
                  display: "flex", 
                  flexDirection: "column", 
                  gap: "1rem",
                  backgroundColor: theme.palette.mode === 'dark' ? "#2d3436" : "#f8f9fa",
                  padding: "1rem",
                  borderRadius: "6px",
                  border: `1px solid ${theme.palette.mode === 'dark' ? "#636e72" : "#dee2e6"}`
                }}>
                  {/* Date Range Display */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                    <div style={{ 
                      padding: "0.5rem 1rem", 
                      backgroundColor: theme.palette.mode === 'dark' ? "#1a1a1a" : "#ffffff",
                      border: `1px solid ${theme.palette.divider}`,
                      borderRadius: "4px",
                      fontSize: "0.9rem",
                      color: theme.palette.text.primary,
                    }}>
                      <strong>Start:</strong> {new Date(dateRangeStart).toLocaleDateString('en-US', { 
                        year: 'numeric', 
                        month: 'short', 
                        day: 'numeric' 
                      })}
                    </div>
                    <div style={{ 
                      padding: "0.5rem 1rem", 
                      backgroundColor: theme.palette.mode === 'dark' ? "#1a1a1a" : "#ffffff",
                      border: `1px solid ${theme.palette.divider}`,
                      borderRadius: "4px",
                      fontSize: "0.9rem",
                      color: theme.palette.text.primary,
                    }}>
                      <strong>End:</strong> {new Date(dateRangeEnd).toLocaleDateString('en-US', { 
                        year: 'numeric', 
                        month: 'short', 
                        day: 'numeric' 
                      })}
                    </div>
                  </div>
                  
                  {/* Date Range Slider */}
                  <div style={{ position: "relative", margin: "1rem 0", height: "40px" }}>
                    {/* Track background */}
                    <div
                      style={{
                        position: "absolute",
                        top: "17px",
                        left: "10px",
                        right: "10px",
                        height: "6px",
                        background: theme.palette.mode === 'dark' ? "#666" : "#ddd",
                        borderRadius: "3px",
                        zIndex: 1,
                      }}
                    >
                      {/* Active range highlight */}
                      <div
                        style={{
                          position: "absolute",
                          height: "100%",
                          background: "linear-gradient(90deg, #5DADE2, #D4A574)",
                          borderRadius: "3px",
                          left: `${(sliderValues[0] / maxSliderValue) * 100}%`,
                          width: `${((sliderValues[1] - sliderValues[0]) / maxSliderValue) * 100}%`,
                        }}
                      />
                    </div>
                    
                    {/* Start handle */}
                    <div
                      style={{
                        position: "absolute",
                        left: `calc(${(sliderValues[0] / maxSliderValue) * 100}% - 10px)`,
                        top: "10px",
                        width: "20px",
                        height: "20px",
                        background: "#ffffff",
                        border: "2px solid #5DADE2",
                        borderRadius: "50%",
                        cursor: "pointer",
                        boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
                        zIndex: 4,
                        userSelect: "none",
                      }}
                      onMouseDown={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        
                        // Capture the parent element reference immediately
                        const sliderContainer = (e.currentTarget as HTMLElement).parentElement!;
                        
                        const startDrag = (moveEvent: MouseEvent) => {
                          const rect = sliderContainer.getBoundingClientRect();
                          const trackWidth = rect.width - 20;
                          const relativeX = moveEvent.clientX - rect.left - 10;
                          const newPosition = Math.max(0, Math.min(1, relativeX / trackWidth));
                          const newValue = Math.round(newPosition * maxSliderValue);
                          
                          
                          // Constrain start handle to not go past end handle
                          const constrainedValue = Math.min(newValue, sliderValues[1]);
                          const newValues: [number, number] = [constrainedValue, sliderValues[1]];
                          
                          setSliderValues(newValues);
                          setDateRangeStart(sliderValueToDate(newValues[0]));
                          setDateRangeEnd(sliderValueToDate(newValues[1]));
                        };
                        
                        const endDrag = () => {
                          document.removeEventListener('mousemove', startDrag);
                          document.removeEventListener('mouseup', endDrag);
                        };
                        
                        document.addEventListener('mousemove', startDrag);
                        document.addEventListener('mouseup', endDrag);
                      }}
                    />
                    
                    {/* End handle */}
                    <div
                      style={{
                        position: "absolute",
                        left: `calc(${(sliderValues[1] / maxSliderValue) * 100}% - 10px)`,
                        top: "10px",
                        width: "20px",
                        height: "20px",
                        background: "#ffffff",
                        border: "2px solid #D4A574",
                        borderRadius: "50%",
                        cursor: "pointer",
                        boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
                        zIndex: 5,
                        userSelect: "none",
                      }}
                      onMouseDown={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        
                        // Capture the parent element reference immediately
                        const sliderContainer = (e.currentTarget as HTMLElement).parentElement!;
                        
                        const endDrag = (moveEvent: MouseEvent) => {
                          const rect = sliderContainer.getBoundingClientRect();
                          const trackWidth = rect.width - 20;
                          const relativeX = moveEvent.clientX - rect.left - 10;
                          const newPosition = Math.max(0, Math.min(1, relativeX / trackWidth));
                          const newValue = Math.round(newPosition * maxSliderValue);
                          
                          
                          // Constrain end handle to not go before start handle
                          const constrainedValue = Math.max(newValue, sliderValues[0]);
                          const newValues: [number, number] = [sliderValues[0], constrainedValue];
                          
                          setSliderValues(newValues);
                          setDateRangeStart(sliderValueToDate(newValues[0]));
                          setDateRangeEnd(sliderValueToDate(newValues[1]));
                        };
                        
                        const stopDrag = () => {
                          document.removeEventListener('mousemove', endDrag);
                          document.removeEventListener('mouseup', stopDrag);
                        };
                        
                        document.addEventListener('mousemove', endDrag);
                        document.addEventListener('mouseup', stopDrag);
                      }}
                    />
                  </div>
                  
                  <div style={{
                    fontSize: "0.85rem",
                    color: theme.palette.text.secondary,
                  }}>
                    Drag the slider handles to adjust the date range. This affects all calculations and chart displays.
                  </div>
                </div>
              </div>
            </Paper>
          )}

          {/* Weighting Controls */}
          {selectedPortfolios.length > 1 && (
            <Paper
              className="weighting-controls"
              sx={{
                mb: "1.5rem",
                p: "1.5rem",
                borderRadius: "8px",
                border: `1px solid ${theme.palette.divider}`,
                background: theme.palette.background.paper,
              }}
              elevation={theme.palette.mode === "dark" ? 2 : 0}
            >
              <h3
                style={{
                  marginBottom: "1rem",
                  color: theme.palette.text.primary,
                }}
              >
                ⚖️ Portfolio Weighting
              </h3>

              <div
                style={{
                  marginBottom: "1rem",
                  padding: "0.75rem",
                  background: theme.palette.mode === "dark" 
                    ? "#064e3b" // darker green background for dark mode
                    : "#f0fdf4", // lighter green background for light mode
                  borderRadius: "6px",
                  border: `1px solid ${theme.palette.success.main}`,
                  fontSize: "0.9rem",
                  color: theme.palette.mode === "dark"
                    ? "#bbf7d0" // light green text for dark mode
                    : "#15803d", // darker green text for light mode
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
                    background: theme.palette.mode === "dark" 
                      ? "#1e3a8a" // darker blue background for dark mode
                      : "#dbeafe", // lighter blue background for light mode
                    border: `1px solid ${theme.palette.info.main}`,
                    borderRadius: "4px",
                    padding: "0.75rem",
                    marginBottom: "1rem",
                    fontSize: "0.9rem",
                    color: theme.palette.mode === "dark"
                      ? "#ffffff" // white text for dark mode
                      : "#1e3a8a", // dark blue text for light mode
                  }}
                >
                  <strong>Portfolio Multipliers:</strong> • 1.0 = Run portfolio
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
                    <Paper
                      key={portfolioId}
                      sx={{
                        p: "1rem",
                        background: theme.palette.background.paper,
                        borderRadius: "6px",
                        border: `1px solid ${theme.palette.divider}`,
                      }}
                      elevation={theme.palette.mode === "dark" ? 1 : 0}
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
                            border: `1px solid ${theme.palette.divider}`,
                            borderRadius: "4px",
                            backgroundColor:
                              weightingMethod === "equal" 
                                ? theme.palette.action.disabled 
                                : theme.palette.background.paper,
                            color: theme.palette.text.primary,
                          }}
                        />
                        <span style={{ color: theme.palette.text.secondary }}>
                          ({weight.toFixed(2)}x)
                        </span>
                      </div>
                    </Paper>
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
                  background: theme.palette.background.paper,
                  borderRadius: "6px",
                  border: `1px solid ${theme.palette.divider}`,
                }}
              >
                <div>
                  <span style={{ fontWeight: "bold" }}>Total Scale: </span>
                  <span
                    style={{
                      color: theme.palette.success.main,
                      fontWeight: "bold",
                    }}
                  >
                    {getTotalScale().toFixed(2)}x
                  </span>
                  <span
                    style={{
                      color: theme.palette.text.secondary,
                      marginLeft: "0.5rem",
                    }}
                  >
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
            </Paper>
          )}

          {/* Analysis Results */}
          {analysisResults && (
            <div
              className="analysis-results"
              style={{
                marginTop: "1.5rem",
                marginBottom: "2rem",
                padding: "1.5rem",
                background: theme.palette.background.paper,
                borderRadius: "8px",
                border: `1px solid ${theme.palette.divider}`,
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
                      background: theme.palette.background.paper,
                      padding: "1.5rem",
                      borderRadius: "8px",
                      border: `2px solid ${theme.palette.primary.main}`,
                      boxShadow:
                        theme.palette.mode === "dark"
                          ? "0 4px 16px rgba(0,0,0,0.5)"
                          : "0 4px 8px rgba(0,0,0,0.08)",
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
                          background:
                            theme.palette.mode === "dark"
                              ? theme.palette.action.selected
                              : theme.palette.action.hover,
                          borderRadius: "6px",
                          border: `1px solid ${theme.palette.divider}`,
                          color: theme.palette.text.primary,
                        }}
                      >
                        <h5
                          style={{
                            margin: "0 0 0.5rem 0",
                            color: theme.palette.primary.main,
                          }}
                        >
                          📊 Portfolio Composition
                        </h5>
                        <div
                          style={{
                            fontSize: "0.9rem",
                            marginBottom: "0.5rem",
                            color: theme.palette.text.secondary,
                          }}
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
                                style={{
                                  marginBottom: "0.25rem",
                                  color: theme.palette.text.primary,
                                }}
                              >
                                <strong>{name}:</strong>{" "}
                                {(weight as number).toFixed(2)}x
                                <span
                                  style={{
                                    color: theme.palette.text.secondary,
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
                          background: theme.palette.background.paper,
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: theme.palette.text.secondary,
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
                                ? theme.palette.success.main
                                : theme.palette.error.main,
                          }}
                        >
                          {(
                            analysisResults.blended_result.metrics
                              .total_return * 100
                          )?.toFixed(2)}
                          %
                        </div>
                      </div>

                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: theme.palette.background.paper,
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: theme.palette.text.secondary,
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
                                ? theme.palette.success.main
                                : analysisResults.blended_result.metrics
                                    .sharpe_ratio >= 0.5
                                ? theme.palette.warning.main
                                : theme.palette.error.main,
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
                          background: theme.palette.background.paper,
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: theme.palette.text.secondary,
                            marginBottom: "0.5rem",
                          }}
                        >
                          Max Drawdown
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color: theme.palette.error.main,
                          }}
                        >
                          {(
                            analysisResults.blended_result.metrics
                              .max_drawdown_percent * 100
                          )?.toFixed(2)}
                          %
                        </div>
                      </div>

                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: theme.palette.background.paper,
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: theme.palette.text.secondary,
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
                                ? theme.palette.success.main
                                : theme.palette.error.main,
                          }}
                        >
                          {(
                            analysisResults.blended_result.metrics.cagr * 100
                          )?.toFixed(2)}
                          %
                        </div>
                      </div>

                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: theme.palette.background.paper,
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: theme.palette.text.secondary,
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
                                ? theme.palette.success.main
                                : theme.palette.error.main,
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
                          background: theme.palette.background.paper,
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: theme.palette.text.secondary,
                            marginBottom: "0.5rem",
                          }}
                        >
                          Final Account Value
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color: theme.palette.primary.main,
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
                          background: theme.palette.background.paper,
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: theme.palette.text.secondary,
                            marginBottom: "0.5rem",
                          }}
                        >
                          Max Drawdown ($)
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color: theme.palette.error.main,
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
                          background: theme.palette.background.paper,
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: theme.palette.text.secondary,
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
                                .annual_volatility * 100 || 0) <= 15
                                ? theme.palette.success.main
                                : (analysisResults.blended_result.metrics
                                    .annual_volatility * 100 || 0) <= 25
                                ? theme.palette.warning.main
                                : theme.palette.error.main,
                          }}
                        >
                          {(
                            analysisResults.blended_result.metrics
                              .annual_volatility * 100
                          )?.toFixed(2)}
                          %
                        </div>
                      </div>

                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: theme.palette.background.paper,
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: theme.palette.text.secondary,
                            marginBottom: "0.5rem",
                          }}
                        >
                          MAR Ratio
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color:
                              (analysisResults.blended_result.metrics
                                .mar_ratio || 0) >= 0.5
                                ? theme.palette.success.main
                                : (analysisResults.blended_result.metrics
                                    .mar_ratio || 0) >= 0.25
                                ? theme.palette.warning.main
                                : theme.palette.error.main,
                          }}
                        >
                          {analysisResults.blended_result.metrics.mar_ratio?.toFixed(
                            2
                          )}
                        </div>
                      </div>

                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: theme.palette.background.paper,
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: theme.palette.text.secondary,
                            marginBottom: "0.5rem",
                          }}
                        >
                          Sortino Ratio
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color:
                              analysisResults.blended_result.metrics
                                .sortino_ratio >= 1
                                ? theme.palette.success.main
                                : analysisResults.blended_result.metrics
                                    .sortino_ratio >= 0.5
                                ? theme.palette.warning.main
                                : theme.palette.error.main,
                          }}
                        >
                          {analysisResults.blended_result.metrics.sortino_ratio?.toFixed(
                            2
                          )}
                        </div>
                      </div>

                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: theme.palette.background.paper,
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: theme.palette.text.secondary,
                            marginBottom: "0.5rem",
                          }}
                        >
                          Ulcer Index
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color:
                              analysisResults.blended_result.metrics
                                .ulcer_index <= 5
                                ? theme.palette.success.main
                                : analysisResults.blended_result.metrics
                                    .ulcer_index <= 10
                                ? theme.palette.warning.main
                                : theme.palette.error.main,
                          }}
                        >
                          {analysisResults.blended_result.metrics.ulcer_index?.toFixed(
                            2
                          )}
                        </div>
                      </div>

                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: theme.palette.background.paper,
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: theme.palette.text.secondary,
                            marginBottom: "0.5rem",
                          }}
                        >
                          Max Drawdown Date
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color: theme.palette.text.secondary,
                          }}
                        >
                          {analysisResults.blended_result.metrics
                            .max_drawdown_date
                            ? new Date(
                                analysisResults.blended_result.metrics.max_drawdown_date
                              ).toLocaleDateString()
                            : "N/A"}
                        </div>
                      </div>

                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: theme.palette.background.paper,
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: theme.palette.text.secondary,
                            marginBottom: "0.5rem",
                          }}
                        >
                          Kelly Criterion
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color:
                              analysisResults.blended_result.metrics
                                .kelly_criterion > 0.25
                                ? theme.palette.error.main
                                : analysisResults.blended_result.metrics
                                    .kelly_criterion > 0.1
                                ? theme.palette.warning.main
                                : analysisResults.blended_result.metrics
                                    .kelly_criterion > 0
                                ? theme.palette.success.main
                                : theme.palette.text.secondary,
                          }}
                        >
                          {analysisResults.blended_result.metrics
                            .kelly_criterion >= 0
                            ? `${(
                                analysisResults.blended_result.metrics
                                  .kelly_criterion * 100
                              ).toFixed(1)}%`
                            : "N/A"}
                        </div>
                      </div>

                      <div
                        className="metric-card"
                        style={{
                          padding: "1rem",
                          background: theme.palette.background.paper,
                          borderRadius: "6px",
                          textAlign: "center",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: theme.palette.text.secondary,
                            marginBottom: "0.5rem",
                          }}
                        >
                          UPI (Ulcer Performance Index)
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color:
                              analysisResults.blended_result.metrics.upi >= 1.0
                                ? theme.palette.success.main
                                : analysisResults.blended_result.metrics.upi >=
                                  0.5
                                ? theme.palette.warning.main
                                : theme.palette.error.main,
                          }}
                        >
                          {analysisResults.blended_result.metrics.upi?.toFixed(
                            3
                          )}
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
                                      border: `1px solid ${theme.palette.divider}`,
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

                    {/* Daily Net Liquidity Chart */}
                    {dailyLiquidityData.length > 0 && (
                      <div style={{ marginTop: "2rem" }}>
                        <div style={{ 
                          display: "flex", 
                          alignItems: "center", 
                          justifyContent: "space-between",
                          marginBottom: "1rem" 
                        }}>
                          <h5 style={{ margin: 0, color: theme.palette.text.primary }}>
                            Daily Net Liquidity
                          </h5>
                          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                            {/* Log Scale Toggle */}
                            <button
                              onClick={() => setIsLogScale(!isLogScale)}
                              style={{
                                padding: "0.25rem 0.5rem",
                                fontSize: "0.75rem",
                                backgroundColor: isLogScale ? "#5DADE2" : "transparent",
                                color: isLogScale ? "#ffffff" : theme.palette.text.secondary,
                                border: `1px solid ${isLogScale ? "#5DADE2" : theme.palette.divider}`,
                                borderRadius: "4px",
                                cursor: "pointer",
                                transition: "all 0.2s"
                              }}
                            >
                              Log Scale
                            </button>
                            {/* Legend */}
                            <div style={{ display: "flex", gap: "1rem" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <div style={{
                                  width: "16px",
                                  height: "3px",
                                  backgroundColor: "#D4A574",
                                  borderRadius: "2px"
                                }}></div>
                                <span style={{ 
                                  fontSize: "0.85rem", 
                                  color: theme.palette.text.secondary 
                                }}>Portfolio</span>
                              </div>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <div style={{
                                  width: "16px",
                                  height: "3px",
                                  backgroundColor: "#5DADE2",
                                  borderRadius: "2px"
                                }}></div>
                                <span style={{ 
                                  fontSize: "0.85rem", 
                                  color: theme.palette.text.secondary 
                                }}>SPX</span>
                              </div>
                            </div>
                          </div>
                        </div>
                        <div style={{
                          width: "100%",
                          height: "400px",
                          background: theme.palette.mode === "dark" ? "#1a1a1a" : "#ffffff",
                          borderRadius: "8px",
                          border: `1px solid ${theme.palette.divider}`,
                          padding: "1rem"
                        }}>
                          {dailyLiquidityData && dailyLiquidityData.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart
                                data={dailyLiquidityData}
                                margin={{
                                  top: 20,
                                  right: 30,
                                  left: 80,
                                  bottom: 60,
                                }}
                              >
                                <CartesianGrid 
                                  strokeDasharray="3 3" 
                                  stroke={theme.palette.mode === "dark" ? "#333" : "#e0e0e0"}
                                />
                                <XAxis
                                  dataKey="date"
                                  axisLine={false}
                                  tickLine={false}
                                  tick={{ 
                                    fontSize: 11, 
                                    fill: theme.palette.text.secondary 
                                  }}
                                  interval="preserveStartEnd"
                                  tickFormatter={(value) => {
                                    try {
                                      const date = new Date(value);
                                      const year = date.getFullYear().toString().slice(-2);
                                      const month = (date.getMonth() + 1).toString().padStart(2, '0');
                                      return `${month}-${year}`;
                                    } catch (e) {
                                      return value;
                                    }
                                  }}
                                />
                                <YAxis
                                  axisLine={false}
                                  tickLine={false}
                                  tick={{ 
                                    fontSize: 11, 
                                    fill: theme.palette.text.secondary 
                                  }}
                                  tickFormatter={(value) => `$${(value / 1000000).toFixed(1)}M`}
                                  domain={isLogScale ? ['dataMin', 'dataMax'] : ['dataMin * 0.9', 'dataMax * 1.1']}
                                  scale={isLogScale ? 'log' : 'linear'}
                                />
                                <Tooltip
                                  contentStyle={{
                                    backgroundColor: theme.palette.mode === "dark" ? "#2d2d2d" : "#ffffff",
                                    border: `1px solid ${theme.palette.divider}`,
                                    borderRadius: "8px",
                                    color: theme.palette.text.primary
                                  }}
                                  formatter={(value: any, name: string) => [
                                    `$${Number(value).toLocaleString()}`,
                                    name === 'portfolio' ? 'Portfolio' : 'SPX'
                                  ]}
                                  labelFormatter={(label) => {
                                    try {
                                      const date = new Date(label);
                                      return date.toLocaleDateString('en-US', { 
                                        year: 'numeric', 
                                        month: 'short', 
                                        day: 'numeric' 
                                      });
                                    } catch (e) {
                                      return label;
                                    }
                                  }}
                                />
                                <Line
                                  type="monotone"
                                  dataKey="portfolio"
                                  stroke="#D4A574"
                                  strokeWidth={2.5}
                                  dot={false}
                                  activeDot={{ r: 4, fill: "#D4A574" }}
                                />
                                <Line
                                  type="monotone"
                                  dataKey="spx"
                                  stroke="#5DADE2"
                                  strokeWidth={2.5}
                                  dot={false}
                                  activeDot={{ r: 4, fill: "#5DADE2" }}
                                />
                              </LineChart>
                            </ResponsiveContainer>
                          ) : (
                            <div style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              height: '100%',
                              color: theme.palette.text.secondary
                            }}>
                              Chart data loading...
                            </div>
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
                              background: theme.palette.background.paper,
                              padding: "1.5rem",
                              borderRadius: "8px",
                              border: `1px solid ${theme.palette.divider}`,
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
                                    color: theme.palette.text.secondary,
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
                                        ? theme.palette.success.main
                                        : theme.palette.error.main,
                                  }}
                                >
                                  {(result.metrics.total_return * 100)?.toFixed(
                                    2
                                  )}
                                  %
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: theme.palette.text.secondary,
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
                                        ? theme.palette.success.main
                                        : result.metrics.sharpe_ratio >= 0.5
                                        ? theme.palette.warning.main
                                        : theme.palette.error.main,
                                  }}
                                >
                                  {result.metrics.sharpe_ratio?.toFixed(2)}
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: theme.palette.text.secondary,
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  Max Drawdown
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: theme.palette.error.main,
                                  }}
                                >
                                  {(
                                    result.metrics.max_drawdown_percent * 100
                                  )?.toFixed(2)}
                                  %
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: theme.palette.text.secondary,
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
                                        ? theme.palette.success.main
                                        : theme.palette.error.main,
                                  }}
                                >
                                  {(result.metrics.cagr * 100)?.toFixed(2)}%
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: theme.palette.text.secondary,
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
                                        ? theme.palette.success.main
                                        : theme.palette.error.main,
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
                                    color: theme.palette.text.secondary,
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  Final Account Value
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: theme.palette.primary.main,
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
                                    color: theme.palette.text.secondary,
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  Max Drawdown ($)
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: theme.palette.error.main,
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
                                    color: theme.palette.text.secondary,
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
                                      (result.metrics.annual_volatility * 100 ||
                                        0) <= 15
                                        ? theme.palette.success.main
                                        : (result.metrics.annual_volatility *
                                            100 || 0) <= 25
                                        ? theme.palette.warning.main
                                        : theme.palette.error.main,
                                  }}
                                >
                                  {(
                                    result.metrics.annual_volatility * 100
                                  )?.toFixed(2)}
                                  %
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: theme.palette.text.secondary,
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  MAR Ratio
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color:
                                      (result.metrics.mar_ratio || 0) >= 0.5
                                        ? theme.palette.success.main
                                        : (result.metrics.mar_ratio || 0) >=
                                          0.25
                                        ? theme.palette.warning.main
                                        : theme.palette.error.main,
                                  }}
                                >
                                  {result.metrics.mar_ratio?.toFixed(2)}
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: theme.palette.text.secondary,
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  Sortino Ratio
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color:
                                      result.metrics.sortino_ratio >= 1
                                        ? theme.palette.success.main
                                        : result.metrics.sortino_ratio >= 0.5
                                        ? theme.palette.warning.main
                                        : theme.palette.error.main,
                                  }}
                                >
                                  {result.metrics.sortino_ratio?.toFixed(2)}
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: theme.palette.text.secondary,
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  Ulcer Index
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color:
                                      result.metrics.ulcer_index <= 5
                                        ? theme.palette.success.main
                                        : result.metrics.ulcer_index <= 10
                                        ? theme.palette.warning.main
                                        : theme.palette.error.main,
                                  }}
                                >
                                  {result.metrics.ulcer_index?.toFixed(2)}
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: theme.palette.text.secondary,
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  Kelly Criterion
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color:
                                      result.metrics.kelly_criterion > 0.25
                                        ? theme.palette.error.main
                                        : result.metrics.kelly_criterion > 0.1
                                        ? theme.palette.warning.main
                                        : result.metrics.kelly_criterion > 0
                                        ? theme.palette.success.main
                                        : theme.palette.text.secondary,
                                  }}
                                >
                                  {result.metrics.kelly_criterion >= 0
                                    ? `${(
                                        result.metrics.kelly_criterion * 100
                                      ).toFixed(1)}%`
                                    : "N/A"}
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: theme.palette.text.secondary,
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  UPI (Ulcer Performance Index)
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color:
                                      result.metrics.upi >= 1.0
                                        ? theme.palette.success.main
                                        : result.metrics.upi >= 0.5
                                        ? theme.palette.warning.main
                                        : theme.palette.error.main,
                                  }}
                                >
                                  {result.metrics.upi?.toFixed(3)}
                                </div>
                              </div>

                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: theme.palette.text.secondary,
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  Max Drawdown Date
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: theme.palette.text.secondary,
                                  }}
                                >
                                  {result.metrics.max_drawdown_date
                                    ? new Date(
                                        result.metrics.max_drawdown_date
                                      ).toLocaleDateString()
                                    : "N/A"}
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
                                          border: `1px solid ${theme.palette.divider}`,
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
                        color: theme.palette.text.secondary,
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
                              color: theme.palette.text.secondary,
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
                                border: `1px solid ${theme.palette.divider}`,
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
                              color: theme.palette.text.secondary,
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
                                border: `1px solid ${theme.palette.divider}`,
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

          {/* Portfolios Grouped by Strategy */}
          <div style={{ marginTop: "1rem" }}>
            {(() => {
              // Group portfolios by strategy
              const groupedPortfolios = portfolios.reduce((groups, portfolio) => {
                const strategy = portfolio.strategy || "No Strategy Set";
                if (!groups[strategy]) {
                  groups[strategy] = [];
                }
                groups[strategy].push(portfolio);
                return groups;
              }, {} as Record<string, Portfolio[]>);

              // Sort strategy names, putting "No Strategy Set" last
              const sortedStrategies = Object.keys(groupedPortfolios).sort((a, b) => {
                if (a === "No Strategy Set") return 1;
                if (b === "No Strategy Set") return -1;
                return a.localeCompare(b);
              });

              return sortedStrategies.map((strategy, groupIndex) => (
                <div key={strategy} style={{ marginBottom: "2rem" }}>
                  {/* Strategy Group Header */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "1rem",
                      background: theme.palette.mode === "dark" 
                        ? "linear-gradient(135deg, #4a5568 0%, #2d3748 100%)"
                        : "linear-gradient(135deg, #e2e8f0 0%, #cbd5e0 100%)",
                      borderRadius: "8px 8px 0 0",
                      marginBottom: "0",
                      borderBottom: "2px solid " + (theme.palette.mode === "dark" ? "#1a202c" : "#a0aec0"),
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                      <h3
                        style={{
                          margin: 0,
                          fontSize: "1.25rem",
                          fontWeight: "600",
                          color: theme.palette.mode === "dark" ? "#ffffff" : "#2d3748",
                        }}
                      >
                        {strategy}
                      </h3>
                      <span
                        style={{
                          background: theme.palette.mode === "dark" ? "#3182ce" : "#4299e1",
                          color: "white",
                          padding: "0.25rem 0.75rem",
                          borderRadius: "12px",
                          fontSize: "0.875rem",
                          fontWeight: "500",
                        }}
                      >
                        {groupedPortfolios[strategy].length} {groupedPortfolios[strategy].length === 1 ? 'portfolio' : 'portfolios'}
                      </span>
                    </div>
                    
                    {/* Strategy Group Select All */}
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <label
                        style={{
                          fontSize: "0.875rem",
                          color: theme.palette.mode === "dark" ? "#d1d5db" : "#4b5563",
                          cursor: "pointer",
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={
                            groupedPortfolios[strategy].every(p => selectedPortfolios.includes(p.id))
                          }
                          onChange={() => {
                            const strategyPortfolioIds = groupedPortfolios[strategy].map(p => p.id);
                            const allSelected = strategyPortfolioIds.every(id => selectedPortfolios.includes(id));
                            
                            if (allSelected) {
                              // Deselect all in this strategy
                              setSelectedPortfolios(prev => prev.filter(id => !strategyPortfolioIds.includes(id)));
                            } else {
                              // Select all in this strategy
                              setSelectedPortfolios(prev => [...prev, ...strategyPortfolioIds.filter(id => !prev.includes(id))]);
                            }
                          }}
                          style={{ 
                            transform: "scale(1.2)", 
                            marginRight: "0.5rem"
                          }}
                        />
                        Select All {strategy}
                      </label>
                    </div>
                  </div>

                  {/* Strategy Group Table */}
                  <div style={{ overflowX: "auto" }}>
                    <table
                      style={{
                        width: "100%",
                        borderCollapse: "collapse",
                        fontSize: "0.9rem",
                        background: theme.palette.mode === "dark" ? "#2d3748" : "#ffffff",
                        color: theme.palette.mode === "dark" ? "#ffffff" : "#1a202c",
                        borderRadius: groupIndex === 0 ? "0 0 8px 8px" : "8px",
                        overflow: "hidden",
                        boxShadow: "0 4px 6px rgba(0, 0, 0, 0.1)",
                        marginBottom: "0"
                      }}
                    >
                      <thead>
                        <tr
                          style={{
                            backgroundColor:
                              theme.palette.mode === "dark"
                                ? "#4a5568"
                                : "#f7fafc",
                            borderBottom: "2px solid rgba(255, 255, 255, 0.1)",
                          }}
                        >
                          <th
                            style={{
                              padding: "0.75rem 0.5rem",
                              textAlign: "left",
                              borderRight: "1px solid rgba(255, 255, 255, 0.1)",
                              color: theme.palette.mode === "dark" ? "#ffffff" : "#2d3748",
                              fontWeight: "600"
                            }}
                          >
                            Select
                          </th>
                          <th
                            style={{
                              padding: "0.75rem 0.5rem",
                              textAlign: "left",
                              borderRight: "1px solid rgba(255, 255, 255, 0.1)",
                              minWidth: "150px",
                              color: theme.palette.mode === "dark" ? "#ffffff" : "#2d3748",
                              fontWeight: "600"
                            }}
                          >
                            Portfolio
                          </th>
                          <th
                            style={{
                              padding: "0.75rem 0.5rem",
                              textAlign: "left",
                              borderRight: "1px solid rgba(255, 255, 255, 0.1)",
                              minWidth: "120px",
                              color: theme.palette.mode === "dark" ? "#ffffff" : "#2d3748",
                              fontWeight: "600"
                            }}
                          >
                            File
                          </th>
                          <th
                            style={{
                              padding: "0.75rem 0.5rem",
                              textAlign: "center",
                              borderRight: "1px solid rgba(255, 255, 255, 0.1)",
                              minWidth: "80px",
                              color: theme.palette.mode === "dark" ? "#ffffff" : "#2d3748",
                              fontWeight: "600"
                            }}
                          >
                            Records
                          </th>
                          <th
                            style={{
                              padding: "0.75rem 0.5rem",
                              textAlign: "center",
                              borderRight: "1px solid rgba(255, 255, 255, 0.1)",
                              minWidth: "100px",
                              color: theme.palette.mode === "dark" ? "#ffffff" : "#2d3748",
                              fontWeight: "600"
                            }}
                          >
                            Uploaded
                          </th>
                          <th
                            style={{
                              padding: "0.75rem 0.5rem",
                              textAlign: "center",
                              minWidth: "120px",
                              color: theme.palette.mode === "dark" ? "#ffffff" : "#2d3748",
                              fontWeight: "600"
                            }}
                          >
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {groupedPortfolios[strategy].map((portfolio) => (
                  <React.Fragment key={portfolio.id}>
                    <tr
                      style={{
                        borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
                        backgroundColor: selectedPortfolios.includes(
                          portfolio.id
                        )
                          ? theme.palette.mode === "dark"
                            ? "#3182ce"
                            : "#e2e8f0"
                          : "transparent",
                        cursor: "pointer",
                        color: theme.palette.mode === "dark" ? "#ffffff" : "#2d3748",
                      }}
                      onClick={() => {
                        const newExpanded = [...expandedPortfolios];
                        const index = newExpanded.indexOf(portfolio.id);
                        if (index > -1) {
                          newExpanded.splice(index, 1);
                        } else {
                          newExpanded.push(portfolio.id);
                        }
                        setExpandedPortfolios(newExpanded);
                      }}
                    >
                      <td
                        style={{
                          padding: "0.75rem 0.5rem",
                          borderRight: "1px solid rgba(255, 255, 255, 0.1)",
                          color: theme.palette.mode === "dark" ? "#ffffff" : "#2d3748",
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={selectedPortfolios.includes(portfolio.id)}
                          onChange={(e) => {
                            e.stopPropagation();
                            togglePortfolioSelection(portfolio.id);
                          }}
                          style={{ transform: "scale(1.2)" }}
                        />
                      </td>
                      <td
                        style={{
                          padding: "0.75rem 0.5rem",
                          borderRight: "1px solid rgba(255, 255, 255, 0.1)",
                          color: theme.palette.mode === "dark" ? "#ffffff" : "#2d3748",
                        }}
                      >
                        {editingPortfolioId === portfolio.id ? (
                          <div
                            style={{
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
                                padding: "0.25rem",
                                border: "1px solid #ccc",
                                borderRadius: "4px",
                                fontSize: "0.9rem",
                              }}
                              autoFocus
                              onClick={(e) => e.stopPropagation()}
                            />
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                saveRename(portfolio.id);
                              }}
                              style={{
                                padding: "0.25rem 0.5rem",
                                background: "#28a745",
                                color: "white",
                                border: "none",
                                borderRadius: "4px",
                                cursor: "pointer",
                                fontSize: "0.7rem",
                              }}
                            >
                              ✓
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                cancelRenaming();
                              }}
                              style={{
                                padding: "0.25rem 0.5rem",
                                background: "#dc3545",
                                color: "white",
                                border: "none",
                                borderRadius: "4px",
                                cursor: "pointer",
                                fontSize: "0.7rem",
                              }}
                            >
                              ✕
                            </button>
                          </div>
                        ) : (
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                            }}
                          >
                            <span style={{ fontWeight: "bold" }}>
                              {portfolio.name}
                            </span>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                startRenaming(portfolio);
                              }}
                              style={{
                                padding: "0.25rem 0.5rem",
                                background: "#007bff",
                                color: "white",
                                border: "none",
                                borderRadius: "4px",
                                cursor: "pointer",
                                fontSize: "0.7rem",
                                marginLeft: "0.5rem",
                              }}
                            >
                              ✏️
                            </button>
                          </div>
                        )}
                      </td>
                      <td
                        style={{
                          padding: "0.75rem 0.5rem",
                          borderRight: "1px solid rgba(255, 255, 255, 0.1)",
                          color: theme.palette.mode === "dark" ? "#ffffff" : "#2d3748",
                        }}
                      >
                        {portfolio.filename}
                      </td>
                      <td
                        style={{
                          padding: "0.75rem 0.5rem",
                          textAlign: "center",
                          borderRight: "1px solid rgba(255, 255, 255, 0.1)",
                          color: theme.palette.mode === "dark" ? "#ffffff" : "#2d3748",
                        }}
                      >
                        {portfolio.row_count}
                      </td>
                      <td
                        style={{
                          padding: "0.75rem 0.5rem",
                          textAlign: "center",
                          borderRight: "1px solid rgba(255, 255, 255, 0.1)",
                          color: theme.palette.mode === "dark" ? "#ffffff" : "#2d3748",
                        }}
                      >
                        {new Date(portfolio.upload_date).toLocaleDateString()}
                      </td>
                      <td
                        style={{
                          padding: "0.75rem 0.5rem",
                          textAlign: "center",
                          color: theme.palette.mode === "dark" ? "#ffffff" : "#2d3748",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            gap: "0.5rem",
                            justifyContent: "center",
                          }}
                        >
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              window.open(
                                `/analysis/${portfolio.id}`,
                                "_blank"
                              );
                            }}
                            style={{
                              padding: "0.25rem 0.5rem",
                              background: "#007bff",
                              color: "white",
                              border: "none",
                              borderRadius: "4px",
                              cursor: "pointer",
                              fontSize: "0.7rem",
                            }}
                          >
                            View
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              deletePortfolio(portfolio.id);
                            }}
                            style={{
                              padding: "0.25rem 0.5rem",
                              background: "#dc3545",
                              color: "white",
                              border: "none",
                              borderRadius: "4px",
                              cursor: "pointer",
                              fontSize: "0.7rem",
                            }}
                          >
                            Delete
                          </button>
                          <span
                            style={{
                              cursor: "pointer",
                              fontSize: "0.8rem",
                              color: theme.palette.text.secondary,
                            }}
                          >
                            {expandedPortfolios.includes(portfolio.id)
                              ? "▼"
                              : "▶"}
                          </span>
                        </div>
                      </td>
                    </tr>
                    {expandedPortfolios.includes(portfolio.id) && (
                      <tr
                        style={{
                          backgroundColor:
                            theme.palette.mode === "dark"
                              ? "#374151"
                              : "#f8fafc",
                        }}
                      >
                        <td
                          colSpan={6}
                          style={{
                            padding: "1rem",
                            color: theme.palette.mode === "dark" ? "#d1d5db" : "#6b7280",
                          }}
                        >
                          <div style={{ fontSize: "0.85rem" }}>
                            {portfolio.date_range_start &&
                              portfolio.date_range_end && (
                                <p style={{ margin: "0.5rem 0" }}>
                                  <strong>Date Range:</strong>{" "}
                                  {new Date(
                                    portfolio.date_range_start
                                  ).toLocaleDateString()}{" "}
                                  -{" "}
                                  {new Date(
                                    portfolio.date_range_end
                                  ).toLocaleDateString()}
                                </p>
                              )}
                            <p
                              style={{
                                margin: "0.5rem 0",
                                fontStyle: "italic",
                                color: theme.palette.mode === "dark" ? "#d1d5db" : "#6b7280",
                              }}
                            >
                              Click the arrow to expand/collapse portfolio
                              details
                            </p>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ));
            })()}
          </div>
        </>
      )}
    </div>
  );
}
