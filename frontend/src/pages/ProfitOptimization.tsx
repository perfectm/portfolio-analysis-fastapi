import React, { useState, useEffect } from "react";
import {
  Container,
  Typography,
  Paper,
  Box,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Card,
  CardContent,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  OutlinedInput,
  SelectChangeEvent,
} from "@mui/material";
import { portfolioAPI, Portfolio as APIPortfolio } from "../services/api";

interface Portfolio {
  id: number;
  name: string;
  filename: string;
  upload_date: string;
  row_count?: number;
  date_range_start?: string;
  date_range_end?: string;
  strategy?: string;
}

interface OptimizationResult {
  success: boolean;
  message: string;
  optimal_weights: { [key: string]: number };
  optimal_ratios: { [key: string]: number };
  metrics: {
    cagr: number;
    max_drawdown_percent: number;
    return_drawdown_ratio: number;
    sharpe_ratio: number;
  };
  target_profit_achieved: number;
  portfolio_names: string[];
  portfolio_ids: number[];
  details?: {
    error_type?: string;
    description?: string;
    suggestion?: string;
    troubleshooting?: string[];
    optimization_method?: string;
    iterations_completed?: number;
    execution_time_seconds?: number;
    portfolio_count?: number;
    target_profit?: number;
  };
  suggestions?: string[];
}

const ProfitOptimization: React.FC = () => {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selectedPortfolios, setSelectedPortfolios] = useState<number[]>([]);
  const [targetAnnualProfit, setTargetAnnualProfit] = useState<number>(100000);
  const [loading, setLoading] = useState(false);
  const [optimizationResult, setOptimizationResult] = useState<OptimizationResult | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    fetchPortfolios();
  }, []);

  const fetchPortfolios = async () => {
    try {
      const data = await portfolioAPI.getPortfolios();
      setPortfolios(data.portfolios || []);
    } catch (error) {
      console.error("Error fetching portfolios:", error);
      setError("Failed to load portfolios");
    }
  };

  const handlePortfolioChange = (event: SelectChangeEvent<string>) => {
    const value = event.target.value;
    // Handle multiple selection - value will be a string[] for multiple select
    const values = typeof value === 'string' ? value.split(',') : value as unknown as string[];
    setSelectedPortfolios(values.map(id => parseInt(id, 10)));
  };

  const handleOptimize = async () => {
    if (selectedPortfolios.length < 2) {
      setError("Please select at least 2 portfolios for optimization");
      return;
    }

    if (targetAnnualProfit <= 0) {
      setError("Target annual profit must be greater than 0");
      return;
    }

    setLoading(true);
    setError("");
    setOptimizationResult(null);

    try {
      const result = await portfolioAPI.optimizeForProfit(selectedPortfolios, targetAnnualProfit);
      
      if (result.success) {
        setOptimizationResult(result);
        setError("");
      } else {
        // Handle detailed error information
        let errorMessage = result.error || "Optimization failed";
        
        if (result.details) {
          errorMessage += `\n\nError Type: ${result.details.error_type || 'Unknown'}`;
          if (result.details.description) {
            errorMessage += `\nDetails: ${result.details.description}`;
          }
          if (result.details.suggestion) {
            errorMessage += `\n\nSuggestion: ${result.details.suggestion}`;
          }
          if (result.details.troubleshooting && result.details.troubleshooting.length > 0) {
            errorMessage += `\n\nTroubleshooting Steps:\n${result.details.troubleshooting.map((step, i) => `${i + 1}. ${step}`).join('\n')}`;
          }
        }
        
        if (result.suggestions && result.suggestions.length > 0) {
          errorMessage += `\n\nRecommendations:\n${result.suggestions.map((suggestion, i) => `• ${suggestion}`).join('\n')}`;
        }
        
        console.error("Optimization failed with details:", result);
        setError(errorMessage);
      }
    } catch (error) {
      console.error("Network/API error:", error);
      setError(`Failed to communicate with the optimization service.\n\nThis could be due to:\n• Network connectivity issues\n• Server problems\n• Invalid request format\n\nPlease check your internet connection and try again.`);
    } finally {
      setLoading(false);
    }
  };

  const formatPercentage = (value: number) => `${(value * 100).toFixed(2)}%`;
  const formatCurrency = (value: number) => `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Profit Optimization
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        Set a target annual profit and optimize portfolio weights to achieve it while minimizing drawdown.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3, whiteSpace: 'pre-line' }}>
          <Typography variant="body2" component="div" sx={{ whiteSpace: 'pre-line' }}>
            {error}
          </Typography>
        </Alert>
      )}

      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
        {/* Configuration Section */}
        <Box sx={{ flex: '1 1 400px', minWidth: '400px' }}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Optimization Settings
            </Typography>
            
            <TextField
              label="Target Annual Profit"
              type="number"
              value={targetAnnualProfit}
              onChange={(e) => setTargetAnnualProfit(Number(e.target.value))}
              fullWidth
              sx={{ mb: 3 }}
              InputProps={{
                startAdornment: "$",
              }}
            />

            <FormControl fullWidth sx={{ mb: 3 }}>
              <InputLabel id="portfolios-select-label">Select Portfolios</InputLabel>
              <Select<string[]>
                labelId="portfolios-select-label"
                id="portfolios-select"
                multiple
                value={selectedPortfolios.map(id => id.toString())}
                onChange={handlePortfolioChange as any}
                input={<OutlinedInput label="Select Portfolios" />}
                renderValue={(selected) => (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {(selected as string[]).map((portfolioIdStr) => {
                      const portfolioId = parseInt(portfolioIdStr, 10);
                      const portfolio = portfolios.find(p => p.id === portfolioId);
                      return (
                        <Chip 
                          key={portfolioId} 
                          label={portfolio?.name || `Portfolio ${portfolioId}`}
                          size="small"
                        />
                      );
                    })}
                  </Box>
                )}
                sx={{ minHeight: '56px' }}
              >
                {portfolios.map((portfolio) => (
                  <MenuItem key={portfolio.id} value={portfolio.id.toString()}>
                    <Box>
                      <Typography variant="body2">{portfolio.name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {portfolio.row_count || 0} trades
                      </Typography>
                    </Box>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Button
              variant="contained"
              onClick={handleOptimize}
              disabled={loading || selectedPortfolios.length < 2}
              fullWidth
              sx={{ mt: 2 }}
            >
              {loading ? (
                <CircularProgress size={24} color="inherit" />
              ) : (
                "Optimize Portfolio"
              )}
            </Button>
          </Paper>
        </Box>

        {/* Results Section */}
        <Box sx={{ flex: '1 1 400px', minWidth: '400px' }}>
          {optimizationResult && (
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Optimization Results
              </Typography>

              <Alert severity="success" sx={{ mb: 2 }}>
                {optimizationResult.message}
              </Alert>

              <Card sx={{ mb: 2 }}>
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>
                    Target vs Achieved
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 2 }}>
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="body2" color="text.secondary">
                        Target Profit:
                      </Typography>
                      <Typography variant="h6">
                        {formatCurrency(targetAnnualProfit)}
                      </Typography>
                    </Box>
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="body2" color="text.secondary">
                        Projected Profit:
                      </Typography>
                      <Typography variant="h6">
                        {formatCurrency(optimizationResult.target_profit_achieved)}
                      </Typography>
                    </Box>
                  </Box>
                </CardContent>
              </Card>

              <Card sx={{ mb: 2 }}>
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>
                    Portfolio Metrics
                  </Typography>
                  <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        CAGR:
                      </Typography>
                      <Typography variant="body1">
                        {formatPercentage(optimizationResult.metrics.cagr)}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Max Drawdown:
                      </Typography>
                      <Typography variant="body1">
                        {formatPercentage(optimizationResult.metrics.max_drawdown_percent)}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Sharpe Ratio:
                      </Typography>
                      <Typography variant="body1">
                        {optimizationResult.metrics.sharpe_ratio.toFixed(3)}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Return/Drawdown Ratio:
                      </Typography>
                      <Typography variant="body1">
                        {optimizationResult.metrics.return_drawdown_ratio.toFixed(3)}
                      </Typography>
                    </Box>
                  </Box>
                </CardContent>
              </Card>

              <Typography variant="subtitle1" gutterBottom>
                Optimal Portfolio Weights
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Portfolio</TableCell>
                      <TableCell align="right">Weight</TableCell>
                      <TableCell align="right">Ratio</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {optimizationResult.portfolio_names.map((name, index) => (
                      <TableRow key={name}>
                        <TableCell>
                          <Typography variant="body2">{name}</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Chip 
                            label={formatPercentage(optimizationResult.optimal_weights[name])}
                            size="small"
                            color="primary"
                            variant="outlined"
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2">
                            {optimizationResult.optimal_ratios[name].toFixed(2)}x
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          )}
        </Box>
      </Box>
    </Container>
  );
};

export default ProfitOptimization;