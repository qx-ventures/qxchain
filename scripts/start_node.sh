#!/bin/bash

# QX Chain Node Startup Script
# Starts a QX Chain blockchain node with Aura+GRANDPA consensus

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
DEFAULT_P2P_PORT=30333
DEFAULT_CHAIN="local"
DEFAULT_NAME="node1"

# Parse command line arguments
RPC_PORT=$DEFAULT_RPC_PORT
P2P_PORT=$DEFAULT_P2P_PORT
CHAIN=$DEFAULT_CHAIN
NODE_NAME=$DEFAULT_NAME
PURGE_CHAIN=false
VERBOSE=false
VALIDATOR=false
BOOTNODES=""
NODE_KEY_FILE=""
BASE_PATH=""
AURA_KEY=""
GRANDPA_KEY=""

show_usage() {
    echo "QX Chain Node Startup Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --name NAME          Node name/identifier (default: node1)"
    echo "  --rpc-port PORT      RPC/WebSocket port (default: 9944)"
    echo "  --p2p-port PORT      P2P networking port (default: 30333)"
    echo "  --chain CHAIN        Chain specification: dev, local, or path to JSON file (default: local)"
    echo "  --bootnodes ADDR     Connect to bootnode (multiaddr format, can be used multiple times)"
    echo "  --node-key-file FILE Path to node key file (hex-encoded 32 bytes)"
    echo "  --base-path PATH     Base path for node data (default: ~/.local/share/qxchain/NODE_NAME)"
    echo "  --validator          Run as validator (requires keys in keystore)"
    echo "  --aura-key SEED      Insert Aura (Sr25519) key from seed phrase"
    echo "  --grandpa-key SEED   Insert GRANDPA (Ed25519) key from seed phrase"
    echo "  --purge-chain        Remove all chain data before starting"
    echo "  --verbose            Enable verbose logging"
    echo "  --help               Show this help message"
    echo ""
    echo "Examples:"
    echo ""
    echo "  Development mode (single node):"
    echo "    $0 --chain dev"
    echo ""
    echo "  Multi-node local testnet:"
    echo "    # Terminal 1 (bootnode):"
    echo "    $0 --name node1 --rpc-port 9944 --p2p-port 30333 --validator"
    echo ""
    echo "    # Terminal 2 (node2, connecting to node1):"
    echo "    $0 --name node2 --rpc-port 9945 --p2p-port 30334 --validator \\"
    echo "       --bootnodes /ip4/127.0.0.1/tcp/30333/p2p/12D3KooW..."
    echo ""
    echo "  With key insertion:"
    echo "    $0 --name node1 --validator \\"
    echo "       --aura-key '//Alice' \\"
    echo "       --grandpa-key '//Alice'"
    echo ""
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --name)
            NODE_NAME="$2"
            shift 2
            ;;
        --rpc-port)
            RPC_PORT="$2"
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
        --bootnodes)
            if [ -z "$BOOTNODES" ]; then
                BOOTNODES="$2"
            else
                BOOTNODES="$BOOTNODES,$2"
            fi
            shift 2
            ;;
        --node-key-file)
            NODE_KEY_FILE="$2"
            shift 2
            ;;
        --base-path)
            BASE_PATH="$2"
            shift 2
            ;;
        --validator)
            VALIDATOR=true
            shift
            ;;
        --aura-key)
            AURA_KEY="$2"
            shift 2
            ;;
        --grandpa-key)
            GRANDPA_KEY="$2"
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
    echo -e "${YELLOW}Please build the chain first with: cd $SCRIPT_DIR && ./build_chain.sh${NC}"
    exit 1
fi

# Set default base path if not specified
if [ -z "$BASE_PATH" ]; then
    BASE_PATH="$HOME/.local/share/qxchain/$NODE_NAME"
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
echo -e "  Node Name:      ${GREEN}$NODE_NAME${NC}"
echo -e "  Chain:          ${GREEN}$CHAIN${NC}"
echo -e "  Validator:      ${GREEN}$VALIDATOR${NC}"
echo -e "  RPC/WS Port:    ${GREEN}$RPC_PORT${NC}"
echo -e "  P2P Port:       ${GREEN}$P2P_PORT${NC}"
echo -e "  Base Path:      ${GREEN}$BASE_PATH${NC}"
if [ -n "$NODE_KEY_FILE" ]; then
    echo -e "  Node Key File:  ${GREEN}$NODE_KEY_FILE${NC}"
fi
if [ -n "$BOOTNODES" ]; then
    echo -e "  Bootnodes:      ${GREEN}$BOOTNODES${NC}"
fi
echo ""

# Purge chain data if requested
if [ "$PURGE_CHAIN" = true ]; then
    echo -e "${YELLOW}🗑️  Purging chain data...${NC}"
    $BINARY purge-chain --chain=$CHAIN --base-path="$BASE_PATH" -y 2>/dev/null || true
    echo -e "${GREEN}✅ Chain data purged${NC}"
    echo ""
fi

# Insert keys if provided
if [ -n "$AURA_KEY" ] || [ -n "$GRANDPA_KEY" ]; then
    echo -e "${YELLOW}🔑 Inserting keys into keystore...${NC}"

    if [ -n "$AURA_KEY" ]; then
        echo -e "${CYAN}  Inserting Aura (Sr25519) key...${NC}"
        $BINARY key insert --base-path="$BASE_PATH" \
            --chain=$CHAIN \
            --scheme Sr25519 \
            --suri "$AURA_KEY" \
            --key-type aura
        echo -e "${GREEN}  ✅ Aura key inserted${NC}"
    fi

    if [ -n "$GRANDPA_KEY" ]; then
        echo -e "${CYAN}  Inserting GRANDPA (Ed25519) key...${NC}"
        $BINARY key insert --base-path="$BASE_PATH" \
            --chain=$CHAIN \
            --scheme Ed25519 \
            --suri "$GRANDPA_KEY" \
            --key-type gran
        echo -e "${GREEN}  ✅ GRANDPA key inserted${NC}"
    fi

    echo ""
fi

# Build the command
CMD="$BINARY"
CMD="$CMD --name=$NODE_NAME"
CMD="$CMD --chain=$CHAIN"
CMD="$CMD --base-path=$BASE_PATH"
CMD="$CMD --rpc-port=$RPC_PORT"
CMD="$CMD --port=$P2P_PORT"
CMD="$CMD --rpc-cors=all"
CMD="$CMD --rpc-methods=unsafe"
CMD="$CMD --rpc-external"

# Add validator flag if requested
if [ "$VALIDATOR" = true ]; then
    CMD="$CMD --validator"
fi

# Add dev mode for dev chain
if [ "$CHAIN" = "dev" ]; then
    CMD="$CMD --alice --dev"
fi

# Add node key file if provided
if [ -n "$NODE_KEY_FILE" ]; then
    if [ ! -f "$NODE_KEY_FILE" ]; then
        echo -e "${RED}❌ Node key file not found: $NODE_KEY_FILE${NC}"
        exit 1
    fi
    CMD="$CMD --node-key-file=$NODE_KEY_FILE"
fi

# Add bootnodes if provided
if [ -n "$BOOTNODES" ]; then
    # Replace commas with spaces and add --bootnodes for each
    IFS=',' read -ra BOOTNODE_ARRAY <<< "$BOOTNODES"
    for bootnode in "${BOOTNODE_ARRAY[@]}"; do
        CMD="$CMD --bootnodes $bootnode"
    done
fi

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
echo -e "  Node Name:   ${CYAN}$NODE_NAME${NC}"
echo -e "  WebSocket:   ${CYAN}ws://localhost:$RPC_PORT${NC}"
echo -e "  HTTP RPC:    ${CYAN}http://localhost:$RPC_PORT${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo ""

if [ "$CHAIN" = "dev" ]; then
    # Pre-funded test accounts for dev mode
    echo -e "${BLUE}📦 Pre-funded Test Accounts (Dev Mode):${NC}"
    echo -e "  Alice:   5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
    echo -e "  Bob:     5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
    echo -e "  Charlie: 5FLSigC9HGRKVhB9FiEo4Y3koPsNmBmLJbpXg2mp1hXcS59Y"
    echo ""
fi

echo -e "${YELLOW}💡 Press Ctrl+C to stop the node${NC}"
echo ""

if [ "$VALIDATOR" = true ] && [ -z "$AURA_KEY" ] && [ -z "$GRANDPA_KEY" ] && [ "$CHAIN" != "dev" ]; then
    echo -e "${YELLOW}⚠️  WARNING: Running as validator but no keys were inserted!${NC}"
    echo -e "${YELLOW}   Add keys with --aura-key and --grandpa-key flags, or insert them manually.${NC}"
    echo ""
fi

echo -e "${CYAN}📖 Useful commands:${NC}"
echo -e "  View node identity: Look for 'Local node identity is: 12D3KooW...' in the logs"
echo -e "  Generate keys:      ${GREEN}./generate_keypair.sh --name $NODE_NAME${NC}"
echo ""
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""

# Execute the command
exec $CMD
