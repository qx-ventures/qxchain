# QX Chain Scripts

Comprehensive scripts for setting up and running the QX Chain opML environment with request-based AI inference.

## 🚀 Quick Start

```bash
./setup_qx_chain.sh  # Complete setup (one-time)
```

## 🔧 Setup Scripts

- **`setup_qx_chain.sh`** - Complete setup (dependencies, Ollama, build)
- **`check_dependencies.sh`** - Install Rust, Python, Ollama
- **`setup_ollama.sh`** - Setup Ollama service and models
- **`build_chain.sh`** - Build the QX Chain node

## 🚦 Service Scripts (Run in Separate Terminals)

### Core Services
- **`start_chain.sh`** - Start QX Chain blockchain node
- **`start_worker.sh`** - Start AI worker (processes requests)
- **`start_validator.sh`** - Start validator (validates inferences)

### User Interface
- **`start_customer.sh`** - Start interactive customer interface

## Usage

### 1. Setup (one time)
```bash
./setup_qx_chain.sh
```

### 2. Run Services (separate terminals)
```bash
# Terminal 1 - Blockchain
./start_chain.sh

# Terminal 2 - AI Worker
./start_worker.sh

# Terminal 3 - Validator
./start_validator.sh

# Terminal 4 - Customer Interface
./start_customer.sh
```

### 3. Stop Services
Press `Ctrl+C` in each terminal

## 🌐 Service Information

- **QX Chain RPC**: `ws://localhost:9944`
- **Ollama API**: `http://localhost:11434`  
- **Worker API**: `http://localhost:8000` (dynamic port)
- **Customer Interface**: Interactive terminal interface

## 🧪 Testing & Usage

### Option 1: Interactive Customer Interface (Recommended)
```bash
./start_customer.sh
```

**Features:**
- Browse available workers and their status
- Submit inference requests to specific workers
- Monitor request queue and processing status
- View inference results in real-time
- User-friendly menu navigation

### Customer Interface Commands
The interactive customer interface provides:
1. **List Workers** - View all registered workers, their online status, and queue lengths
2. **Submit Request** - Create new inference requests with custom prompts
3. **Monitor Requests** - Track status of your submitted requests
4. **Check Request Status** - Get detailed status of specific requests
5. **Exit** - Close the interface

## 🐍 Python Scripts

### Core Components
- **`ollama_worker.py`** - AI worker that processes inference requests from queue
- **`validator.py`** - Validator that monitors and validates inference results
- **`customer.py`** - Interactive customer interface for request submission

### Testing & Utilities
- **`check_account.py`** - Check account balances and status

### Configuration
- **`requirements.txt`** - Python package dependencies

## 📋 Request Workflow

1. **Customer** submits request via `start_customer.sh`
2. **Request** gets queued in selected worker's queue on-chain
3. **Worker** picks up request from queue and processes AI inference
4. **Worker** submits result back to blockchain
5. **Validators** can challenge incorrect results
6. **Customer** receives result through interface or monitoring

## 📊 Logs & Monitoring

### Log Files (in `logs/` directory)
- `chain.log` - Blockchain node logs
- `worker.log` - Worker processing logs
- `validator_*.log` - Validator monitoring logs
- `worker_*.log` - Individual worker session logs

### Real-time Monitoring
All scripts show logs in terminal for real-time monitoring while also saving to files.

## 🔧 Troubleshooting

### Common Issues
1. **Build issues**: Run `./check_dependencies.sh`
2. **Ollama issues**: Re-run `./setup_ollama.sh`  
3. **Port conflicts**: Stop services with `Ctrl+C` and restart
4. **Chain connection errors**: Ensure `start_chain.sh` is running first
5. **No workers available**: Start at least one worker with `start_worker.sh`

### Account Management
- Each service uses different test accounts (Alice, Bob, Charlie, etc.)
- Workers need 1,000+ tokens for staking
- Validators need 100+ tokens for staking
