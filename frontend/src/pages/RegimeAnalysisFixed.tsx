import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Button,
  CircularProgress,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  SelectChangeEvent,
  OutlinedInput,
} from '@mui/material';
import {
  Timeline,
  TrendingUp,
  Assessment,
} from '@mui/icons-material';
import RegimeStatus from '../components/RegimeStatus';
import { api } from '../services/api';

interface RegimeHistory {
  id: number;
  date: string;
  regime: string;
  confidence: number;
  volatility_percentile?: number;
  trend_strength?: number;
  momentum_score?: number;
  drawdown_severity?: number;
  volume_anomaly?: number;
  description?: string;
}

interface RegimePerformance {
  portfolio_id: number;
  portfolio_name: string;
  regime_performance: {
    [regime: string]: {
      total_return: number;
      avg_daily_return: number;
      volatility: number;
      sharpe_ratio: number;
      max_drawdown: number;
      win_rate: number;
    };
  };
}

interface AllocationRecommendation {
  current_regime: string;
  confidence: number;
  recommendations: { [key: string]: number };
  reasoning: string;
}

interface Portfolio {
  id: number;
  name: string;
  filename: string;
  upload_date: string;
}

const RegimeAnalysisFixed: React.FC = () => {
  const [regimeHistory, setRegimeHistory] = useState<RegimeHistory[]>([]);
  const [portfolioPerformances, setPortfolioPerformances] = useState<RegimePerformance[]>([]);
  const [recommendations, setRecommendations] = useState<AllocationRecommendation | null>(null);
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selectedPortfolios, setSelectedPortfolios] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [historyDays, setHistoryDays] = useState(90);

  useEffect(() => {
    fetchData();
  }, [historyDays]);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch regime history and portfolios
      const [historyResponse, portfoliosResponse] = await Promise.all([
        api.get<RegimeHistory[]>(`/api/regime/history?days=${historyDays}`),
        api.get<{ strategies: Portfolio[] }>('/api/strategies'),
      ]);

      setRegimeHistory(historyResponse.data);
      setPortfolios(portfoliosResponse.data.strategies || []);

      // Auto-select first few portfolios if any exist
      if (portfoliosResponse.data.strategies && portfoliosResponse.data.strategies.length > 0) {
        const defaultSelection = portfoliosResponse.data.strategies.slice(0, 3).map(p => p.id);
        setSelectedPortfolios(defaultSelection);

        // Fetch performance data for all portfolios
        await fetchPortfolioPerformances(portfoliosResponse.data.strategies.map(p => p.id));
      }
    } catch (err: any) {
      console.error('Failed to fetch regime analysis data:', err);
      setError('Failed to load regime analysis data');
    } finally {
      setLoading(false);
    }
  };

  const fetchPortfolioPerformances = async (portfolioIds: number[]) => {
    try {
      const performancePromises = portfolioIds.map(id =>
        api.get<RegimePerformance>(`/api/regime/analyze-portfolio/${id}`)
          .catch(() => null) // Handle individual failures gracefully
      );

      const responses = await Promise.all(performancePromises);
      const validResponses = responses.filter(r => r !== null) as { data: RegimePerformance }[];
      setPortfolioPerformances(validResponses.map(r => r.data));
    } catch (err) {
      console.error('Failed to fetch portfolio performances:', err);
    }
  };

  const fetchRecommendations = async () => {
    if (selectedPortfolios.length === 0) {
      setRecommendations(null);
      return;
    }

    try {
      const response = await api.post<AllocationRecommendation>(
        '/api/regime/recommendations',
        { portfolio_ids: selectedPortfolios }
      );
      setRecommendations(response.data);
    } catch (err) {
      console.error('Failed to fetch recommendations:', err);
      setError('Failed to generate allocation recommendations');
    }
  };

  const handlePortfolioSelection = (event: SelectChangeEvent<unknown>) => {
    const value = event.target.value as number[];
    setSelectedPortfolios(value);
  };

  const getRegimeColor = (regime: string): 'success' | 'error' | 'warning' | 'default' => {
    switch (regime) {
      case 'bull': return 'success';
      case 'bear': return 'error';
      case 'volatile': return 'warning';
      default: return 'default';
    }
  };

  const formatPercentage = (value: number) => `${(value * 100).toFixed(1)}%`;
  const formatDecimal = (value: number, decimals: number = 2) => value.toFixed(decimals);

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ py: 3, minHeight: '100vh' }}>
        <Box display="flex" alignItems="center" justifyContent="center" minHeight="400px">
          <CircularProgress />
          <Typography variant="body1" sx={{ ml: 2 }}>
            Loading regime analysis...
          </Typography>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 3, minHeight: '100vh' }}>
      <Box py={3}>
        <Typography variant="h4" gutterBottom display="flex" alignItems="center">
          <Assessment sx={{ mr: 2 }} />
          Market Regime Analysis
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}

        {/* Current Regime Status */}
        <Box mb={4}>
          <RegimeStatus />
        </Box>

        {/* Main Content */}
        <Box display="flex" flexDirection="column" gap={4}>
          
          {/* Regime History */}
          <Card>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                <Typography variant="h6" display="flex" alignItems="center">
                  <Timeline sx={{ mr: 1 }} />
                  Regime History
                </Typography>
                <FormControl size="small" sx={{ minWidth: 120 }}>
                  <InputLabel>Time Period</InputLabel>
                  <Select
                    value={historyDays}
                    label="Time Period"
                    onChange={(e) => setHistoryDays(e.target.value as number)}
                  >
                    <MenuItem value={30}>30 Days</MenuItem>
                    <MenuItem value={90}>90 Days</MenuItem>
                    <MenuItem value={180}>180 Days</MenuItem>
                    <MenuItem value={365}>1 Year</MenuItem>
                  </Select>
                </FormControl>
              </Box>

              {regimeHistory.length > 0 ? (
                <TableContainer component={Paper} variant="outlined">
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Date</TableCell>
                        <TableCell>Regime</TableCell>
                        <TableCell align="right">Confidence</TableCell>
                        <TableCell align="right">Volatility %ile</TableCell>
                        <TableCell align="right">Trend Strength</TableCell>
                        <TableCell>Description</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {regimeHistory.slice(0, 10).map((row) => (
                        <TableRow key={row.id}>
                          <TableCell>
                            {new Date(row.date).toLocaleDateString()}
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={row.regime.toUpperCase()}
                              color={getRegimeColor(row.regime)}
                              size="small"
                            />
                          </TableCell>
                          <TableCell align="right">
                            {formatPercentage(row.confidence)}
                          </TableCell>
                          <TableCell align="right">
                            {row.volatility_percentile ? formatPercentage(row.volatility_percentile) : 'N/A'}
                          </TableCell>
                          <TableCell align="right">
                            {row.trend_strength !== undefined ? formatDecimal(row.trend_strength) : 'N/A'}
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" color="text.secondary">
                              {row.description || 'No description'}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Alert severity="info">
                  No regime history available yet. The system will automatically track market regimes over time.
                </Alert>
              )}
            </CardContent>
          </Card>

          {/* Strategy Performance by Regime */}
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom display="flex" alignItems="center">
                <TrendingUp sx={{ mr: 1 }} />
                Strategy Performance by Regime
              </Typography>

              {portfolioPerformances.length > 0 ? (
                <TableContainer component={Paper} variant="outlined">
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Strategy</TableCell>
                        <TableCell>Regime</TableCell>
                        <TableCell align="right">Total Return</TableCell>
                        <TableCell align="right">Sharpe Ratio</TableCell>
                        <TableCell align="right">Max Drawdown</TableCell>
                        <TableCell align="right">Win Rate</TableCell>
                        <TableCell align="right">Volatility</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {portfolioPerformances.map((perf) =>
                        Object.entries(perf.regime_performance).map(([regime, metrics]) => (
                          <TableRow key={`${perf.portfolio_id}-${regime}`}>
                            <TableCell>{perf.portfolio_name}</TableCell>
                            <TableCell>
                              <Chip
                                label={regime.toUpperCase()}
                                color={getRegimeColor(regime)}
                                size="small"
                              />
                            </TableCell>
                            <TableCell align="right">
                              {formatPercentage(metrics.total_return)}
                            </TableCell>
                            <TableCell align="right">
                              {formatDecimal(metrics.sharpe_ratio)}
                            </TableCell>
                            <TableCell align="right">
                              -{formatPercentage(Math.abs(metrics.max_drawdown))}
                            </TableCell>
                            <TableCell align="right">
                              {formatPercentage(metrics.win_rate)}
                            </TableCell>
                            <TableCell align="right">
                              {formatPercentage(metrics.volatility)}
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Alert severity="info">
                  No performance data available. Upload portfolios to see regime-specific performance analysis.
                </Alert>
              )}
            </CardContent>
          </Card>

          {/* Allocation Recommendations */}
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom display="flex" alignItems="center">
                <Assessment sx={{ mr: 1 }} />
                Regime-Optimized Allocation Recommendations
              </Typography>

              {portfolios.length > 0 ? (
                <>
                  <Box mb={3}>
                    <FormControl fullWidth>
                      <InputLabel>Select Portfolios for Recommendations</InputLabel>
                      <Select
                        multiple
                        value={selectedPortfolios}
                        onChange={handlePortfolioSelection}
                        input={<OutlinedInput label="Select Portfolios for Recommendations" />}
                        renderValue={(selected) => 
                          portfolios
                            .filter(p => (selected as number[]).includes(p.id))
                            .map(p => p.name)
                            .join(', ')
                        }
                      >
                        {portfolios.map((portfolio) => (
                          <MenuItem key={portfolio.id} value={portfolio.id}>
                            {portfolio.name}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Box>

                  <Box mb={3}>
                    <Button
                      variant="contained"
                      onClick={fetchRecommendations}
                      disabled={selectedPortfolios.length === 0}
                    >
                      Get Recommendations
                    </Button>
                  </Box>

                  {recommendations && (
                    <Box>
                      <Alert severity="info" sx={{ mb: 2 }}>
                        <Typography variant="subtitle2" gutterBottom>
                          Current Market Regime: {recommendations.current_regime.toUpperCase()}
                        </Typography>
                        <Typography variant="body2">
                          {recommendations.reasoning}
                        </Typography>
                      </Alert>

                      <Box display="grid" gridTemplateColumns={{ xs: '1fr', sm: '1fr 1fr', md: '1fr 1fr 1fr' }} gap={2}>
                        {Object.entries(recommendations.recommendations).map(([strategy, allocation]) => (
                          <Card key={strategy} variant="outlined">
                            <CardContent>
                              <Typography variant="h6" gutterBottom>
                                {strategy}
                              </Typography>
                              <Typography variant="h4" color="primary">
                                {formatPercentage(allocation)}
                              </Typography>
                              <Typography variant="body2" color="text.secondary">
                                Recommended Allocation
                              </Typography>
                            </CardContent>
                          </Card>
                        ))}
                      </Box>
                    </Box>
                  )}
                </>
              ) : (
                <Alert severity="info">
                  No portfolios available. Upload some portfolio data first to get regime-based allocation recommendations.
                </Alert>
              )}
            </CardContent>
          </Card>
        </Box>
      </Box>
    </Container>
  );
};

export default RegimeAnalysisFixed;