import { createTheme } from '@mui/material/styles';
import { PaletteMode } from '@mui/material';

// Portfolio analysis theme colors
const getDesignTokens = (mode: PaletteMode) => ({
  palette: {
    mode,
    ...(mode === 'light'
      ? {
          // Light mode colors
          primary: {
            main: '#3498db',
            light: '#5dade2',
            dark: '#2980b9',
            contrastText: '#ffffff',
          },
          secondary: {
            main: '#2c3e50',
            light: '#34495e',
            dark: '#1b2631',
            contrastText: '#ffffff',
          },
          background: {
            default: '#ffffff',
            paper: '#f8f9fa',
          },
          text: {
            primary: '#213547',
            secondary: '#495057',
          },
          success: {
            main: '#28a745',
            light: '#d4edda',
            dark: '#155724',
          },
          error: {
            main: '#dc3545',
            light: '#f8d7da',
            dark: '#721c24',
          },
          warning: {
            main: '#ffc107',
            light: '#fff3cd',
            dark: '#856404',
          },
          info: {
            main: '#007bff',
            light: '#d1ecf1',
            dark: '#0c5460',
          },
        }
      : {
          // Dark mode colors
          primary: {
            main: '#646cff',
            light: '#747bff',
            dark: '#535bf2',
            contrastText: '#ffffff',
          },
          secondary: {
            main: '#f0f0f0',
            light: '#ffffff',
            dark: '#cccccc',
            contrastText: '#213547',
          },
          background: {
            default: '#242424',
            paper: '#1a1a1a',
          },
          text: {
            primary: 'rgba(255, 255, 255, 0.87)',
            secondary: 'rgba(255, 255, 255, 0.6)',
          },
          success: {
            main: '#4caf50',
            light: '#81c784',
            dark: '#388e3c',
          },
          error: {
            main: '#f44336',
            light: '#e57373',
            dark: '#d32f2f',
          },
          warning: {
            main: '#ff9800',
            light: '#ffb74d',
            dark: '#f57c00',
          },
          info: {
            main: '#2196f3',
            light: '#64b5f6',
            dark: '#1976d2',
          },
        }),
  },
  typography: {
    fontFamily: 'system-ui, Avenir, Helvetica, Arial, sans-serif',
    h1: {
      fontSize: '3.2rem',
      fontWeight: 700,
      lineHeight: 1.1,
    },
    h2: {
      fontSize: '2.5rem',
      fontWeight: 600,
    },
    h3: {
      fontSize: '2rem',
      fontWeight: 600,
    },
    h4: {
      fontSize: '1.5rem',
      fontWeight: 600,
    },
    h5: {
      fontSize: '1.25rem',
      fontWeight: 600,
    },
    h6: {
      fontSize: '1.1rem',
      fontWeight: 600,
    },
    body1: {
      fontSize: '1rem',
      lineHeight: 1.6,
    },
    body2: {
      fontSize: '0.875rem',
      lineHeight: 1.5,
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          textTransform: 'none' as const,
          fontWeight: 500,
          transition: 'all 0.3s ease',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid',
          borderBottomColor: mode === 'light' ? '#dee2e6' : 'rgba(255, 255, 255, 0.12)',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 6,
        },
      },
    },
  },
});

export const createPortfolioTheme = (mode: PaletteMode) =>
  createTheme(getDesignTokens(mode));

// Default themes
export const lightTheme = createPortfolioTheme('light');
export const darkTheme = createPortfolioTheme('dark');