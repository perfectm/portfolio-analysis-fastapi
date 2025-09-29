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
  Menu,
  MenuItem,
  Avatar,
  IconButton,
} from "@mui/material";
import { Assessment, AccountCircle, ExitToApp } from "@mui/icons-material";
import { ThemeToggle } from "./ThemeToggle";
import { useAuth } from "../contexts/AuthContext";

const Navigation: React.FC = () => {
  const location = useLocation();
  const theme = useTheme();
  const { user, isAuthenticated, logout } = useAuth();
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  const navItems = [
    { path: "/", label: "Home" },
    { path: "/upload", label: "Upload" },
    { path: "/portfolios", label: "Portfolios" },
    { path: "/margin", label: "Margin Management" },
    { path: "/robustness", label: "Robustness" },
    { path: "/profit-optimization", label: "Profit Optimization" },
    { path: "/optimization-history", label: "Optimization History" },
  ];

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    logout();
    handleMenuClose();
  };

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
            <Link
              to="/"
              style={{ textDecoration: "none" }}
            >
              <Typography
                variant="h5"
                sx={{
                  fontWeight: 700,
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
            </Link>
          </Box>

          {/* Navigation Items */}
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            {/* Main Navigation - only show if authenticated */}
            {isAuthenticated && navItems.map((item) => (
              <Link key={item.path} to={item.path} style={{ textDecoration: "none" }}>
                <Button
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
              </Link>
            ))}

            {/* Theme Toggle */}
            <ThemeToggle size="medium" />

            {/* User Menu - only show if authenticated */}
            {isAuthenticated && user && (
              <>
                <IconButton
                  onClick={handleMenuOpen}
                  sx={{
                    ml: 1,
                    color: theme.palette.text.primary,
                  }}
                >
                  <Avatar
                    sx={{
                      width: 32,
                      height: 32,
                      bgcolor: theme.palette.primary.main,
                      fontSize: '0.875rem',
                    }}
                  >
                    {user.username.charAt(0).toUpperCase()}
                  </Avatar>
                </IconButton>
                <Menu
                  anchorEl={anchorEl}
                  open={Boolean(anchorEl)}
                  onClose={handleMenuClose}
                  anchorOrigin={{
                    vertical: 'bottom',
                    horizontal: 'right',
                  }}
                  transformOrigin={{
                    vertical: 'top',
                    horizontal: 'right',
                  }}
                >
                  <MenuItem disabled>
                    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                      <Typography variant="body2" fontWeight={600}>
                        {user.full_name || user.username}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {user.email}
                      </Typography>
                    </Box>
                  </MenuItem>
                  <MenuItem onClick={handleLogout}>
                    <ExitToApp sx={{ mr: 1, fontSize: 20 }} />
                    Logout
                  </MenuItem>
                </Menu>
              </>
            )}
          </Box>
        </Toolbar>
      </Container>
    </AppBar>
  );
};

export default Navigation;
