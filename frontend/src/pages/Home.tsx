import React from "react";
import { Link as RouterLink } from "react-router-dom";
import {
  Container,
  Typography,
  Box,
  Button,
  Grid,
  Card,
  CardContent,
  Chip,
  useTheme,
  alpha,
} from "@mui/material";
import {
  Assessment,
  CloudUpload,
  Visibility,
  TrendingUp,
  BarChart,
  FolderOpen,
  Security,
} from "@mui/icons-material";

const Home: React.FC = () => {
  const theme = useTheme();

  const features = [
    {
      icon: <Assessment sx={{ fontSize: 40 }} />,
      title: "Performance Analytics",
      description:
        "Comprehensive analysis including P&L, win rates, Sharpe ratios, Sortino ratios, and Kelly Criterion.",
      color: theme.palette.primary.main,
    },
    {
      icon: <TrendingUp sx={{ fontSize: 40 }} />,
      title: "Advanced Visualizations",
      description:
        "Interactive charts, correlation heatmaps, and Monte Carlo simulations for deep insights.",
      color: theme.palette.success.main,
    },
    {
      icon: <FolderOpen sx={{ fontSize: 40 }} />,
      title: "Portfolio Management",
      description:
        "Upload, manage, and compare multiple portfolios with weighted blending capabilities.",
      color: theme.palette.warning.main,
    },
    {
      icon: <Security sx={{ fontSize: 40 }} />,
      title: "Risk Analysis",
      description:
        "Detailed risk metrics including Ulcer Index, UPI, maximum drawdown, and volatility analysis.",
      color: theme.palette.error.main,
    },
  ];

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Hero Section */}
      <Box
        sx={{
          textAlign: "center",
          py: 8,
          background: `linear-gradient(135deg, ${alpha(
            theme.palette.primary.main,
            0.1
          )}, ${alpha(theme.palette.secondary.main, 0.1)})`,
          borderRadius: 4,
          mb: 6,
          position: "relative",
          overflow: "hidden",
          "&::before": {
            content: '""',
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background:
              theme.palette.mode === "dark"
                ? "radial-gradient(circle at 50% 50%, rgba(144, 202, 249, 0.1) 0%, transparent 70%)"
                : "radial-gradient(circle at 50% 50%, rgba(25, 118, 210, 0.1) 0%, transparent 70%)",
            zIndex: 0,
          },
        }}
      >
        <Box sx={{ position: "relative", zIndex: 1 }}>
          <Typography
            variant="h1"
            sx={{
              fontWeight: 800,
              background: `linear-gradient(135deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
              backgroundClip: "text",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              mb: 2,
              fontSize: { xs: "2.5rem", sm: "3rem", md: "4rem" },
            }}
          >
            Portfolio Analysis Dashboard
          </Typography>

          <Typography
            variant="h5"
            sx={{
              color: theme.palette.text.secondary,
              mb: 4,
              maxWidth: 800,
              mx: "auto",
              fontWeight: 400,
              lineHeight: 1.6,
            }}
          >
            Analyze your trading portfolios with comprehensive metrics, advanced
            visualizations, and AI-powered insights. Upload your CSV files and
            get institutional-grade analytics.
          </Typography>

          <Box
            sx={{
              display: "flex",
              gap: 2,
              justifyContent: "center",
              flexWrap: "wrap",
            }}
          >
            <RouterLink to="/upload" style={{ textDecoration: "none" }}>
              <Button
                variant="contained"
                size="large"
                startIcon={<CloudUpload />}
                sx={{
                  py: 1.5,
                  px: 4,
                  borderRadius: 3,
                  fontWeight: 600,
                  fontSize: "1.1rem",
                  background: `linear-gradient(135deg, ${theme.palette.primary.main}, ${theme.palette.primary.dark})`,
                  boxShadow: theme.shadows[4],
                  "&:hover": {
                    background: `linear-gradient(135deg, ${theme.palette.primary.dark}, ${theme.palette.primary.main})`,
                    boxShadow: theme.shadows[8],
                    transform: "translateY(-2px)",
                  },
                  transition: "all 0.2s ease-in-out",
                }}
              >
                Upload Portfolio
              </Button>
            </RouterLink>

            <RouterLink to="/portfolios" style={{ textDecoration: "none" }}>
              <Button
                variant="outlined"
                size="large"
                startIcon={<Visibility />}
                sx={{
                  py: 1.5,
                  px: 4,
                  borderRadius: 3,
                  fontWeight: 600,
                  fontSize: "1.1rem",
                  borderWidth: 2,
                  "&:hover": {
                    borderWidth: 2,
                    transform: "translateY(-2px)",
                    boxShadow: theme.shadows[4],
                  },
                  transition: "all 0.2s ease-in-out",
                }}
              >
                View Portfolios
              </Button>
            </RouterLink>
          </Box>

          {/* Metrics Chips */}
          <Box
            sx={{
              mt: 4,
              display: "flex",
              gap: 1,
              justifyContent: "center",
              flexWrap: "wrap",
            }}
          >
            {[
              "Sharpe Ratio",
              "Kelly Criterion",
              "UPI",
              "Monte Carlo",
              "Risk Analysis",
            ].map((metric) => (
              <Chip
                key={metric}
                label={metric}
                variant="outlined"
                sx={{
                  fontWeight: 600,
                  borderRadius: 2,
                  "&:hover": {
                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                  },
                }}
              />
            ))}
          </Box>
        </Box>
      </Box>

      {/* Features Section */}
      <Box sx={{ mb: 6 }}>
        <Typography
          variant="h2"
          sx={{
            textAlign: "center",
            mb: 6,
            fontWeight: 700,
            color: theme.palette.text.primary,
          }}
        >
          Powerful Features
        </Typography>

        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: {
              xs: "1fr",
              sm: "repeat(2, 1fr)",
              md: "repeat(4, 1fr)",
            },
            gap: 3,
          }}
        >
          {features.map((feature, index) => (
            <Card
              key={index}
              sx={{
                height: "100%",
                transition: "all 0.3s ease-in-out",
                cursor: "pointer",
                border: `1px solid ${theme.palette.divider}`,
                "&:hover": {
                  transform: "translateY(-8px)",
                  boxShadow: theme.shadows[12],
                  border: `1px solid ${feature.color}`,
                },
              }}
            >
              <CardContent sx={{ p: 3, textAlign: "center" }}>
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "center",
                    mb: 2,
                    color: feature.color,
                  }}
                >
                  {feature.icon}
                </Box>

                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 600,
                    mb: 2,
                    color: theme.palette.text.primary,
                  }}
                >
                  {feature.title}
                </Typography>

                <Typography
                  variant="body2"
                  sx={{
                    color: theme.palette.text.secondary,
                    lineHeight: 1.6,
                  }}
                >
                  {feature.description}
                </Typography>
              </CardContent>
            </Card>
          ))}
        </Box>
      </Box>
    </Container>
  );
};

export default Home;
