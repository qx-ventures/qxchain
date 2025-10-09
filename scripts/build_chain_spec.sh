#!/bin/bash

# QX Chain Spec Builder
# Builds a chain specification file for local testnet

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

# Check if binary exists
BINARY="$PROJECT_ROOT/target/release/qxchain"
if [ ! -f "$BINARY" ]; then
    echo -e "${RED}❌ QX Chain binary not found at: $BINARY${NC}"
    echo -e "${YELLOW}Please build the chain first with: cd $SCRIPT_DIR && ./build_chain.sh${NC}"
    exit 1
fi

show_usage() {
    echo "QX Chain Spec Builder"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --chain-id ID        Chain ID (default: qx_local)"
    echo "  --output FILE        Output file path (default: ./local_testnet.json)"
    echo "  --raw                Generate raw chain spec (default: false)"
    echo "  --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0"
    echo "  $0 --chain-id my_network --output my_chain.json"
    echo "  $0 --raw --output raw_chain.json"
    echo ""
}

# Default values
CHAIN_ID="local"
OUTPUT_FILE="$PROJECT_ROOT/local_testnet.json"
RAW_SPEC=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --chain-id)
            CHAIN_ID="$2"
            shift 2
            ;;
        --output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --raw)
            RAW_SPEC=true
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

echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${BLUE}    QX Chain Spec Builder${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}📋 Configuration:${NC}"
echo -e "  Chain ID:    ${GREEN}$CHAIN_ID${NC}"
echo -e "  Output File: ${GREEN}$OUTPUT_FILE${NC}"
echo -e "  Raw Spec:    ${GREEN}$RAW_SPEC${NC}"
echo ""

# Build the chain spec
if [ "$RAW_SPEC" = true ]; then
    echo -e "${YELLOW}🔨 Building raw chain specification...${NC}"
    $BINARY build-spec --chain=$CHAIN_ID --raw > "$OUTPUT_FILE"
else
    echo -e "${YELLOW}🔨 Building chain specification...${NC}"
    $BINARY build-spec --chain=$CHAIN_ID > "$OUTPUT_FILE"
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Chain specification built successfully!${NC}"
    echo -e "${GREEN}Output: $OUTPUT_FILE${NC}"

    # Check file size
    if [ -f "$OUTPUT_FILE" ]; then
        SIZE=$(ls -lh "$OUTPUT_FILE" | awk '{print $5}')
        echo -e "${BLUE}📊 File size: $SIZE${NC}"
    fi
else
    echo -e "${RED}❌ Failed to build chain specification${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${CYAN}📖 Next Steps:${NC}"
echo ""

if [ "$RAW_SPEC" = false ]; then
    echo -e "  ${YELLOW}1. (Optional) Edit the chain spec to add validator keys:${NC}"
    echo -e "     Edit the ${GREEN}$OUTPUT_FILE${NC} file"
    echo ""
    echo -e "  ${YELLOW}2. Generate raw chain spec:${NC}"
    echo -e "     ${GREEN}$0 --chain-id $CHAIN_ID --raw --output ${OUTPUT_FILE%.json}_raw.json${NC}"
    echo ""
    echo -e "  ${YELLOW}3. Use the raw spec when starting nodes:${NC}"
    echo -e "     ${GREEN}./start_node.sh --chain ${OUTPUT_FILE%.json}_raw.json${NC}"
else
    echo -e "  ${YELLOW}1. Start your first node (bootnode):${NC}"
    echo -e "     ${GREEN}./start_node.sh --chain $OUTPUT_FILE --name node1${NC}"
    echo ""
    echo -e "  ${YELLOW}2. Note the bootnode address from the logs${NC}"
    echo -e "     Look for: ${CYAN}Local node identity is: 12D3KooW...${NC}"
    echo ""
    echo -e "  ${YELLOW}3. Start additional nodes:${NC}"
    echo -e "     ${GREEN}./start_node.sh --chain $OUTPUT_FILE --name node2 --bootnodes /ip4/127.0.0.1/tcp/30333/p2p/12D3KooW...${NC}"
fi

echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""
