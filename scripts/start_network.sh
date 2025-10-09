#!/bin/bash

# QX Chain Network Launcher
# Launches multiple QX Chain nodes to form a local testnet

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default configuration
NUM_NODES=4
CHAIN="local"
BASE_RPC_PORT=9944
BASE_P2P_PORT=30333
PURGE=false
USE_ALICE_BOB=false

show_usage() {
    echo "QX Chain Network Launcher"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --nodes NUM          Number of nodes to start (default: 4)"
    echo "  --chain CHAIN        Chain specification: dev, local (default: local)"
    echo "  --rpc-port PORT      Starting RPC port (default: 9944, increments for each node)"
    echo "  --p2p-port PORT      Starting P2P port (default: 30333, increments for each node)"
    echo "  --purge              Purge chain data before starting"
    echo "  --use-alice-bob      Use Alice/Bob/Charlie/Dave keys (for testing only)"
    echo "  --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Start 4 nodes with default settings"
    echo "  $0 --nodes 3 --purge                  # Start 3 nodes, purge old data"
    echo "  $0 --use-alice-bob                    # Start nodes with test keys"
    echo ""
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --nodes)
            NUM_NODES="$2"
            shift 2
            ;;
        --chain)
            CHAIN="$2"
            shift 2
            ;;
        --rpc-port)
            BASE_RPC_PORT="$2"
            shift 2
            ;;
        --p2p-port)
            BASE_P2P_PORT="$2"
            shift 2
            ;;
        --purge)
            PURGE=true
            shift
            ;;
        --use-alice-bob)
            USE_ALICE_BOB=true
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

# Use dev chain when using test keys (Alice/Bob) to avoid network key issues
if [ "$USE_ALICE_BOB" = true ] && [ "$CHAIN" = "local" ]; then
    CHAIN="dev"
fi

# Validate number of nodes
if [ "$NUM_NODES" -lt 1 ]; then
    echo -e "${RED}❌ Number of nodes must be at least 1${NC}"
    exit 1
fi

if [ "$NUM_NODES" -gt 10 ]; then
    echo -e "${RED}❌ Number of nodes cannot exceed 10${NC}"
    exit 1
fi

# Check if binary exists
BINARY="$PROJECT_ROOT/target/release/qxchain"
if [ ! -f "$BINARY" ]; then
    echo -e "${RED}❌ QX Chain binary not found at: $BINARY${NC}"
    echo -e "${YELLOW}Please build the chain first with: cd $SCRIPT_DIR && ./build_chain.sh${NC}"
    exit 1
fi

echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${BLUE}    QX Chain Network Launcher${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}📋 Configuration:${NC}"
echo -e "  Number of Nodes: ${GREEN}$NUM_NODES${NC}"
echo -e "  Chain:           ${GREEN}$CHAIN${NC}"
echo -e "  Base RPC Port:   ${GREEN}$BASE_RPC_PORT${NC}"
echo -e "  Base P2P Port:   ${GREEN}$BASE_P2P_PORT${NC}"
echo -e "  Purge Data:      ${GREEN}$PURGE${NC}"
echo -e "  Use Test Keys:   ${GREEN}$USE_ALICE_BOB${NC}"
echo ""

# Well-known test keys
declare -a TEST_KEYS=("//Alice" "//Bob" "//Charlie" "//Dave" "//Eve" "//Ferdie")

# Create logs directory
LOGS_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOGS_DIR"

# Create keys directory if generating new keys
KEYS_DIR="$PROJECT_ROOT/keys"
if [ "$USE_ALICE_BOB" = false ]; then
    mkdir -p "$KEYS_DIR"
fi

echo -e "${YELLOW}🔧 Setting up nodes...${NC}"
echo ""

# Array to store node information
declare -a NODE_NAMES
declare -a NODE_KEYS
declare -a AURA_KEYS
declare -a GRANDPA_KEYS

# Generate or assign keys for each node
for i in $(seq 1 $NUM_NODES); do
    NODE_NAME="node$i"
    NODE_NAMES+=("$NODE_NAME")

    if [ "$USE_ALICE_BOB" = true ]; then
        # Use pre-defined test keys
        KEY_INDEX=$((i - 1))
        if [ $KEY_INDEX -ge ${#TEST_KEYS[@]} ]; then
            echo -e "${RED}❌ Not enough test keys for $NUM_NODES nodes${NC}"
            echo -e "${YELLOW}Maximum nodes with test keys: ${#TEST_KEYS[@]}${NC}"
            exit 1
        fi

        AURA_KEYS+=("${TEST_KEYS[$KEY_INDEX]}")
        GRANDPA_KEYS+=("${TEST_KEYS[$KEY_INDEX]}")
        NODE_KEYS+=("")

        echo -e "${CYAN}  Node $i: ${GREEN}$NODE_NAME${NC} (using ${TEST_KEYS[$KEY_INDEX]} keys)"
    else
        # Generate new random keys
        echo -e "${CYAN}  Node $i: ${GREEN}$NODE_NAME${NC}"
        echo -e "    Generating keypair..."

        # Generate node key
        NODE_KEY=$(openssl rand -hex 32)
        NODE_KEYS+=("$NODE_KEY")
        echo "$NODE_KEY" > "$KEYS_DIR/${NODE_NAME}_node_key.txt"

        # Generate Aura key
        AURA_OUTPUT=$($BINARY key generate --scheme Sr25519 2>&1)
        AURA_SEED=$(echo "$AURA_OUTPUT" | grep "Secret seed:" | awk '{print $3}')
        AURA_KEYS+=("$AURA_SEED")
        echo "$AURA_OUTPUT" > "$KEYS_DIR/${NODE_NAME}_aura_key.txt"

        # Generate GRANDPA key
        GRANDPA_OUTPUT=$($BINARY key generate --scheme Ed25519 2>&1)
        GRANDPA_SEED=$(echo "$GRANDPA_OUTPUT" | grep "Secret seed:" | awk '{print $3}')
        GRANDPA_KEYS+=("$GRANDPA_SEED")
        echo "$GRANDPA_OUTPUT" > "$KEYS_DIR/${NODE_NAME}_grandpa_key.txt"

        echo -e "    ${GREEN}✅ Keys generated and saved to $KEYS_DIR/${NC}"
    fi
done

echo ""
echo -e "${GREEN}✅ All nodes configured${NC}"
echo ""

# Purge data if requested
if [ "$PURGE" = true ]; then
    echo -e "${YELLOW}🗑️  Purging chain data for all nodes...${NC}"
    for i in $(seq 1 $NUM_NODES); do
        NODE_NAME="${NODE_NAMES[$((i-1))]}"
        BASE_PATH="$HOME/.local/share/qxchain/$NODE_NAME"
        $BINARY purge-chain --chain=$CHAIN --base-path="$BASE_PATH" -y 2>/dev/null || true
    done
    echo -e "${GREEN}✅ Chain data purged${NC}"
    echo ""
fi

echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${YELLOW}🚀 Starting network...${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""

# Function to start a node
start_node() {
    local NODE_NUM=$1
    local NODE_NAME="${NODE_NAMES[$((NODE_NUM-1))]}"
    local RPC_PORT=$((BASE_RPC_PORT + NODE_NUM - 1))
    local P2P_PORT=$((BASE_P2P_PORT + NODE_NUM - 1))
    local NODE_KEY="${NODE_KEYS[$((NODE_NUM-1))]}"
    local AURA_KEY="${AURA_KEYS[$((NODE_NUM-1))]}"
    local GRANDPA_KEY="${GRANDPA_KEYS[$((NODE_NUM-1))]}"
    local LOG_FILE="$LOGS_DIR/${NODE_NAME}.log"

    # Build command
    local CMD="$SCRIPT_DIR/start_node.sh"
    CMD="$CMD --name $NODE_NAME"
    CMD="$CMD --chain $CHAIN"
    CMD="$CMD --rpc-port $RPC_PORT"
    CMD="$CMD --p2p-port $P2P_PORT"
    CMD="$CMD --validator"
    CMD="$CMD --aura-key \"$AURA_KEY\""
    CMD="$CMD --grandpa-key \"$GRANDPA_KEY\""

    # Add node key file if available
    if [ -n "$NODE_KEY" ]; then
        local NODE_KEY_FILE="$KEYS_DIR/${NODE_NAME}_node_key.txt"
        CMD="$CMD --node-key-file $NODE_KEY_FILE"
    fi

    # Add bootnode for non-first nodes
    if [ $NODE_NUM -gt 1 ] && [ -n "$BOOTNODE_ADDR" ]; then
        CMD="$CMD --bootnodes $BOOTNODE_ADDR"
    fi

    echo -e "${CYAN}Starting $NODE_NAME (RPC: $RPC_PORT, P2P: $P2P_PORT)...${NC}"
    echo -e "${BLUE}Log file: $LOG_FILE${NC}"

    # Start node in background
    eval "$CMD > $LOG_FILE 2>&1 &"
    local PID=$!

    echo -e "${GREEN}✅ $NODE_NAME started (PID: $PID)${NC}"
    echo ""

    # For the first node, wait and extract bootnode address
    if [ $NODE_NUM -eq 1 ]; then
        echo -e "${YELLOW}⏳ Waiting for bootnode to initialize...${NC}"
        sleep 5

        # Extract peer ID from log
        if [ -f "$LOG_FILE" ]; then
            # Wait for the actual log line (not the help text)
            PEER_ID=$(grep "🏷  Local node identity is:" "$LOG_FILE" | tail -1 | awk '{print $NF}' | tr -d '\r\n ')
            if [ -n "$PEER_ID" ] && [ "$PEER_ID" != "logs" ] && [ ${#PEER_ID} -gt 20 ]; then
                BOOTNODE_ADDR="/ip4/127.0.0.1/tcp/$P2P_PORT/p2p/$PEER_ID"
                echo -e "${GREEN}✅ Bootnode address: $BOOTNODE_ADDR${NC}"
            else
                echo -e "${YELLOW}⚠️  Could not extract bootnode address, waiting longer...${NC}"
                sleep 5
                PEER_ID=$(grep "🏷  Local node identity is:" "$LOG_FILE" | tail -1 | awk '{print $NF}' | tr -d '\r\n ')
                if [ -n "$PEER_ID" ] && [ "$PEER_ID" != "logs" ] && [ ${#PEER_ID} -gt 20 ]; then
                    BOOTNODE_ADDR="/ip4/127.0.0.1/tcp/$P2P_PORT/p2p/$PEER_ID"
                    echo -e "${GREEN}✅ Bootnode address: $BOOTNODE_ADDR${NC}"
                else
                    echo -e "${RED}❌ Failed to get bootnode address${NC}"
                    echo -e "${YELLOW}Check the log file: $LOG_FILE${NC}"
                fi
            fi
        fi
        echo ""
        sleep 2
    else
        # Small delay between starting nodes
        sleep 1
    fi
}

# Start all nodes
for i in $(seq 1 $NUM_NODES); do
    start_node $i
done

echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Network started successfully!${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""

# Display node information
echo -e "${CYAN}📊 Node Information:${NC}"
echo ""
for i in $(seq 1 $NUM_NODES); do
    NODE_NAME="${NODE_NAMES[$((i-1))]}"
    RPC_PORT=$((BASE_RPC_PORT + i - 1))
    P2P_PORT=$((BASE_P2P_PORT + i - 1))

    echo -e "${GREEN}$NODE_NAME:${NC}"
    echo -e "  RPC:     ${CYAN}http://localhost:$RPC_PORT${NC}"
    echo -e "  WS:      ${CYAN}ws://localhost:$RPC_PORT${NC}"
    echo -e "  P2P:     ${CYAN}$P2P_PORT${NC}"
    echo -e "  Log:     ${CYAN}$LOGS_DIR/${NODE_NAME}.log${NC}"
    echo ""
done

echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${CYAN}📖 Useful Commands:${NC}"
echo ""
echo -e "  View logs:"
echo -e "    ${GREEN}tail -f $LOGS_DIR/node1.log${NC}"
echo ""
echo -e "  Stop all nodes:"
echo -e "    ${GREEN}$SCRIPT_DIR/kill_all.sh${NC}"
echo ""
echo -e "  Check running processes:"
echo -e "    ${GREEN}ps aux | grep qxchain${NC}"
echo ""

if [ "$USE_ALICE_BOB" = false ]; then
    echo -e "  Keys saved in: ${GREEN}$KEYS_DIR/${NC}"
    echo ""
fi

echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${YELLOW}💡 Network is running in the background${NC}"
echo -e "${YELLOW}   Monitor logs to see blocks being produced${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""
