import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "./contexts/ThemeContext";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import Navigation from "./components/Navigation";
import { AuthPage } from "./components/AuthPage";
import Home from "./pages/Home";
import Upload from "./pages/Upload";
import Portfolios from "./pages/Portfolios";
import Analysis from "./pages/Analysis";
import MarginManagement from "./pages/MarginManagement";
import MarginTest from "./pages/MarginTest";
import RegimeAnalysisFixed from "./pages/RegimeAnalysisFixed";
import { CircularProgress, Box } from "@mui/material";
import "./App.css";

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
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/portfolios" element={<Portfolios />} />
          <Route path="/analysis/:id" element={<Analysis />} />
          <Route path="/margin" element={<MarginManagement />} />
          <Route path="/regime" element={<RegimeAnalysisFixed />} />
        </Routes>
      </main>
    </div>
  );
};

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <Router>
          <AppContent />
        </Router>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
