#!/bin/bash

# QX Chain Startup Script
# Starts only the QX Chain node

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
CHAIN_PORT=9944
LOG_DIR="./logs"

# Create logs directory
mkdir -p $LOG_DIR

# Function to check if a port is in use
port_in_use() {
    lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null
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

# Function to show log tail
show_log_tail() {
    local log_file=$1
    local name=$2
    local lines=${3:-10}
    
    if [ -f "$log_file" ]; then
        echo -e "${YELLOW}📄 Last $lines lines of $name log:${NC}"
        tail -$lines "$log_file"
        echo -e "${BLUE}────────────────────────────────────────${NC}"
    else
        echo -e "${YELLOW}⚠️ No log file found: $log_file${NC}"
    fi
}

# Function to wait for chain RPC to be ready
wait_for_chain_rpc() {
    local url=$1
    local name=$2
    local max_attempts=60
    local attempt=0
    
    echo -e "${YELLOW}⏳ Waiting for $name RPC to be ready...${NC}"
    echo -e "${BLUE}🔍 Testing RPC URL: $url${NC}"
    
    while [ $attempt -lt $max_attempts ]; do
        echo -e "${BLUE}📡 Attempt $((attempt + 1))/$max_attempts - Testing $name RPC...${NC}"
        
        # Test with a simple RPC call
        local response=$(curl -s -X POST "$url" \
            -H "Content-Type: application/json" \
            -d '{"id":1,"jsonrpc":"2.0","method":"system_health","params":[]}' \
            2>&1)
        local curl_exit=$?
        
        echo -e "${BLUE}📋 Curl exit code: $curl_exit${NC}"
        if [ $curl_exit -eq 0 ]; then
            echo -e "${BLUE}📋 Response: $response${NC}"
            if [[ "$response" == *'"jsonrpc":"2.0"'* ]] || [[ "$response" == *'"result"'* ]]; then
                echo -e "${GREEN}✅ $name RPC is ready!${NC}"
                return 0
            fi
        else
            echo -e "${BLUE}📋 Connection failed: $response${NC}"
        fi
        
        attempt=$((attempt + 1))
        sleep 3
    done
    
    echo -e "${RED}❌ $name RPC failed to start within timeout${NC}"
    echo -e "${YELLOW}💡 Check the logs for more details${NC}"
    return 1
}

# Get script directory and project root
SCRIPT_DIR="$(dirname "$0")"
PROJECT_ROOT="$SCRIPT_DIR/.."

# Start the QX Chain node
echo -e "${BLUE}🚀 Starting QX Chain node...${NC}"
kill_port $CHAIN_PORT

# Check if binary exists
cd "$PROJECT_ROOT"
if [ ! -f "./target/release/qxchain" ]; then
    echo -e "${RED}❌ Binary not found: ./target/release/qxchain${NC}"
    echo -e "${YELLOW}💡 Run ./scripts/build_chain.sh first${NC}"
    exit 1
fi

echo -e "${BLUE}📋 Starting chain with command:${NC}"
echo -e "${BLUE}   ./target/release/qxchain --dev --consensus=instant-seal --rpc-port=$CHAIN_PORT --rpc-cors=all --rpc-methods=unsafe${NC}"
echo ""
echo -e "${YELLOW}🔧 Instant Seal Mode: Blocks created ONLY when transactions occur${NC}"
echo -e "${YELLOW}💡 No automatic block production - purely transaction-driven${NC}"
echo -e "${YELLOW}💡 Available consensus options: instant-seal, manual-seal-<ms>, none${NC}"

# Start chain in foreground (logs will show in terminal)
echo -e "${YELLOW}💡 Chain will run in foreground. Press Ctrl+C to stop.${NC}"
echo -e "${YELLOW}📄 Logs will be shown in terminal and also saved to: $LOG_DIR/chain.log${NC}"
echo ""

# Use tee to show logs in terminal AND save to file  
./target/release/qxchain \
    --dev \
    --consensus=instant-seal \
    --rpc-port=$CHAIN_PORT \
    --rpc-cors=all \
    --rpc-methods=unsafe \
    --log=info,manual_seal=debug,sc_consensus_manual_seal=debug,runtime=debug \
    --detailed-log-output \
    2>&1 | tee "$LOG_DIR/chain.log"

# Chain will run in foreground - no process management needed
# When process exits, script exits automatically
