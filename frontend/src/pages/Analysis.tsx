import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { portfolioAPI } from "../services/api";

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

  return (
    <div className="analysis-page">
      <h1>Portfolio Analysis</h1>

      <div className="portfolio-info">
        <h2>{analysisData.portfolio?.name || "Unknown Portfolio"}</h2>
        <p>
          <strong>File:</strong> {analysisData.portfolio?.filename || "Unknown"}
        </p>
      </div>

      {!analysisData.analysis_results ||
      analysisData.analysis_results.length === 0 ? (
        <div className="no-analysis">
          <p>No analysis results found for this portfolio.</p>
        </div>
      ) : (
        <div className="analysis-results">
          {analysisData.analysis_results.map((result: any, index: number) => (
            <div key={result.id || index} className="analysis-result">
              <h3>Analysis #{index + 1}</h3>
              <p>
                <strong>Type:</strong> {result.analysis_type}
              </p>
              <p>
                <strong>Created:</strong>{" "}
                {new Date(result.created_at).toLocaleString()}
              </p>

              {result.metrics && (
                <div className="metrics">
                  <h4>Metrics</h4>
                  <div className="metrics-grid">
                    {Object.entries(result.metrics).map(([key, value]) => (
                      <div key={key} className="metric">
                        <span className="metric-label">{key}:</span>
                        <span className="metric-value">{String(value)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {result.plots && result.plots.length > 0 && (
                <div className="plots">
                  <h4>Charts</h4>
                  <div className="plots-grid">
                    {result.plots.map((plot: any, plotIndex: number) => (
                      <div key={plotIndex} className="plot">
                        <p>
                          <strong>{plot.plot_type}</strong>
                        </p>
                        <a
                          href={plot.file_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          View Chart
                        </a>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
