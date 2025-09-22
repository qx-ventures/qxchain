#!/bin/bash

# QX Chain Debug Status Script
# Shows current status of all services and processes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
CHAIN_PORT=9944
OLLAMA_PORT=11434
WORKER_API_PORT=8000
LOG_DIR="./logs"

echo -e "${BLUE}🔍 QX Chain Debug Status${NC}"
echo ""

# Function to check if a port is in use
port_in_use() {
    lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null
}

# Function to get process info on port
get_port_info() {
    local port=$1
    if port_in_use $port; then
        local pid=$(lsof -ti:$port)
        local cmd=$(ps -p $pid -o comm= 2>/dev/null || echo "unknown")
        echo -e "${GREEN}✅ Port $port: LISTENING (PID: $pid, CMD: $cmd)${NC}"
    else
        echo -e "${RED}❌ Port $port: NOT LISTENING${NC}"
    fi
}

# Check ports
echo -e "${BLUE}📡 Port Status:${NC}"
get_port_info $CHAIN_PORT
get_port_info $OLLAMA_PORT  
get_port_info $WORKER_API_PORT
echo ""

# Check processes
echo -e "${BLUE}🔄 Relevant Processes:${NC}"
ps aux | grep -E "(parachain-template-node|ollama|python.*worker|python.*validator)" | grep -v grep || echo "No relevant processes found"
echo ""

# Check PID files
echo -e "${BLUE}📋 PID Files:${NC}"
for pid_file in "$LOG_DIR"/*.pid; do
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        local name=$(basename "$pid_file" .pid)
        if ps -p $pid > /dev/null 2>&1; then
            echo -e "${GREEN}✅ $name: Running (PID: $pid)${NC}"
        else
            echo -e "${RED}❌ $name: Dead (PID: $pid)${NC}"
        fi
    fi
done

if [ ! -f "$LOG_DIR"/*.pid 2>/dev/null ]; then
    echo "No PID files found"
fi
echo ""

# Check log files
echo -e "${BLUE}📄 Log Files:${NC}"
for log_file in "$LOG_DIR"/*.log; do
    if [ -f "$log_file" ]; then
        local name=$(basename "$log_file" .log)
        local size=$(wc -l < "$log_file" 2>/dev/null || echo "0")
        local modified=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$log_file" 2>/dev/null || echo "unknown")
        echo -e "${BLUE}📄 $name.log: $size lines, modified: $modified${NC}"
    fi
done

if [ ! -f "$LOG_DIR"/*.log 2>/dev/null ]; then
    echo "No log files found"
fi
echo ""

# Test connections
echo -e "${BLUE}🌐 Connection Tests:${NC}"

# Test Chain
echo -n "Chain (HTTP): "
if curl -s "http://localhost:$CHAIN_PORT" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Responding${NC}"
else
    echo -e "${RED}❌ Not responding${NC}"
fi

# Test Ollama
echo -n "Ollama: "
if curl -s "http://localhost:$OLLAMA_PORT" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Responding${NC}"
else
    echo -e "${RED}❌ Not responding${NC}"
fi

# Test Worker
echo -n "Worker: "
if curl -s "http://localhost:$WORKER_API_PORT/status" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Responding${NC}"
else
    echo -e "${RED}❌ Not responding${NC}"
fi
echo ""

# Show recent log tails
echo -e "${BLUE}📄 Recent Log Activity:${NC}"
for log_file in "$LOG_DIR"/*.log; do
    if [ -f "$log_file" ]; then
        local name=$(basename "$log_file" .log)
        echo -e "${YELLOW}── $name.log (last 5 lines) ──${NC}"
        tail -5 "$log_file" 2>/dev/null || echo "Cannot read log"
        echo ""
    fi
done
