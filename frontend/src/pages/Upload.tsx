import React, { useState } from 'react';
import { portfolioAPI } from '../services/api';
import './Upload.css';

const Upload: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string>('');
  const [messageType, setMessageType] = useState<'success' | 'error' | ''>('');

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      if (file.type === 'text/csv' || file.name.endsWith('.csv')) {
        setSelectedFile(file);
        setMessage('');
      } else {
        setMessage('Please select a CSV file');
        setMessageType('error');
        setSelectedFile(null);
      }
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setMessage('Please select a file first');
      setMessageType('error');
      return;
    }

    setUploading(true);
    setMessage('');

    try {
      const result = await portfolioAPI.uploadPortfolio(selectedFile);
      setMessage(`Upload successful! Portfolio ID: ${result.portfolio_id}`);
      setMessageType('success');
      setSelectedFile(null);
      // Reset file input
      const fileInput = document.getElementById('file-input') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
    } catch (error) {
      setMessage(`Upload failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setMessageType('error');
    } finally {
      setUploading(false);
    }
  };

  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault();
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    const files = event.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      if (file.type === 'text/csv' || file.name.endsWith('.csv')) {
        setSelectedFile(file);
        setMessage('');
      } else {
        setMessage('Please select a CSV file');
        setMessageType('error');
      }
    }
  };

  return (
    <div className="upload">
      <div className="upload-container">
        <h1>Upload Portfolio CSV</h1>
        <p className="upload-description">
          Upload your trading portfolio CSV file to get detailed analytics and insights.
        </p>

        <div 
          className={`upload-area ${selectedFile ? 'has-file' : ''}`}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <div className="upload-content">
            <div className="upload-icon">📁</div>
            {selectedFile ? (
              <div className="file-info">
                <h3>Selected File:</h3>
                <p>{selectedFile.name}</p>
                <p>Size: {(selectedFile.size / 1024).toFixed(2)} KB</p>
              </div>
            ) : (
              <div className="upload-text">
                <h3>Drag and drop your CSV file here</h3>
                <p>or click to select a file</p>
              </div>
            )}
            <input
              id="file-input"
              type="file"
              accept=".csv"
              onChange={handleFileSelect}
              className="file-input"
            />
          </div>
        </div>

        {message && (
          <div className={`message ${messageType}`}>
            {message}
          </div>
        )}

        <div className="upload-actions">
          <button
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
            className={`btn btn-primary ${uploading ? 'loading' : ''}`}
          >
            {uploading ? 'Uploading...' : 'Upload Portfolio'}
          </button>
        </div>

        <div className="upload-info">
          <h3>CSV Format Requirements:</h3>
          <ul>
            <li>File must be in CSV format (.csv)</li>
            <li>Should contain trading data with columns for dates, trades, P&L, etc.</li>
            <li>Maximum file size: 10MB</li>
            <li>Ensure data is properly formatted for accurate analysis</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default Upload;
