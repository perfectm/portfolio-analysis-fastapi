import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Alert,
  CircularProgress,
} from '@mui/material';
import { api } from '../services/api';

const RegimeAnalysisSimple: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentRegime, setCurrentRegime] = useState<any>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        console.log('Fetching current regime...');
        const response = await api.get('/api/regime/current');
        console.log('Current regime response:', response);
        setCurrentRegime(response.data);
      } catch (err: any) {
        console.error('Failed to fetch current regime:', err);
        setError(`Failed to load data: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <Container>
        <Box display="flex" alignItems="center" justifyContent="center" minHeight="400px">
          <CircularProgress />
          <Typography variant="body1" sx={{ ml: 2 }}>
            Loading...
          </Typography>
        </Box>
      </Container>
    );
  }

  if (error) {
    return (
      <Container>
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 3, minHeight: '100vh', bgcolor: 'background.default' }}>
      <Box sx={{ py: 3 }}>
        <Typography variant="h4" gutterBottom color="text.primary">
          Market Regime Analysis (Simple)
        </Typography>
        
        {currentRegime ? (
          <Box>
            <Typography variant="h6">
              Current Regime: {currentRegime.regime?.toUpperCase() || 'Unknown'}
            </Typography>
            <Typography variant="body1">
              Confidence: {currentRegime.confidence ? (currentRegime.confidence * 100).toFixed(1) : '0'}%
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              {currentRegime.description || 'No description available'}
            </Typography>
            <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
              <Typography variant="body2">
                Raw API Response:
              </Typography>
              <pre style={{ fontSize: '12px', overflow: 'auto' }}>
                {JSON.stringify(currentRegime, null, 2)}
              </pre>
            </Box>
          </Box>
        ) : (
          <Alert severity="info">
            No regime data available
          </Alert>
        )}
      </Box>
    </Container>
  );
};

export default RegimeAnalysisSimple;