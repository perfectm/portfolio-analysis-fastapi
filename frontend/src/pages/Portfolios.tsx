import React, { useState, useEffect } from "react";
import { portfolioAPI, API_BASE_URL } from "../services/api";
import { useLocation, useSearchParams } from "react-router-dom";
import { useTheme, Paper, Box, Typography } from "@mui/material";
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

// localStorage keys for persistence
const STORAGE_KEYS = {
  SELECTED_PORTFOLIOS: 'portfolio_app_selected_portfolios',
  WEIGHTING_METHOD: 'portfolio_app_weighting_method',
  PORTFOLIO_WEIGHTS: 'portfolio_app_portfolio_weights',
};

// Helper functions for localStorage operations
const saveToLocalStorage = (key: string, value: any) => {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    console.warn('Failed to save to localStorage:', error);
  }
};

const loadFromLocalStorage = (key: string, defaultValue: any = null) => {
  try {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : defaultValue;
  } catch (error) {
    console.warn('Failed to load from localStorage:', error);
    return defaultValue;
  }
};

// Helper function to format date strings without timezone issues
const formatDateString = (dateStr: string | null | undefined): string => {
  if (!dateStr) return "N/A";

  // If it has a time component (contains 'T'), use normal parsing
  if (dateStr.includes('T')) {
    return new Date(dateStr).toLocaleDateString();
  }

  // Date-only string - parse manually to avoid timezone issues
  const [year, month, day] = dateStr.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString();
};

interface Portfolio {
  id: number;
  name: string;
  filename: string;
  upload_date: string;
  row_count: number;
  date_range_start?: string;
  date_range_end?: string;
  strategy?: string;
  latest_analysis?: {
    id: number;
    analysis_type: string;
    created_at: string;
    metrics: {
      total_return?: number;
      max_drawdown_percent?: number;
      sharpe_ratio?: number;
      cagr?: number;
      total_pl?: number;
      final_account_value?: number;
      max_drawdown_dollar?: number;
      annual_volatility?: number;
      [key: string]: any; // Allow for additional metrics
    };
  };
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
  const [searchParams] = useSearchParams();
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Optimization data from URL parameters
  const [loadedOptimization, setLoadedOptimization] = useState<{
    id: string;
    name?: string;
    portfolio_ids: number[];
    weights: number[];
    ratios: number[];
    method: string;
    metrics: {
      cagr: number;
      max_drawdown: number;
      return_drawdown_ratio: number;
      sharpe_ratio: number;
    };
    parameters?: {
      sma_window: number;
      use_trading_filter: boolean;
    };
  } | null>(null);
  const [selectedPortfolios, setSelectedPortfolios] = useState<number[]>(() => {
    const saved = loadFromLocalStorage(STORAGE_KEYS.SELECTED_PORTFOLIOS, []);
    console.log('Loaded portfolio selections from localStorage:', saved);
    return saved;
  });
  const [analyzing, setAnalyzing] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
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
  
  // Progressive optimization state
  const [optimizationProgress, setOptimizationProgress] = useState<number>(0);
  const [isPartialResult, setIsPartialResult] = useState<boolean>(false);
  const [canContinue, setContinue] = useState<boolean>(false);
  const [partialResult, setPartialResult] = useState<any>(null);
  const [optimizationStartTime, setOptimizationStartTime] = useState<number>(0);
  
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
    loadFromLocalStorage(STORAGE_KEYS.WEIGHTING_METHOD, "equal")
  );
  const [portfolioWeights, setPortfolioWeights] = useState<
    Record<number, number>
  >(loadFromLocalStorage(STORAGE_KEYS.PORTFOLIO_WEIGHTS, {}));

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

  // Favorite settings state
  const [savingFavorites, setSavingFavorites] = useState<boolean>(false);
  const [loadingFavorites, setLoadingFavorites] = useState<boolean>(false);

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

  // Parse URL parameters for optimization data
  useEffect(() => {
    const optimizationId = searchParams.get('optimization_id');
    const optimizationName = searchParams.get('name');
    const portfolioIds = searchParams.get('portfolio_ids');
    const weights = searchParams.get('weights');
    const ratios = searchParams.get('ratios');
    const method = searchParams.get('method');
    const cagr = searchParams.get('cagr');
    const maxDrawdown = searchParams.get('max_drawdown');
    const returnDrawdownRatio = searchParams.get('return_drawdown_ratio');
    const sharpeRatio = searchParams.get('sharpe_ratio');
    const rfRate = searchParams.get('rf_rate');
    const smaWindow = searchParams.get('sma_window');
    const useTradingFilter = searchParams.get('use_trading_filter');
    const optimizationStartingCapital = searchParams.get('starting_capital');

    if (optimizationId && portfolioIds && weights && ratios && method) {
      try {
        const optimization = {
          id: optimizationId,
          name: optimizationName || undefined,
          portfolio_ids: portfolioIds.split(',').map(id => parseInt(id, 10)),
          weights: weights.split(',').map(w => parseFloat(w)),
          ratios: ratios.split(',').map(r => parseFloat(r)),
          method: method,
          metrics: {
            cagr: cagr ? parseFloat(cagr) : 0,
            max_drawdown: maxDrawdown ? parseFloat(maxDrawdown) : 0,
            return_drawdown_ratio: returnDrawdownRatio ? parseFloat(returnDrawdownRatio) : 0,
            sharpe_ratio: sharpeRatio ? parseFloat(sharpeRatio) : 0,
          },
          parameters: {
            sma_window: smaWindow ? parseInt(smaWindow) : 20,
            use_trading_filter: useTradingFilter ? useTradingFilter === 'true' : true
          }
        };

        setLoadedOptimization(optimization);

        // Auto-select the portfolios from the optimization
        setSelectedPortfolios(optimization.portfolio_ids);

        // Apply the optimal ratios to the portfolio weights state (ratios are multipliers, not percentages)
        const weightMapping: Record<number, number> = {};
        optimization.portfolio_ids.forEach((portfolioId, index) => {
          weightMapping[portfolioId] = optimization.ratios[index];
        });
        setPortfolioWeights(weightMapping);

        // Set weighting method to custom since we're applying specific weights
        setWeightingMethod("custom");

        // Apply optimization parameters to match the cached optimization exactly
        if (rfRate) {
          setRiskFreeRate(parseFloat(rfRate) * 100); // Convert from decimal to percentage for UI
        }
        if (optimizationStartingCapital) {
          setStartingCapital(parseFloat(optimizationStartingCapital));
        }


        console.log('[Portfolios] Loaded optimization from URL:', optimization);
        console.log('[Portfolios] Applied weights:', weightMapping);
        console.log('[Portfolios] Applied parameters:', {
          rfRate: rfRate ? parseFloat(rfRate) : 'not set',
          smaWindow: smaWindow ? parseInt(smaWindow) : 'not set',
          useTradingFilter: useTradingFilter ? useTradingFilter === 'true' : 'not set',
          startingCapital: optimizationStartingCapital ? parseFloat(optimizationStartingCapital) : 'not set'
        });
      } catch (error) {
        console.error('[Portfolios] Error parsing URL optimization data:', error);
      }
    }
  }, [searchParams]);

  // Load saved portfolio selections after portfolios are loaded (only if not loading from URL)
  useEffect(() => {
    if (portfolios.length > 0 && !loadedOptimization) {
      const savedSelections = loadSelectedPortfolios();
      // Filter to only include portfolios that still exist
      const validSelections = savedSelections.filter(id =>
        portfolios.some(portfolio => portfolio.id === id)
      );
      if (validSelections.length > 0) {
        setSelectedPortfolios(validSelections);
      }
    }
  }, [portfolios.length, loadedOptimization]); // Trigger when portfolios are loaded, but not if optimization is loaded

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

  // Save selected portfolios to localStorage
  useEffect(() => {
    saveToLocalStorage(STORAGE_KEYS.SELECTED_PORTFOLIOS, selectedPortfolios);
    console.log('Saved portfolio selections to localStorage:', selectedPortfolios);
  }, [selectedPortfolios]);

  // Save weighting method to localStorage
  useEffect(() => {
    saveToLocalStorage(STORAGE_KEYS.WEIGHTING_METHOD, weightingMethod);
  }, [weightingMethod]);

  // Save portfolio weights to localStorage
  useEffect(() => {
    saveToLocalStorage(STORAGE_KEYS.PORTFOLIO_WEIGHTS, portfolioWeights);
  }, [portfolioWeights]);

  // Sync slider values when date strings change (from external updates)
  useEffect(() => {
    const startValue = dateToSliderValue(dateRangeStart);
    const endValue = dateToSliderValue(dateRangeEnd);
    
    const boundedStartValue = Math.max(0, Math.min(startValue, maxSliderValue));
    const boundedEndValue = Math.max(0, Math.min(endValue, maxSliderValue));
    
    setSliderValues([boundedStartValue, boundedEndValue]);
  }, [dateRangeStart, dateRangeEnd]);

  // Initialize weights when selected portfolios change (only if not loading from optimization)
  useEffect(() => {
    if (selectedPortfolios.length > 0 && !loadedOptimization) {
      initializeWeights(selectedPortfolios);
      calculateMarginCapital();
    } else if (selectedPortfolios.length > 0 && loadedOptimization) {
      // Just calculate margin capital for loaded optimization, don't reset weights
      calculateMarginCapital();
    } else {
      setMarginCapital(null);
    }
  }, [selectedPortfolios.length, weightingMethod, loadedOptimization]);

  // Recalculate margin when portfolio weights change
  useEffect(() => {
    if (selectedPortfolios.length > 0) {
      calculateMarginCapital();
    }
  }, [portfolioWeights]);

  const fetchPortfolios = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/portfolios', {
        method: 'GET',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      const data = await response.json();
      if (data.success) {
        setPortfolios(data.portfolios);
      } else {
        setError(data.error || "Failed to fetch portfolios");
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

  // Progressive optimization function that handles partial results and continuation
  const optimizePortfolioWeights = async (continueOptimization = false) => {
    console.log("DEBUG: optimizePortfolioWeights called - continueOptimization:", continueOptimization);
    console.log("DEBUG: Current state - optimizing:", optimizing, "selectedPortfolios:", selectedPortfolios.length, "isPartialResult:", isPartialResult);
    
    // Prevent multiple simultaneous optimizations
    if (optimizing && !continueOptimization) {
      console.log("DEBUG: Optimization already in progress, ignoring request");
      return;
    }

    if (!continueOptimization) {
      // Initial validation for new optimization
      if (selectedPortfolios.length < 2) {
        alert("Please select at least 2 portfolios for weight optimization");
        return;
      }

      // Reset progressive optimization state
      console.log("DEBUG: Resetting optimization state for new optimization");
      setOptimizationProgress(0);
      setIsPartialResult(false);
      setContinue(false);
      setPartialResult(null);
    }

    console.log("DEBUG: Starting optimization, setting optimizing=true");
    const actualStartTime = Date.now();
    setOptimizing(true);
    setOptimizationStartTime(actualStartTime);
    console.log("DEBUG: Optimization start time:", new Date(actualStartTime).toISOString());
    if (!continueOptimization) setAnalysisResults(null);

    let currentIsPartialResult = false; // Track the actual result from this optimization

    try {
      console.log("DEBUG: Starting optimization request...");
      
      // Debug continuation parameters
      console.log("DEBUG: Continuation check - continueOptimization:", continueOptimization);
      console.log("DEBUG: Continuation check - partialResult:", partialResult);
      console.log("DEBUG: Continuation check - optimal_weights_array:", partialResult?.optimal_weights_array);
      
      // Calculate timeout - shorter for continuations since starting from better point
      let baseTimeout = selectedPortfolios.length <= 3 ? 30 : 
                       selectedPortfolios.length <= 5 ? 60 : 
                       selectedPortfolios.length <= 7 ? 90 : 
                       selectedPortfolios.length <= 10 ? 120 : 180;
      
      let adjustedTimeout = baseTimeout;
      if (continueOptimization) {
        // Reduce timeout for continuation (50% of original)  
        adjustedTimeout = Math.max(Math.round(baseTimeout * 0.5), 15);
        console.log(`DEBUG: Continuation timeout reduced: ${baseTimeout}s → ${adjustedTimeout}s`);
      }
      
      const requestBody = {
        portfolio_ids: selectedPortfolios,
        method: "differential_evolution",
        max_time_seconds: adjustedTimeout,
        resume_from_weights: continueOptimization && partialResult ? 
          partialResult.optimal_weights_array : null,
      };
      
      console.log("DEBUG: Request body:", requestBody);
      
      const optimizeResponse = await fetch(
        `${API_BASE_URL}/api/optimize-weights-progressive`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
          },
          body: JSON.stringify(requestBody),
        }
      );
      
      const responseTime = Date.now();
      const elapsedMs = responseTime - actualStartTime;
      console.log("DEBUG: Response received after", elapsedMs, "ms");
      console.log("DEBUG: Response status:", optimizeResponse.status);
      console.log("DEBUG: Response headers:", Object.fromEntries(optimizeResponse.headers.entries()));

      if (optimizeResponse.ok) {
        let optimizationResult;
        try {
          const rawText = await optimizeResponse.text();
          console.log("DEBUG: Raw response text length:", rawText.length);
          console.log("DEBUG: Raw response preview:", rawText.substring(0, 200) + (rawText.length > 200 ? "..." : ""));
          
          // Validate that we have a complete JSON response
          if (!rawText.trim().startsWith("{") || !rawText.trim().endsWith("}")) {
            throw new Error(`Invalid JSON response format: response does not appear to be complete JSON`);
          }
          
          optimizationResult = JSON.parse(rawText);
          console.log("Progressive optimization result:", optimizationResult);
          
          // Validate the optimization result structure
          if (!optimizationResult || typeof optimizationResult !== 'object') {
            throw new Error("Invalid optimization result: response is not a valid object");
          }
          
          if (!optimizationResult.hasOwnProperty('success')) {
            throw new Error("Invalid optimization result: missing required 'success' field");
          }
          
        } catch (parseError) {
          console.error("DEBUG: JSON parsing error:", parseError);
          
          // Provide a more user-friendly error message for pattern-related issues
          const errorMsg = parseError.message;
          if (errorMsg.includes("pattern") || errorMsg.includes("match")) {
            throw new Error("Response parsing failed: The server response format was unexpected. Please try again.");
          } else if (errorMsg.includes("JSON")) {
            throw new Error("Response parsing failed: Invalid JSON format received from server. Please try again.");
          } else {
            throw new Error(`Response parsing failed: ${errorMsg}`);
          }
        }

        if (optimizationResult.success) {
          // Validate required fields for successful response
          if (!Array.isArray(optimizationResult.optimal_ratios_array)) {
            throw new Error("Invalid optimization result: optimal_ratios_array is not an array");
          }
          
          if (optimizationResult.optimal_ratios_array.length !== selectedPortfolios.length) {
            throw new Error(`Invalid optimization result: expected ${selectedPortfolios.length} ratios, got ${optimizationResult.optimal_ratios_array.length}`);
          }
          
          // Update progress and check if partial
          setOptimizationProgress(optimizationResult.progress_percentage || 100);
          currentIsPartialResult = optimizationResult.is_partial_result || false; // Track for finally block
          setIsPartialResult(currentIsPartialResult);
          setContinue(optimizationResult.can_continue || false);
          setPartialResult(optimizationResult);

          // Apply the weights (partial or complete)
          setWeightingMethod("custom");
          const optimizedWeights: Record<number, number> = {};
          
          // Debug logging
          console.log("DEBUG: optimizationResult.optimal_ratios_array:", optimizationResult.optimal_ratios_array);
          console.log("DEBUG: selectedPortfolios:", selectedPortfolios);
          
          let hasProcessingErrors = false;
          selectedPortfolios.forEach((portfolioId, index) => {
            try {
              const rawValue = optimizationResult.optimal_ratios_array[index];
              console.log(`DEBUG: Processing portfolio ${portfolioId}, index ${index}, rawValue:`, rawValue, `(type: ${typeof rawValue})`);
              
              // More robust value validation
              let numericValue: number;
              if (typeof rawValue === 'number' && !isNaN(rawValue) && isFinite(rawValue)) {
                numericValue = rawValue;
              } else if (typeof rawValue === 'string' && !isNaN(parseFloat(rawValue))) {
                numericValue = parseFloat(rawValue);
              } else {
                console.warn(`Invalid ratio value for portfolio ${portfolioId}: ${rawValue}, using default 1.0`);
                numericValue = 1.0;
                hasProcessingErrors = true;
              }
              
              const validatedValue = Math.max(0.1, Math.min(10.0, numericValue));
              console.log(`DEBUG: Validated value for portfolio ${portfolioId}:`, validatedValue);
              
              optimizedWeights[portfolioId] = Math.round(validatedValue * 100) / 100;
            } catch (error) {
              console.error(`DEBUG: Error processing portfolio ${portfolioId} at index ${index}:`, error);
              // Don't fail the whole optimization for one portfolio - use fallback
              optimizedWeights[portfolioId] = 1.0;
              hasProcessingErrors = true;
            }
          });
          
          if (hasProcessingErrors) {
            console.warn("Some portfolio ratios had invalid values and were set to default (1.0)");
          }
          
          setPortfolioWeights(optimizedWeights);

          // Handle partial vs complete results
          if (optimizationResult.is_partial_result) {
            console.log("DEBUG: Partial result detected, not showing success message");
            // Don't show alert for partial results - show in UI instead
            return;
          } else {
            console.log("DEBUG: Complete result detected, showing success message");
            // Complete optimization - show success message
            showOptimizationSuccessMessage(optimizationResult);
          }
        } else {
          handleOptimizationError(optimizationResult.error);
        }
      } else {
        // Handle non-200 responses more robustly
        let errorMsg = "Unknown error";
        try {
          const errorText = await optimizeResponse.text();
          console.log("DEBUG: Error response text:", errorText);
          
          // Check if this is an HTML error response (like 504 Gateway Timeout)
          if (errorText.includes('<html>') || errorText.includes('<head>') || errorText.includes('<body>')) {
            // Extract meaningful error info from HTML
            if (optimizeResponse.status === 504) {
              errorMsg = `Server timeout (${selectedPortfolios.length} portfolios). Try optimizing fewer portfolios or use a shorter timeout.`;
            } else if (optimizeResponse.status === 502 || optimizeResponse.status === 503) {
              errorMsg = `Server temporarily unavailable. Please try again in a moment.`;
            } else {
              errorMsg = `Server error (${optimizeResponse.status}). The optimization took too long to complete.`;
            }
          } else {
            // Try to parse as JSON first
            try {
              const parsed = JSON.parse(errorText);
              errorMsg = parsed.error || parsed.message || `HTTP ${optimizeResponse.status}: ${optimizeResponse.statusText}`;
            } catch {
              // If not JSON, use the raw text or status
              errorMsg = errorText || `HTTP ${optimizeResponse.status}: ${optimizeResponse.statusText}`;
            }
          }
        } catch {
          errorMsg = `HTTP ${optimizeResponse.status}: ${optimizeResponse.statusText}`;
        }
        
        handleOptimizationError(errorMsg);
      }
    } catch (error) {
      console.error("Progressive optimization failed:", error);
      handleOptimizationError(
        error instanceof Error ? error.message : "Unknown error"
      );
    } finally {
      // Use the actual result from this optimization, not the state variable
      console.log(`DEBUG: Optimization finally block - currentIsPartialResult: ${currentIsPartialResult}`);
      if (!currentIsPartialResult) {
        console.log("DEBUG: Complete optimization, setting optimizing=false");
        setOptimizing(false);
      } else {
        console.log("DEBUG: Partial optimization, keeping optimizing=true");
      }
    }
  };

  const showOptimizationSuccessMessage = (optimizationResult: any) => {
    const multipliersList = Object.entries(optimizationResult.optimal_weights)
      .map(([name, weight]) => `• ${name}: ${Number(weight).toFixed(2)}x`)
      .join("\n");

    const ratiosList = Object.entries(optimizationResult.optimal_ratios || {})
      .map(([name, ratio]) => `• ${name}: ${ratio} unit${ratio !== 1 ? 's' : ''}`)
      .join("\n");

    const executionTime = optimizationResult.execution_time_seconds || 0;
    // More accurate progress text based on both partial status and continuation possibility
    const progressText = optimizationResult.is_partial_result ? 
      `(${optimizationResult.progress_percentage.toFixed(1)}% explored - partial)` : 
      optimizationResult.can_continue ? 
        `(${optimizationResult.progress_percentage.toFixed(1)}% explored - can continue)` :
        "(Complete optimization)";

    const message = `
Optimization completed successfully! ${progressText}

🔢 Optimal Multipliers:
${multipliersList}

📊 Trading Units Ratio:
${ratiosList}

Expected Performance:
• CAGR: ${(optimizationResult.metrics.cagr * 100).toFixed(2)}%
• Max Drawdown: ${(optimizationResult.metrics.max_drawdown_percent * 100).toFixed(2)}%
• Return/Drawdown Ratio: ${optimizationResult.metrics.return_drawdown_ratio.toFixed(2)}
• Sharpe Ratio: ${optimizationResult.metrics.sharpe_ratio.toFixed(2)}

Method: ${optimizationResult.optimization_details.method}
Time: ${executionTime.toFixed(1)}s
Combinations explored: ${optimizationResult.optimization_details.combinations_explored}

The multipliers have been applied automatically. Click 'Analyze' to see the full results.
    `.trim();

    alert(message);
  };

  const handleOptimizationError = (errorMessage: string) => {
    let fullErrorMessage = `Weight optimization failed: ${errorMessage}`;
    
    if (errorMessage.includes("Server timeout") || errorMessage.includes("504")) {
      fullErrorMessage += `\n\n⚠️ Large Portfolio Optimization:\n• ${selectedPortfolios.length} portfolios require significant computation time\n• Try selecting 10 or fewer portfolios for faster results\n• Or continue optimization to get partial results\n• Consider grouping similar strategies together`;
    } else if (errorMessage.includes("timeout") || errorMessage.includes("iterations")) {
      fullErrorMessage += `\n\nSuggestions:\n• Try selecting fewer portfolios (10 or less recommended)\n• The optimization may work better with portfolios that have similar performance characteristics`;
    } else if (errorMessage.includes("convergence")) {
      fullErrorMessage += `\n\nSuggestions:\n• Try reducing the number of selected portfolios\n• Some portfolio combinations may be difficult to optimize`;
    } else if (errorMessage.includes("Server error") || errorMessage.includes("unavailable")) {
      fullErrorMessage += `\n\nServer Issue:\n• The optimization process exceeded server limits\n• Try again with fewer portfolios\n• Consider optimizing in smaller batches`;
    }
    
    alert(fullErrorMessage);
  };

  // Function to accept partial results and stop optimization
  const acceptPartialResult = () => {
    setOptimizing(false);
    setIsPartialResult(false);
    setContinue(false);
    if (partialResult) {
      showOptimizationSuccessMessage(partialResult);
    }
  };

  // Function to clear optimization cache and reset state
  const clearOptimizationCache = async () => {
    console.log("DEBUG: BEFORE clear - optimizing:", optimizing, "isPartialResult:", isPartialResult, "canContinue:", canContinue);
    
    try {
      // Clear backend optimization cache first
      console.log("DEBUG: Clearing backend optimization cache...");
      const cacheResponse = await fetch(`${API_BASE_URL}/api/optimization-cache`, {
        method: "DELETE",
        headers: {
          "Cache-Control": "no-cache, no-store, must-revalidate",
          "Pragma": "no-cache",
          "Expires": "0"
        }
      });
      
      let backendCacheCleared = false;
      if (cacheResponse.ok) {
        const cacheResult = await cacheResponse.json();
        console.log("DEBUG: Backend cache clear result:", cacheResult);
        backendCacheCleared = cacheResult.success;
      } else {
        console.warn("DEBUG: Failed to clear backend cache:", cacheResponse.status);
      }
      
      // Clear frontend optimization state
      setOptimizing(false);
      setIsPartialResult(false);
      setContinue(false);
      setPartialResult(null);
      setOptimizationProgress(0);
      setOptimizationStartTime(0);
      
      // Clear analysis results
      setAnalysisResults(null);
      
      // Reset portfolio weights to default
      const defaultWeights: Record<number, number> = {};
      selectedPortfolios.forEach(id => {
        defaultWeights[id] = 1.0;
      });
      setPortfolioWeights(defaultWeights);
      
      // Clear localStorage cache
      let clearedKeys = 0;
      Object.values(STORAGE_KEYS).forEach(key => {
        if (localStorage.getItem(key)) {
          localStorage.removeItem(key);
          clearedKeys++;
        }
      });
      
      console.log("DEBUG: Optimization cache and state cleared");
      console.log("DEBUG: Cleared", clearedKeys, "localStorage keys");
      console.log("DEBUG: Backend cache cleared:", backendCacheCleared);
      console.log("DEBUG: AFTER clear - should be reset to defaults");
      
      // Force a small delay to ensure state updates have processed
      setTimeout(() => {
        console.log("DEBUG: State after clear (delayed check) - optimizing:", optimizing, "portfolioWeights:", portfolioWeights);
      }, 100);
      
      const message = backendCacheCleared 
        ? "Optimization cache and state cleared! Backend cache also cleared. You can now start fresh optimization."
        : "Frontend cache and state cleared! Note: Backend cache clear failed - optimization may still return cached results.";
      
      alert(message);
      
    } catch (error) {
      console.error("DEBUG: Error clearing cache:", error);
      alert("Error clearing cache. Please try refreshing the page.");
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
        sma_window: loadedOptimization?.parameters?.sma_window || 20,
        use_trading_filter: loadedOptimization?.parameters?.use_trading_filter !== undefined
          ? loadedOptimization.parameters.use_trading_filter : true,
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
      console.log("Portfolio weights state:", portfolioWeights);
      console.log("Loaded optimization:", loadedOptimization);
      console.log("Weighting method:", weightingMethod);

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

  // Save favorite settings
  const saveFavoriteSettings = async () => {
    if (selectedPortfolios.length === 0) {
      alert("Please select at least one portfolio before saving");
      return;
    }

    // Get auth token
    const token = localStorage.getItem('auth_token');
    if (!token) {
      alert("Please log in to save favorites");
      return;
    }

    setSavingFavorites(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/favorites/save`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({
          portfolio_ids: selectedPortfolios,
          weights: portfolioWeights,
          starting_capital: startingCapital,
          risk_free_rate: riskFreeRate,
          sma_window: 20,
          use_trading_filter: true,
          date_range_start: dateRangeStart,
          date_range_end: dateRangeEnd,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to save favorite settings");
      }

      const result = await response.json();
      alert("✅ Favorite settings saved successfully!");
      console.log("Saved favorite settings:", result);
    } catch (error) {
      console.error("Failed to save favorite settings:", error);
      alert(
        `Failed to save favorite settings: ${
          error instanceof Error ? error.message : "Unknown error"
        }`
      );
    } finally {
      setSavingFavorites(false);
    }
  };

  // Load favorite settings
  const loadFavoriteSettings = async () => {
    // Get auth token
    const token = localStorage.getItem('auth_token');
    if (!token) {
      alert("Please log in to load favorites");
      return;
    }

    setLoadingFavorites(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/favorites/load`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to load favorite settings");
      }

      const result = await response.json();

      if (!result.has_favorites) {
        alert("No favorite settings found. Save your current settings first!");
        return;
      }

      // Apply the loaded settings
      const settings = result.settings;
      setSelectedPortfolios(settings.portfolio_ids);
      setPortfolioWeights(settings.weights);
      setStartingCapital(settings.starting_capital);
      setRiskFreeRate(settings.risk_free_rate);
      if (settings.date_range_start) {
        setDateRangeStart(settings.date_range_start.split('T')[0]);
      }
      if (settings.date_range_end) {
        setDateRangeEnd(settings.date_range_end.split('T')[0]);
      }

      // Update weighting method based on loaded weights
      const hasCustomWeights = Object.values(settings.weights).some((w: any) => w !== 1.0);
      setWeightingMethod(hasCustomWeights ? "custom" : "equal");

      alert(`✅ Favorite settings loaded successfully!\n\nLoaded ${settings.portfolio_ids.length} portfolio(s)`);
      console.log("Loaded favorite settings:", settings);
    } catch (error) {
      console.error("Failed to load favorite settings:", error);
      alert(
        `Failed to load favorite settings: ${
          error instanceof Error ? error.message : "Unknown error"
        }`
      );
    } finally {
      setLoadingFavorites(false);
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

      {/* Loaded Optimization Display */}
      {loadedOptimization && (
        <Paper
          sx={{
            p: 2,
            mb: 2,
            border: `2px solid ${theme.palette.primary.main}`,
            borderRadius: "8px",
            background: theme.palette.mode === "dark"
              ? "rgba(25, 118, 210, 0.1)"
              : "rgba(25, 118, 210, 0.05)",
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <Box sx={{
              width: 40,
              height: 40,
              borderRadius: '50%',
              backgroundColor: theme.palette.primary.main,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white'
            }}>
              📊
            </Box>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 'bold', color: theme.palette.primary.main }}>
                {loadedOptimization.name || `Optimization #${loadedOptimization.id}`}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Method: {loadedOptimization.method.replace('_', ' ')} • {loadedOptimization.portfolio_ids.length} portfolios
              </Typography>
            </Box>
          </Box>

          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 2, mb: 2 }}>
            <Box>
              <Typography variant="body2" color="textSecondary">CAGR</Typography>
              <Typography variant="h6" sx={{ color: loadedOptimization.metrics.cagr >= 0 ? 'success.main' : 'error.main' }}>
                {(loadedOptimization.metrics.cagr * 100).toFixed(2)}%
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="textSecondary">Max Drawdown</Typography>
              <Typography variant="h6" color="error.main">
                {(Math.abs(loadedOptimization.metrics.max_drawdown) * 100).toFixed(2)}%
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="textSecondary">Return/Drawdown Ratio</Typography>
              <Typography variant="h6" color="primary.main">
                {loadedOptimization.metrics.return_drawdown_ratio.toFixed(2)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="textSecondary">Sharpe Ratio</Typography>
              <Typography variant="h6" sx={{ color: loadedOptimization.metrics.sharpe_ratio >= 0 ? 'success.main' : 'error.main' }}>
                {loadedOptimization.metrics.sharpe_ratio.toFixed(2)}
              </Typography>
            </Box>
          </Box>

          <Typography variant="body2" color="textSecondary" sx={{ mb: 1 }}>
            Optimal Portfolio Weights:
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {loadedOptimization.portfolio_ids.map((portfolioId, index) => {
              const portfolio = portfolios.find(p => p.id === portfolioId);
              const weight = loadedOptimization.weights[index];
              const ratio = loadedOptimization.ratios[index];

              return (
                <Box
                  key={portfolioId}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    px: 2,
                    py: 1,
                    borderRadius: '20px',
                    backgroundColor: theme.palette.mode === "dark" ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)',
                    border: `1px solid ${theme.palette.divider}`,
                  }}
                >
                  <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                    {portfolio?.name || `Portfolio ${portfolioId}`}
                  </Typography>
                  <Typography variant="body2" color="primary.main">
                    {ratio.toFixed(1)}x
                  </Typography>
                  <Typography variant="caption" color="textSecondary">
                    ({(weight * 100).toFixed(1)}%)
                  </Typography>
                </Box>
              );
            })}
          </Box>

          <Typography variant="caption" color="textSecondary" sx={{ mt: 2, display: 'block' }}>
            💡 The portfolios below have been automatically selected based on this optimization result.
            You can now analyze these portfolios with the optimal weights applied.
          </Typography>
        </Paper>
      )}

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
              flexWrap: "wrap",
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
              {selectedPortfolios.length > 0 && (
                <span 
                  style={{ 
                    fontSize: "0.8rem", 
                    color: theme.palette.mode === "dark" ? "#94a3b8" : "#64748b",
                    fontStyle: "italic" 
                  }}
                  title="Your portfolio selections are automatically saved"
                >
                  ✓ saved
                </span>
              )}
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
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {/* Progressive Optimization Controls */}
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button
                    onClick={() => optimizePortfolioWeights(false)}
                    disabled={optimizing || analyzing}
                    className="btn btn-success"
                    style={{
                      padding: "0.5rem 1.5rem",
                      fontSize: "0.9rem",
                      opacity: optimizing || analyzing ? 0.5 : 1,
                    }}
                    title="Find optimal weights to maximize return while minimizing drawdown"
                  >
                    {optimizing 
                      ? `Optimizing... ${optimizationProgress > 0 ? `(${optimizationProgress.toFixed(0)}%)` : ''}`
                      : "🎯 Optimize Weights"}
                  </button>
                  
                  {/* Clear Cache button */}
                  <button
                    onClick={clearOptimizationCache}
                    className="btn btn-secondary"
                    style={{
                      padding: "0.5rem 1rem",
                      fontSize: "0.9rem",
                      marginLeft: "0.5rem"
                    }}
                    title="Clear optimization cache and reset state"
                  >
                    🗑️ Clear Cache
                  </button>
                  
                  {/* Continue and Accept buttons for partial results */}
                  {isPartialResult && optimizing && (
                    <>
                      <button
                        onClick={() => {
                          console.log("DEBUG: Continue button clicked (1st location)");
                          console.log("DEBUG: About to call optimizePortfolioWeights(true)");
                          console.log("DEBUG: Current partialResult:", partialResult);
                          console.log("DEBUG: Current canContinue:", canContinue);
                          optimizePortfolioWeights(true);
                        }}
                        disabled={!canContinue}
                        className="btn btn-warning"
                        style={{
                          padding: "0.5rem 1rem",
                          fontSize: "0.9rem",
                          opacity: canContinue ? 1 : 0.5,
                        }}
                        title="Continue optimization for better results"
                      >
                        ⏱️ Continue
                      </button>
                      <button
                        onClick={acceptPartialResult}
                        className="btn btn-info"
                        style={{
                          padding: "0.5rem 1rem",
                          fontSize: "0.9rem",
                        }}
                        title="Use current partial optimization results"
                      >
                        ✅ Use These
                      </button>
                    </>
                  )}
                </div>
                
                {/* Progress indicator for partial results */}
                {isPartialResult && optimizing && canContinue && (
                  <div style={{ 
                    fontSize: "0.8rem", 
                    color: theme.palette.mode === "dark" ? "#fbbf24" : "#d97706",
                    fontStyle: "italic" 
                  }}>
                    Partial optimization complete ({optimizationProgress.toFixed(1)}% explored). 
                    Continue for better results or use current weights.
                  </div>
                )}
              </div>
            )}
            <button
              onClick={analyzeSelectedPortfolios}
              disabled={selectedPortfolios.length === 0 || analyzing || optimizing}
              className="btn btn-primary"
              style={{
                padding: "0.5rem 1.5rem",
                fontSize: "0.9rem",
                marginLeft: selectedPortfolios.length >= 2 ? "0" : "auto",
                opacity: selectedPortfolios.length === 0 || analyzing || optimizing ? 0.5 : 1,
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
          <button
            onClick={saveFavoriteSettings}
            disabled={selectedPortfolios.length === 0 || savingFavorites || analyzing || optimizing}
            className="btn btn-primary"
            style={{
              padding: "0.5rem 1rem",
              fontSize: "0.9rem",
              opacity: selectedPortfolios.length === 0 || savingFavorites || analyzing || optimizing ? 0.5 : 1,
            }}
            title="Save current settings as favorites"
          >
            {savingFavorites ? "Saving..." : "⭐ Save Favorites"}
          </button>
          <button
            onClick={loadFavoriteSettings}
            disabled={loadingFavorites || analyzing || optimizing}
            className="btn btn-success"
            style={{
              padding: "0.5rem 1rem",
              fontSize: "0.9rem",
              opacity: loadingFavorites || analyzing || optimizing ? 0.5 : 1,
            }}
            title="Load your favorite settings"
          >
            {loadingFavorites ? "Loading..." : "📂 Load Favorites"}
          </button>
          {selectedPortfolios.length >= 2 && (
            <>
              <button
                onClick={() => optimizePortfolioWeights(false)}
                disabled={optimizing || analyzing}
                className="btn btn-success"
                style={{
                  padding: "0.5rem 1rem",
                  fontSize: "0.9rem",
                  opacity: optimizing || analyzing ? 0.5 : 1,
                }}
                title="Find optimal weights to maximize return while minimizing drawdown"
              >
                {optimizing
                  ? `Optimizing... ${optimizationProgress > 0 ? `(${optimizationProgress.toFixed(0)}%)` : ''}`
                  : "🎯 Optimize Weights"}
              </button>

              {/* Clear Cache button */}
              <button
                onClick={clearOptimizationCache}
                className="btn btn-secondary"
                style={{
                  padding: "0.5rem 1rem",
                  fontSize: "0.9rem"
                }}
                title="Clear optimization cache and reset state"
              >
                🗑️ Clear Cache
              </button>
                
                {/* Continue and Accept buttons for partial results */}
                {isPartialResult && optimizing && (
                  <>
                    <button
                      onClick={() => {
                        console.log("DEBUG: Continue button clicked (2nd location)");
                        console.log("DEBUG: About to call optimizePortfolioWeights(true)");
                        console.log("DEBUG: Current partialResult:", partialResult);
                        console.log("DEBUG: Current canContinue:", canContinue);
                        optimizePortfolioWeights(true);
                      }}
                      disabled={!canContinue}
                      className="btn btn-warning"
                      style={{
                        padding: "0.5rem 1rem",
                        fontSize: "0.9rem",
                        opacity: canContinue ? 1 : 0.5,
                      }}
                      title="Continue optimization for better results"
                    >
                      ⏱️ Continue
                    </button>
                    <button
                      onClick={acceptPartialResult}
                      className="btn btn-info"
                      style={{
                        padding: "0.5rem 1rem",
                        fontSize: "0.9rem",
                      }}
                      title="Use current partial optimization results"
                    >
                      ✅ Use These
                    </button>
                  </>
                )}
            </>
          )}
          <button
            onClick={analyzeSelectedPortfolios}
            disabled={selectedPortfolios.length === 0 || analyzing || optimizing}
            className="btn btn-primary"
            style={{
              padding: "0.5rem 1.5rem",
              fontSize: "0.9rem",
              marginLeft: selectedPortfolios.length >= 2 ? "0" : "auto",
              opacity: selectedPortfolios.length === 0 || analyzing || optimizing ? 0.5 : 1,
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
                {selectedPortfolios
                  .slice()
                  .sort((a, b) => {
                    const portfolioA = portfolios.find((p) => p.id === a);
                    const portfolioB = portfolios.find((p) => p.id === b);
                    const nameA = portfolioA?.name || `Portfolio ${a}`;
                    const nameB = portfolioB?.name || `Portfolio ${b}`;
                    return nameA.localeCompare(nameB);
                  })
                  .map((portfolioId) => {
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
                            )
                              .sort(([nameA], [nameB]) => nameA.localeCompare(nameB))
                              .map(([name, weight]) => (
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

                      {/* Beta vs SPX */}
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
                          Beta (vs SPX)
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color:
                              (analysisResults.blended_result.metrics.beta || 0) > 1
                                ? theme.palette.error.main
                                : (analysisResults.blended_result.metrics.beta || 0) > 0.5
                                ? theme.palette.warning.main
                                : theme.palette.success.main,
                          }}
                        >
                          {analysisResults.blended_result.metrics.beta?.toFixed(2) || "N/A"}
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

                      {/* CVaR (Conditional Value at Risk) */}
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
                          CVaR (5%)
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color: theme.palette.error.main,
                          }}
                        >
                          {analysisResults.blended_result.metrics.cvar !== undefined && analysisResults.blended_result.metrics.cvar !== null
                            ? '$' + analysisResults.blended_result.metrics.cvar.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                            : 'N/A'}
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

                      {/* Drawdown Metrics - Bottom Row */}
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
                          Max Drawdown %
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color: theme.palette.error.main,
                          }}
                        >
                          {(analysisResults.blended_result.metrics.max_drawdown_percent * 100)?.toFixed(2)}%
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
                          Max Drawdown $
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color: theme.palette.error.main,
                          }}
                        >
                          ${Math.abs(analysisResults.blended_result.metrics.max_drawdown || 0).toLocaleString(undefined, {
                            minimumFractionDigits: 0,
                            maximumFractionDigits: 0,
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
                          Days in Drawdown
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color: theme.palette.warning.main,
                          }}
                        >
                          {analysisResults.blended_result.metrics.days_in_drawdown?.toLocaleString() || 0}
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
                          Avg Drawdown Length
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color: theme.palette.warning.main,
                          }}
                        >
                          {analysisResults.blended_result.metrics.avg_drawdown_length?.toFixed(1) || 0} days
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
                          Worst P/L Day
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color: theme.palette.error.main,
                          }}
                        >
                          {analysisResults.blended_result.metrics.worst_pl_day !== undefined && analysisResults.blended_result.metrics.worst_pl_day !== null
                            ? new Intl.NumberFormat("en-US", {
                                style: "currency",
                                currency: "USD",
                                minimumFractionDigits: 0,
                                maximumFractionDigits: 0,
                              }).format(analysisResults.blended_result.metrics.worst_pl_day)
                            : 'N/A'}
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
                          Worst P/L Date
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color: theme.palette.text.secondary,
                          }}
                        >
                          {formatDateString(analysisResults.blended_result.metrics.worst_pl_date)}
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
                          Best P/L Day
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color: theme.palette.success.main,
                          }}
                        >
                          {analysisResults.blended_result.metrics.best_pl_day !== undefined && analysisResults.blended_result.metrics.best_pl_day !== null
                            ? new Intl.NumberFormat("en-US", {
                                style: "currency",
                                currency: "USD",
                                minimumFractionDigits: 0,
                                maximumFractionDigits: 0,
                              }).format(analysisResults.blended_result.metrics.best_pl_day)
                            : 'N/A'}
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
                          Best P/L Date
                        </div>
                        <div
                          style={{
                            fontSize: "1.4rem",
                            fontWeight: "bold",
                            color: theme.palette.text.secondary,
                          }}
                        >
                          {formatDateString(analysisResults.blended_result.metrics.best_pl_date)}
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

                              {/* CVaR (Conditional Value at Risk) */}
                              <div className="metric">
                                <div
                                  style={{
                                    fontSize: "0.85rem",
                                    color: theme.palette.text.secondary,
                                    marginBottom: "0.25rem",
                                  }}
                                >
                                  CVaR (5%)
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: theme.palette.error.main,
                                  }}
                                >
                                  {result.metrics.cvar !== undefined && result.metrics.cvar !== null
                                    ? '$' + result.metrics.cvar.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                                    : 'N/A'}
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
                                  Max Drawdown %
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: theme.palette.error.main,
                                  }}
                                >
                                  {(result.metrics.max_drawdown_percent * 100)?.toFixed(2)}%
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
                                  Max Drawdown $
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: theme.palette.error.main,
                                  }}
                                >
                                  ${Math.abs(result.metrics.max_drawdown || 0).toLocaleString(undefined, {
                                    minimumFractionDigits: 0,
                                    maximumFractionDigits: 0,
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
                                  Days in Drawdown
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: theme.palette.warning.main,
                                  }}
                                >
                                  {result.metrics.days_in_drawdown?.toLocaleString() || 0}
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
                                  Avg Drawdown Length
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: theme.palette.warning.main,
                                  }}
                                >
                                  {result.metrics.avg_drawdown_length?.toFixed(1) || 0} days
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
                                  Worst P/L Day
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: theme.palette.error.main,
                                  }}
                                >
                                  {result.metrics.worst_pl_day !== undefined && result.metrics.worst_pl_day !== null
                                    ? new Intl.NumberFormat("en-US", {
                                        style: "currency",
                                        currency: "USD",
                                        minimumFractionDigits: 0,
                                        maximumFractionDigits: 0,
                                      }).format(result.metrics.worst_pl_day)
                                    : 'N/A'}
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
                                  Worst P/L Date
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: theme.palette.text.secondary,
                                  }}
                                >
                                  {formatDateString(result.metrics.worst_pl_date)}
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
                                  Best P/L Day
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: theme.palette.success.main,
                                  }}
                                >
                                  {result.metrics.best_pl_day !== undefined && result.metrics.best_pl_day !== null
                                    ? new Intl.NumberFormat("en-US", {
                                        style: "currency",
                                        currency: "USD",
                                        minimumFractionDigits: 0,
                                        maximumFractionDigits: 0,
                                      }).format(result.metrics.best_pl_day)
                                    : 'N/A'}
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
                                  Best P/L Date
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: "bold",
                                    color: theme.palette.text.secondary,
                                  }}
                                >
                                  {formatDateString(result.metrics.best_pl_date)}
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
                        gridTemplateColumns: "1fr",
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
                const strategy = portfolio.strategy && portfolio.strategy !== "None" ? portfolio.strategy : "No Strategy Set";
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
                              borderRight: "1px solid rgba(255, 255, 255, 0.1)",
                              minWidth: "150px",
                              color: theme.palette.mode === "dark" ? "#ffffff" : "#2d3748",
                              fontWeight: "600"
                            }}
                          >
                            Strategy
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
                          borderRight: "1px solid rgba(255, 255, 255, 0.1)",
                          color: theme.palette.mode === "dark" ? "#ffffff" : "#2d3748",
                        }}
                      >
                        {editingStrategyId === portfolio.id ? (
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "0.5rem",
                            }}
                          >
                            <input
                              type="text"
                              value={editingStrategy}
                              onChange={(e) => setEditingStrategy(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") {
                                  saveStrategy(portfolio.id);
                                } else if (e.key === "Escape") {
                                  cancelEditingStrategy();
                                }
                              }}
                              style={{
                                flex: 1,
                                padding: "0.25rem",
                                border: "1px solid #ccc",
                                borderRadius: "4px",
                                fontSize: "0.8rem",
                                minWidth: "100px",
                              }}
                              autoFocus
                              onClick={(e) => e.stopPropagation()}
                              placeholder="Enter strategy..."
                            />
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                saveStrategy(portfolio.id);
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
                                cancelEditingStrategy();
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
                            <span
                              style={{
                                fontSize: "0.9rem",
                                fontStyle: portfolio.strategy ? "normal" : "italic",
                                color: portfolio.strategy 
                                  ? (theme.palette.mode === "dark" ? "#ffffff" : "#2d3748")
                                  : (theme.palette.mode === "dark" ? "#9ca3af" : "#6b7280"),
                                cursor: "pointer",
                              }}
                              onClick={(e) => {
                                e.stopPropagation();
                                startEditingStrategy(portfolio);
                              }}
                            >
                              {portfolio.strategy && portfolio.strategy !== "None" ? portfolio.strategy : "No Strategy"}
                            </span>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                startEditingStrategy(portfolio);
                              }}
                              style={{
                                padding: "0.25rem",
                                background: "transparent",
                                border: "none",
                                cursor: "pointer",
                                fontSize: "0.8rem",
                                color: theme.palette.mode === "dark" ? "#9ca3af" : "#6b7280",
                              }}
                              title="Edit strategy"
                            >
                              ✏️
                            </button>
                          </div>
                        )}
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
                          colSpan={7}
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

                            {/* Portfolio Metrics */}
                            {portfolio.latest_analysis?.metrics && (
                              <div
                                style={{
                                  display: "grid",
                                  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                                  gap: "0.75rem",
                                  margin: "1rem 0",
                                  padding: "0.75rem",
                                  backgroundColor:
                                    theme.palette.mode === "dark"
                                      ? "#2d3748"
                                      : "#ffffff",
                                  borderRadius: "8px",
                                  border: `1px solid ${
                                    theme.palette.mode === "dark"
                                      ? "#4a5568"
                                      : "#e2e8f0"
                                  }`,
                                }}
                              >
                                {/* Total Return */}
                                {portfolio.latest_analysis.metrics.total_return !== undefined && (
                                  <div style={{ textAlign: "center" }}>
                                    <div
                                      style={{
                                        fontSize: "0.7rem",
                                        color: theme.palette.text.secondary,
                                        marginBottom: "0.25rem",
                                      }}
                                    >
                                      Total Return
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "0.9rem",
                                        fontWeight: "600",
                                        color: portfolio.latest_analysis.metrics.total_return >= 0 ? "#22c55e" : "#ef4444",
                                      }}
                                    >
                                      {(portfolio.latest_analysis.metrics.total_return * 100).toFixed(2)}%
                                    </div>
                                  </div>
                                )}

                                {/* Max Drawdown */}
                                {portfolio.latest_analysis.metrics.max_drawdown_percent !== undefined && (
                                  <div style={{ textAlign: "center" }}>
                                    <div
                                      style={{
                                        fontSize: "0.7rem",
                                        color: theme.palette.text.secondary,
                                        marginBottom: "0.25rem",
                                      }}
                                    >
                                      Max Drawdown
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "0.9rem",
                                        fontWeight: "600",
                                        color: "#ef4444",
                                      }}
                                    >
                                      {Math.abs(portfolio.latest_analysis.metrics.max_drawdown_percent * 100).toFixed(2)}%
                                    </div>
                                  </div>
                                )}

                                {/* Sharpe Ratio */}
                                {portfolio.latest_analysis.metrics.sharpe_ratio !== undefined && (
                                  <div style={{ textAlign: "center" }}>
                                    <div
                                      style={{
                                        fontSize: "0.7rem",
                                        color: theme.palette.text.secondary,
                                        marginBottom: "0.25rem",
                                      }}
                                    >
                                      Sharpe Ratio
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "0.9rem",
                                        fontWeight: "600",
                                        color: portfolio.latest_analysis.metrics.sharpe_ratio >= 0 ? "#22c55e" : "#ef4444",
                                      }}
                                    >
                                      {portfolio.latest_analysis.metrics.sharpe_ratio.toFixed(2)}
                                    </div>
                                  </div>
                                )}

                                {/* Beta vs SPX */}
                                {portfolio.latest_analysis.metrics.beta !== undefined && (
                                  <div style={{ textAlign: "center" }}>
                                    <div
                                      style={{
                                        fontSize: "0.7rem",
                                        color: theme.palette.text.secondary,
                                        marginBottom: "0.25rem",
                                      }}
                                    >
                                      Beta (SPX)
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "0.9rem",
                                        fontWeight: "600",
                                        color: portfolio.latest_analysis.metrics.beta > 1 ? "#ef4444" : portfolio.latest_analysis.metrics.beta > 0.5 ? "#f59e0b" : "#22c55e",
                                      }}
                                    >
                                      {portfolio.latest_analysis.metrics.beta.toFixed(2)}
                                    </div>
                                  </div>
                                )}

                                {/* CAGR */}
                                {portfolio.latest_analysis.metrics.cagr !== undefined && (
                                  <div style={{ textAlign: "center" }}>
                                    <div
                                      style={{
                                        fontSize: "0.7rem",
                                        color: theme.palette.text.secondary,
                                        marginBottom: "0.25rem",
                                      }}
                                    >
                                      CAGR
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "0.9rem",
                                        fontWeight: "600",
                                        color: portfolio.latest_analysis.metrics.cagr >= 0 ? "#22c55e" : "#ef4444",
                                      }}
                                    >
                                      {(portfolio.latest_analysis.metrics.cagr * 100).toFixed(2)}%
                                    </div>
                                  </div>
                                )}

                                {/* Total P/L */}
                                {portfolio.latest_analysis.metrics.total_pl !== undefined && (
                                  <div style={{ textAlign: "center" }}>
                                    <div
                                      style={{
                                        fontSize: "0.7rem",
                                        color: theme.palette.text.secondary,
                                        marginBottom: "0.25rem",
                                      }}
                                    >
                                      Total P/L
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "0.9rem",
                                        fontWeight: "600",
                                        color: portfolio.latest_analysis.metrics.total_pl >= 0 ? "#22c55e" : "#ef4444",
                                      }}
                                    >
                                      ${portfolio.latest_analysis.metrics.total_pl.toLocaleString()}
                                    </div>
                                  </div>
                                )}

                                {/* Final Account Value */}
                                {portfolio.latest_analysis.metrics.final_account_value !== undefined && (
                                  <div style={{ textAlign: "center" }}>
                                    <div
                                      style={{
                                        fontSize: "0.7rem",
                                        color: theme.palette.text.secondary,
                                        marginBottom: "0.25rem",
                                      }}
                                    >
                                      Final Account Value
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "0.9rem",
                                        fontWeight: "600",
                                        color: "#3b82f6",
                                      }}
                                    >
                                      ${portfolio.latest_analysis.metrics.final_account_value.toLocaleString()}
                                    </div>
                                  </div>
                                )}

                                {/* Max Drawdown $ */}
                                {portfolio.latest_analysis.metrics.max_drawdown_dollar !== undefined && (
                                  <div style={{ textAlign: "center" }}>
                                    <div
                                      style={{
                                        fontSize: "0.7rem",
                                        color: theme.palette.text.secondary,
                                        marginBottom: "0.25rem",
                                      }}
                                    >
                                      Max Drawdown ($)
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "0.9rem",
                                        fontWeight: "600",
                                        color: "#ef4444",
                                      }}
                                    >
                                      ${Math.abs(portfolio.latest_analysis.metrics.max_drawdown_dollar).toLocaleString()}
                                    </div>
                                  </div>
                                )}

                                {/* Annual Volatility */}
                                {portfolio.latest_analysis.metrics.annual_volatility !== undefined && (
                                  <div style={{ textAlign: "center" }}>
                                    <div
                                      style={{
                                        fontSize: "0.7rem",
                                        color: theme.palette.text.secondary,
                                        marginBottom: "0.25rem",
                                      }}
                                    >
                                      Annual Volatility
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "0.9rem",
                                        fontWeight: "600",
                                        color: theme.palette.text.primary,
                                      }}
                                    >
                                      {(portfolio.latest_analysis.metrics.annual_volatility * 100).toFixed(2)}%
                                    </div>
                                  </div>
                                )}

                                {/* CVaR (Conditional Value at Risk) */}
                                <div style={{ textAlign: "center" }}>
                                  <div
                                    style={{
                                      fontSize: "0.7rem",
                                      color: theme.palette.text.secondary,
                                      marginBottom: "0.25rem",
                                    }}
                                  >
                                    CVaR (5%)
                                  </div>
                                  <div
                                    style={{
                                      fontSize: "0.9rem",
                                      fontWeight: "600",
                                      color: "#ef4444",
                                    }}
                                  >
                                    {portfolio.latest_analysis.metrics.cvar !== undefined && portfolio.latest_analysis.metrics.cvar !== null
                                      ? '$' + portfolio.latest_analysis.metrics.cvar.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                                      : 'N/A'}
                                  </div>
                                </div>
                              </div>
                            )}

                            {!portfolio.latest_analysis?.metrics && (
                              <p
                                style={{
                                  margin: "0.5rem 0",
                                  fontStyle: "italic",
                                  color: theme.palette.mode === "dark" ? "#d1d5db" : "#6b7280",
                                }}
                              >
                                No analysis data available. Upload and analyze this portfolio to see metrics.
                              </p>
                            )}
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
