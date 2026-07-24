import React from "react";
import { Box } from "@mui/material";

/**
 * Live vs Backtest performance dashboard.
 *
 * The dashboard itself is a self-contained page served at
 * /comparison-dashboard.html (see frontend/public/). It fetches its data from
 * GET /api/comparison/dashboard-data and does all metric/drift math client-side
 * so the capital slider and bot->strategy mapping overrides stay adjustable.
 *
 * We embed it in an iframe so its styling stays fully isolated from the app's
 * Material-UI theme (its own light/dark handling), with zero CSS/JS collisions.
 */
const LiveDashboard: React.FC = () => {
  return (
    <Box sx={{ width: "100%", height: "calc(100vh - 64px)" }}>
      <iframe
        src="/comparison-dashboard.html"
        title="Live vs Backtest Performance Dashboard"
        style={{ border: 0, width: "100%", height: "100%", display: "block" }}
      />
    </Box>
  );
};

export default LiveDashboard;
