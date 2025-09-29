# Core correlation calculation function that excludes zeros
def calculate_correlation_excluding_zeros(x, y):
    """
    Calculate Pearson correlation between two arrays, excluding pairs where either value is zero
    
    Args:
        x, y: arrays of equal length containing P&L values
    
    Returns:
        correlation coefficient (float) or None if insufficient data
    """
    # Convert to numpy arrays for easier handling
    import numpy as np
    
    x = np.array(x)
    y = np.array(y)
    
    # Create mask for valid pairs (both non-zero and not NaN)
    valid_mask = (x != 0) & (y != 0) & (~np.isnan(x)) & (~np.isnan(y))
    
    # Filter to only valid pairs
    x_valid = x[valid_mask]
    y_valid = y[valid_mask]
    
    # Need at least 2 data points for correlation
    if len(x_valid) < 2:
        return None
    
    # Calculate correlation manually using Pearson formula
    n = len(x_valid)
    
    # Calculate means
    mean_x = np.mean(x_valid)
    mean_y = np.mean(y_valid)
    
    # Calculate numerator and denominators
    numerator = np.sum((x_valid - mean_x) * (y_valid - mean_y))
    denominator_x = np.sum((x_valid - mean_x) ** 2)
    denominator_y = np.sum((y_valid - mean_y) ** 2)
    
    # Check for zero variance (would cause division by zero)
    if denominator_x == 0 or denominator_y == 0:
        return 0.0
    
    # Calculate correlation
    correlation = numerator / np.sqrt(denominator_x * denominator_y)
    
    return correlation


# Alternative implementation using scipy (simpler but requires scipy)
def calculate_correlation_scipy(x, y):
    """
    Same calculation using scipy.stats.pearsonr
    """
    from scipy.stats import pearsonr
    import numpy as np
    
    x = np.array(x)
    y = np.array(y)
    
    # Filter out zeros and NaN values
    valid_mask = (x != 0) & (y != 0) & (~np.isnan(x)) & (~np.isnan(y))
    x_valid = x[valid_mask]
    y_valid = y[valid_mask]
    
    if len(x_valid) < 2:
        return None
    
    correlation, p_value = pearsonr(x_valid, y_valid)
    return correlation


# Example of how to build the full correlation matrix
def build_correlation_matrix(data_dict):
    """
    Build correlation matrix for multiple strategies
    
    Args:
        data_dict: dictionary where keys are strategy names and values are P&L arrays
    
    Returns:
        2D numpy array with correlation matrix
    """
    import numpy as np
    
    strategy_names = list(data_dict.keys())
    n_strategies = len(strategy_names)
    
    # Initialize correlation matrix
    correlation_matrix = np.zeros((n_strategies, n_strategies))
    
    # Calculate correlations for all pairs
    for i, strategy1 in enumerate(strategy_names):
        for j, strategy2 in enumerate(strategy_names):
            if i == j:
                # Correlation of strategy with itself is always 1
                correlation_matrix[i, j] = 1.0
            else:
                # Calculate correlation between different strategies
                corr = calculate_correlation_excluding_zeros(
                    data_dict[strategy1], 
                    data_dict[strategy2]
                )
                correlation_matrix[i, j] = corr if corr is not None else np.nan
    
    return correlation_matrix, strategy_names


# Example usage with pandas DataFrame
def calculate_from_dataframe(df, strategy_columns):
    """
    Calculate correlation matrix directly from pandas DataFrame
    """
    import numpy as np
    
    n_strategies = len(strategy_columns)
    correlation_matrix = np.zeros((n_strategies, n_strategies))
    
    for i, col1 in enumerate(strategy_columns):
        for j, col2 in enumerate(strategy_columns):
            if i == j:
                correlation_matrix[i, j] = 1.0
            else:
                # Get the data arrays
                x = df[col1].values
                y = df[col2].values
                
                # Calculate correlation excluding zeros
                corr = calculate_correlation_excluding_zeros(x, y)
                correlation_matrix[i, j] = corr if corr is not None else np.nan
    
    return correlation_matrix


# Manual calculation step-by-step (for debugging)
def manual_correlation_step_by_step(x, y, verbose=True):
    """
    Manual correlation calculation with detailed steps for debugging
    """
    import numpy as np
    
    if verbose:
        print(f"Original data lengths: x={len(x)}, y={len(y)}")
    
    # Step 1: Filter out zeros and NaN
    valid_mask = (x != 0) & (y != 0) & (~np.isnan(x)) & (~np.isnan(y))
    x_filtered = x[valid_mask]
    y_filtered = y[valid_mask]
    
    if verbose:
        print(f"After filtering zeros/NaN: {len(x_filtered)} valid pairs")
        print(f"Sample of filtered data:")
        print(f"  x: {x_filtered[:5]}...")
        print(f"  y: {y_filtered[:5]}...")
    
    if len(x_filtered) < 2:
        if verbose:
            print("Insufficient data for correlation")
        return None
    
    # Step 2: Calculate means
    mean_x = np.mean(x_filtered)
    mean_y = np.mean(y_filtered)
    
    if verbose:
        print(f"Means: x={mean_x:.3f}, y={mean_y:.3f}")
    
    # Step 3: Calculate deviations from mean
    dev_x = x_filtered - mean_x
    dev_y = y_filtered - mean_y
    
    # Step 4: Calculate correlation components
    numerator = np.sum(dev_x * dev_y)
    sum_sq_x = np.sum(dev_x ** 2)
    sum_sq_y = np.sum(dev_y ** 2)
    
    if verbose:
        print(f"Numerator (sum of products): {numerator:.3f}")
        print(f"Sum of squares x: {sum_sq_x:.3f}")
        print(f"Sum of squares y: {sum_sq_y:.3f}")
    
    # Step 5: Calculate correlation
    if sum_sq_x == 0 or sum_sq_y == 0:
        if verbose:
            print("Zero variance detected - returning 0")
        return 0.0
    
    correlation = numerator / np.sqrt(sum_sq_x * sum_sq_y)
    
    if verbose:
        print(f"Final correlation: {correlation:.6f}")
    
    return correlation

