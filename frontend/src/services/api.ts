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
  console.log(`[API] Making request to: ${API_BASE_URL}${url}`, {
    method: options.method || 'GET',
    headers: options.headers,
    body: options.body ? 'FormData or JSON body present' : 'No body'
  });

  try {
    const response = await fetch(`${API_BASE_URL}${url}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    console.log(`[API] Response from ${url}:`, {
      status: response.status,
      statusText: response.statusText,
      ok: response.ok,
      contentType: response.headers.get('content-type')
    });

    if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
        console.error(`[API] Error response body from ${url}:`, errorData);
      } catch (jsonError) {
        console.error(`[API] Failed to parse error response as JSON from ${url}:`, jsonError);
        errorData = { detail: 'Unknown error - could not parse response' };
      }
      
      const errorMessage = `${response.status}: ${errorData.detail || errorData.message || errorData.error || 'Server error'}`;
      console.error(`[API] Throwing error for ${url}:`, errorMessage);
      throw new Error(errorMessage);
    }

    const result = await response.json();
    console.log(`[API] Success response from ${url}:`, result);
    return result;
  } catch (error) {
    console.error(`[API] Network or other error for ${url}:`, error);
    throw error;
  }
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
    console.log('[API] Starting single file upload:', {
      fileName: file.name,
      fileSize: file.size,
      fileType: file.type
    });

    const formData = new FormData();
    formData.append('files', file);
    
    // Add required form parameters with default values
    formData.append('rf_rate', '0.05');
    formData.append('daily_rf_rate', '0.0001369');
    formData.append('sma_window', '20');
    formData.append('use_trading_filter', 'true');
    formData.append('starting_capital', '100000');
    formData.append('weighting_method', 'equal');

    console.log('[API] Form data prepared for single upload:', {
      fileCount: 1,
      formDataKeys: Array.from(formData.keys()),
      targetUrl: `${API_BASE_URL}/upload`
    });
    
    return fetch(`${API_BASE_URL}/upload`, {
      method: 'POST',
      body: formData,
    }).then(async (response) => {
      console.log('[API] Single upload response received:', {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        contentType: response.headers.get('content-type'),
        url: response.url
      });

      if (!response.ok) {
        let errorData;
        try {
          errorData = await response.json();
          console.error('[API] Single upload error response body:', errorData);
        } catch (jsonError) {
          console.error('[API] Failed to parse single upload error response as JSON:', jsonError);
          errorData = { detail: 'Upload failed - could not parse error response' };
        }
        
        const errorMessage = `${response.status}: ${errorData.detail || 'Upload failed'}`;
        console.error('[API] Single upload throwing error:', errorMessage);
        throw new Error(errorMessage);
      }
      
      // Handle HTML response from /upload endpoint
      const contentType = response.headers.get('content-type');
      console.log('[API] Single upload content type:', contentType);
      
      if (contentType && contentType.includes('text/html')) {
        console.log('[API] Single upload received HTML response, treating as success');
        // If HTML response, assume success and return a basic success response
        return {
          message: "File uploaded successfully",
          portfolio_id: 0
        };
      } else {
        const result = await response.json();
        console.log('[API] Single upload JSON response:', result);
        return result;
      }
    }).catch(error => {
      console.error('[API] Single upload caught error:', error);
      throw error;
    });
  },

  // Upload multiple portfolio CSV files
  uploadMultiplePortfolios: async (files: File[]): Promise<{ message: string; portfolio_ids: number[] }> => {
    console.log('[API] Starting multiple file upload:', {
      fileCount: files.length,
      files: files.map(f => ({ name: f.name, size: f.size, type: f.type }))
    });

    const formData = new FormData();
    files.forEach((file, index) => {
      console.log(`[API] Adding file ${index + 1}/${files.length} to FormData:`, file.name);
      formData.append('files', file);
    });
    
    // Add required form parameters with default values
    const params = {
      rf_rate: '0.05',
      daily_rf_rate: '0.0001369',
      sma_window: '20',
      use_trading_filter: 'true',
      starting_capital: '100000',
      weighting_method: 'equal'
    };

    Object.entries(params).forEach(([key, value]) => {
      formData.append(key, value);
    });

    console.log('[API] Form data prepared for multiple upload:', {
      fileCount: files.length,
      formDataKeys: Array.from(formData.keys()),
      parameters: params
    });
    
    // Try /api/upload first, fallback to /upload if that fails
    let url = `${API_BASE_URL}/api/upload`;
    
    try {
      console.log('[API] Attempting primary upload to:', url);
      
      const response = await fetch(url, {
        method: 'POST',
        body: formData,
      });
      
      console.log('[API] Primary upload response:', {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        contentType: response.headers.get('content-type'),
        url: response.url
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('[API] Primary upload failed with response:', errorText);
        throw new Error(`${response.status}: API upload failed - ${errorText}`);
      }
      
      const result = await response.json();
      console.log('[API] Primary upload successful:', result);
      return result;
      
    } catch (apiError) {
      // Fallback to /upload endpoint
      console.log('[API] Primary upload failed, trying fallback endpoint. Error was:', apiError);
      url = `${API_BASE_URL}/upload`;
      
      console.log('[API] Attempting fallback upload to:', url);
      
      try {
        const response = await fetch(url, {
          method: 'POST',
          body: formData,
        });
        
        console.log('[API] Fallback upload response:', {
          status: response.status,
          statusText: response.statusText,
          ok: response.ok,
          contentType: response.headers.get('content-type'),
          url: response.url
        });
        
        if (!response.ok) {
          let errorData;
          try {
            errorData = await response.json();
            console.error('[API] Fallback upload error response body:', errorData);
          } catch (jsonError) {
            const errorText = await response.text();
            console.error('[API] Fallback upload error response text:', errorText);
            errorData = { detail: `Upload failed - ${errorText || 'Unknown error'}` };
          }
          
          const errorMessage = `${response.status}: ${errorData.detail || errorData.error || 'Upload failed'}`;
          console.error('[API] Fallback upload throwing error:', errorMessage);
          throw new Error(errorMessage);
        }
        
        // The /upload endpoint returns HTML, so we need to handle that differently
        const contentType = response.headers.get('content-type');
        console.log('[API] Fallback upload content type:', contentType);
        
        if (contentType && contentType.includes('text/html')) {
          console.log('[API] Fallback upload received HTML response, treating as success');
          // If HTML response, assume success and return a basic success response
          return {
            message: "Files uploaded successfully",
            portfolio_ids: []
          };
        } else {
          const result = await response.json();
          console.log('[API] Fallback upload JSON response:', result);
          return result;
        }
      } catch (fallbackError) {
        console.error('[API] Fallback upload also failed:', fallbackError);
        throw new Error(`Both upload endpoints failed. Primary: ${apiError.message}, Fallback: ${fallbackError.message}`);
      }
    }
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
