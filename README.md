# QX Chain - Decentralized AI Inference Network

QX Chain is a Polkadot SDK-based blockchain that implements **Optimistic Machine Learning (opML)** for decentralized AI inference validation. It provides a trustless environment where customers submit AI inference requests to workers, and validators can challenge incorrect computations through a stake-based consensus mechanism.

## 🔑 Key Features

- **Request-Based AI Inference**: Customers submit requests to specific workers who process AI inference
- **Worker Queue Management**: Workers maintain queues of pending requests with configurable limits
- **Optimistic Validation**: Inferences are assumed correct unless challenged by validators
- **Stake-based Security**: Workers stake 1,000+ tokens, validators stake 100+ tokens, with slashing for malicious behavior
- **Multiple AI Models**: Support for various AI models through Ollama integration
- **Real-time Status Tracking**: Monitor worker availability, request status, and inference results
- **Interactive Customer Interface**: User-friendly interface for browsing workers and submitting requests

## 🏗️ Architecture

The QX Chain consists of several key components:

- **QX Chain Node**: Polkadot SDK-based blockchain node with custom opML pallet
- **AI Workers**: Python services that process inference requests and submit results to blockchain
- **Customers**: Users who submit inference requests through interactive interface
- **Validators**: Network participants who validate inference correctness
- **opML Pallet**: Custom Substrate pallet implementing optimistic ML consensus with request queuing

## 📋 Prerequisites

- **Rust** (stable toolchain)
- **Python 3.8+**
- **Ollama** (for AI model serving)
- **Git**

## 🚀 Quick Start

Choose between **Docker** (recommended for quick testing) or **Native** setup:

### Option A: Docker Setup (Recommended)

**1. Start Ollama Service:**
```bash
# Start official Ollama container
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama

# Pull AI model
docker exec -it ollama ollama pull gemma3:1b
```

**2. Build QX Chain Node:**
```bash
# Build the unified node image (Apple Silicon / arm64)
DOCKER_BUILDKIT=1 docker build --platform linux/arm64 -f Dockerfile.node -t qxchain-node .
```

**3. Start Services (In Separate Terminals):**

**Terminal 1 - Worker Node:**
```bash
docker run -d -p 9944:9944 -p 9933:9933 --name worker \
  qxchain-node --type worker --seed //Bob --setup-zoo
```

**Terminal 2 - Validator Node:**
```bash
docker run -d -p 9945:9945 -p 9934:9934 --name validator \
  qxchain-node --type validator --seed //Charlie --auto-register
```

**Terminal 3 - Client Interface:**
```bash
# Build client image
docker build -f Dockerfile.client -t qxchain-client .

# Run interactive client
docker run -it --name client qxchain-client
```

**4. Check Status:**
```bash
# View container logs
docker logs worker
docker logs validator
docker logs client

# Check blockchain health
curl http://localhost:9933/health
```

### Docker Dev Caching (Faster Rebuilds)

Use BuildKit cache mounts (already enabled in Dockerfile) and persistent volumes for scripts:

```bash
# Ensure BuildKit is on
export DOCKER_BUILDKIT=1

# Build (arm64), caches persist across builds
docker build --platform linux/arm64 -f Dockerfile.node -t qxchain-node .

# Optional: mount scripts live for development
docker run -it \
  -v $(pwd)/scripts:/home/qxuser/scripts \
  -p 9944:9944 -p 9933:9933 \
  --name worker-dev qxchain-node --type worker --seed //Bob
```

### Option B: Native Setup

**1. Complete Setup (One-time):**
```bash
cd scripts
./setup_qx_chain.sh
```

**2. Start Services (In Separate Terminals):**

**Terminal 1 - Start QX Chain:**
```bash
cd scripts
./start_chain.sh
```

**Terminal 2 - Start AI Worker:**
```bash
cd scripts
./start_worker.sh
```

**Terminal 3 - Start Validator:**
```bash
cd scripts
./start_validator.sh
```

**Terminal 4 - Start Customer Interface:**
```bash
cd scripts
./start_customer.sh
```

## 🔧 How to Run

### Running the Main Chain

To start the QX Chain node:

```bash
# Navigate to scripts directory
cd scripts

# Start the blockchain node
./start_chain.sh
```

This will:
- Start the QX Chain node on `ws://localhost:9944`
- Enable instant-seal consensus (blocks created only when transactions occur)
- Set up pre-funded test accounts (Alice, Bob, Charlie, Dave, Eve, Ferdie)
- Show logs in terminal and save to `logs/chain.log`

### Running AI Workers

To start an AI worker that processes inference requests:

```bash
# In a separate terminal
cd scripts

# Start the worker service
./start_worker.sh
```

The worker will:
- Connect to Ollama for AI model inference
- Listen for requests on `http://localhost:8000` (or dynamic port)
- Submit inference results to the QX Chain
- Log activities to `logs/worker.log`

### Running Validators

To start a validator that monitors and validates inferences:

```bash
# In a separate terminal  
cd scripts

# Start the validator service
./start_validator.sh
```

### Running Customer Interface

To start the interactive customer interface for submitting inference requests:

```bash
# In a separate terminal
cd scripts

# Start the customer interface
./start_customer.sh
```

The customer interface provides:
- Browse available workers and their status
- Submit inference requests to specific workers
- Monitor request status and retrieve results
- Interactive menu for easy navigation

## 🧪 How to Test

### Testing AI Inference Pipeline

**Option 1: Interactive Customer Interface (Recommended)**

```bash
cd scripts
./start_customer.sh
```

This provides a user-friendly interface to:
1. Browse available workers
2. Submit inference requests
3. Monitor request status
4. View results

### Manual API Testing

Test the worker API directly:

```bash
# Test inference endpoint
curl -X POST http://localhost:8000/inference \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello, how are you?", "model_id": 0}'

# Check worker status
curl http://localhost:8000/status
```

## 🌐 Service Endpoints

### Docker Services
- **Worker Node WebSocket**: `ws://localhost:9944`
- **Worker Node HTTP**: `http://localhost:9933`
- **Validator Node WebSocket**: `ws://localhost:9945`
- **Validator Node HTTP**: `http://localhost:9934`
- **Ollama API**: `http://localhost:11434`
- **Customer Interface**: Interactive terminal interface via Docker container

### Native Services
- **QX Chain RPC**: `ws://localhost:9944`
- **QX Chain HTTP**: `http://localhost:9944`
- **Ollama API**: `http://localhost:11434`
- **Customer Interface**: Interactive terminal interface via `start_customer.sh`

## 📁 Project Structure

```
qxchain/
├── node/                    # Blockchain node implementation
├── runtime/                 # Runtime logic and configuration  
├── pallets/
│   ├── pallet-qx-ai/       # Custom opML pallet
│   └── template/           # Template pallet
├── scripts/                # Setup and service scripts
│   ├── setup_qx_chain.sh   # Complete setup
│   ├── start_chain.sh      # Start blockchain
│   ├── start_worker.sh     # Start AI worker
│   ├── start_validator.sh  # Start validator
│   ├── start_customer.sh   # Start customer interface
│   ├── customer.py         # Customer interface implementation
│   ├── ollama_worker.py    # Worker implementation
│   └── validator.py        # Validator implementation
└── logs/                   # Service logs
```

## 🎯 opML Workflow

1. **Worker Registration**: AI workers stake tokens and register on-chain with status tracking
2. **Request Submission**: Customers submit inference requests to specific workers
3. **Queue Management**: Workers maintain queues of pending requests (max 100 per worker)
4. **Inference Processing**: Workers process requests and submit results to blockchain
5. **Challenge Period**: Validators can challenge incorrect inferences
6. **Validation**: Consensus determines if inference is correct
7. **Rewards/Slashing**: Honest participants earn rewards, malicious actors are slashed

## 🔄 Request Lifecycle

1. **Queued**: Request submitted to worker's queue
2. **Assigned**: Request assigned to worker for processing
3. **Processing**: Worker executing AI inference
4. **Completed**: Result submitted to blockchain
5. **Validated**: Result validated by network consensus

## 🛠️ Development

### Building from Source

```bash
# Build the chain
cargo build --release

# Build specific components
cd node && cargo build --release
cd runtime && cargo build --release
cd pallets/pallet-qx-ai && cargo build --release
```

### Running Tests

```bash
# Run Rust tests
cargo test

# Run Python tests
cd scripts
python -m pytest test_*.py
```

## 🔍 Monitoring

### Logs

All services save logs to the `logs/` directory:
- `chain.log` - Blockchain node logs
- `worker.log` - AI worker logs  
- `validator_*.log` - Validator logs

### Chain Status

Check chain status via RPC:
```bash
curl -X POST http://localhost:9944 \
  -H "Content-Type: application/json" \
  -d '{"id":1,"jsonrpc":"2.0","method":"system_health","params":[]}'
```

## 🛑 Stopping Services

### Docker Services
```bash
# Stop and remove containers
docker stop ollama worker validator client
docker rm ollama worker validator client

# Remove images (optional)
docker rmi ollama/ollama qxchain-node qxchain-client

# Clean up volumes (WARNING: deletes all data)
docker volume rm ollama
```

### Native Services
To stop all native services:
- Press `Ctrl+C` in each terminal running the services
- Or use the cleanup script: `./scripts/cleanup.sh` (if available)

## 🔧 Troubleshooting

### Common Issues

1. **Build Issues**: Run `./scripts/check_dependencies.sh`
2. **Ollama Issues**: Re-run `./scripts/setup_ollama.sh`
3. **Port Conflicts**: Stop services with `Ctrl+C` and restart
4. **Missing Dependencies**: Ensure Rust, Python, and Ollama are properly installed

### Worker Registration Fails with "InsufficientBalance"

**Problem**: Worker fails to register with error `InsufficientBalance`

**Root Cause**: The worker account doesn't have enough tokens for staking

**Solution**: Each test account has exactly 1,000 tokens, which is the minimum required:
- Workers need minimum 1,000 tokens to stake
- Validators need minimum 100 tokens to stake  
- Transaction fees are minimal (1 token per transaction)

**Pre-funded Test Accounts** (all have 1,000 tokens):
- `//Alice` - Root/Sudo account
- `//Bob` - Default worker account  
- `//Charlie` - Default validator account
- `//Dave`, `//Eve`, `//Ferdie` - Additional test accounts

**Quick Fix**: The scripts now use the correct minimum stake amounts (1,000 for workers, 100 for validators)

## 📝 License

This project is licensed under MIT-0 License. See [LICENSE](LICENSE) for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## 📚 Learn More

- [Polkadot SDK Documentation](https://paritytech.github.io/polkadot-sdk/)
- [FRAME Framework](https://paritytech.github.io/polkadot-sdk/master/polkadot_sdk_docs/polkadot_sdk/frame_runtime/index.html)
- [Substrate Development](https://docs.substrate.io/)