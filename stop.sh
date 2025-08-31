#!/bin/bash

# Portfolio Analysis Web App - Stop Script
# Usage: ./stop.sh [dev|prod]

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default mode
MODE=${1:-dev}

echo -e "${BLUE}🛑 Stopping Portfolio Analysis Web App${NC}"
echo -e "${BLUE}Mode: ${MODE}${NC}"

# Function to kill process by PID file
kill_by_pidfile() {
    local pidfile=$1
    local service_name=$2
    
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${YELLOW}🛑 Stopping $service_name (PID: $pid)...${NC}"
            kill "$pid"
            
            # Wait up to 10 seconds for graceful shutdown
            local count=0
            while kill -0 "$pid" 2>/dev/null && [ $count -lt 10 ]; do
                sleep 1
                ((count++))
            done
            
            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                echo -e "${RED}⚡ Force killing $service_name...${NC}"
                kill -9 "$pid" 2>/dev/null || true
            fi
            
            echo -e "${GREEN}✅ $service_name stopped${NC}"
        else
            echo -e "${YELLOW}⚠️  $service_name was not running${NC}"
        fi
        rm -f "$pidfile"
    else
        echo -e "${YELLOW}⚠️  No $service_name PID file found${NC}"
    fi
}

# Function to kill processes by port
kill_by_port() {
    local port=$1
    local service_name=$2
    
    local pids=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo -e "${YELLOW}🛑 Stopping $service_name on port $port...${NC}"
        echo "$pids" | xargs kill 2>/dev/null || true
        sleep 2
        
        # Force kill if still running
        local remaining_pids=$(lsof -ti :$port 2>/dev/null || true)
        if [ -n "$remaining_pids" ]; then
            echo -e "${RED}⚡ Force killing $service_name...${NC}"
            echo "$remaining_pids" | xargs kill -9 2>/dev/null || true
        fi
        echo -e "${GREEN}✅ $service_name stopped${NC}"
    else
        echo -e "${YELLOW}⚠️  No $service_name running on port $port${NC}"
    fi
}

if [ "$MODE" = "dev" ]; then
    echo -e "${BLUE}📦 Development Mode${NC}"
    
    # Stop frontend
    kill_by_pidfile ".frontend.pid" "React frontend"
    
    # Stop backend  
    kill_by_pidfile ".backend.pid" "FastAPI backend"
    
    # Cleanup any remaining processes on the ports
    kill_by_port 5173 "Frontend processes"
    kill_by_port 8000 "Backend processes"
    
    # Clean up log files
    if [ -f "backend.log" ]; then
        echo -e "${BLUE}🧹 Cleaning up backend.log${NC}"
        rm -f backend.log
    fi
    
    if [ -f "frontend.log" ]; then
        echo -e "${BLUE}🧹 Cleaning up frontend.log${NC}"
        rm -f frontend.log
    fi

elif [ "$MODE" = "prod" ]; then
    echo -e "${BLUE}🐳 Production Mode (Docker)${NC}"
    
    # Check if docker-compose is running
    if docker-compose ps -q portfolio-analysis 2>/dev/null | grep -q .; then
        echo -e "${YELLOW}🛑 Stopping Docker containers...${NC}"
        docker-compose down
        echo -e "${GREEN}✅ Docker containers stopped${NC}"
    else
        echo -e "${YELLOW}⚠️  No Docker containers running${NC}"
    fi
    
    # Also check for any remaining processes on port 8000
    kill_by_port 8000 "Production server processes"

elif [ "$MODE" = "all" ]; then
    echo -e "${BLUE}🧹 Stopping All Services${NC}"
    
    # Stop dev mode services
    kill_by_pidfile ".frontend.pid" "React frontend"
    kill_by_pidfile ".backend.pid" "FastAPI backend"
    
    # Stop docker services
    if docker-compose ps -q 2>/dev/null | grep -q .; then
        echo -e "${YELLOW}🛑 Stopping Docker containers...${NC}"
        docker-compose down
    fi
    
    # Kill all processes on relevant ports
    kill_by_port 5173 "Frontend processes"
    kill_by_port 8000 "Backend/Production processes"
    
    # Clean up log files
    rm -f backend.log frontend.log

else
    echo -e "${RED}❌ Invalid mode: $MODE${NC}"
    echo -e "${YELLOW}Usage: ./stop.sh [dev|prod|all]${NC}"
    echo -e "${YELLOW}  dev  - Stop development servers${NC}"
    echo -e "${YELLOW}  prod - Stop production Docker container${NC}"
    echo -e "${YELLOW}  all  - Stop everything${NC}"
    exit 1
fi

echo -e "${GREEN}🎉 Shutdown complete!${NC}"