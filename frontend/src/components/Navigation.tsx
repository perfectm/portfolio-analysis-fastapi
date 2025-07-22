import React from "react";
import { Link, useLocation } from "react-router-dom";
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Container,
  useTheme,
} from "@mui/material";
import { Assessment } from "@mui/icons-material";
import { ThemeToggle } from "./ThemeToggle";

const Navigation: React.FC = () => {
  const location = useLocation();
  const theme = useTheme();

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  const navItems = [
    { path: "/", label: "Home" },
    { path: "/upload", label: "Upload" },
    { path: "/portfolios", label: "Portfolios" },
  ];

  return (
    <AppBar
      position="sticky"
      elevation={2}
      sx={{
        backgroundColor:
          theme.palette.mode === "dark"
            ? "rgba(18, 18, 18, 0.95)"
            : "rgba(255, 255, 255, 0.95)",
        backdropFilter: "blur(10px)",
        borderBottom: `1px solid ${theme.palette.divider}`,
      }}
    >
      <Container maxWidth="xl">
        <Toolbar sx={{ justifyContent: "space-between", py: 1 }}>
          {/* Brand/Logo */}
          <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
            <Assessment
              sx={{
                fontSize: 32,
                color: theme.palette.primary.main,
              }}
            />
            <Typography
              variant="h5"
              component={Link}
              to="/"
              sx={{
                fontWeight: 700,
                textDecoration: "none",
                color: theme.palette.text.primary,
                background: `linear-gradient(135deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                backgroundClip: "text",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                "&:hover": {
                  opacity: 0.8,
                },
              }}
            >
              Portfolio Analysis
            </Typography>
          </Box>

          {/* Navigation Items */}
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            {navItems.map((item) => (
              <Button
                key={item.path}
                component={Link}
                to={item.path}
                variant={isActive(item.path) ? "contained" : "text"}
                sx={{
                  minWidth: "auto",
                  px: 2,
                  py: 1,
                  borderRadius: 2,
                  fontWeight: 600,
                  textTransform: "none",
                  ...(isActive(item.path)
                    ? {
                        background: `linear-gradient(135deg, ${theme.palette.primary.main}, ${theme.palette.primary.dark})`,
                        boxShadow: theme.shadows[3],
                        "&:hover": {
                          background: `linear-gradient(135deg, ${theme.palette.primary.dark}, ${theme.palette.primary.main})`,
                          boxShadow: theme.shadows[6],
                        },
                      }
                    : {
                        color: theme.palette.text.primary,
                        "&:hover": {
                          backgroundColor: theme.palette.action.hover,
                          borderRadius: 2,
                        },
                      }),
                }}
              >
                {item.label}
              </Button>
            ))}

            {/* Theme Toggle */}
            <ThemeToggle size="medium" />
          </Box>
        </Toolbar>
      </Container>
    </AppBar>
  );
};

export default Navigation;
