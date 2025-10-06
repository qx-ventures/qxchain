#!/bin/bash

# QX Chain Build Script
# Builds the QX Chain blockchain binary

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${BLUE}       QX Chain Build Script${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Check if Rust is installed
if ! command -v rustc &> /dev/null; then
    echo -e "${RED}❌ Rust is not installed${NC}"
    echo -e "${YELLOW}Please install Rust from https://rustup.rs/${NC}"
    exit 1
fi

echo -e "${BLUE}🔍 Rust version:${NC}"
rustc --version
echo ""

# Check if wasm target is installed
if ! rustup target list --installed | grep -q wasm32-unknown-unknown; then
    echo -e "${YELLOW}📦 Installing wasm32-unknown-unknown target...${NC}"
    rustup target add wasm32-unknown-unknown
fi

# Build the chain
echo -e "${BLUE}🔨 Building QX Chain...${NC}"
echo -e "${YELLOW}This may take a few minutes on first build...${NC}"
echo ""

cargo build --release

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Build completed successfully!${NC}"
    echo -e "${GREEN}Binary location: $PROJECT_ROOT/target/release/qxchain${NC}"

    # Check binary size
    if [ -f "$PROJECT_ROOT/target/release/qxchain" ]; then
        SIZE=$(ls -lh "$PROJECT_ROOT/target/release/qxchain" | awk '{print $5}')
        echo -e "${BLUE}📊 Binary size: $SIZE${NC}"
    fi
else
    echo -e "${RED}❌ Build failed${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}📖 Next steps:${NC}"
echo -e "  1. Start the blockchain: ${GREEN}./start_node.sh${NC}"
echo -e "  2. Use qxchain_connect to interact with the chain"
echo ""
