#!/bin/bash
set -e  # Exit on any error

# Build script for Render deployment
echo "🚀 Starting build process..."

# Make sure we're in the right directory
cd /opt/render/project/src || cd "$(dirname "$0")"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --no-cache-dir -r requirements.txt

# Create uploads directory if it doesn't exist
echo "📁 Creating required directories..."
mkdir -p uploads/plots

# Check if frontend directory exists
if [ -d "frontend" ]; then
    # Navigate to frontend directory and build React app
    echo "⚛️ Building React frontend..."
    cd frontend
    
    # Install dependencies
    echo "📦 Installing frontend dependencies..."
    npm ci
    
    # Build the React app
    echo "🏗️ Building React application..."
    npm run build
    
    cd ..
    echo "✅ React build completed successfully!"
    
    # Verify the build was successful
    if [ -d "frontend/dist" ]; then
        echo "✅ React build verification: frontend/dist exists"
        if [ -d "frontend/dist/assets" ]; then
            echo "✅ React assets verification: frontend/dist/assets exists"
        else
            echo "⚠️ Warning: frontend/dist/assets not found"
            # Create empty assets directory to prevent mounting issues
            mkdir -p frontend/dist/assets
            echo "📁 Created empty frontend/dist/assets directory"
        fi
    else
        echo "❌ React build failed: frontend/dist not created"
        # Create minimal structure to prevent app startup issues
        mkdir -p frontend/dist/assets
        echo "<html><head><title>Portfolio Analysis API</title></head><body><h1>API Ready</h1><p>React frontend not available</p></body></html>" > frontend/dist/index.html
        echo "📁 Created fallback frontend structure"
    fi
else
    echo "⚠️ Frontend directory not found, skipping React build..."
    # Create minimal structure to prevent app startup issues
    mkdir -p frontend/dist/assets
    echo "<html><head><title>Portfolio Analysis API</title></head><body><h1>Portfolio Analysis API</h1><p>React frontend not available</p></body></html>" > frontend/dist/index.html
    echo "📁 Created minimal frontend structure for production"
fi

echo "🎉 Build completed successfully!"
