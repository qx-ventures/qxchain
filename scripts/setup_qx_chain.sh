#!/bin/bash

# QX Chain Main Setup Script
# Orchestrates the complete QX Chain opML environment setup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
LOG_DIR="./logs"

echo -e "${BLUE}🌟 QX Chain opML Setup Starting...${NC}"

# Create logs directory
mkdir -p $LOG_DIR

# Get script directory
SCRIPT_DIR="$(dirname "$0")"

# Function to run script and check result
run_script() {
    local script_name=$1
    local description=$2
    
    echo -e "${BLUE}🔄 $description${NC}"
    
    if bash "$SCRIPT_DIR/$script_name"; then
        echo -e "${GREEN}✅ $description completed${NC}"
    else
        echo -e "${RED}❌ $description failed${NC}"
        echo -e "${YELLOW}🛑 Setup aborted${NC}"
        exit 1
    fi
}

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up...${NC}"
    bash "$SCRIPT_DIR/stop_services.sh" 2>/dev/null || true
    echo -e "${GREEN}✅ Cleanup complete${NC}"
}

# Set trap to cleanup on exit
trap cleanup EXIT INT TERM

# Step 1: Check and install dependencies
run_script "check_dependencies.sh" "Checking and installing dependencies"

# Step 2: Setup Ollama
run_script "setup_ollama.sh" "Setting up Ollama service and models"

# Step 3: Build QX Chain
run_script "build_chain.sh" "Building QX Chain"

# Step 4: Start all services
run_script "start_services.sh" "Starting all services"

# Step 5: Test the setup
sleep 5  # Give services a moment to fully initialize
run_script "test_setup.sh" "Testing the setup"

echo ""
echo -e "${GREEN}🎉 QX Chain opML Environment Setup Complete!${NC}"
echo ""
echo -e "${BLUE}📊 Available Scripts:${NC}"
echo -e "  • ${GREEN}./check_dependencies.sh${NC} - Check and install dependencies"
echo -e "  • ${GREEN}./setup_ollama.sh${NC} - Setup Ollama service and models"
echo -e "  • ${GREEN}./build_chain.sh${NC} - Build the QX Chain"
echo -e "  • ${GREEN}./start_services.sh${NC} - Start all services"
echo -e "  • ${GREEN}./stop_services.sh${NC} - Stop all services"
echo -e "  • ${GREEN}./test_setup.sh${NC} - Test the complete setup"
echo ""
echo -e "${BLUE}🔗 Quick Commands:${NC}"
echo -e "  • Stop services: ${YELLOW}./stop_services.sh${NC}"
echo -e "  • Restart services: ${YELLOW}./stop_services.sh && ./start_services.sh${NC}"
echo -e "  • Test setup: ${YELLOW}./test_setup.sh${NC}"
echo ""
echo -e "${YELLOW}📝 To test inference:${NC}"
echo -e "${BLUE}curl -X POST http://localhost:8000/inference \\${NC}"
echo -e "${BLUE}  -H \"Content-Type: application/json\" \\${NC}"
echo -e "${BLUE}  -d '{\"prompt\": \"What are the zoo operating hours?\", \"model_id\": 0}'${NC}"
echo ""
echo -e "${YELLOW}To stop all services, run: ${GREEN}./stop_services.sh${NC}"

# Keep the script running
echo -e "${BLUE}⌛ Press Ctrl+C to stop all services...${NC}"
wait