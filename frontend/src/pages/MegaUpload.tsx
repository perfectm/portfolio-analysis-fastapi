import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { portfolioAPI, MegaUploadResponse } from "../services/api";
import "./Upload.css";

const MegaUpload: React.FC = () => {
  const navigate = useNavigate();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [startingCapital, setStartingCapital] = useState<string>("1000000");
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [messageType, setMessageType] = useState<"success" | "error" | "">("");
  const [result, setResult] = useState<MegaUploadResponse | null>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    if (files.length > 0) {
      const file = files[0];
      if (file.type === "text/csv" || file.name.endsWith(".csv")) {
        setSelectedFile(file);
        setMessage("");
        setMessageType("");
      } else {
        setMessage("Only CSV files are allowed.");
        setMessageType("error");
        setSelectedFile(null);
      }
    }
  };

  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault();
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) {
      const file = files[0];
      if (file.type === "text/csv" || file.name.endsWith(".csv")) {
        setSelectedFile(file);
        setMessage("");
        setMessageType("");
      } else {
        setMessage("Only CSV files are allowed.");
        setMessageType("error");
      }
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setMessage("Please select a CSV file");
      setMessageType("error");
      return;
    }

    const capital = parseFloat(startingCapital);
    if (isNaN(capital) || capital <= 0) {
      setMessage("Please enter a valid starting capital");
      setMessageType("error");
      return;
    }

    setUploading(true);
    setMessage("");
    setResult(null);

    try {
      const response = await portfolioAPI.megaUpload(selectedFile, capital);

      if (response.success) {
        const createdCount = response.created?.length || 0;
        const updatedCount = response.updated?.length || 0;
        const errorCount = response.errors?.length || 0;
        setMessage(
          `Successfully processed ${response.total_positions} portfolios: ${createdCount} created, ${updatedCount} updated` +
          (errorCount > 0 ? `, ${errorCount} errors` : "")
        );
        setMessageType("success");
        setResult(response);
        setSelectedFile(null);
        const fileInput = document.getElementById("mega-file-input") as HTMLInputElement;
        if (fileInput) fileInput.value = "";
      } else {
        setMessage(response.error || "Upload failed");
        setMessageType("error");
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      setMessage(`Upload failed: ${errorMessage}`);
      setMessageType("error");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="upload">
      <div className="upload-container">
        <h1>Mega Upload</h1>
        <p className="upload-description">
          Upload a single CSV file containing multiple portfolios. A "Position
          Name" column determines which portfolio each row belongs to. Each
          unique value becomes a separate portfolio saved to the database.
        </p>

        <div
          className={`upload-area ${selectedFile ? "has-file" : ""}`}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <div className="upload-content">
            <div className="upload-icon">📁</div>
            {selectedFile ? (
              <div className="files-info">
                <h3>Selected File:</h3>
                <div className="files-list">
                  <div className="file-item">
                    <div className="file-details">
                      <p className="file-name">{selectedFile.name}</p>
                      <p className="file-size">
                        Size: {(selectedFile.size / 1024).toFixed(2)} KB
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedFile(null);
                        const fileInput = document.getElementById("mega-file-input") as HTMLInputElement;
                        if (fileInput) fileInput.value = "";
                      }}
                      className="remove-file-btn"
                      title="Remove file"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="upload-text">
                <h3>Drag and drop your CSV file here</h3>
                <p>or click to select a file with a "Position Name" column</p>
              </div>
            )}
            <input
              id="mega-file-input"
              type="file"
              accept=".csv"
              onChange={handleFileSelect}
              className="file-input"
            />
          </div>
        </div>

        <div style={{ margin: "16px 0" }}>
          <label htmlFor="starting-capital" style={{ display: "block", marginBottom: "4px", fontWeight: 600 }}>
            Starting Capital ($):
          </label>
          <input
            id="starting-capital"
            type="number"
            value={startingCapital}
            onChange={(e) => setStartingCapital(e.target.value)}
            style={{
              padding: "8px 12px",
              borderRadius: "6px",
              border: "1px solid #ccc",
              fontSize: "14px",
              width: "200px",
            }}
          />
        </div>

        {message && <div className={`message ${messageType}`}>{message}</div>}

        {result && result.success && (
          <div className="analysis-results">
            <h2>Results</h2>

            {result.created && result.created.length > 0 && (
              <div style={{ marginBottom: "12px" }}>
                <h3>Created ({result.created.length}):</h3>
                <ul>
                  {result.created.map((p) => (
                    <li key={p.id}>
                      {p.name} (ID: {p.id})
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.updated && result.updated.length > 0 && (
              <div style={{ marginBottom: "12px" }}>
                <h3>Updated ({result.updated.length}):</h3>
                <ul>
                  {result.updated.map((p) => (
                    <li key={p.id}>
                      {p.name} (ID: {p.id})
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.errors && result.errors.length > 0 && (
              <div style={{ marginBottom: "12px" }}>
                <h3 style={{ color: "#d32f2f" }}>Errors ({result.errors.length}):</h3>
                <ul>
                  {result.errors.map((e, i) => (
                    <li key={i} style={{ color: "#d32f2f" }}>
                      {e.name}: {e.error}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="results-actions">
              <button
                onClick={() => navigate("/portfolios")}
                className="btn btn-primary"
              >
                Go to Portfolios
              </button>
            </div>
          </div>
        )}

        <div className="upload-actions">
          <button
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
            className={`btn btn-primary ${uploading ? "loading" : ""}`}
          >
            {uploading ? "Processing..." : "Upload & Split Portfolios"}
          </button>
        </div>

        <div className="upload-info">
          <h3>CSV Format Requirements:</h3>
          <ul>
            <li>File must be in CSV format (.csv)</li>
            <li>
              Must contain a <strong>"Position Name"</strong> column — each
              unique value becomes a separate portfolio
            </li>
            <li>Must also contain Date and P/L columns (standard format)</li>
            <li>
              Re-uploading will update existing portfolios with matching names
              (not duplicate them)
            </li>
            <li>Each portfolio's strategy field will be set to its Position Name</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default MegaUpload;
