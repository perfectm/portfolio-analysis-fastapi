#!/bin/bash

# Portfolio Analysis Web App - Start Script
# Usage: ./start.sh [dev|prod]

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default mode
MODE=${1:-dev}

echo -e "${BLUE}🚀 Starting Portfolio Analysis Web App${NC}"
echo -e "${BLUE}Mode: ${MODE}${NC}"

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Port $port is already in use${NC}"
        echo -e "${YELLOW}   Use ./stop.sh to stop existing services${NC}"
        return 1
    fi
    return 0
}

# Function to wait for service
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}⏳ Waiting for $service_name to start...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s $url >/dev/null 2>&1; then
            echo -e "${GREEN}✅ $service_name is ready!${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    echo -e "${RED}❌ $service_name failed to start within 60 seconds${NC}"
    return 1
}

if [ "$MODE" = "dev" ]; then
    echo -e "${BLUE}📦 Development Mode${NC}"
    
    # Check if backend port is available
    if ! check_port 8000; then
        exit 1
    fi
    
    # Check if frontend port is available  
    if ! check_port 5173; then
        exit 1
    fi
    
    # Ensure required directories exist
    mkdir -p uploads/plots
    mkdir -p frontend/dist/assets
    
    echo -e "${BLUE}📦 Checking dependencies...${NC}"
    
    # Quick dependency check - only warn if missing
    if ! python -c "import fastapi, uvicorn, pandas" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Backend dependencies may be missing. Run: pip install -r requirements.txt${NC}"
    fi
    
    if [ ! -d "frontend/node_modules" ]; then
        echo -e "${YELLOW}⚠️  Frontend dependencies missing. Run: cd frontend && npm ci${NC}"
    fi
    
    # Start backend in background
    echo -e "${BLUE}🚀 Starting FastAPI backend on port 8000...${NC}"
    uvicorn app:app --reload --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > .backend.pid
    
    # Wait for backend to start
    if ! wait_for_service "http://0.0.0.0:8000/api/debug/database" "Backend API"; then
        kill $BACKEND_PID 2>/dev/null || true
        rm -f .backend.pid
        exit 1
    fi
    
    # Start frontend in background
    echo -e "${BLUE}🚀 Starting React frontend on port 5173...${NC}"
    cd frontend
    npm run dev > ../frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > ../.frontend.pid
    cd ..
    
    # Wait for frontend to start
    if ! wait_for_service "http://0.0.0.0:5173" "Frontend Dev Server"; then
        kill $FRONTEND_PID 2>/dev/null || true
        kill $BACKEND_PID 2>/dev/null || true
        rm -f .frontend.pid .backend.pid
        exit 1
    fi
    
    echo -e "${GREEN}🎉 Development servers started successfully!${NC}"
    echo -e "${GREEN}   Backend API: http://0.0.0.0:8000${NC}"
    echo -e "${GREEN}   Frontend: http://0.0.0.0:5173${NC}"
    echo -e "${GREEN}   API Docs: http://0.0.0.0:8000/docs${NC}"
    echo -e "${YELLOW}   Logs: backend.log, frontend.log${NC}"
    echo -e "${YELLOW}   Stop with: ./stop.sh${NC}"

elif [ "$MODE" = "prod" ]; then
    echo -e "${BLUE}🐳 Production Mode (Docker)${NC}"
    
    # Check if port is available
    if ! check_port 8000; then
        exit 1
    fi
    
    # Build and start with docker-compose
    echo -e "${BLUE}🏗️  Building Docker image...${NC}"
    docker-compose build
    
    echo -e "${BLUE}🚀 Starting production server...${NC}"
    docker-compose up -d
    
    # Wait for service to be ready
    if ! wait_for_service "http://0.0.0.0:8000" "Production Server"; then
        echo -e "${RED}❌ Production server failed to start${NC}"
        docker-compose logs
        exit 1
    fi
    
    echo -e "${GREEN}🎉 Production server started successfully!${NC}"
    echo -e "${GREEN}   Application: http://0.0.0.0:8000${NC}"
    echo -e "${GREEN}   API Docs: http://0.0.0.0:8000/docs${NC}"
    echo -e "${YELLOW}   View logs: docker-compose logs -f${NC}"
    echo -e "${YELLOW}   Stop with: ./stop.sh prod${NC}"

else
    echo -e "${RED}❌ Invalid mode: $MODE${NC}"
    echo -e "${YELLOW}Usage: ./start.sh [dev|prod]${NC}"
    echo -e "${YELLOW}  dev  - Start development servers (FastAPI + React)${NC}"
    echo -e "${YELLOW}  prod - Start production server (Docker)${NC}"
    exit 1
fi