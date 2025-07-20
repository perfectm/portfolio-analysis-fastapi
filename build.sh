#!/bin/bash

# Build script for Render deployment
echo "Starting build process..."

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Check if frontend directory exists
if [ -d "frontend" ]; then
    # Navigate to frontend directory and build React app
    echo "Building React frontend..."
    cd frontend
    
    # Install dependencies
    echo "Installing frontend dependencies..."
    npm ci
    
    # Build the React app
    echo "Building React application..."
    npm run build
    
    cd ..
    echo "React build completed successfully!"
else
    echo "Frontend directory not found, skipping React build..."
fi

# Create uploads directory if it doesn't exist
mkdir -p uploads/plots

echo "Build completed successfully!"
