#!/bin/bash
# Build chain specification files for QX Chain
# This script generates both development and local testnet chain specs

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Building QX Chain specifications...${NC}"

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BINARY="${PROJECT_ROOT}/target/release/qxchain"

# Check if binary exists
if [ ! -f "$BINARY" ]; then
    echo "Error: qxchain binary not found at $BINARY"
    echo "Please run 'cargo build --release' first"
    exit 1
fi

cd "$PROJECT_ROOT"

echo -e "${GREEN}Building development chain spec...${NC}"
"$BINARY" build-spec --chain dev --disable-default-bootnode > "dev_chain_spec.json"
echo "  ✓ Created: dev_chain_spec.json"

echo -e "${GREEN}Building development chain spec (raw)...${NC}"
"$BINARY" build-spec --chain "dev_chain_spec.json" --raw --disable-default-bootnode > "dev_chain_spec_raw.json"
echo "  ✓ Created: dev_chain_spec_raw.json"

echo -e "${GREEN}Building local testnet chain spec...${NC}"
"$BINARY" build-spec --chain local_testnet --disable-default-bootnode > "local_testnet_chain_spec.json"
echo "  ✓ Created: local_testnet_chain_spec.json"

echo -e "${GREEN}Building local testnet chain spec (raw)...${NC}"
"$BINARY" build-spec --chain "local_testnet_chain_spec.json" --raw --disable-default-bootnode > "local_testnet_chain_spec_raw.json"
echo "  ✓ Created: local_testnet_chain_spec_raw.json"

echo -e "${BLUE}✓ All chain specifications built successfully!${NC}"
echo ""
echo "Chain specs are located in: $PROJECT_ROOT"
echo ""
echo "Usage:"
echo "  - Single node (dev): zombienet-single.toml"
echo "  - Multi node (4 validators): zombienet.toml"
