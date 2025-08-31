import React from 'react';
import { Box, Typography, Card, CardContent } from '@mui/material';
import { Assessment } from '@mui/icons-material';

const MarginTest: React.FC = () => {
  return (
    <Box sx={{ p: 3, maxWidth: 1200, margin: '0 auto' }}>
      <Typography variant="h4" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Assessment />
        Margin Management Test Page
      </Typography>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Test Page Loaded Successfully
          </Typography>
          <Typography variant="body1">
            This is a simplified test version of the Margin Management page.
            If you can see this, the routing is working correctly.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
};

export default MarginTest;