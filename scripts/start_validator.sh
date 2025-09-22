#!/bin/bash

# QX Validator Startup Script
# Starts a single validator instance with optional API server
#
# Usage:
#   ./start_validator.sh                    # Start full validator (validation loop + API server)
#   ./start_validator.sh --api-only         # Start only API server (no validation)
#   ./start_validator.sh --no-register      # Start without auto-registration
#   ./start_validator.sh --port=8002        # Use custom API port
#   ./start_validator.sh --interval=30      # Set validation interval (seconds)

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
API_PORT=8001
LOG_DIR="./logs"
VALIDATION_INTERVAL=15

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

# Function to check if ollama is running
check_ollama_running() {
    echo -e "${BLUE}🔍 Checking if Ollama is running...${NC}"
    if ! port_in_use $OLLAMA_PORT; then
        echo -e "${YELLOW}⚠️ Ollama is not running on port $OLLAMA_PORT${NC}"
        echo -e "${YELLOW}💡 You may want to start Ollama first with: ./scripts/setup_ollama.sh${NC}"
        echo -e "${YELLOW}💡 Validator will still start but may have issues with model validation${NC}"
    else
        echo -e "${GREEN}✅ Ollama is running${NC}"
    fi
}

# Parse command line arguments
REGISTER_FLAG="--register"
API_ONLY_FLAG=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-register)
            REGISTER_FLAG=""
            shift
            ;;
        --interval=*)
            VALIDATION_INTERVAL="${1#*=}"
            shift
            ;;
        --port=*)
            API_PORT="${1#*=}"
            shift
            ;;
        --api-only)
            API_ONLY_FLAG="--api-only"
            shift
            ;;
        *)
            echo -e "${YELLOW}Unknown option: $1${NC}"
            shift
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$(dirname "$0")"

# Find available API port
ORIGINAL_API_PORT=$API_PORT
if port_in_use $API_PORT; then
    API_PORT=$(find_available_port $API_PORT)
    echo -e "${YELLOW}⚠️ Default API port $ORIGINAL_API_PORT is in use${NC}"
    echo -e "${GREEN}✅ Using available port $API_PORT instead${NC}"
else
    echo -e "${GREEN}✅ API port $API_PORT is available${NC}"
fi

# Check if chain is running first (skip if API-only mode)
if [ -z "$API_ONLY_FLAG" ]; then
    check_chain_running
fi

# Check if ollama is running (warning only, skip if API-only mode)
if [ -z "$API_ONLY_FLAG" ]; then
    check_ollama_running
fi

# Check if Python virtual environment exists
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo -e "${RED}❌ Python virtual environment not found: $SCRIPT_DIR/.venv${NC}"
    echo -e "${YELLOW}💡 Please set up the Python environment first${NC}"
    exit 1
fi

# Generate unique validator ID
VALIDATOR_ID="validator_$(date +%s)_$$"
LOG_FILE="$LOG_DIR/${VALIDATOR_ID}.log"

echo -e "${BLUE}🛡️ Starting Validator...${NC}"
echo -e "${BLUE}📋 Validator ID: $VALIDATOR_ID${NC}"
echo -e "${BLUE}📋 API Server port: $API_PORT${NC}"
if [ -n "$API_ONLY_FLAG" ]; then
    echo -e "${BLUE}📋 Mode: API Server Only${NC}"
else
    echo -e "${BLUE}📋 Mode: Full Validator (API + Validation Loop)${NC}"
    echo -e "${BLUE}📋 Validation interval: ${VALIDATION_INTERVAL}s${NC}"
fi
if [ -n "$REGISTER_FLAG" ]; then
    echo -e "${BLUE}📋 Auto-registration: Enabled${NC}"
else
    echo -e "${BLUE}📋 Auto-registration: Disabled${NC}"
fi

cd "$SCRIPT_DIR"
source .venv/bin/activate

# Build validator command
VALIDATOR_CMD="python validator.py --chain=\"ws://localhost:$CHAIN_PORT\" --ollama=\"http://localhost:$OLLAMA_PORT\" --port=$API_PORT"

if [ -z "$API_ONLY_FLAG" ]; then
    VALIDATOR_CMD="$VALIDATOR_CMD --interval=$VALIDATION_INTERVAL"
fi

if [ -n "$REGISTER_FLAG" ]; then
    VALIDATOR_CMD="$VALIDATOR_CMD $REGISTER_FLAG"
fi

if [ -n "$API_ONLY_FLAG" ]; then
    VALIDATOR_CMD="$VALIDATOR_CMD $API_ONLY_FLAG"
fi

echo -e "${BLUE}📋 Command: $VALIDATOR_CMD${NC}"
echo -e "${YELLOW}💡 Validator will run in foreground. Press Ctrl+C to stop.${NC}"
echo -e "${YELLOW}📄 Logs will be shown in terminal and also saved to: $LOG_FILE${NC}"
if [ -n "$API_ONLY_FLAG" ]; then
    echo -e "${GREEN}🌐 API Documentation available at: http://localhost:$API_PORT/docs${NC}"
else
    echo -e "${GREEN}🌐 API Documentation available at: http://localhost:$API_PORT/docs${NC}"
    echo -e "${GREEN}🔍 Validator Status available at: http://localhost:$API_PORT/status${NC}"
fi
echo ""

# Start validator in foreground
eval $VALIDATOR_CMD 2>&1 | tee "../$LOG_FILE"

# Validator will run in foreground - no process management needed
# When process exits, script exits automatically
