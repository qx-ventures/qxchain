#!/bin/bash

# QX Chain Single Node Startup Script
# Start a single worker or validator node with integrated blockchain
# Run multiple times in different terminals to build your network

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
OLLAMA_PORT=11434
LOG_DIR="./logs"

# Create logs directory
mkdir -p $LOG_DIR

# Function to check if a port is in use
port_in_use() {
    lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>/dev/null
}

# Function to check and start Ollama
check_and_start_ollama() {
    if port_in_use $OLLAMA_PORT; then
        echo -e "${GREEN}✅ Ollama is already running on port $OLLAMA_PORT${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}🔄 Ollama not running, attempting to start...${NC}"
    
    # Check if ollama command is available
    if ! command -v ollama &> /dev/null; then
        echo -e "${RED}❌ Ollama command not found${NC}"
        echo -e "${YELLOW}💡 Please install Ollama first: https://ollama.com${NC}"
        return 1
    fi
    
    # Start Ollama in background
    echo -e "${BLUE}🚀 Starting Ollama server...${NC}"
    nohup ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
    
    # Wait for Ollama to start
    echo -e "${YELLOW}⏳ Waiting for Ollama to be ready...${NC}"
    local attempts=0
    local max_attempts=30
    
    while [ $attempts -lt $max_attempts ]; do
        if port_in_use $OLLAMA_PORT; then
            echo -e "${GREEN}✅ Ollama started successfully${NC}"
            sleep 2  # Give it a moment to fully initialize
            return 0
        fi
        attempts=$((attempts + 1))
        sleep 1
    done
    
    echo -e "${RED}❌ Failed to start Ollama within timeout${NC}"
    return 1
}

# Function to ensure required model is available
ensure_ollama_model() {
    local model="gemma3:4b"
    
    echo -e "${BLUE}🔍 Checking if model $model is available...${NC}"
    
    # Check if model exists
    local models_response=$(curl -s "http://localhost:$OLLAMA_PORT/api/tags" 2>/dev/null)
    if [[ "$models_response" == *"$model"* ]]; then
        echo -e "${GREEN}✅ Model $model is available${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}📥 Model $model not found, downloading...${NC}"
    echo -e "${BLUE}💡 This may take a few minutes on first run${NC}"
    
    # Pull the model
    ollama pull "$model"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Model $model downloaded successfully${NC}"
        return 0
    else
        echo -e "${RED}❌ Failed to download model $model${NC}"
        return 1
    fi
}

# Function to check prerequisites
check_prerequisites() {
    # Check Python virtual environment
    if [ ! -d ".venv" ]; then
        echo -e "${RED}❌ Python virtual environment not found: .venv${NC}"
        echo -e "${YELLOW}💡 Please set up the Python environment first${NC}"
        exit 1
    fi
    
    # Check QX Chain binary
    if [ ! -f "../target/release/qxchain" ]; then
        echo -e "${RED}❌ QX Chain binary not found: ../target/release/qxchain${NC}"
        echo -e "${YELLOW}💡 Please build the chain first with: cargo build --release${NC}"
        exit 1
    fi
}

# Function to show usage
show_usage() {
    echo "QX Chain Single Node Startup"
    echo ""
    echo "Usage:"
    echo "  $0 worker [options]      # Start a worker node"
    echo "  $0 validator [options]   # Start a validator node"
    echo ""
    echo "Worker Options:"
    echo "  --seed SEED              # Account seed (default: //Bob)"
    echo "  --setup-zoo              # Setup zoo model"
    echo "  --interactive            # Interactive mode (default: queue listener)"
    echo ""
    echo "Validator Options:"
    echo "  --seed SEED              # Account seed (default: //Charlie)"
    echo "  --register               # Auto-register as validator"
    echo "  --auto-mode              # Automatic validation mode (default: interactive)"
    echo ""
    echo "Examples:"
    echo "  $0 worker                                    # Basic worker with //Bob"
    echo "  $0 worker --seed //Dave --setup-zoo         # Worker with Dave account and zoo model"
    echo "  $0 validator --seed //Alice --register      # Validator with Alice account, auto-register"
    echo "  $0 validator --auto-mode                     # Auto-validating validator"
    echo ""
    echo "Network Building:"
    echo "  Terminal 1: $0 worker --seed //Bob --setup-zoo"
    echo "  Terminal 2: $0 worker --seed //Dave"
    echo "  Terminal 3: $0 validator --seed //Charlie --register"
    echo "  Terminal 4: $0 validator --seed //Alice --auto-mode"
}

# Function to start worker
start_worker() {
    local seed="//Bob"
    local setup_zoo=false
    local interactive=false
    
    # Parse worker-specific options
    shift # Remove 'worker' from args
    while [[ $# -gt 0 ]]; do
        case $1 in
            --seed)
                seed="$2"
                shift 2
                ;;
            --setup-zoo)
                setup_zoo=true
                shift
                ;;
            --interactive)
                interactive=true
                shift
                ;;
            *)
                echo -e "${RED}❌ Unknown worker option: $1${NC}"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Generate node name
    local node_name="worker_$(echo $seed | tr -d '/' | tr '[:upper:]' '[:lower:]')_$(date +%s)"
    
    echo -e "${CYAN}🤖 Starting Worker Node${NC}"
    echo -e "${BLUE}═══════════════════════════${NC}"
    # Auto-enable zoo model if no specific setup specified
    if [ "$setup_zoo" = false ] && [[ "$@" != *"--setup-zoo"* ]]; then
        setup_zoo=true
        echo -e "${CYAN}💡 Auto-enabling zoo model for worker${NC}"
    fi
    
    echo -e "${BLUE}📋 Node Name: $node_name${NC}"
    echo -e "${BLUE}📋 Account: $seed${NC}"
    echo -e "${BLUE}📋 Zoo Model: $([ "$setup_zoo" = true ] && echo "Yes" || echo "No")${NC}"
    echo -e "${BLUE}📋 Mode: $([ "$interactive" = true ] && echo "Interactive" || echo "Queue Listener")${NC}"
    echo ""
    
    # Build command
    local cmd="python ollama_worker.py --seed=\"$seed\" --node-name=\"$node_name\""
    
    if [ "$setup_zoo" = true ]; then
        cmd="$cmd --setup-zoo"
    fi
    
    if [ "$interactive" = true ]; then
        cmd="$cmd --interactive"
    fi
    
    # Check and start Ollama for workers
    echo -e "${BLUE}🔧 Preparing Ollama for worker...${NC}"
    if ! check_and_start_ollama; then
        echo -e "${RED}❌ Failed to start Ollama. Worker may not function properly.${NC}"
        echo -e "${YELLOW}💡 Continuing anyway, but AI processing will fail${NC}"
    else
        # Ensure the required model is available
        if ! ensure_ollama_model; then
            echo -e "${YELLOW}⚠️ Model download failed, but continuing...${NC}"
        fi
    fi
    echo ""
    
    echo -e "${YELLOW}🚀 Starting worker with integrated blockchain node...${NC}"
    echo -e "${BLUE}📋 Command: $cmd${NC}"
    echo -e "${YELLOW}💡 Node will run in foreground. Press Ctrl+C to stop gracefully.${NC}"
    echo -e "${YELLOW}📄 Each component logs to its own file in $LOG_DIR/${NC}"
    echo ""
    
    # Execute command
    eval $cmd
}

# Function to start validator
start_validator() {
    local seed="//Charlie"
    local register=false
    local auto_mode=false
    
    # Parse validator-specific options
    shift # Remove 'validator' from args
    while [[ $# -gt 0 ]]; do
        case $1 in
            --seed)
                seed="$2"
                shift 2
                ;;
            --register)
                register=true
                shift
                ;;
            --auto-mode)
                auto_mode=true
                shift
                ;;
            *)
                echo -e "${RED}❌ Unknown validator option: $1${NC}"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Generate node name
    local node_name="validator_$(echo $seed | tr -d '/' | tr '[:upper:]' '[:lower:]')_$(date +%s)"
    
    echo -e "${PURPLE}🛡️ Starting Validator Node${NC}"
    echo -e "${BLUE}═════════════════════════════${NC}"
    echo -e "${BLUE}📋 Node Name: $node_name${NC}"
    echo -e "${BLUE}📋 Account: $seed${NC}"
    echo -e "${BLUE}📋 Register: $([ "$register" = true ] && echo "Yes" || echo "No")${NC}"
    echo -e "${BLUE}📋 Mode: $([ "$auto_mode" = true ] && echo "Automatic" || echo "Interactive")${NC}"
    echo ""
    
    # Build command
    local cmd="python validator.py --seed=\"$seed\" --node-name=\"$node_name\""
    
    if [ "$register" = true ]; then
        cmd="$cmd --register"
    fi
    
    if [ "$auto_mode" = true ]; then
        cmd="$cmd --auto-mode"
    fi
    
    echo -e "${YELLOW}🚀 Starting validator with integrated blockchain node...${NC}"
    echo -e "${BLUE}📋 Command: $cmd${NC}"
    echo -e "${YELLOW}💡 Node will run in foreground. Press Ctrl+C to stop gracefully.${NC}"
    echo -e "${YELLOW}📄 Each component logs to its own file in $LOG_DIR/${NC}"
    echo ""
    
    # Execute command
    eval $cmd
}

# Main script execution
main() {
    # Get script directory and change to it
    SCRIPT_DIR="$(dirname "$0")"
    cd "$SCRIPT_DIR"
    
    # Check prerequisites
    check_prerequisites
    
    # Activate Python environment
    source .venv/bin/activate
    
    # Check if no arguments provided
    if [ $# -eq 0 ]; then
        echo -e "${RED}❌ No node type specified${NC}"
        echo ""
        show_usage
        exit 1
    fi
    
    # Parse main command
    case $1 in
        worker)
            start_worker "$@"
            ;;
        validator)
            start_validator "$@"
            ;;
        --help|-h)
            show_usage
            ;;
        *)
            echo -e "${RED}❌ Unknown node type: $1${NC}"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
