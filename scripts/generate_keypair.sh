#!/bin/bash

# QX Chain Keypair Generator
# Generates account keys and node keys for network nodes

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
    echo "QX Chain Keypair Generator"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --name NAME          Node name/identifier (e.g., node1, node2)"
    echo "  --output-dir DIR     Directory to save keys (default: ./keys)"
    echo "  --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --name node1"
    echo "  $0 --name node2 --output-dir /path/to/keys"
    echo ""
}

# Default values
NODE_NAME=""
OUTPUT_DIR="$PROJECT_ROOT/keys"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --name)
            NODE_NAME="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
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

# Validate node name
if [ -z "$NODE_NAME" ]; then
    echo -e "${RED}❌ Node name is required${NC}"
    echo ""
    show_usage
    exit 1
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${BLUE}    QX Chain Keypair Generator${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}📋 Configuration:${NC}"
echo -e "  Node Name:   ${GREEN}$NODE_NAME${NC}"
echo -e "  Output Dir:  ${GREEN}$OUTPUT_DIR${NC}"
echo ""

# Generate node key (for p2p identity)
echo -e "${YELLOW}🔑 Generating node key...${NC}"
NODE_KEY=$(openssl rand -hex 32)
echo "$NODE_KEY" > "$OUTPUT_DIR/${NODE_NAME}_node_key.txt"
echo -e "${GREEN}✅ Node key saved to: ${OUTPUT_DIR}/${NODE_NAME}_node_key.txt${NC}"

# Generate Sr25519 account key (for Aura/block production)
echo -e "${YELLOW}🔑 Generating Sr25519 account key (Aura)...${NC}"
AURA_OUTPUT=$($BINARY key generate --scheme Sr25519 2>&1)
AURA_SECRET=$(echo "$AURA_OUTPUT" | grep "Secret seed:" | awk '{print $3}')
AURA_PUBLIC=$(echo "$AURA_OUTPUT" | grep "Public key (hex):" | awk '{print $4}')
AURA_SS58=$(echo "$AURA_OUTPUT" | grep "Account ID:" | awk '{print $3}')

echo "$AURA_OUTPUT" > "$OUTPUT_DIR/${NODE_NAME}_aura_key.txt"
echo -e "${GREEN}✅ Aura key saved to: ${OUTPUT_DIR}/${NODE_NAME}_aura_key.txt${NC}"

# Generate Ed25519 account key (for GRANDPA/finality)
echo -e "${YELLOW}🔑 Generating Ed25519 account key (GRANDPA)...${NC}"
GRANDPA_OUTPUT=$($BINARY key generate --scheme Ed25519 2>&1)
GRANDPA_SECRET=$(echo "$GRANDPA_OUTPUT" | grep "Secret seed:" | awk '{print $3}')
GRANDPA_PUBLIC=$(echo "$GRANDPA_OUTPUT" | grep "Public key (hex):" | awk '{print $4}')
GRANDPA_SS58=$(echo "$GRANDPA_OUTPUT" | grep "Account ID:" | awk '{print $3}')

echo "$GRANDPA_OUTPUT" > "$OUTPUT_DIR/${NODE_NAME}_grandpa_key.txt"
echo -e "${GREEN}✅ GRANDPA key saved to: ${OUTPUT_DIR}/${NODE_NAME}_grandpa_key.txt${NC}"

echo ""
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${BLUE}    Generated Keys Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}Node Key (P2P Identity):${NC}"
echo -e "  ${GREEN}$NODE_KEY${NC}"
echo ""
echo -e "${CYAN}Aura Key (Sr25519 - Block Production):${NC}"
echo -e "  Secret Seed: ${GREEN}$AURA_SECRET${NC}"
echo -e "  Public Key:  ${GREEN}$AURA_PUBLIC${NC}"
echo -e "  SS58 Addr:   ${GREEN}$AURA_SS58${NC}"
echo ""
echo -e "${CYAN}GRANDPA Key (Ed25519 - Finality):${NC}"
echo -e "  Secret Seed: ${GREEN}$GRANDPA_SECRET${NC}"
echo -e "  Public Key:  ${GREEN}$GRANDPA_PUBLIC${NC}"
echo -e "  SS58 Addr:   ${GREEN}$GRANDPA_SS58${NC}"
echo ""

# Create a summary JSON file
cat > "$OUTPUT_DIR/${NODE_NAME}_summary.json" <<EOF
{
  "node_name": "$NODE_NAME",
  "node_key": "$NODE_KEY",
  "aura": {
    "secret_seed": "$AURA_SECRET",
    "public_key": "$AURA_PUBLIC",
    "ss58_address": "$AURA_SS58",
    "scheme": "Sr25519"
  },
  "grandpa": {
    "secret_seed": "$GRANDPA_SECRET",
    "public_key": "$GRANDPA_PUBLIC",
    "ss58_address": "$GRANDPA_SS58",
    "scheme": "Ed25519"
  }
}
EOF

echo -e "${GREEN}✅ Summary saved to: ${OUTPUT_DIR}/${NODE_NAME}_summary.json${NC}"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: Keep these keys secure! Anyone with access to the secret seeds can control this node.${NC}"
echo ""
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${CYAN}📖 Next Steps:${NC}"
echo -e "  1. Use these keys when starting your node"
echo -e "  2. Insert keys into keystore: ${GREEN}$BINARY key insert${NC}"
echo -e "  3. Start node with: ${GREEN}./start_node.sh --name $NODE_NAME --node-key-file $OUTPUT_DIR/${NODE_NAME}_node_key.txt${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""
