import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Chip,
  Box,
  Alert,
  CircularProgress,
  Grid,
  LinearProgress,
  Tooltip,
  IconButton,
  Collapse,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  TrendingFlat,
  Warning,
  ExpandMore,
  ExpandLess,
  InfoOutlined,
} from '@mui/icons-material';
import { api } from '../services/api';

interface RegimeIndicators {
  volatility_percentile: number;
  trend_strength: number;
  momentum_score: number;
  drawdown_severity: number;
  volume_anomaly: number;
}

interface RegimeClassification {
  regime: string;
  confidence: number;
  indicators: RegimeIndicators;
  detected_at: string;
  description: string;
}

interface RegimeAlert {
  id: number;
  alert_type: string;
  previous_regime?: string;
  new_regime: string;
  confidence: number;
  title: string;
  message: string;
  severity: string;
  recommended_allocations: { [key: string]: number };
  created_at: string;
  is_active: boolean;
}

const RegimeStatus: React.FC = () => {
  const [currentRegime, setCurrentRegime] = useState<RegimeClassification | null>(null);
  const [alerts, setAlerts] = useState<RegimeAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    fetchRegimeData();
    // Refresh every 10 minutes
    const interval = setInterval(fetchRegimeData, 10 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const fetchRegimeData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch current regime and alerts in parallel
      const [regimeResponse, alertsResponse] = await Promise.all([
        api.get<RegimeClassification>('/api/regime/current'),
        api.get<RegimeAlert[]>('/api/regime/alerts'),
      ]);

      setCurrentRegime(regimeResponse.data);
      setAlerts(alertsResponse.data);
    } catch (err: any) {
      console.error('Failed to fetch regime data:', err);
      setError('Failed to load market regime data');
    } finally {
      setLoading(false);
    }
  };

  const dismissAlert = async (alertId: number) => {
    try {
      await api.post(`/api/regime/alerts/${alertId}/dismiss`);
      setAlerts(alerts.filter(alert => alert.id !== alertId));
    } catch (err) {
      console.error('Failed to dismiss alert:', err);
    }
  };

  const getRegimeIcon = (regime: string) => {
    switch (regime) {
      case 'bull':
        return <TrendingUp sx={{ color: 'success.main' }} />;
      case 'bear':
        return <TrendingDown sx={{ color: 'error.main' }} />;
      case 'volatile':
        return <Warning sx={{ color: 'warning.main' }} />;
      default:
        return <TrendingFlat sx={{ color: 'grey.500' }} />;
    }
  };

  const getRegimeColor = (regime: string) => {
    switch (regime) {
      case 'bull':
        return 'success';
      case 'bear':
        return 'error';
      case 'volatile':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'success';
    if (confidence >= 0.6) return 'warning';
    return 'error';
  };

  const formatPercentage = (value: number) => `${(value * 100).toFixed(1)}%`;

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" alignItems="center" justifyContent="center" p={3}>
            <CircularProgress />
            <Typography variant="body2" sx={{ ml: 2 }}>
              Loading market regime...
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!currentRegime) {
    return (
      <Alert severity="info" sx={{ mb: 2 }}>
        No regime data available
      </Alert>
    );
  }

  return (
    <Box>
      {/* Active Alerts */}
      {alerts.length > 0 && (
        <Box mb={2}>
          {alerts.map((alert) => (
            <Alert
              key={alert.id}
              severity={alert.severity as any}
              onClose={() => dismissAlert(alert.id)}
              sx={{ mb: 1 }}
            >
              <Typography variant="subtitle2" gutterBottom>
                {alert.title}
              </Typography>
              <Typography variant="body2">
                {alert.message}
              </Typography>
              {Object.keys(alert.recommended_allocations).length > 0 && (
                <Box mt={1}>
                  <Typography variant="caption" display="block" gutterBottom>
                    Recommended Allocations:
                  </Typography>
                  <Grid container spacing={1}>
                    {Object.entries(alert.recommended_allocations).map(([strategy, weight]) => (
                      <Grid key={strategy}>
                        <Chip
                          size="small"
                          label={`${strategy}: ${formatPercentage(weight)}`}
                          variant="outlined"
                        />
                      </Grid>
                    ))}
                  </Grid>
                </Box>
              )}
            </Alert>
          ))}
        </Box>
      )}

      {/* Current Regime Status */}
      <Card>
        <CardContent>
          <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
            <Typography variant="h6">
              Market Regime
            </Typography>
            <Tooltip title="Show detailed indicators">
              <IconButton onClick={() => setShowDetails(!showDetails)} size="small">
                {showDetails ? <ExpandLess /> : <ExpandMore />}
              </IconButton>
            </Tooltip>
          </Box>

          <Grid container spacing={3} alignItems="center">
            <Grid>
              {getRegimeIcon(currentRegime.regime)}
            </Grid>
            <Grid sx={{ flex: 1 }}>
              <Box display="flex" alignItems="center" gap={2}>
                <Chip
                  label={currentRegime.regime.toUpperCase()}
                  color={getRegimeColor(currentRegime.regime) as any}
                  variant="filled"
                  size="medium"
                />
                <Typography variant="body2" color="text.secondary">
                  {currentRegime.description}
                </Typography>
              </Box>
            </Grid>
            <Grid>
              <Box textAlign="center">
                <Typography variant="caption" display="block" color="text.secondary">
                  Confidence
                </Typography>
                <Chip
                  label={formatPercentage(currentRegime.confidence)}
                  color={getConfidenceColor(currentRegime.confidence) as any}
                  size="small"
                />
              </Box>
            </Grid>
          </Grid>

          <Box mt={2}>
            <Typography variant="caption" color="text.secondary">
              Last updated: {new Date(currentRegime.detected_at).toLocaleString()}
            </Typography>
          </Box>

          {/* Detailed Indicators */}
          <Collapse in={showDetails}>
            <Box mt={3}>
              <Typography variant="subtitle2" gutterBottom>
                Market Indicators
              </Typography>
              
              <Box display="grid" gridTemplateColumns={{ xs: '1fr', sm: '1fr 1fr' }} gap={2}>
                <Box mb={2}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="body2">
                      Volatility Percentile
                    </Typography>
                    <Tooltip title="Higher values indicate increased market volatility">
                      <InfoOutlined fontSize="small" color="action" />
                    </Tooltip>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={currentRegime.indicators.volatility_percentile * 100}
                    color={currentRegime.indicators.volatility_percentile > 0.7 ? 'warning' : 'primary'}
                    sx={{ height: 8, borderRadius: 4 }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {formatPercentage(currentRegime.indicators.volatility_percentile)}
                  </Typography>
                </Box>

                <Box mb={2}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="body2">
                      Trend Strength
                    </Typography>
                    <Tooltip title="Positive values indicate uptrend, negative values indicate downtrend">
                      <InfoOutlined fontSize="small" color="action" />
                    </Tooltip>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={Math.abs(currentRegime.indicators.trend_strength) * 100}
                    color={currentRegime.indicators.trend_strength > 0 ? 'success' : 'error'}
                    sx={{ height: 8, borderRadius: 4 }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {currentRegime.indicators.trend_strength > 0 ? '+' : ''}{formatPercentage(currentRegime.indicators.trend_strength)}
                  </Typography>
                </Box>

                <Box mb={2}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="body2">
                      Momentum Score
                    </Typography>
                    <Tooltip title="Measures recent price momentum relative to longer-term trends">
                      <InfoOutlined fontSize="small" color="action" />
                    </Tooltip>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={Math.abs(currentRegime.indicators.momentum_score * 100)}
                    color={currentRegime.indicators.momentum_score > 0 ? 'success' : 'error'}
                    sx={{ height: 8, borderRadius: 4 }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {currentRegime.indicators.momentum_score.toFixed(2)}
                  </Typography>
                </Box>

                <Box mb={2}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="body2">
                      Drawdown Severity
                    </Typography>
                    <Tooltip title="Current drawdown from recent highs">
                      <InfoOutlined fontSize="small" color="action" />
                    </Tooltip>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={currentRegime.indicators.drawdown_severity * 100}
                    color={currentRegime.indicators.drawdown_severity > 0.1 ? 'error' : 'primary'}
                    sx={{ height: 8, borderRadius: 4 }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    -{formatPercentage(currentRegime.indicators.drawdown_severity)}
                  </Typography>
                </Box>
              </Box>
            </Box>
          </Collapse>
        </CardContent>
      </Card>
    </Box>
  );
};

export default RegimeStatus;