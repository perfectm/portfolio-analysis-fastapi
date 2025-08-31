#!/bin/bash

# Portfolio Analysis Web App - Installation Script
# Usage: ./install.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Installing Portfolio Analysis Web App Dependencies${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo -e "${RED}❌ Python is not installed. Please install Python 3.8+ first.${NC}"
    exit 1
fi

# Use python3 if available, otherwise python
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
echo -e "${BLUE}🐍 Using Python ${PYTHON_VERSION}${NC}"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed. Please install Node.js 16+ first.${NC}"
    exit 1
fi

NODE_VERSION=$(node --version)
echo -e "${BLUE}📦 Using Node.js ${NODE_VERSION}${NC}"

# Install backend dependencies
echo -e "${BLUE}📥 Installing backend dependencies...${NC}"
if command -v pip3 &> /dev/null; then
    pip3 install -r requirements.txt
elif command -v pip &> /dev/null; then
    pip install -r requirements.txt
else
    echo -e "${RED}❌ pip is not installed. Please install pip first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Backend dependencies installed${NC}"

# Install frontend dependencies
echo -e "${BLUE}📥 Installing frontend dependencies...${NC}"
cd frontend

if [ -f "package-lock.json" ]; then
    npm ci
else
    npm install
fi

cd ..
echo -e "${GREEN}✅ Frontend dependencies installed${NC}"

# Create required directories
echo -e "${BLUE}📁 Creating required directories...${NC}"
mkdir -p uploads/plots
mkdir -p frontend/dist/assets

# Initialize database
echo -e "${BLUE}🗄️  Initializing database...${NC}"
$PYTHON_CMD init_db.py

echo -e "${GREEN}🎉 Installation completed successfully!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo -e "${GREEN}  1. Start the application: ./start.sh${NC}"
echo -e "${GREEN}  2. Visit: http://localhost:5173 (dev) or http://localhost:8000 (prod)${NC}"
echo ""
echo -e "${YELLOW}Available commands:${NC}"
echo -e "${YELLOW}  ./start.sh         - Start development servers${NC}"
echo -e "${YELLOW}  ./start.sh prod    - Start production server${NC}"
echo -e "${YELLOW}  ./stop.sh          - Stop all servers${NC}"