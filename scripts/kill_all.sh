#!/bin/bash

# QX Chain Kill All Script
# Stops all QX Chain related processes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${BLUE}     QX Chain Process Terminator${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""

# Function to kill processes gracefully
kill_processes() {
    local pattern=$1
    local name=$2

    local pids=$(pgrep -f "$pattern" 2>/dev/null)
    if [ -n "$pids" ]; then
        echo -e "${YELLOW}🔄 Stopping $name processes...${NC}"
        for pid in $pids; do
            echo "   Terminating PID $pid"
            kill -TERM $pid 2>/dev/null || true
        done
        return 0
    else
        echo -e "${GREEN}✅ No $name processes running${NC}"
        return 1
    fi
}

# Kill processes gracefully first
any_killed=false

echo -e "${BLUE}🎯 Stopping QX Chain components...${NC}"
echo ""

# Kill blockchain node
if kill_processes "target/release/qxchain" "QX Chain node"; then
    any_killed=true
fi

# Kill qxconnect processes (new CLI tool)
if kill_processes "qxconnect\.py" "QX Connect CLI"; then
    any_killed=true
fi

# Kill any Python processes in qxchain_connect directory
if kill_processes "qxchain_connect.*python" "QX Connect Python"; then
    any_killed=true
fi

# Wait for graceful shutdown
if [ "$any_killed" = true ]; then
    echo ""
    echo -e "${YELLOW}⏳ Waiting 3 seconds for graceful shutdown...${NC}"
    sleep 3
fi

# Force kill any remaining processes
echo ""
echo -e "${YELLOW}🔥 Checking for any stubborn processes...${NC}"

remaining_killed=false

for pattern in "target/release/qxchain" "qxconnect\.py" "qxchain_connect.*python"; do
    pids=$(pgrep -f "$pattern" 2>/dev/null)
    if [ -n "$pids" ]; then
        echo "   Force killing: $pattern"
        kill -KILL $pids 2>/dev/null || true
        remaining_killed=true
    fi
done

if [ "$remaining_killed" = false ]; then
    echo -e "${GREEN}✅ No processes needed force killing${NC}"
fi

# Kill processes on specific ports
echo ""
echo -e "${BLUE}🔍 Checking for processes on common ports...${NC}"

# Function to kill process on port
kill_port() {
    local port=$1
    local name=$2

    local pid=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$pid" ]; then
        echo -e "${YELLOW}   Killing process on port $port ($name): PID $pid${NC}"
        kill -TERM $pid 2>/dev/null || kill -KILL $pid 2>/dev/null || true
        return 0
    else
        echo -e "${GREEN}   Port $port ($name) is free${NC}"
        return 1
    fi
}

# Kill processes on known ports
kill_port 9944 "RPC/WebSocket"
kill_port 30333 "P2P"

echo ""
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}✅ All QX Chain processes stopped${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"

# Show any processes that might still be running
echo ""
echo -e "${BLUE}🔍 Final check for remaining processes...${NC}"
remaining=$(ps aux | grep -E "(qxchain|qxconnect)" | grep -v grep | grep -v kill_all.sh)
if [ -n "$remaining" ]; then
    echo -e "${RED}⚠️  Some processes may still be running:${NC}"
    echo "$remaining"
else
    echo -e "${GREEN}✅ All clear - no QX Chain processes running${NC}"
fi

echo ""
echo -e "${BLUE}💡 To start QX Chain again:${NC}"
echo -e "  1. Start node:   ${GREEN}./start_node.sh${NC}"
echo -e "  2. Use CLI:      ${GREEN}cd ../qxchain_connect && ./cli.sh --help${NC}"
echo ""
