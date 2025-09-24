#!/bin/bash

# QX Chain Kill All Script
# Stops all QX Chain related processes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🛑 Stopping all QX Chain processes...${NC}"

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

if kill_processes "qxchain" "blockchain node"; then
    any_killed=true
fi

if kill_processes "ollama_worker" "worker"; then
    any_killed=true
fi

if kill_processes "validator\.py" "validator"; then
    any_killed=true
fi

if kill_processes "customer\.py" "customer"; then
    any_killed=true
fi

# Wait for graceful shutdown
if [ "$any_killed" = true ]; then
    echo -e "${YELLOW}⏳ Waiting 3 seconds for graceful shutdown...${NC}"
    sleep 3
fi

# Force kill any remaining processes
echo -e "${YELLOW}🔥 Force killing any remaining processes...${NC}"

remaining_killed=false

for pattern in "qxchain" "ollama_worker" "validator\.py" "customer\.py"; do
    local pids=$(pgrep -f "$pattern" 2>/dev/null)
    if [ -n "$pids" ]; then
        echo "   Force killing: $pattern"
        kill -KILL $pids 2>/dev/null || true
        remaining_killed=true
    fi
done

if [ "$remaining_killed" = false ]; then
    echo -e "${GREEN}✅ No processes needed force killing${NC}"
fi

echo ""
echo -e "${GREEN}✅ All QX Chain processes stopped${NC}"

# Show any processes that might still be running
echo -e "${YELLOW}🔍 Checking for any remaining processes...${NC}"
remaining=$(ps aux | grep -E "(qxchain|ollama_worker|validator\.py|customer\.py)" | grep -v grep | grep -v kill_all.sh)
if [ -n "$remaining" ]; then
    echo -e "${RED}⚠️ Some processes may still be running:${NC}"
    echo "$remaining"
else
    echo -e "${GREEN}✅ All clear${NC}"
fi
