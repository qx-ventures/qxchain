#!/bin/bash

# QX Worker Startup Script
# Starts a single worker instance with dynamic port allocation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
CHAIN_PORT=9944
OLLAMA_PORT=11434
WORKER_BASE_PORT=8000
LOG_DIR="./logs"

# Create logs directory
mkdir -p $LOG_DIR

# Function to check if a port is in use
port_in_use() {
    lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>/dev/null
}

# Function to find next available port
find_available_port() {
    local base_port=$1
    local port=$base_port
    
    while port_in_use $port; do
        port=$((port + 1))
    done
    
    echo $port
}

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=0
    
    echo -e "${YELLOW}⏳ Waiting for $name to be ready...${NC}"
    echo -e "${BLUE}🔍 Testing URL: $url${NC}"
    
    while [ $attempt -lt $max_attempts ]; do
        echo -e "${BLUE}📡 Attempt $((attempt + 1))/$max_attempts - Testing $name...${NC}"
        
        local response=$(curl -s -w "HTTP_CODE:%{http_code}" "$url" 2>&1)
        local curl_exit=$?
        
        if [ $curl_exit -eq 0 ]; then
            if [[ "$response" == *"HTTP_CODE:200"* ]] || [[ "$response" == *"HTTP_CODE:404"* ]] || [[ "$response" == *"method not found"* ]]; then
                echo -e "${GREEN}✅ $name is ready!${NC}"
                return 0
            fi
        fi
        
        attempt=$((attempt + 1))
        sleep 2
    done
    
    echo -e "${RED}❌ $name failed to start within timeout${NC}"
    return 1
}

# Function to check if chain is running
check_chain_running() {
    echo -e "${BLUE}🔍 Checking if QX Chain is running...${NC}"
    if ! port_in_use $CHAIN_PORT; then
        echo -e "${RED}❌ QX Chain is not running on port $CHAIN_PORT${NC}"
        echo -e "${YELLOW}💡 Please start the chain first with: ./scripts/start_chain.sh${NC}"
        exit 1
    fi
    
    local response=$(curl -s -X POST "http://localhost:$CHAIN_PORT" \
        -H "Content-Type: application/json" \
        -d '{"id":1,"jsonrpc":"2.0","method":"system_health","params":[]}' \
        2>&1)
    local curl_exit=$?
    
    if [ $curl_exit -eq 0 ] && [[ "$response" == *'"jsonrpc":"2.0"'* ]]; then
        echo -e "${GREEN}✅ QX Chain is running and responsive${NC}"
    else
        echo -e "${RED}❌ QX Chain is not responding properly${NC}"
        echo -e "${YELLOW}💡 Please check the chain status and restart if needed${NC}"
        exit 1
    fi
}

# Get script directory
SCRIPT_DIR="$(dirname "$0")"

# Check if chain is running first
check_chain_running

# Check if Python virtual environment exists
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo -e "${RED}❌ Python virtual environment not found: $SCRIPT_DIR/.venv${NC}"
    echo -e "${YELLOW}💡 Please set up the Python environment first${NC}"
    exit 1
fi

# Find available port for this worker
WORKER_PORT=$(find_available_port $WORKER_BASE_PORT)
echo -e "${BLUE}📋 Using port $WORKER_PORT for worker${NC}"

# Generate unique worker ID
WORKER_ID="worker_$(date +%s)_$$"
LOG_FILE="$LOG_DIR/${WORKER_ID}.log"

echo -e "${BLUE}🤖 Starting Ollama Worker on port $WORKER_PORT...${NC}"
echo -e "${YELLOW}💡 Worker will run in foreground. Press Ctrl+C to stop.${NC}"
echo -e "${YELLOW}📄 Logs will be shown in terminal and also saved to: $LOG_FILE${NC}"
echo ""

cd "$SCRIPT_DIR"
source .venv/bin/activate
python ollama_worker.py \
    --chain="ws://localhost:$CHAIN_PORT" \
    --ollama="http://localhost:$OLLAMA_PORT" \
    --port=$WORKER_PORT \
    --setup-zoo \
    2>&1 | tee "../$LOG_FILE"

# Worker will run in foreground - no process management needed
# When process exits, script exits automatically
