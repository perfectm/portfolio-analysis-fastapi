// API client for Portfolio Analysis FastAPI backend
// Note: axios will be installed when npm issues are resolved
// For now, we'll use fetch API as fallback

// API base URL - will be configured for both development and production
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Types for API responses
export interface Portfolio {
  id: number;
  name: string;
  filename: string;
  upload_date: string;
  processed_data?: any;
}

export interface PortfoliosResponse {
  portfolios: Portfolio[];
  total_count: number;
}

export interface AnalysisResponse {
  portfolio_id: number;
  portfolio_name: string;
  summary: {
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    win_rate: number;
    total_pnl: number;
    max_drawdown: number;
    sharpe_ratio: number;
  };
  monthly_pnl: Array<{
    month: string;
    pnl: number;
  }>;
  trade_distribution: Array<{
    range: string;
    count: number;
  }>;
}

// Fetch wrapper with error handling
const apiCall = async (url: string, options: RequestInit = {}): Promise<any> => {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(`${response.status}: ${errorData.detail || errorData.message || 'Server error'}`);
  }

  return response.json();
};

// API service methods
export const portfolioAPI = {
  // Get all portfolios/strategies
  getPortfolios: async (): Promise<PortfoliosResponse> => {
    return apiCall('/api/portfolios');
  },

  // Get strategies list (lightweight)
  getStrategiesList: async (): Promise<any> => {
    return apiCall('/api/strategies/list');
  },

  // Upload a new portfolio CSV file
  uploadPortfolio: async (file: File): Promise<{ message: string; portfolio_id: number }> => {
    const formData = new FormData();
    formData.append('file', file);
    
    return fetch(`${API_BASE_URL}/api/upload`, {
      method: 'POST',
      body: formData,
    }).then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(`${response.status}: ${errorData.detail || 'Upload failed'}`);
      }
      return response.json();
    });
  },

  // Upload multiple portfolio CSV files
  uploadMultiplePortfolios: async (files: File[]): Promise<{ message: string; portfolio_ids: number[] }> => {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });
    
    return fetch(`${API_BASE_URL}/api/upload`, {
      method: 'POST',
      body: formData,
    }).then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(`${response.status}: ${errorData.detail || errorData.error || 'Upload failed'}`);
      }
      return response.json();
    });
  },

  // Get analysis for a specific portfolio
  getAnalysis: async (portfolioId: number): Promise<AnalysisResponse> => {
    return apiCall(`/api/analysis/${portfolioId}`);
  },

  // Delete a portfolio
  deletePortfolio: async (portfolioId: number): Promise<any> => {
    return apiCall(`/api/portfolio/${portfolioId}`, { method: 'DELETE' });
  },

  // Update portfolio name
  updatePortfolioName: async (portfolioId: number, newName: string): Promise<{ message: string }> => {
    return apiCall(`/api/portfolio/${portfolioId}/name`, {
      method: 'PUT',
      body: JSON.stringify({ new_name: newName }),
    });
  },

  // Health check
  healthCheck: async (): Promise<{ status: string }> => {
    return apiCall('/');
  },
};
