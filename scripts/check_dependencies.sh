#!/bin/bash

# QX Chain Dependencies Check Script
# Checks and installs required dependencies

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

echo -e "${BLUE}🔍 Checking dependencies...${NC}"

# Check if Rust/Cargo is installed
if ! command_exists cargo; then
    echo -e "${RED}❌ Cargo not found. Please install Rust: https://rustup.rs/${NC}"
    exit 1
fi

# Check if Python3 is installed
if ! command_exists python3; then
    echo -e "${RED}❌ Python3 not found. Please install Python3${NC}"
    exit 1
fi

# Check if pip is installed
if ! command_exists pip3; then
    echo -e "${RED}❌ pip3 not found. Please install pip3${NC}"
    exit 1
fi

# Check/Install Ollama
if ! command_exists ollama; then
    echo -e "${YELLOW}📥 Installing Ollama...${NC}"
    curl -fsSL https://ollama.ai/install.sh | sh
else
    echo -e "${GREEN}✅ Ollama already installed${NC}"
fi

echo -e "${GREEN}✅ Dependencies check passed${NC}"

# Install Python dependencies
echo -e "${BLUE}📦 Installing Python dependencies...${NC}"
SCRIPT_DIR="$(dirname "$0")"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q substrate-interface fastapi uvicorn requests asyncio pydantic

echo -e "${GREEN}✅ Python dependencies installed${NC}"
