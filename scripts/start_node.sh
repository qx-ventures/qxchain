#!/bin/bash

# QX Chain Node Startup Script
# Starts a single QX Chain blockchain node in development mode

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default configuration
DEFAULT_RPC_PORT=9944
DEFAULT_WS_PORT=9944  # Same as RPC for qxchain
DEFAULT_P2P_PORT=30333
DEFAULT_CHAIN="dev"
DEFAULT_CONSENSUS="instant-seal"

# Parse command line arguments
RPC_PORT=$DEFAULT_RPC_PORT
WS_PORT=$DEFAULT_WS_PORT
P2P_PORT=$DEFAULT_P2P_PORT
CHAIN=$DEFAULT_CHAIN
CONSENSUS=$DEFAULT_CONSENSUS
PURGE_CHAIN=false
VERBOSE=false

show_usage() {
    echo "QX Chain Node Startup Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --rpc-port PORT      RPC/WebSocket port (default: 9944)"
    echo "  --p2p-port PORT      P2P networking port (default: 30333)"
    echo "  --chain CHAIN        Chain specification: dev, local (default: dev)"
    echo "  --consensus TYPE     Consensus: instant-seal, manual-seal (default: instant-seal)"
    echo "  --purge-chain        Remove all chain data before starting"
    echo "  --verbose            Enable verbose logging"
    echo "  --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                           # Start with defaults"
    echo "  $0 --purge-chain            # Start fresh (remove old data)"
    echo "  $0 --rpc-port 9945          # Use different RPC port"
    echo "  $0 --consensus manual-seal  # Use manual seal for testing"
    echo ""
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --rpc-port)
            RPC_PORT="$2"
            WS_PORT="$2"  # qxchain uses same port for RPC and WS
            shift 2
            ;;
        --p2p-port)
            P2P_PORT="$2"
            shift 2
            ;;
        --chain)
            CHAIN="$2"
            shift 2
            ;;
        --consensus)
            CONSENSUS="$2"
            shift 2
            ;;
        --purge-chain)
            PURGE_CHAIN=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            echo ""
            show_usage
            exit 1
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Check if binary exists
BINARY="$PROJECT_ROOT/target/release/qxchain"
if [ ! -f "$BINARY" ]; then
    echo -e "${RED}❌ QX Chain binary not found at: $BINARY${NC}"
    echo -e "${YELLOW}Please build the chain first with: ./build_chain.sh${NC}"
    exit 1
fi

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Check for port conflicts
if check_port $RPC_PORT; then
    echo -e "${RED}❌ Port $RPC_PORT is already in use${NC}"
    echo -e "${YELLOW}Please stop the existing service or use --rpc-port to specify a different port${NC}"
    exit 1
fi

if check_port $P2P_PORT; then
    echo -e "${RED}❌ Port $P2P_PORT is already in use${NC}"
    echo -e "${YELLOW}Please stop the existing service or use --p2p-port to specify a different port${NC}"
    exit 1
fi

# Show startup banner
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${BLUE}       QX Chain Node Starting${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""

# Display configuration
echo -e "${CYAN}📋 Configuration:${NC}"
echo -e "  Chain:          ${GREEN}$CHAIN${NC}"
echo -e "  Consensus:      ${GREEN}$CONSENSUS${NC}"
echo -e "  RPC/WS Port:    ${GREEN}$RPC_PORT${NC}"
echo -e "  P2P Port:       ${GREEN}$P2P_PORT${NC}"
echo -e "  Data Directory: ${GREEN}$HOME/.local/share/qxchain${NC}"
echo ""

# Purge chain data if requested
if [ "$PURGE_CHAIN" = true ]; then
    echo -e "${YELLOW}🗑️  Purging chain data...${NC}"
    $BINARY purge-chain --chain=$CHAIN -y 2>/dev/null || true
    echo -e "${GREEN}✅ Chain data purged${NC}"
    echo ""
fi

# Build the command
CMD="$BINARY"
CMD="$CMD --chain=$CHAIN"
CMD="$CMD --rpc-port=$RPC_PORT"
CMD="$CMD --port=$P2P_PORT"
CMD="$CMD --rpc-cors=all"
CMD="$CMD --rpc-methods=unsafe"
CMD="$CMD --rpc-external"
CMD="$CMD --consensus=$CONSENSUS"

# Add Alice key for dev chain (gives us a funded account)
if [ "$CHAIN" = "dev" ]; then
    CMD="$CMD --alice --dev"
fi

# Add node key file
CMD="$CMD --node-key-file=$PROJECT_ROOT/node-key"

# Add verbose logging if requested
if [ "$VERBOSE" = true ]; then
    CMD="$CMD -lruntime=debug"
else
    CMD="$CMD -linfo"
fi

# Show startup message
echo -e "${YELLOW}🚀 Starting QX Chain node...${NC}"
echo -e "${BLUE}📝 Command: $CMD${NC}"
echo ""
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}Node Information:${NC}"
echo -e "  WebSocket:   ${CYAN}ws://localhost:$RPC_PORT${NC}"
echo -e "  HTTP RPC:    ${CYAN}http://localhost:$RPC_PORT${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}💡 Press Ctrl+C to stop the node${NC}"
echo ""

# Pre-funded test accounts
echo -e "${BLUE}📦 Pre-funded Test Accounts:${NC}"
echo -e "  Alice:   5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY (1,000,000 tokens)"
echo -e "  Bob:     5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty (1,000,000 tokens)"
echo -e "  Charlie: 5FLSigC9HGRKVhB9FiEo4Y3koPsNmBmLJbpXg2mp1hXcS59Y (1,000,000 tokens)"
echo ""

# Instructions for interacting with the chain
echo -e "${CYAN}📖 To interact with the chain:${NC}"
echo -e "  1. In a new terminal, navigate to: ${GREEN}cd ../qxchain_connect${NC}"
echo -e "  2. Start a worker:    ${GREEN}./cli.sh worker --seed //Bob${NC}"
echo -e "  3. Submit requests:   ${GREEN}./cli.sh customer --seed //Alice${NC}"
echo -e "  4. Validate results:  ${GREEN}./cli.sh validator --seed //Charlie${NC}"
echo ""
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""

# Execute the command
exec $CMD