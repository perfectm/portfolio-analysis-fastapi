import React, { useState, useEffect } from 'react';
import { useTheme, Paper, Typography, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Chip, Button, Box, Select, MenuItem, FormControl, InputLabel, TablePagination, Card, CardContent, Grid, TextField, IconButton } from '@mui/material';
import { TrendingUp, Assessment, History, Refresh, Visibility, Edit, Save, Cancel, Delete } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

interface CachedOptimization {
  id: number;
  name: string | null;
  portfolio_ids: number[];
  portfolio_names: string[];
  portfolio_count: number;
  optimization_method: string;
  optimal_weights: number[];
  optimal_ratios: number[];
  metrics: {
    cagr: number;
    max_drawdown: number;
    return_drawdown_ratio: number;
    sharpe_ratio: number;
  };
  parameters: {
    rf_rate: number;
    sma_window: number;
    use_trading_filter: boolean;
    starting_capital: number;
    min_weight: number;
    max_weight: number;
  };
  execution_info: {
    iterations: number;
    execution_time_seconds: number;
    explored_combinations_count: number;
    access_count: number;
  };
  timestamps: {
    created_at: string;
    last_accessed_at: string;
  };
}

interface OptimizationHistoryResponse {
  success: boolean;
  results: CachedOptimization[];
  pagination: {
    total_count: number;
    limit: number;
    offset: number;
    has_more: boolean;
  };
  error?: string;
}

const OptimizationHistory: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const [optimizations, setOptimizations] = useState<CachedOptimization[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalCount, setTotalCount] = useState(0);
  const [orderBy, setOrderBy] = useState('created_at');
  const [orderDirection, setOrderDirection] = useState('desc');
  const [editingNameId, setEditingNameId] = useState<number | null>(null);
  const [editingNameValue, setEditingNameValue] = useState<string>('');

  const fetchOptimizations = async () => {
    try {
      setLoading(true);
      const offset = page * rowsPerPage;
      const response = await fetch(
        `/api/cached-results?limit=${rowsPerPage}&offset=${offset}&order_by=${orderBy}&order_direction=${orderDirection}`,
        {
          method: 'GET',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      const data: OptimizationHistoryResponse = await response.json();

      if (data.success) {
        setOptimizations(data.results);
        setTotalCount(data.pagination.total_count);
      } else {
        setError(data.error || 'Failed to fetch optimization history');
      }
    } catch (err) {
      setError('Failed to fetch optimization history');
      console.error('Error fetching optimization history:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOptimizations();
  }, [page, rowsPerPage, orderBy, orderDirection]);

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const formatPercentage = (value: number) => {
    return `${(value * 100).toFixed(2)}%`;
  };

  const formatCurrency = (value: number) => {
    return `$${value.toLocaleString()}`;
  };

  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    if (seconds < 3600) return `${(seconds / 60).toFixed(1)}m`;
    return `${(seconds / 3600).toFixed(1)}h`;
  };

  const getMethodColor = (method: string) => {
    switch (method) {
      case 'differential_evolution': return 'primary';
      case 'scipy': return 'secondary';
      case 'grid_search': return 'success';
      default: return 'default';
    }
  };

  const handleViewOptimization = (optimization: CachedOptimization) => {
    // Create URL parameters with optimization data
    const params = new URLSearchParams({
      optimization_id: optimization.id.toString(),
      portfolio_ids: optimization.portfolio_ids.join(','),
      weights: optimization.optimal_weights.join(','),
      ratios: optimization.optimal_ratios.join(','),
      method: optimization.optimization_method,
      cagr: optimization.metrics.cagr.toString(),
      max_drawdown: optimization.metrics.max_drawdown.toString(),
      return_drawdown_ratio: optimization.metrics.return_drawdown_ratio.toString(),
      sharpe_ratio: optimization.metrics.sharpe_ratio.toString(),
      rf_rate: optimization.parameters.rf_rate.toString(),
      sma_window: optimization.parameters.sma_window.toString(),
      use_trading_filter: optimization.parameters.use_trading_filter.toString(),
      starting_capital: optimization.parameters.starting_capital.toString(),
    });

    // Add name if it exists
    if (optimization.name) {
      params.set('name', optimization.name);
    }

    // Navigate to portfolios page with optimization data
    navigate(`/portfolios?${params.toString()}`);
  };

  const handleEditName = (optimization: CachedOptimization) => {
    setEditingNameId(optimization.id);
    setEditingNameValue(optimization.name || `Optimization #${optimization.id}`);
  };

  const handleSaveName = async (optimizationId: number) => {
    try {
      const response = await fetch(`/api/cached-results/${optimizationId}/name`, {
        method: 'PUT',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name: editingNameValue }),
      });

      const data = await response.json();

      if (data.success) {
        // Update the local state
        setOptimizations(optimizations.map(opt =>
          opt.id === optimizationId
            ? { ...opt, name: editingNameValue }
            : opt
        ));
        setEditingNameId(null);
        setEditingNameValue('');
      } else {
        alert(data.error || 'Failed to update name');
      }
    } catch (error) {
      console.error('Error updating optimization name:', error);
      alert('Failed to update name');
    }
  };

  const handleCancelEdit = () => {
    setEditingNameId(null);
    setEditingNameValue('');
  };

  const handleDeleteOptimization = async (optimization: CachedOptimization) => {
    const confirmMessage = `Are you sure you want to delete "${optimization.name || `Optimization #${optimization.id}`}"? This action cannot be undone.`;

    if (!window.confirm(confirmMessage)) {
      return;
    }

    try {
      const response = await fetch(`/api/cached-results/${optimization.id}`, {
        method: 'DELETE',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (data.success) {
        // Remove the optimization from the local state
        setOptimizations(optimizations.filter(opt => opt.id !== optimization.id));
        setTotalCount(prev => prev - 1);

        // Show success message
        alert('Optimization deleted successfully');
      } else {
        alert(data.error || 'Failed to delete optimization');
      }
    } catch (error) {
      console.error('Error deleting optimization:', error);
      alert('Failed to delete optimization');
    }
  };

  const handleClearAllOptimizations = async () => {
    if (optimizations.length === 0) {
      alert('No optimizations to delete');
      return;
    }

    const confirmMessage = `Are you sure you want to delete ALL ${optimizations.length} optimization results? This action cannot be undone.`;

    if (!window.confirm(confirmMessage)) {
      return;
    }

    try {
      let deletedCount = 0;
      let failedCount = 0;

      // Delete each optimization individually
      for (const optimization of optimizations) {
        try {
          const response = await fetch(`/api/cached-results/${optimization.id}`, {
            method: 'DELETE',
            credentials: 'include',
            headers: {
              'Content-Type': 'application/json',
            },
          });

          const data = await response.json();
          if (data.success) {
            deletedCount++;
          } else {
            failedCount++;
          }
        } catch (error) {
          failedCount++;
        }
      }

      // Refresh the data after bulk delete
      await fetchOptimizations();

      if (failedCount === 0) {
        alert(`Successfully deleted all ${deletedCount} optimization results`);
      } else {
        alert(`Deleted ${deletedCount} optimizations, ${failedCount} failed to delete`);
      }
    } catch (error) {
      console.error('Error during bulk delete:', error);
      alert('Failed to delete optimizations');
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <Typography>Loading optimization history...</Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ padding: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', marginBottom: 3 }}>
        <History sx={{ marginRight: 1, color: theme.palette.primary.main }} />
        <Typography variant="h4" component="h1">
          Optimization History
        </Typography>
        <Box sx={{ marginLeft: 'auto', display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={fetchOptimizations}
          >
            Refresh
          </Button>
          {optimizations.length > 0 && (
            <Button
              variant="outlined"
              color="error"
              startIcon={<Delete />}
              onClick={handleClearAllOptimizations}
            >
              Clear All
            </Button>
          )}
        </Box>
      </Box>

      <Paper sx={{ marginBottom: 3, padding: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Sort By</InputLabel>
            <Select
              value={orderBy}
              label="Sort By"
              onChange={(e) => setOrderBy(e.target.value)}
            >
              <MenuItem value="created_at">Created Date</MenuItem>
              <MenuItem value="portfolio_count">Portfolio Count</MenuItem>
              <MenuItem value="optimal_cagr">CAGR</MenuItem>
              <MenuItem value="optimal_max_drawdown">Max Drawdown</MenuItem>
              <MenuItem value="optimal_return_drawdown_ratio">Return/Drawdown Ratio</MenuItem>
              <MenuItem value="access_count">Access Count</MenuItem>
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Order</InputLabel>
            <Select
              value={orderDirection}
              label="Order"
              onChange={(e) => setOrderDirection(e.target.value)}
            >
              <MenuItem value="desc">Descending</MenuItem>
              <MenuItem value="asc">Ascending</MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Paper>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Portfolio Combination</TableCell>
              <TableCell>Method</TableCell>
              <TableCell align="right">CAGR</TableCell>
              <TableCell align="right">Max Drawdown</TableCell>
              <TableCell align="right">Return/DD Ratio</TableCell>
              <TableCell align="right">Sharpe Ratio</TableCell>
              <TableCell>Optimal Weights</TableCell>
              <TableCell align="right">Execution Time</TableCell>
              <TableCell align="right">Created</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {optimizations.map((opt) => (
              <TableRow key={opt.id} hover>
                <TableCell>
                  {editingNameId === opt.id ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <TextField
                        size="small"
                        value={editingNameValue}
                        onChange={(e) => setEditingNameValue(e.target.value)}
                        variant="outlined"
                        sx={{ minWidth: 200 }}
                        onKeyPress={(e) => {
                          if (e.key === 'Enter') {
                            handleSaveName(opt.id);
                          } else if (e.key === 'Escape') {
                            handleCancelEdit();
                          }
                        }}
                        autoFocus
                      />
                      <IconButton
                        size="small"
                        onClick={() => handleSaveName(opt.id)}
                        color="primary"
                      >
                        <Save />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={handleCancelEdit}
                        color="secondary"
                      >
                        <Cancel />
                      </IconButton>
                    </Box>
                  ) : (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                        {opt.name || `Optimization #${opt.id}`}
                      </Typography>
                      <IconButton
                        size="small"
                        onClick={() => handleEditName(opt)}
                        sx={{ opacity: 0.6, '&:hover': { opacity: 1 } }}
                      >
                        <Edit fontSize="small" />
                      </IconButton>
                    </Box>
                  )}
                </TableCell>
                <TableCell>
                  <Box>
                    <Typography variant="body2" fontWeight="bold">
                      {opt.portfolio_count} Portfolios
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      {opt.portfolio_names.slice(0, 3).join(', ')}
                      {opt.portfolio_names.length > 3 && ` +${opt.portfolio_names.length - 3} more`}
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell>
                  <Chip
                    label={opt.optimization_method.replace('_', ' ')}
                    color={getMethodColor(opt.optimization_method) as any}
                    size="small"
                    variant="outlined"
                  />
                </TableCell>
                <TableCell align="right">
                  <Typography
                    color={opt.metrics.cagr >= 0 ? 'success.main' : 'error.main'}
                    fontWeight="bold"
                  >
                    {formatPercentage(opt.metrics.cagr)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography color="error.main" fontWeight="bold">
                    {formatPercentage(Math.abs(opt.metrics.max_drawdown))}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography fontWeight="bold">
                    {opt.metrics.return_drawdown_ratio.toFixed(2)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography
                    color={opt.metrics.sharpe_ratio >= 0 ? 'success.main' : 'error.main'}
                    fontWeight="bold"
                  >
                    {opt.metrics.sharpe_ratio.toFixed(2)}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {opt.optimal_weights.map((weight, index) => (
                      <Chip
                        key={index}
                        label={`${formatPercentage(weight)}`}
                        size="small"
                        variant="outlined"
                        sx={{ fontSize: '0.7rem' }}
                      />
                    ))}
                  </Box>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="body2">
                    {formatDuration(opt.execution_info.execution_time_seconds)}
                  </Typography>
                  <Typography variant="caption" color="textSecondary">
                    {opt.execution_info.iterations} iterations
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="body2">
                    {new Date(opt.timestamps.created_at).toLocaleDateString()}
                  </Typography>
                  <Typography variant="caption" color="textSecondary">
                    {new Date(opt.timestamps.created_at).toLocaleTimeString()}
                  </Typography>
                </TableCell>
                <TableCell align="center">
                  <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center' }}>
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<Visibility />}
                      onClick={() => handleViewOptimization(opt)}
                      sx={{ minWidth: 'auto' }}
                    >
                      View
                    </Button>
                    <IconButton
                      size="small"
                      onClick={() => handleDeleteOptimization(opt)}
                      color="error"
                      title="Delete optimization"
                    >
                      <Delete fontSize="small" />
                    </IconButton>
                  </Box>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        <TablePagination
          rowsPerPageOptions={[10, 25, 50]}
          component="div"
          count={totalCount}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </TableContainer>

      {optimizations.length === 0 && (
        <Card sx={{ marginTop: 3 }}>
          <CardContent sx={{ textAlign: 'center', padding: 4 }}>
            <Assessment sx={{ fontSize: 48, color: theme.palette.text.secondary, marginBottom: 2 }} />
            <Typography variant="h6" color="textSecondary" gutterBottom>
              No Optimization History Found
            </Typography>
            <Typography variant="body2" color="textSecondary">
              Start optimizing portfolio weights to see your optimization history here.
            </Typography>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default OptimizationHistory;