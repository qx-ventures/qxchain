#!/bin/bash

# QX Chain Customer Interface Launcher
# This script starts the interactive customer interface for submitting inference requests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default configuration
CHAIN_ENDPOINT=""  # Will be auto-detected or specified
CUSTOMER_SEED="//Alice"
PYTHON_ENV=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_info() {
    echo -e "${BLUE}ℹ️ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Help function
show_help() {
    cat << EOF
QX Chain Customer Interface Launcher

Usage: $0 [OPTIONS]

Options:
    --chain ENDPOINT     Chain WebSocket endpoint (default: auto-detect)
    --seed SEED         Customer account seed (default: //Alice)
    --env PATH          Python virtual environment path
    --help              Show this help message

Examples:
    $0                                          # Auto-detect running nodes
    $0 --chain ws://localhost:10314            # Connect to specific node port
    $0 --seed "//Bob"                          # Use different account
    $0 --env ./venv                            # Use specific Python environment

First start some nodes:
    ./start_node.sh worker --seed //Bob --setup-zoo
    ./start_node.sh validator --seed //Charlie --register

Customer Seeds:
    //Alice             Default customer account
    //Bob               Alternative customer account
    //Charlie           Another customer account
    //Dave              Yet another customer account

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --chain)
            CHAIN_ENDPOINT="$2"
            shift 2
            ;;
        --seed)
            CUSTOMER_SEED="$2"
            shift 2
            ;;
        --env)
            PYTHON_ENV="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Function to find running QX Chain nodes
find_running_nodes() {
    local found_endpoints=()
    
    # Check common port range for running qxchain processes
    for port in 9933 $(seq 9944 9999) $(seq 10000 11000); do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>/dev/null; then
            # Test if it's a qxchain node by trying an RPC call
            local response=$(curl -s -m 2 -X POST "http://localhost:$port" \
                -H "Content-Type: application/json" \
                -d '{"id":1,"jsonrpc":"2.0","method":"system_name","params":[]}' \
                2>/dev/null)
            
            if [[ "$response" == *'"result"'* ]] && [[ "$response" == *'"qxchain"'* || "$response" == *'"Substrate"'* ]]; then
                found_endpoints+=("ws://localhost:$port")
            fi
        fi
    done
    
    echo "${found_endpoints[@]}"
}

# Auto-detect chain endpoint if not specified
if [ -z "$CHAIN_ENDPOINT" ]; then
    print_info "Searching for running QX Chain nodes..."
    
    available_endpoints=($(find_running_nodes))
    
    if [ ${#available_endpoints[@]} -eq 0 ]; then
        print_error "No QX Chain nodes found running"
        echo ""
        echo "Please start a node first:"
        echo "  ./start_node.sh worker --seed //Bob --setup-zoo"
        echo "  ./start_node.sh validator --seed //Charlie --register"
        echo ""
        echo "Or specify a chain endpoint manually:"
        echo "  $0 --chain ws://localhost:PORT"
        exit 1
    elif [ ${#available_endpoints[@]} -eq 1 ]; then
        CHAIN_ENDPOINT="${available_endpoints[0]}"
        print_success "Found QX Chain node: $CHAIN_ENDPOINT"
    else
        echo ""
        print_info "Multiple QX Chain nodes found:"
        for i in "${!available_endpoints[@]}"; do
            echo "  $((i+1))) ${available_endpoints[$i]}"
        done
        echo ""
        echo -n "Select node to connect to [1]: "
        read choice
        
        if [[ -z "$choice" ]]; then
            choice=1
        fi
        
        if [[ "$choice" -ge 1 ]] && [[ "$choice" -le ${#available_endpoints[@]} ]]; then
            CHAIN_ENDPOINT="${available_endpoints[$((choice-1))]}"
            print_success "Selected: $CHAIN_ENDPOINT"
        else
            print_error "Invalid selection"
            exit 1
        fi
    fi
    echo ""
fi

# Banner
echo "
🎯 QX Chain Customer Interface
================================
"

print_info "Starting QX Chain Customer Interface..."
print_info "Chain endpoint: $CHAIN_ENDPOINT"
print_info "Customer seed: $CUSTOMER_SEED"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not installed"
    exit 1
fi

# Activate Python environment if specified
if [[ -n "$PYTHON_ENV" ]]; then
    if [[ -f "$PYTHON_ENV/bin/activate" ]]; then
        print_info "Activating Python environment: $PYTHON_ENV"
        source "$PYTHON_ENV/bin/activate"
    else
        print_error "Python environment not found: $PYTHON_ENV"
        exit 1
    fi
fi

# Check for required Python packages
print_info "Checking Python dependencies..."
python3 -c "
import sys
required_packages = ['substrateinterface', 'requests', 'asyncio']
missing_packages = []

for package in required_packages:
    try:
        __import__(package)
    except ImportError:
        missing_packages.append(package)

if missing_packages:
    print('Missing packages:', ', '.join(missing_packages))
    print('Install them with: pip install ' + ' '.join(missing_packages))
    sys.exit(1)
else:
    print('All required packages are available')
" || {
    print_error "Missing required Python packages"
    print_info "Install dependencies with: pip install -r requirements.txt"
    exit 1
}

# Check if chain is running
print_info "Checking chain connection..."
python3 -c "
import asyncio
from substrateinterface import SubstrateInterface

async def check_chain():
    try:
        substrate = SubstrateInterface(url='$CHAIN_ENDPOINT')
        block = substrate.get_block_number(None)
        print(f'Chain is running - Latest block: {block}')
        return True
    except Exception as e:
        print(f'Chain connection failed: {e}')
        return False

result = asyncio.run(check_chain())
exit(0 if result else 1)
" || {
    print_error "Cannot connect to chain at $CHAIN_ENDPOINT"
    print_info "Make sure the chain is running with: ./scripts/start_chain.sh"
    exit 1
}

print_success "Chain connection successful"

# Check if there are any workers available
print_info "Checking for available workers..."
python3 -c "
import asyncio
from substrateinterface import SubstrateInterface

async def check_workers():
    try:
        substrate = SubstrateInterface(url='$CHAIN_ENDPOINT')
        workers_query = substrate.query_map('QxAi', 'Workers')
        workers = list(workers_query)
        
        if workers:
            print(f'Found {len(workers)} registered workers')
            for worker_account, stake in workers:
                worker_addr = worker_account.value
                status_query = substrate.query('QxAi', 'WorkerStatus', [worker_addr])
                online = status_query.value if status_query.value is not None else False
                status = 'online' if online else 'offline'
                print(f'  - {worker_addr}: {status}')
        else:
            print('No workers found')
            print('Start a worker with: ./scripts/start_worker.sh')
            return False
        return True
    except Exception as e:
        print(f'Error checking workers: {e}')
        return False

result = asyncio.run(check_workers())
" || {
    print_warning "No workers available or error checking workers"
    print_info "You can still start the customer interface, but no inference requests can be processed"
}

# Start the customer interface
print_info "Starting customer interface..."
print_info "Press Ctrl+C to exit"

cd "$SCRIPT_DIR"

# Run the customer interface
python3 customer.py --chain "$CHAIN_ENDPOINT" --seed "$CUSTOMER_SEED"

print_success "Customer interface stopped"
