// API client for Portfolio Analysis FastAPI backend
// Note: axios will be installed when npm issues are resolved
// For now, we'll use fetch API as fallback

// API Configuration - handles both development and production environments
const getApiBaseUrl = () => {
  // 1. Environment variable override (highest priority)
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  
  // 2. Development mode
  if (import.meta.env.DEV) {
    return 'http://localhost:8000';
  }
  
  // 3. Production mode - check common deployment patterns
  const { protocol, hostname, port } = window.location;
  
  // If running on a specific port, try common API ports
  if (port && port !== '80' && port !== '443') {
    // Try the same host with common API ports
    const commonApiPorts = ['8000', '8001', '3001', '5000'];
    // For now, return the same origin - this can be customized per deployment
    return `${protocol}//${hostname}${port ? `:${port}` : ''}`;
  }
  
  // Default: same origin (works for most production deployments)
  return window.location.origin;
};

const API_BASE_URL = getApiBaseUrl();

console.log('[API Config] Using API_BASE_URL:', API_BASE_URL);
console.log('[API Config] Current hostname:', window.location.hostname);
console.log('[API Config] Current origin:', window.location.origin);
console.log('[API Config] Dev mode:', import.meta.env.DEV);
console.log('[API Config] VITE_API_URL:', import.meta.env.VITE_API_URL);

// Export the API base URL for use in other components
export { API_BASE_URL };

// Authentication types
export interface AuthUser {
  id: number;
  username: string;
  email: string;
  full_name?: string;
  is_active: boolean;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

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

// New interfaces for enhanced upload responses
export interface AdvancedPlots {
  correlation_heatmap?: string;
  monte_carlo_simulation?: string;
}

export interface UploadAnalysisResult {
  filename: string;
  metrics: {
    sharpe_ratio: number;
    total_return: number;
    total_pl: number;
    final_account_value: number;
    max_drawdown: number;
    max_drawdown_percent: number;
    cagr: number;
    annual_volatility: number;
    [key: string]: any;
  };
  plots: Array<{
    filename: string;
    url: string;
  }>;
}

export interface UploadResponse {
  success: boolean;
  message: string;
  portfolio_id?: number;
  portfolio_ids?: number[];
  individual_results?: UploadAnalysisResult[];
  blended_result?: UploadAnalysisResult | null;
  multiple_portfolios?: boolean;
  advanced_plots?: AdvancedPlots;
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

// Authentication helper functions
const getAuthToken = (): string | null => {
  return localStorage.getItem('auth_token');
};

const setAuthToken = (token: string): void => {
  localStorage.setItem('auth_token', token);
};

const clearAuthToken = (): void => {
  localStorage.removeItem('auth_token');
};

const getAuthHeaders = (): HeadersInit => {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
};

// Authentication API methods
export const authAPI = {
  // Register new user
  register: async (userData: RegisterRequest): Promise<AuthUser> => {
    return apiCall('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  },

  // Login user
  login: async (credentials: LoginRequest): Promise<AuthToken> => {
    const response = await apiCall('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
    
    // Store token in localStorage
    if (response.access_token) {
      setAuthToken(response.access_token);
    }
    
    return response;
  },

  // Get current user
  getCurrentUser: async (): Promise<AuthUser> => {
    return apiCall('/api/auth/me', {
      headers: getAuthHeaders(),
    });
  },

  // Logout user
  logout: async (): Promise<void> => {
    try {
      await apiCall('/api/auth/logout', {
        method: 'POST',
        headers: getAuthHeaders(),
      });
    } finally {
      // Always clear local token regardless of server response
      clearAuthToken();
    }
  },

  // Check if user is authenticated
  isAuthenticated: (): boolean => {
    return !!getAuthToken();
  },

  // Get stored auth token
  getToken: getAuthToken,

  // Clear stored auth token
  clearToken: clearAuthToken,
};

// API service methods
export const portfolioAPI = {
  // Get all portfolios/strategies
  getPortfolios: async (): Promise<PortfoliosResponse> => {
    return apiCall('/api/portfolios');
  },

  // Get strategies list (lightweight)
  getStrategiesList: async (): Promise<any> => {
    return apiCall('/api/strategies/list', { headers: getAuthHeaders() });
  },

  // Upload a new portfolio CSV file
  uploadPortfolio: async (file: File): Promise<UploadResponse> => {
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
    formData.append('starting_capital', '1000000');
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
          success: true,
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
  uploadMultiplePortfolios: async (files: File[]): Promise<UploadResponse> => {
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
      starting_capital: '1000000',
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
            success: true,
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
    return apiCall(`/api/strategies/${portfolioId}/analysis`);
  },

  // Delete a portfolio
  deletePortfolio: async (portfolioId: number): Promise<any> => {
    return apiCall(`/api/portfolio/${portfolioId}`, { method: 'DELETE' });
  },

  // Update portfolio name
  updatePortfolioName: async (portfolioId: number, newName: string): Promise<{ success: boolean; message?: string; error?: string; portfolio_id?: number; old_name?: string; new_name?: string }> => {
    return apiCall(`/api/portfolio/${portfolioId}/name`, {
      method: 'PUT',
      body: JSON.stringify({ name: newName }),
    });
  },

  // Update portfolio strategy
  updatePortfolioStrategy: async (portfolioId: number, newStrategy: string): Promise<{ success: boolean; message?: string; error?: string; portfolio_id?: number; old_strategy?: string; new_strategy?: string }> => {
    return apiCall(`/api/portfolio/${portfolioId}/strategy`, {
      method: 'PUT',
      body: JSON.stringify({ strategy: newStrategy }),
    });
  },

  // Health check
  healthCheck: async (): Promise<{ status: string }> => {
    return apiCall('/');
  },

  // Analyze multiple portfolios with advanced plots
  analyzePortfolios: async (portfolioIds: number[]): Promise<UploadResponse> => {
    return apiCall('/api/analyze-portfolios', {
      method: 'POST',
      body: JSON.stringify({ portfolio_ids: portfolioIds }),
    });
  },

  // Optimize portfolio weights for target profit
  optimizeForProfit: async (portfolioIds: number[], targetAnnualProfit: number): Promise<any> => {
    return apiCall('/api/profit-optimization/optimize', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ 
        portfolio_ids: portfolioIds,
        target_annual_profit: targetAnnualProfit 
      }),
    });
  },
};

// Margin API methods
const marginAPI = {
  // Bulk upload margin files
  bulkUploadMargin: async (
    files: FileList, 
    startingCapital: number = 1000000, 
    maxMarginPercent: number = 0.85
  ): Promise<any> => {
    const formData = new FormData();
    
    Array.from(files).forEach((file) => {
      formData.append('files', file);
    });
    
    formData.append('starting_capital', startingCapital.toString());
    formData.append('max_margin_percent', maxMarginPercent.toString());

    return fetch(`${API_BASE_URL}/api/margin/bulk-upload`, {
      method: 'POST',
      body: formData,
      headers: {
        ...getAuthHeaders(),
        // Don't set Content-Type for FormData - browser will set it automatically
      },
    }).then(async (response) => {
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      return response.json();
    });
  },

  // Get margin summary
  getMarginSummary: async (): Promise<any> => {
    return apiCall('/api/margin/summary', {
      headers: getAuthHeaders(),
    });
  },

  // Get daily margin aggregates
  getDailyMarginAggregates: async (limit: number = 100, validOnly: boolean = false): Promise<any> => {
    const params = new URLSearchParams({ 
      limit: limit.toString(),
      valid_only: validOnly.toString()
    });
    return apiCall(`/api/margin/daily-aggregates?${params}`, {
      headers: getAuthHeaders(),
    });
  },

  // Get margin data for specific portfolio
  getPortfolioMarginData: async (portfolioId: number, limit: number = 1000): Promise<any> => {
    const params = new URLSearchParams({ limit: limit.toString() });
    return apiCall(`/api/margin/portfolio/${portfolioId}?${params}`, {
      headers: getAuthHeaders(),
    });
  },

  // Get supported margin file formats
  getSupportedFormats: async (): Promise<any> => {
    return apiCall('/api/margin/supported-formats', {
      headers: getAuthHeaders(),
    });
  },

  // Recalculate margin aggregates
  recalculateMarginAggregates: async (
    startingCapital: number = 1000000, 
    maxMarginPercent: number = 0.85
  ): Promise<any> => {
    const formData = new FormData();
    formData.append('starting_capital', startingCapital.toString());
    formData.append('max_margin_percent', maxMarginPercent.toString());

    return fetch(`${API_BASE_URL}/api/margin/recalculate-aggregates`, {
      method: 'POST',
      body: formData,
      headers: {
        ...getAuthHeaders(),
        // Don't set Content-Type for FormData - browser will set it automatically
      },
    }).then(async (response) => {
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      return response.json();
    });
  },
  // Get strategies margin overview
  getStrategiesOverview: async (): Promise<any> => {
    return apiCall('/api/margin/strategies-overview', {
      headers: getAuthHeaders(),
    });
  },
};

// Create a unified API object that includes both generic methods and portfolio-specific methods
export const api = {
  // Generic HTTP methods with auth support
  get: <T = any>(url: string): Promise<{ data: T }> => 
    apiCall(url, { headers: getAuthHeaders() }).then(data => ({ data })),
  
  post: <T = any>(url: string, data?: any): Promise<{ data: T }> => 
    apiCall(url, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
      headers: getAuthHeaders(),
    }).then(response => ({ data: response })),
  
  put: <T = any>(url: string, data?: any): Promise<{ data: T }> => 
    apiCall(url, {
      method: 'PUT', 
      body: data ? JSON.stringify(data) : undefined,
      headers: getAuthHeaders(),
    }).then(response => ({ data: response })),
  
  delete: <T = any>(url: string): Promise<{ data: T }> => 
    apiCall(url, { 
      method: 'DELETE',
      headers: getAuthHeaders() 
    }).then(data => ({ data })),

  // Authentication methods
  auth: authAPI,

  // Portfolio-specific methods (for backward compatibility)
  ...portfolioAPI,

  // Margin-specific methods
  margin: marginAPI,
};
