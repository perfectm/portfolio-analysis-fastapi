import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  Box,
  Paper,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Button,
  Grid,
  Card,
  CardContent,
  CardHeader,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tabs,
  Tab,
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
  ScatterChart,
  Scatter,
} from "recharts";
import { Delete } from "@mui/icons-material";
import { portfolioAPI } from "../services/api";

interface Portfolio {
  id: number;
  name: string;
  filename: string;
  date_range_start: string;
  date_range_end: string;
  row_count: number;
  available_for_testing: boolean;
  max_testable_start_date: string;
  full_dataset_metrics?: Record<string, number>;
}

interface RobustnessTest {
  test_id: number;
  status: string;
  num_periods: number;
  min_period_length_days?: number;
  overall_robustness_score?: number;
  created_at: string;
  completed_at?: string;
}

interface TestResults {
  test_id: number;
  portfolio_id: number;
  portfolio_name: string;
  status: string;
  overall_robustness_score?: number;
  periods: Array<{
    period_number: number;
    start_date: string;
    end_date: string;
    cagr: number;
    sharpe_ratio: number;
    max_drawdown: number;
    volatility: number;
    win_rate: number;
    total_return: number;
    total_pl: number;
    pcr: number;
    trade_count: number;
  }>;
  statistics: Record<string, {
    max_value: number;
    min_value: number;
    mean_value: number;
    median_value: number;
    std_deviation: number;
    q1_value: number;
    q3_value: number;
    full_dataset_value: number;
    robustness_component_score: number;
    relative_deviation: number;
  }>;
}

const RobustnessTest: React.FC = () => {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<number | null>(null);
  const [selectedPortfolio, setSelectedPortfolio] = useState<Portfolio | null>(null);
  const [numPeriods, setNumPeriods] = useState(10);
  const [periodType, setPeriodType] = useState<'month' | 'year'>('year');
  const [periodLength, setPeriodLength] = useState(365);
  const [rfRate, setRfRate] = useState(0.043);
  const [smaWindow, setSmaWindow] = useState(20);
  const [startingCapital, setStartingCapital] = useState(1000000);
  const [loading, setLoading] = useState(false);
  const [testInProgress, setTestInProgress] = useState(false);
  const [currentTestId, setCurrentTestId] = useState<number | null>(null);
  const [testProgress, setTestProgress] = useState(0);
  const [testResults, setTestResults] = useState<TestResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [portfolioTests, setPortfolioTests] = useState<RobustnessTest[]>([]);
  const [resultsDialogOpen, setResultsDialogOpen] = useState(false);
  const [selectedTab, setSelectedTab] = useState(0);
  const [chartMetric, setChartMetric] = useState<'pcr' | 'totalPL'>('pcr');

  // Load available portfolios
  useEffect(() => {
    loadPortfolios(periodLength);
  }, [periodLength]);

  // Initial load
  useEffect(() => {
    loadPortfolios(periodLength);
  }, []);

  // Load portfolio tests and metrics when portfolio is selected
  useEffect(() => {
    if (selectedPortfolioId) {
      // Set the selected portfolio immediately from the list (without metrics)
      const portfolio = portfolios.find(p => p.id === selectedPortfolioId);
      setSelectedPortfolio(portfolio || null);

      // Then load tests and metrics in the background
      loadPortfolioTests(selectedPortfolioId);
      loadPortfolioMetrics(selectedPortfolioId);
    }
  }, [selectedPortfolioId, portfolios]);

  // Poll for test progress
  useEffect(() => {
    if (testInProgress && currentTestId) {
      const interval = setInterval(async () => {
        try {
          const response = await fetch(`/api/robustness/test/${currentTestId}/status`);
          const status = await response.json();

          setTestProgress(status.progress || 0);

          if (status.status === 'completed') {
            setTestInProgress(false);
            setTestProgress(100);
            loadTestResults(currentTestId);
            loadPortfolioTests(selectedPortfolioId!);
          } else if (status.status === 'failed') {
            setTestInProgress(false);
            setError(status.error_message || 'Test failed');
          }
        } catch (error) {
          console.error('Error polling test status:', error);
        }
      }, 2000);

      return () => clearInterval(interval);
    }
  }, [testInProgress, currentTestId, selectedPortfolioId]);

  const loadPortfolios = async (minPeriodLength: number = 30) => {
    try {
      // Load portfolios WITHOUT metrics for faster initial load
      const response = await fetch(`/api/robustness/portfolios?period_length=${minPeriodLength}&include_metrics=false`);
      const data = await response.json();
      setPortfolios(data.filter((p: Portfolio) => p.available_for_testing));
    } catch (error) {
      console.error('Error loading portfolios:', error);
      setError('Failed to load portfolios');
    }
  };

  const loadPortfolioMetrics = async (portfolioId: number) => {
    try {
      // Load full metrics for the selected portfolio
      const response = await fetch(`/api/robustness/portfolio/${portfolioId}/metrics`);
      const metrics = await response.json();

      // Update the portfolio in the list with metrics
      setPortfolios(prevPortfolios =>
        prevPortfolios.map(p =>
          p.id === portfolioId ? { ...p, full_dataset_metrics: metrics } : p
        )
      );

      // Update selected portfolio with metrics
      setSelectedPortfolio(prev =>
        prev && prev.id === portfolioId ? { ...prev, full_dataset_metrics: metrics } : prev
      );
    } catch (error) {
      console.error('Error loading portfolio metrics:', error);
      // Don't show error to user - metrics are optional
    }
  };

  const loadPortfolioTests = async (portfolioId: number) => {
    try {
      const response = await fetch(`/api/robustness/portfolio/${portfolioId}/tests`);
      const data = await response.json();
      setPortfolioTests(data);
    } catch (error) {
      console.error('Error loading portfolio tests:', error);
    }
  };

  const loadTestResults = async (testId: number) => {
    try {
      const response = await fetch(`/api/robustness/test/${testId}/results`);
      const data = await response.json();
      setTestResults(data);
      setResultsDialogOpen(true);
    } catch (error) {
      console.error('Error loading test results:', error);
      setError('Failed to load test results');
    }
  };

  const deleteRobustnessTest = async (testId: number) => {
    if (!window.confirm('Are you sure you want to delete this robustness test?')) {
      return;
    }

    try {
      const response = await fetch(`/api/robustness/test/${testId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete test');
      }

      // Reload the portfolio tests
      if (selectedPortfolioId) {
        loadPortfolioTests(selectedPortfolioId);
      }
    } catch (error) {
      console.error('Error deleting test:', error);
      setError('Failed to delete test');
    }
  };

  const startRobustnessTest = async () => {
    if (!selectedPortfolioId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/robustness/${selectedPortfolioId}/test`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          num_periods: numPeriods,
          period_length_days: periodLength,
          rf_rate: rfRate,
          sma_window: smaWindow,
          starting_capital: startingCapital,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to start robustness test');
      }

      const result = await response.json();
      setCurrentTestId(result.test_id);
      setTestInProgress(true);
      setTestProgress(0);
    } catch (error) {
      console.error('Error starting robustness test:', error);
      setError('Failed to start robustness test');
    } finally {
      setLoading(false);
    }
  };

  const formatNumber = (value: number | undefined, decimals = 2) => {
    if (value === undefined || value === null) return 'N/A';
    return value.toFixed(decimals);
  };

  const formatPercentage = (value: number | undefined, decimals = 1) => {
    if (value === undefined || value === null) return 'N/A';
    return `${(value * 100).toFixed(decimals)}%`;
  };

  const formatCurrency = (value: number | undefined, decimals = 0) => {
    if (value === undefined || value === null) return 'N/A';
    return `$${Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
  };

  const getScoreColor = (score: number | undefined) => {
    if (!score) return 'default';
    if (score >= 80) return 'success';
    if (score >= 60) return 'warning';
    return 'error';
  };

  const renderStatisticsTable = () => {
    if (!testResults?.statistics) return null;

    const metrics = ['cagr', 'max_drawdown', 'win_rate', 'total_pl', 'pcr'];
    
    return (
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Metric</TableCell>
              <TableCell align="right">Min</TableCell>
              <TableCell align="right">Max</TableCell>
              <TableCell align="right">Mean</TableCell>
              <TableCell align="right">Median</TableCell>
              <TableCell align="right">Std Dev</TableCell>
              <TableCell align="right">Full Dataset</TableCell>
              <TableCell align="right">Score</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {metrics.map((metric) => {
              const stats = testResults.statistics[metric];
              if (!stats) return null;

              const formatMetricValue = (value: number | undefined) => {
                if (metric === 'cagr' || metric === 'win_rate') {
                  return formatPercentage(value);
                } else if (metric === 'max_drawdown') {
                  return `$${Math.abs(value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                } else if (metric === 'total_pl') {
                  return formatCurrency(value);
                } else if (metric === 'pcr') {
                  return formatPercentage(value);
                } else if (metric === 'volatility') {
                  return formatPercentage(value);
                } else {
                  return formatNumber(value);
                }
              };

              return (
                <TableRow key={metric}>
                  <TableCell>{metric.replace('_', ' ').toUpperCase()}</TableCell>
                  <TableCell align="right">{formatMetricValue(stats.min_value)}</TableCell>
                  <TableCell align="right">{formatMetricValue(stats.max_value)}</TableCell>
                  <TableCell align="right">{formatMetricValue(stats.mean_value)}</TableCell>
                  <TableCell align="right">{formatMetricValue(stats.median_value)}</TableCell>
                  <TableCell align="right">{formatMetricValue(stats.std_deviation)}</TableCell>
                  <TableCell align="right">{formatMetricValue(stats.full_dataset_value)}</TableCell>
                  <TableCell align="right">
                    <Chip
                      label={formatNumber(stats.robustness_component_score)}
                      color={getScoreColor(stats.robustness_component_score)}
                      size="small"
                    />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    );
  };

  // Memoize chart data to prevent infinite re-renders
  const chartData = useMemo(() => {
    if (!testResults?.periods) return [];
    return testResults.periods.map(period => ({
      period: `P${period.period_number}`,
      pcr: (period.pcr || 0) * 100, // Convert to percentage
      totalPL: period.total_pl, // Total P/L
      drawdown: Math.abs(period.max_drawdown), // Make drawdown positive for better display
      startDate: period.start_date,
      endDate: period.end_date,
    }));
  }, [testResults?.periods]);

  const hasValidPCR = useMemo(() => {
    if (!testResults?.periods) return false;
    return testResults.periods.some(period =>
      period.pcr !== null && period.pcr !== undefined && period.pcr !== 0
    );
  }, [testResults?.periods]);

  const displayMetric = useMemo(() => {
    return (chartMetric === 'pcr' && !hasValidPCR) ? 'totalPL' : chartMetric;
  }, [chartMetric, hasValidPCR]);

  // Memoize formatter callbacks
  const leftAxisFormatter = useCallback((value: number) => {
    return `$${Math.abs(value).toLocaleString('en-US')}`;
  }, []);

  const rightAxisFormatter = useCallback((value: number) => {
    return displayMetric === 'pcr' ? `${value.toFixed(1)}%` : `$${value.toLocaleString('en-US')}`;
  }, [displayMetric]);

  const tooltipFormatter = useCallback((value: any, name: string) => {
    const numValue = Array.isArray(value) ? value[0] :
                   typeof value === 'string' ? parseFloat(value) : value;
    if (name === 'PCR') return [`${(numValue as number).toFixed(1)}%`, name];
    if (name === 'Total P/L') return [`$${(numValue as number).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`, name];
    if (name === 'Max Drawdown') return [`$${(numValue as number).toFixed(0)}`, name];
    return [(numValue as number).toFixed(3), name];
  }, []);

  const labelFormatter = useCallback((label: string, payload: any) => {
    if (payload && payload.length > 0) {
      const data = payload[0].payload;
      const startDate = new Date(data.startDate).toLocaleDateString();
      const endDate = new Date(data.endDate).toLocaleDateString();
      return `${label} (${startDate} - ${endDate})`;
    }
    return label;
  }, []);

  // Memoize the entire chart component
  const PeriodsChart = useMemo(() => {
    if (!testResults?.periods || chartData.length === 0) return null;

    const secondaryMetricLabel = displayMetric === 'pcr' ? 'PCR' : 'Total P/L';
    const secondaryMetricDataKey = displayMetric;

    return (
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="period" />
          <YAxis
            yAxisId="left"
            orientation="left"
            tickFormatter={leftAxisFormatter}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tickFormatter={rightAxisFormatter}
          />
          <Tooltip
            formatter={tooltipFormatter}
            labelFormatter={labelFormatter}
          />
          <Legend />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey={secondaryMetricDataKey}
            stroke="#8884d8"
            name={secondaryMetricLabel}
            strokeWidth={2}
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="drawdown"
            stroke="#ffc658"
            name="Max Drawdown"
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    );
  }, [testResults, chartData, displayMetric, leftAxisFormatter, rightAxisFormatter, tooltipFormatter, labelFormatter]);

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Portfolio Robustness Testing
      </Typography>
      
      <Typography variant="body1" sx={{ mb: 3 }}>
        Test portfolio performance consistency across multiple random time periods.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Box sx={{ display: 'flex', gap: 3, flexDirection: { xs: 'column', md: 'row' } }}>
        {/* Configuration Panel */}
        <Box sx={{ flex: { xs: '1', md: '0 0 33%' } }}>
          <Card>
            <CardHeader title="Test Configuration" />
            <CardContent>
              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Portfolio</InputLabel>
                <Select
                  value={selectedPortfolioId || ''}
                  onChange={(e) => setSelectedPortfolioId(Number(e.target.value))}
                >
                  {portfolios.map((portfolio) => (
                    <MenuItem key={portfolio.id} value={portfolio.id}>
                      {portfolio.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <TextField
                label="Number of Periods"
                type="number"
                value={numPeriods}
                onChange={(e) => setNumPeriods(Number(e.target.value))}
                inputProps={{ min: 5, max: 99 }}
                fullWidth
                sx={{ mb: 2 }}
              />

              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Period Length</InputLabel>
                <Select
                  value={periodType}
                  onChange={(e) => {
                    const newType = e.target.value as 'month' | 'year';
                    setPeriodType(newType);
                    setPeriodLength(newType === 'month' ? 30 : 365);
                  }}
                >
                  <MenuItem value="month">1 Month (30 days)</MenuItem>
                  <MenuItem value="year">1 Year (365 days)</MenuItem>
                </Select>
              </FormControl>

              <TextField
                label={`Custom Period Length (Days) - Current: ${periodLength}`}
                type="number"
                value={periodLength}
                onChange={(e) => setPeriodLength(Number(e.target.value))}
                inputProps={{ min: 30, max: 1000 }}
                fullWidth
                sx={{ mb: 2 }}
                helperText={periodType === 'month' ? 'Month periods: 30-60 days' : 'Year periods: 200-365 days'}
              />

              <TextField
                label="Risk-Free Rate"
                type="number"
                value={rfRate}
                onChange={(e) => setRfRate(Number(e.target.value))}
                inputProps={{ step: 0.001, min: 0, max: 1 }}
                fullWidth
                sx={{ mb: 2 }}
              />

              <TextField
                label="SMA Window"
                type="number"
                value={smaWindow}
                onChange={(e) => setSmaWindow(Number(e.target.value))}
                inputProps={{ min: 1, max: 100 }}
                fullWidth
                sx={{ mb: 2 }}
              />

              <TextField
                label="Starting Capital"
                type="number"
                value={startingCapital}
                onChange={(e) => setStartingCapital(Number(e.target.value))}
                inputProps={{ min: 1000 }}
                fullWidth
                sx={{ mb: 3 }}
              />

              <Button
                variant="contained"
                onClick={startRobustnessTest}
                disabled={!selectedPortfolioId || loading || testInProgress}
                fullWidth
                sx={{ mb: 2 }}
              >
                {testInProgress ? `Running Test... ${testProgress}%` : 'Start Robustness Test'}
              </Button>

              {testInProgress && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <CircularProgress size={20} />
                  <Typography variant="body2">
                    {testProgress}% Complete
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Box>

        {/* Portfolio Overview */}
        <Box sx={{ flex: { xs: '1', md: '0 0 67%' } }}>
          {selectedPortfolio && (
            <Card sx={{ mb: 3 }}>
              <CardHeader title={`Portfolio: ${selectedPortfolio.name}`} />
              <CardContent>
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                  <Box sx={{ flex: 1, minWidth: '200px' }}>
                    <Typography variant="body2" color="textSecondary">
                      Date Range
                    </Typography>
                    <Typography variant="body1">
                      {new Date(selectedPortfolio.date_range_start).toLocaleDateString()} - {new Date(selectedPortfolio.date_range_end).toLocaleDateString()}
                    </Typography>
                  </Box>
                  <Box sx={{ flex: 1, minWidth: '200px' }}>
                    <Typography variant="body2" color="textSecondary">
                      Total Trades
                    </Typography>
                    <Typography variant="body1">
                      {selectedPortfolio.row_count?.toLocaleString()}
                    </Typography>
                  </Box>
                </Box>

                {selectedPortfolio.full_dataset_metrics && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="h6" gutterBottom>
                      Full Dataset Metrics
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                      <Box sx={{ flex: 1, minWidth: '150px' }}>
                        <Typography variant="body2" color="textSecondary">CAGR</Typography>
                        <Typography variant="body1">
                          {formatPercentage(selectedPortfolio.full_dataset_metrics.cagr)}
                        </Typography>
                      </Box>
                      <Box sx={{ flex: 1, minWidth: '150px' }}>
                        <Typography variant="body2" color="textSecondary">Sharpe Ratio</Typography>
                        <Typography variant="body1">
                          {formatNumber(selectedPortfolio.full_dataset_metrics.sharpe_ratio)}
                        </Typography>
                      </Box>
                      <Box sx={{ flex: 1, minWidth: '150px' }}>
                        <Typography variant="body2" color="textSecondary">Max Drawdown</Typography>
                        <Typography variant="body1">
                          {formatNumber(selectedPortfolio.full_dataset_metrics.max_drawdown)}
                        </Typography>
                      </Box>
                      <Box sx={{ flex: 1, minWidth: '150px' }}>
                        <Typography variant="body2" color="textSecondary">Win Rate</Typography>
                        <Typography variant="body1">
                          {formatPercentage(selectedPortfolio.full_dataset_metrics.win_rate)}
                        </Typography>
                      </Box>
                      <Box sx={{ flex: 1, minWidth: '150px' }}>
                        <Typography variant="body2" color="textSecondary">PCR</Typography>
                        <Typography variant="body1">
                          {selectedPortfolio.full_dataset_metrics.pcr ? 
                            formatPercentage(selectedPortfolio.full_dataset_metrics.pcr) : 
                            'N/A'}
                        </Typography>
                      </Box>
                    </Box>
                  </Box>
                )}
              </CardContent>
            </Card>
          )}

          {/* Previous Tests */}
          {portfolioTests.length > 0 && (
            <Card>
              <CardHeader title="Previous Robustness Tests" />
              <CardContent>
                <TableContainer>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Test Date</TableCell>
                        <TableCell>Periods</TableCell>
                        <TableCell>Period Length</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Score</TableCell>
                        <TableCell>Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {portfolioTests.map((test) => (
                        <TableRow key={test.test_id}>
                          <TableCell>
                            {new Date(test.created_at).toLocaleDateString()}
                          </TableCell>
                          <TableCell>{test.num_periods}</TableCell>
                          <TableCell>
                            {test.min_period_length_days ? 
                              test.min_period_length_days >= 200 ? 
                                `${test.min_period_length_days} days (Yearly)` : 
                                `${test.min_period_length_days} days (Monthly)` 
                              : 'N/A'
                            }
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={test.status}
                              color={test.status === 'completed' ? 'success' : 'default'}
                              size="small"
                            />
                          </TableCell>
                          <TableCell>
                            {test.overall_robustness_score && (
                              <Chip
                                label={formatNumber(test.overall_robustness_score)}
                                color={getScoreColor(test.overall_robustness_score)}
                                size="small"
                              />
                            )}
                          </TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', gap: 1 }}>
                              <Button
                                size="small"
                                onClick={() => loadTestResults(test.test_id)}
                                disabled={test.status !== 'completed'}
                              >
                                View Results
                              </Button>
                              <Button
                                size="small"
                                color="error"
                                onClick={() => deleteRobustnessTest(test.test_id)}
                                startIcon={<Delete />}
                              >
                                Delete
                              </Button>
                            </Box>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          )}
        </Box>
      </Box>

      {/* Results Dialog */}
      <Dialog
        open={resultsDialogOpen}
        onClose={() => setResultsDialogOpen(false)}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Typography variant="h6" component="div">
              Robustness Test Results
              {testResults?.overall_robustness_score && (
                <Chip
                  label={`Overall Score: ${formatNumber(testResults.overall_robustness_score)}`}
                  color={getScoreColor(testResults.overall_robustness_score)}
                  sx={{ ml: 2 }}
                />
              )}
            </Typography>
            {testResults?.portfolio_name && (
              <Typography variant="subtitle1" color="text.secondary" sx={{ fontWeight: 'medium' }}>
                Strategy: {testResults.portfolio_name}
              </Typography>
            )}
          </Box>
        </DialogTitle>
        <DialogContent>
          {testResults && (
            <Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Tabs value={selectedTab} onChange={(_, newValue) => setSelectedTab(newValue)}>
                  <Tab label="Summary Statistics" />
                  <Tab label="Period Performance" />
                </Tabs>

                {selectedTab === 1 && (
                  <ToggleButtonGroup
                    value={chartMetric}
                    exclusive
                    onChange={(_, newValue) => {
                      if (newValue !== null) {
                        setChartMetric(newValue);
                      }
                    }}
                    size="small"
                  >
                    <ToggleButton value="pcr">PCR</ToggleButton>
                    <ToggleButton value="totalPL">Total P/L</ToggleButton>
                  </ToggleButtonGroup>
                )}
              </Box>

              <Box sx={{ mt: 2 }}>
                {selectedTab === 0 && renderStatisticsTable()}
                {selectedTab === 1 && PeriodsChart}
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setResultsDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default RobustnessTest;