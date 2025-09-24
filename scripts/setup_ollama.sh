#!/bin/bash

# QX Chain Ollama Setup Script
# Manages Ollama service and model setup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
OLLAMA_PORT=11434
LOG_DIR="./logs"

# Create logs directory
mkdir -p $LOG_DIR

# Function to check if a port is in use
port_in_use() {
    lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null
}

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=0
    
    echo -e "${YELLOW}⏳ Waiting for $name to be ready...${NC}"
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ $name is ready!${NC}"
            return 0
        fi
        
        attempt=$((attempt + 1))
        sleep 2
    done
    
    echo -e "${RED}❌ $name failed to start within timeout${NC}"
    return 1
}

# Function to kill process on port
kill_port() {
    local port=$1
    if port_in_use $port; then
        echo -e "${YELLOW}🔄 Killing process on port $port${NC}"
        lsof -ti:$port | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
}

# Start Ollama service
echo -e "${BLUE}🚀 Starting Ollama service...${NC}"
kill_port $OLLAMA_PORT

# Start Ollama in background
ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
OLLAMA_PID=$!

# Wait for Ollama to be ready
if ! wait_for_service "http://localhost:$OLLAMA_PORT" "Ollama"; then
    echo -e "${RED}❌ Failed to start Ollama${NC}"
    exit 1
fi

# Pull required models
echo -e "${BLUE}📥 Pulling Ollama models...${NC}"
ollama pull gemma3:2b
echo -e "${GREEN}✅ Models pulled successfully${NC}"

echo -e "${GREEN}✅ Ollama setup complete${NC}"
echo -e "${BLUE}📊 Ollama API: ${GREEN}http://localhost:$OLLAMA_PORT${NC}"
echo -e "${BLUE}📄 Log: ${GREEN}$LOG_DIR/ollama.log${NC}"
echo -e "${BLUE}📋 Process ID: $OLLAMA_PID${NC}"
