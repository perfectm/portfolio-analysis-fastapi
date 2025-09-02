import React, { Suspense, Component, ErrorInfo, ReactNode } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "./contexts/ThemeContext";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import Navigation from "./components/Navigation";
import { AuthPage } from "./components/AuthPage";
import { CircularProgress, Box, Typography } from "@mui/material";
import "./App.css";

// Re-enable lazy loading with fixed vite.config.ts (no manual page chunking conflicts)
const Home = React.lazy(() => import("./pages/Home"));
const Upload = React.lazy(() => import("./pages/Upload"));
const Portfolios = React.lazy(() => import("./pages/Portfolios"));
const Analysis = React.lazy(() => import("./pages/Analysis"));
const MarginManagement = React.lazy(() => import("./pages/MarginManagement"));
const RegimeAnalysisFixed = React.lazy(() => import("./pages/RegimeAnalysisFixed"));

// Loading component for lazy-loaded pages
const PageLoader: React.FC = () => (
  <Box
    display="flex"
    justifyContent="center"
    alignItems="center"
    minHeight="200px"
  >
    <CircularProgress size={40} />
  </Box>
);

// Simple error boundary for catching chunk loading errors
class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): { hasError: boolean } {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return <div>Something went wrong. Please refresh the page.</div>;
    }

    return this.props.children;
  }
}

// Main app content that handles authentication
const AppContent: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="100vh"
      >
        <CircularProgress />
      </Box>
    );
  }

  if (!isAuthenticated) {
    return <AuthPage />;
  }

  return (
    <div className="App">
      <Navigation />
      <main className="main-content">
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/upload" element={<Upload />} />
            <Route path="/portfolios" element={<Portfolios />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/margin" element={<MarginManagement />} />
            <Route path="/regime" element={<RegimeAnalysisFixed />} />
            <Route path="*" element={<Home />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  );
};

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <Router>
            <AppContent />
          </Router>
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
