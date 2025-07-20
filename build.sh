#!/bin/bash

# Build script for Render deployment
echo "Starting build process..."

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Navigate to frontend directory and build React app
echo "Building React frontend..."
cd frontend
npm ci
npm run build
cd ..

echo "Build completed successfully!"
