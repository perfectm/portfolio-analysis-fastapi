import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
import {
  createTheme,
  Theme,
  ThemeProvider as MuiThemeProvider,
} from "@mui/material/styles";
import { CssBaseline } from "@mui/material";

// Define theme modes
export type ThemeMode = "light" | "dark";

// Theme context interface
interface ThemeContextType {
  mode: ThemeMode;
  toggleTheme: () => void;
  theme: Theme;
}

// Create the context
const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

// Custom hook to use theme context
export const useTheme = (): ThemeContextType => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
};

// Theme configuration
const createAppTheme = (mode: ThemeMode): Theme => {
  return createTheme({
    palette: {
      mode,
      ...(mode === "light"
        ? {
            // Light mode colors
            primary: {
              main: "#1976d2",
              light: "#42a5f5",
              dark: "#1565c0",
            },
            secondary: {
              main: "#dc004e",
              light: "#ff5983",
              dark: "#9a0036",
            },
            background: {
              default: "#fafafa",
              paper: "#ffffff",
            },
            success: {
              main: "#2e7d32",
              light: "#4caf50",
              dark: "#1b5e20",
            },
            error: {
              main: "#d32f2f",
              light: "#ef5350",
              dark: "#c62828",
            },
            warning: {
              main: "#ed6c02",
              light: "#ff9800",
              dark: "#e65100",
            },
          }
        : {
            // Dark mode colors
            primary: {
              main: "#90caf9",
              light: "#e3f2fd",
              dark: "#42a5f5",
            },
            secondary: {
              main: "#f48fb1",
              light: "#fce4ec",
              dark: "#e91e63",
            },
            background: {
              default: "#121212",
              paper: "#1e1e1e",
            },
            success: {
              main: "#66bb6a",
              light: "#81c784",
              dark: "#4caf50",
            },
            error: {
              main: "#f44336",
              light: "#ef5350",
              dark: "#d32f2f",
            },
            warning: {
              main: "#ffa726",
              light: "#ffb74d",
              dark: "#f57c00",
            },
          }),
    },
    typography: {
      fontFamily: [
        "-apple-system",
        "BlinkMacSystemFont",
        '"Segoe UI"',
        "Roboto",
        '"Helvetica Neue"',
        "Arial",
        "sans-serif",
        '"Apple Color Emoji"',
        '"Segoe UI Emoji"',
        '"Segoe UI Symbol"',
      ].join(","),
      h1: {
        fontWeight: 600,
        fontSize: "2.5rem",
      },
      h2: {
        fontWeight: 600,
        fontSize: "2rem",
      },
      h3: {
        fontWeight: 600,
        fontSize: "1.75rem",
      },
      h4: {
        fontWeight: 600,
        fontSize: "1.5rem",
      },
      h5: {
        fontWeight: 600,
        fontSize: "1.25rem",
      },
      h6: {
        fontWeight: 600,
        fontSize: "1rem",
      },
    },
    components: {
      // Custom component styling
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: 12,
            boxShadow:
              mode === "dark"
                ? "0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)"
                : "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: 8,
            textTransform: "none",
            fontWeight: 600,
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
    breakpoints: {
      values: {
        xs: 0,
        sm: 600,
        md: 960,
        lg: 1280,
        xl: 1920,
      },
    },
  });
};

// Theme Provider Props
interface ThemeProviderProps {
  children: ReactNode;
}

// Theme Provider Component
export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  // Get initial theme from localStorage or default to light
  const getInitialTheme = (): ThemeMode => {
    if (typeof window !== "undefined") {
      const savedTheme = localStorage.getItem("portfolio-theme");
      if (savedTheme === "light" || savedTheme === "dark") {
        return savedTheme;
      }
      // Check system preference
      if (
        window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches
      ) {
        return "dark";
      }
    }
    return "light";
  };

  const [mode, setMode] = useState<ThemeMode>(getInitialTheme);
  const theme = createAppTheme(mode);

  // Toggle theme function
  const toggleTheme = () => {
    const newMode: ThemeMode = mode === "light" ? "dark" : "light";
    setMode(newMode);
    localStorage.setItem("portfolio-theme", newMode);
  };

  // Listen for system theme changes
  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia) {
      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      const handleChange = (e: MediaQueryListEvent) => {
        const savedTheme = localStorage.getItem("portfolio-theme");
        if (!savedTheme) {
          setMode(e.matches ? "dark" : "light");
        }
      };

      mediaQuery.addEventListener("change", handleChange);
      return () => mediaQuery.removeEventListener("change", handleChange);
    }
  }, []);

  const contextValue: ThemeContextType = {
    mode,
    toggleTheme,
    theme,
  };

  return (
    <ThemeContext.Provider value={contextValue}>
      <MuiThemeProvider theme={theme}>
        <>
          <CssBaseline />
          {children}
        </>
      </MuiThemeProvider>
    </ThemeContext.Provider>
  );
};
