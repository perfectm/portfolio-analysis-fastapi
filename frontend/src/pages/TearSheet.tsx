import React, { useState } from "react";
import {
  Container,
  Paper,
  Typography,
  Box,
  Button,
  CircularProgress,
  Alert,
  useTheme,
  Divider,
} from "@mui/material";
import { Upload, Assessment, Download } from "@mui/icons-material";
import { API_BASE_URL, authAPI } from "../services/api";

const TearSheet: React.FC = () => {
  const theme = useTheme();
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tearSheetHtml, setTearSheetHtml] = useState<string | null>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) {
      if (selectedFile.name.endsWith('.csv')) {
        setFile(selectedFile);
        setError(null);
        setTearSheetHtml(null); // Clear previous results
      } else {
        setError('Please select a CSV file');
        setFile(null);
      }
    }
  };

  const handleGenerateTearSheet = async () => {
    if (!file) {
      setError('Please select a CSV file first');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      // Get auth token and add to headers
      const token = authAPI.getToken();
      const headers: HeadersInit = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${API_BASE_URL}/api/tear-sheet/generate`, {
        method: 'POST',
        body: formData,
        headers: headers,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to generate tear sheet');
      }

      const data = await response.json();
      if (data.success && data.html) {
        setTearSheetHtml(data.html);
      } else {
        throw new Error(data.error || 'Failed to generate tear sheet');
      }
    } catch (err: any) {
      console.error('Error generating tear sheet:', err);
      setError(err.message || 'Failed to generate tear sheet');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadHtml = () => {
    if (!tearSheetHtml) return;

    const blob = new Blob([tearSheetHtml], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tear_sheet_${new Date().getTime()}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Box sx={{ mb: 4 }}>
        <Typography
          variant="h3"
          sx={{
            fontWeight: 700,
            mb: 1,
            background: `linear-gradient(135deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
            backgroundClip: "text",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          QuantStats Tear Sheet Generator
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Generate comprehensive performance tear sheets using QuantStats library
        </Typography>
      </Box>

      <Paper
        elevation={3}
        sx={{
          p: 4,
          mb: 3,
          borderRadius: 3,
          background:
            theme.palette.mode === "dark"
              ? "rgba(18, 18, 18, 0.8)"
              : "rgba(255, 255, 255, 0.9)",
        }}
      >
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
            Upload Portfolio CSV
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Upload the CSV file exported from the Portfolios page. The file should contain Date, Net Liquidity, Daily P/L $, Daily P/L %, and Current Drawdown % columns.
          </Typography>

          <input
            accept=".csv"
            style={{ display: "none" }}
            id="csv-file-upload"
            type="file"
            onChange={handleFileSelect}
          />
          <label htmlFor="csv-file-upload">
            <Button
              variant="outlined"
              component="span"
              startIcon={<Upload />}
              sx={{
                mr: 2,
                borderColor: theme.palette.primary.main,
                color: theme.palette.primary.main,
                "&:hover": {
                  borderColor: theme.palette.primary.dark,
                  backgroundColor: theme.palette.action.hover,
                },
              }}
            >
              Select CSV File
            </Button>
          </label>

          {file && (
            <Typography
              variant="body2"
              sx={{
                mt: 2,
                color: theme.palette.success.main,
                display: "inline-flex",
                alignItems: "center",
              }}
            >
              ✓ Selected: {file.name}
            </Typography>
          )}
        </Box>

        <Divider sx={{ my: 3 }} />

        <Box sx={{ display: "flex", gap: 2, alignItems: "center" }}>
          <Button
            variant="contained"
            startIcon={loading ? <CircularProgress size={20} /> : <Assessment />}
            onClick={handleGenerateTearSheet}
            disabled={!file || loading}
            sx={{
              px: 3,
              py: 1.5,
              fontWeight: 600,
              textTransform: "none",
              background: `linear-gradient(135deg, ${theme.palette.primary.main}, ${theme.palette.primary.dark})`,
              "&:hover": {
                background: `linear-gradient(135deg, ${theme.palette.primary.dark}, ${theme.palette.primary.main})`,
              },
            }}
          >
            {loading ? "Generating..." : "Generate Tear Sheet"}
          </Button>

          {tearSheetHtml && (
            <Button
              variant="outlined"
              startIcon={<Download />}
              onClick={handleDownloadHtml}
              sx={{
                px: 3,
                py: 1.5,
                fontWeight: 600,
                textTransform: "none",
              }}
            >
              Download HTML
            </Button>
          )}
        </Box>

        {error && (
          <Alert severity="error" sx={{ mt: 3 }}>
            {error}
          </Alert>
        )}
      </Paper>

      {tearSheetHtml && (
        <Paper
          elevation={3}
          sx={{
            p: 0,
            borderRadius: 3,
            overflow: "hidden",
            background:
              theme.palette.mode === "dark"
                ? "rgba(18, 18, 18, 0.8)"
                : "rgba(255, 255, 255, 0.9)",
          }}
        >
          <Box
            sx={{
              p: 2,
              background:
                theme.palette.mode === "dark"
                  ? "rgba(30, 30, 30, 0.95)"
                  : "rgba(245, 245, 245, 0.95)",
              borderBottom: `1px solid ${theme.palette.divider}`,
            }}
          >
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              Performance Tear Sheet
            </Typography>
          </Box>
          <Box
            sx={{
              width: "100%",
              height: "calc(100vh - 350px)",
              minHeight: "800px",
              overflow: "hidden",
              position: "relative",
            }}
          >
            <iframe
              srcDoc={tearSheetHtml}
              title="Tear Sheet"
              sandbox="allow-same-origin"
              style={{
                border: "none",
                width: "100%",
                height: "100%",
                display: "block",
              }}
            />
          </Box>
        </Paper>
      )}
    </Container>
  );
};

export default TearSheet;
