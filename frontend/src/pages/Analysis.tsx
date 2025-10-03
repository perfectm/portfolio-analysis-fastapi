import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { portfolioAPI } from "../services/api";

interface MetricCardProps {
  title: string;
  value: string | number;
  format?: "currency" | "percentage" | "number" | "date";
  color?: "teal" | "red" | "gray" | "blue" | "green" | "orange";
}

const MetricCard: React.FC<MetricCardProps> = ({ title, value, format = "number", color = "gray" }) => {
  const formatValue = (val: string | number, fmt: string) => {
    if (val === null || val === undefined || val === "N/A") return "N/A";
    
    const numVal = typeof val === 'string' ? parseFloat(val) : val;
    if (isNaN(numVal)) return String(val);

    switch (fmt) {
      case "currency":
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          minimumFractionDigits: 0,
          maximumFractionDigits: 0
        }).format(numVal);
      case "percentage":
        return `${(numVal * 100).toFixed(1)}%`;
      case "date":
        return new Date(val).toLocaleDateString();
      default:
        return typeof numVal === 'number' ? numVal.toLocaleString() : String(val);
    }
  };

  const getCardColor = (colorName: string) => {
    const colors = {
      teal: "linear-gradient(135deg, #14b8a6, #0f766e)",
      red: "linear-gradient(135deg, #ef4444, #dc2626)",
      gray: "linear-gradient(135deg, #6b7280, #4b5563)",
      blue: "linear-gradient(135deg, #3b82f6, #1d4ed8)",
      green: "linear-gradient(135deg, #10b981, #059669)",
      orange: "linear-gradient(135deg, #f97316, #ea580c)"
    };
    return colors[colorName as keyof typeof colors] || colors.gray;
  };

  return (
    <div
      style={{
        background: getCardColor(color),
        borderRadius: "12px",
        padding: "24px",
        color: "white",
        minWidth: "160px",
        boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)"
      }}
    >
      <div
        style={{
          fontSize: "0.875rem",
          opacity: 0.9,
          marginBottom: "8px",
          fontWeight: "500"
        }}
      >
        {title}
      </div>
      <div
        style={{
          fontSize: "1.5rem",
          fontWeight: "700",
          lineHeight: "1.2"
        }}
      >
        {formatValue(value, format)}
      </div>
    </div>
  );
};

export default function Analysis() {
  const { id } = useParams<{ id: string }>();
  const [analysisData, setAnalysisData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      fetchAnalysis(parseInt(id));
    }
  }, [id]);

  const fetchAnalysis = async (portfolioId: number) => {
    try {
      setLoading(true);
      const response = await portfolioAPI.getAnalysis(portfolioId);
      setAnalysisData(response);
    } catch (err) {
      setError("Failed to fetch analysis data");
      console.error("Error fetching analysis:", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="loading">Loading analysis...</div>;
  if (error) return <div className="error">Error: {error}</div>;
  if (!analysisData) return <div className="error">No analysis data found</div>;

  // Get the latest analysis result
  const latestResult = analysisData.analysis_results?.[0];
  const metrics = latestResult?.metrics;
  const strategy = analysisData.strategy;

  if (!metrics) {
    return (
      <div className="analysis-page">
        <h1>Portfolio Analysis</h1>
        <div className="no-analysis">
          <p>No analysis results found for this portfolio.</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: "2rem", backgroundColor: "#0f172a", minHeight: "100vh", color: "white" }}>
      {/* Header */}
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "2rem", fontWeight: "700", margin: "0 0 0.5rem 0" }}>
          {strategy?.name || "Portfolio Analysis"}
        </h1>
        <p style={{ color: "#94a3b8", margin: 0 }}>
          File: {strategy?.filename || "Unknown"}
        </p>
      </div>

      {/* Date Range Card */}
      <div style={{ marginBottom: "2rem" }}>
        <div
          style={{
            background: "linear-gradient(135deg, #1e293b, #334155)",
            borderRadius: "12px",
            padding: "20px",
            display: "inline-block",
            boxShadow: "0 4px 12px rgba(0, 0, 0, 0.25)"
          }}
        >
          <div style={{ fontSize: "0.875rem", opacity: 0.8, marginBottom: "4px" }}>
            Dates:
          </div>
          <div style={{ fontSize: "0.875rem", fontWeight: "500" }}>
            {metrics.analysis_start_date && metrics.analysis_end_date ? (
              <>
                from: {new Date(metrics.analysis_start_date).toLocaleDateString()}<br />
                to: {new Date(metrics.analysis_end_date).toLocaleDateString()}
              </>
            ) : (
              "Date range not available"
            )}
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "1.5rem",
          marginBottom: "2rem"
        }}
      >
        {/* Primary Metrics from Screenshot */}
        <MetricCard
          title="P/L"
          value={metrics.total_pl || 0}
          format="currency"
          color="teal"
        />
        <MetricCard
          title="CAGR"
          value={metrics.cagr || 0}
          format="percentage"
          color="teal"
        />
        <MetricCard
          title="Max Drawdown"
          value={Math.abs(metrics.max_drawdown_percent || 0)}
          format="percentage"
          color="red"
        />
        <MetricCard
          title="MAR Ratio"
          value={metrics.mar_ratio || 0}
          format="number"
          color="teal"
        />
        
        {/* Additional Metrics */}
        <MetricCard
          title="Total Premium"
          value={metrics.total_premium || 0}
          format="currency"
          color="blue"
        />
        <MetricCard
          title="PCR"
          value={metrics.pcr || 0}
          format="percentage"
          color="orange"
        />
        <MetricCard
          title="Starting Capital"
          value={1000000}
          format="currency"
          color="gray"
        />
        <MetricCard
          title="Ending Capital"
          value={metrics.final_account_value || 0}
          format="currency"
          color="gray"
        />

        {/* Extended Metrics */}
        <MetricCard
          title="Sharpe Ratio"
          value={metrics.sharpe_ratio || 0}
          format="number"
          color="blue"
        />
        <MetricCard
          title="Sortino Ratio"
          value={metrics.sortino_ratio || 0}
          format="number"
          color="blue"
        />
        <MetricCard
          title="Annual Volatility"
          value={metrics.annual_volatility || 0}
          format="percentage"
          color="orange"
        />
        <MetricCard
          title="Total Return"
          value={metrics.total_return || 0}
          format="percentage"
          color="green"
        />
        <MetricCard
          title="Ulcer Index"
          value={metrics.ulcer_index || 0}
          format="number"
          color="orange"
        />
        <MetricCard
          title="UPI"
          value={metrics.upi || 0}
          format="number"
          color="blue"
        />
        <MetricCard
          title="Kelly Criterion"
          value={metrics.kelly_criterion || 0}
          format="percentage"
          color={metrics.kelly_criterion > 0 ? "green" : "red"}
        />
        <MetricCard
          title="Max Drawdown Date"
          value={metrics.max_drawdown_date || "N/A"}
          format="date"
          color="gray"
        />

        {/* Beta Metrics - Portfolio vs S&P 500 */}
        <MetricCard
          title="Beta (vs SPX)"
          value={metrics.beta || 0}
          format="number"
          color={metrics.beta > 1 ? "red" : metrics.beta > 0.5 ? "orange" : "green"}
        />
        <MetricCard
          title="Alpha"
          value={metrics.alpha || 0}
          format="percentage"
          color={metrics.alpha > 0 ? "green" : "red"}
        />
        <MetricCard
          title="R-Squared"
          value={metrics.r_squared || 0}
          format="percentage"
          color="blue"
        />

        {/* CVaR (Conditional Value at Risk) */}
        <MetricCard
          title="CVaR (5%)"
          value={metrics.cvar !== undefined && metrics.cvar !== null ? metrics.cvar : "N/A"}
          format="currency"
          color="red"
        />
      </div>

      {/* Analysis Details */}
      <div
        style={{
          background: "linear-gradient(135deg, #1e293b, #334155)",
          borderRadius: "12px",
          padding: "1.5rem",
          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.25)"
        }}
      >
        <h3 style={{ margin: "0 0 1rem 0", fontSize: "1.25rem" }}>Analysis Details</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: "1rem" }}>
          <div>
            <strong>Analysis Type:</strong> {latestResult.analysis_type}
          </div>
          <div>
            <strong>Created:</strong> {new Date(latestResult.created_at).toLocaleString()}
          </div>
          <div>
            <strong>Risk-Free Rate:</strong> {((latestResult.parameters?.rf_rate || 0) * 100).toFixed(2)}%
          </div>
          <div>
            <strong>SMA Window:</strong> {latestResult.parameters?.sma_window || "N/A"} days
          </div>
        </div>
      </div>
    </div>
  );
}
