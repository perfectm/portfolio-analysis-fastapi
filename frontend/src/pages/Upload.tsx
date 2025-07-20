import React, { useState } from 'react';
import { portfolioAPI } from '../services/api';
import './Upload.css';

const Upload: React.FC = () => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string>('');
  const [messageType, setMessageType] = useState<'success' | 'error' | ''>('');

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    if (files.length > 0) {
      const csvFiles = files.filter(file => 
        file.type === 'text/csv' || file.name.endsWith('.csv')
      );
      
      if (csvFiles.length !== files.length) {
        setMessage('Only CSV files are allowed. Non-CSV files have been removed.');
        setMessageType('error');
      } else {
        setMessage('');
      }
      
      setSelectedFiles(csvFiles);
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles(files => files.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      setMessage('Please select at least one CSV file');
      setMessageType('error');
      return;
    }

    setUploading(true);
    setMessage('');

    try {
      if (selectedFiles.length === 1) {
        // Single file upload
        const result = await portfolioAPI.uploadPortfolio(selectedFiles[0]);
        setMessage(`Upload successful! Portfolio ID: ${result.portfolio_id}`);
        setMessageType('success');
      } else {
        // Multiple file upload
        const result = await portfolioAPI.uploadMultiplePortfolios(selectedFiles);
        setMessage(`Upload successful! Uploaded ${selectedFiles.length} portfolios.`);
        setMessageType('success');
      }
      
      setSelectedFiles([]);
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
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) {
      const csvFiles = files.filter(file => 
        file.type === 'text/csv' || file.name.endsWith('.csv')
      );
      
      if (csvFiles.length !== files.length) {
        setMessage('Only CSV files are allowed. Non-CSV files have been removed.');
        setMessageType('error');
      } else {
        setMessage('');
      }
      
      setSelectedFiles(prev => [...prev, ...csvFiles]);
    }
  };

  return (
    <div className="upload">
      <div className="upload-container">
        <h1>Upload Portfolio CSV Files</h1>
        <p className="upload-description">
          Upload one or more trading portfolio CSV files to get detailed analytics and insights.
          Multiple files will be analyzed individually and can be blended together for comparison.
        </p>

        <div 
          className={`upload-area ${selectedFiles.length > 0 ? 'has-file' : ''}`}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <div className="upload-content">
            <div className="upload-icon">📁</div>
            {selectedFiles.length > 0 ? (
              <div className="files-info">
                <h3>Selected Files ({selectedFiles.length}):</h3>
                <div className="files-list">
                  {selectedFiles.map((file, index) => (
                    <div key={index} className="file-item">
                      <div className="file-details">
                        <p className="file-name">{file.name}</p>
                        <p className="file-size">Size: {(file.size / 1024).toFixed(2)} KB</p>
                      </div>
                      <button 
                        type="button"
                        onClick={() => removeFile(index)}
                        className="remove-file-btn"
                        title="Remove file"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="upload-text">
                <h3>Drag and drop your CSV files here</h3>
                <p>or click to select files (multiple selection supported)</p>
              </div>
            )}
            <input
              id="file-input"
              type="file"
              accept=".csv"
              multiple
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
            disabled={selectedFiles.length === 0 || uploading}
            className={`btn btn-primary ${uploading ? 'loading' : ''}`}
          >
            {uploading ? 'Uploading...' : 
             selectedFiles.length === 1 ? 'Upload Portfolio' : 
             `Upload ${selectedFiles.length} Portfolios`}
          </button>
        </div>

        <div className="upload-info">
          <h3>CSV Format Requirements:</h3>
          <ul>
            <li>Files must be in CSV format (.csv)</li>
            <li>Should contain trading data with columns for dates, trades, P&L, etc.</li>
            <li>Maximum file size per file: 10MB</li>
            <li>Multiple files will be analyzed individually and can be blended for comparison</li>
            <li>Ensure data is properly formatted for accurate analysis</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default Upload;
