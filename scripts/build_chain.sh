#!/bin/bash

# QX Chain Build Script
# Builds the QX Chain parachain node

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Build the QX Chain
echo -e "${BLUE}🔨 Building QX Chain...${NC}"

# Navigate to project root
SCRIPT_DIR="$(dirname "$0")"
cd "$SCRIPT_DIR/.."

# Build the parachain node
cargo build --workspace --release

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to build QX Chain${NC}"
    exit 1
fi

echo -e "${GREEN}✅ QX Chain built successfully${NC}"
echo -e "${BLUE}📊 Binary location: ${GREEN}./target/release/qxchain${NC}"
