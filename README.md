# QX Chain - Decentralized AI Inference Network

QX Chain is a Polkadot SDK-based blockchain that implements **Optimistic Machine Learning (opML)** for decentralized AI inference validation. It provides a **permissionless, signature-based** system where workers and validators participate without pre-registration.

## 🔑 Key Features

- **Signature-Based Identity**: Workers and validators identified by transaction signatures - no registration needed!
- **Permissionless Participation**: Anyone with a keypair can become a worker or validator
- **Request-Based AI Inference**: Customers submit requests to specific workers who process AI inference
- **Automatic Queue Creation**: Worker queues created automatically on first request
- **Optimistic Validation**: Inferences are assumed correct unless challenged by validators
- **Activity Tracking**: System automatically tracks worker/validator activity by block number
- **Multiple AI Models**: Support for various AI models through Ollama integration
- **Real-time Status Tracking**: Monitor worker availability, request status, and inference results
- **Slashing Mechanism**: Economic penalties for malicious behavior without upfront staking
- **Zero Setup**: Workers and validators just start their nodes - no registration scripts needed

## 🏗️ Architecture

The QX Chain consists of several key components:

- **QX Chain Node**: Polkadot SDK-based blockchain node with signature-based ML inference pallet
- **AI Workers**: Rust-native workers that process inference requests and submit results via signed transactions
- **Customers**: Users who submit inference requests by targeting any worker account
- **Validators**: Network participants who validate inference correctness using their signatures
- **ML Inference Pallet**: Custom Substrate pallet implementing permissionless opML consensus

## 📋 Prerequisites

- **Rust** (stable toolchain)
- **Python 3.8+**
- **Ollama** (for AI model serving)
- **Git**

## 🚀 Quick Start

Choose between **Docker** (recommended for quick testing) or **Native** setup:

### Option A: Docker Setup (Recommended)

**🎯 Ultra-Simple Setup - Just 3 Commands!**

**1. Start Ollama Service:**
```bash
# Start official Ollama container
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama

# Pull AI model
docker exec -it ollama ollama pull gemma3:1b
```

**2. Build QX Chain Images:**
```bash
# Build the unified node image (Apple Silicon / arm64)
DOCKER_BUILDKIT=1 docker build --platform linux/arm64 -f Dockerfile.node -t qxchain-node .

# Build the client image
docker build -f Dockerfile.client -t qxchain-client .
```

**3. Start Services (Simplified Setup):**

**Terminal 1 - Worker Node (starts blockchain automatically):**
```bash
docker run -it --rm -p 9933:9933 --name worker \
  qxchain-node /home/qxuser/start_node.sh --type worker --seed //Bob
```

**Terminal 2 - Validator Node (connects to existing blockchain):**
```bash
docker run -it --rm --name validator \
  qxchain-node /home/qxuser/start_node.sh --type validator --seed //Charlie
```

**Terminal 3 - Client Interface:**
```bash
# Build client image
docker build -f Dockerfile.client -t qxchain-client .

# Run interactive client
docker run -it --rm --name client qxchain-client
```

**🎉 That's it! Your QX Chain network is running!**

**What happens automatically:**
- ✅ First node starts blockchain on port 9933
- ✅ Subsequent nodes connect to existing blockchain  
- ✅ Validators auto-register with stake and node identity
- ✅ Validators run in continuous auto-mode (monitoring every 10s)
- ✅ Workers run in continuous auto-mode (queue listener every 5s)
- ✅ Status updates shown every 30 seconds for both
- ✅ No complex configuration needed

**4. Check Status:**
```bash
# Check running containers
docker ps

# View logs
docker logs worker
docker logs validator
```

**5. Stop Services:**
```bash
# Stop all containers
docker stop worker validator client ollama 2>/dev/null || true
docker rm worker validator client ollama 2>/dev/null || true
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

**1. Build the Chain:**
```bash
cargo build --release
```

**2. Setup Ollama (One-time):**
```bash
# Install Ollama (if not already installed)
# macOS/Linux: curl -fsSL https://ollama.com/install.sh | sh

# Pull AI model
ollama pull gemma3:1b
```

**3. Start Services (In Separate Terminals):**

**Terminal 1 - Start Worker Node:**
```bash
./target/release/qxchain --dev --tmp \
  --node-role worker \
  --ai-endpoint http://localhost:11434 \
  --ai-model gemma3:1b
```

**Terminal 2 - Start Validator Node (optional):**
```bash
./target/release/qxchain --dev \
  --node-role validator \
  --rpc-port 9945 \
  --port 30334 \
  --ai-endpoint http://localhost:11434 \
  --ai-model gemma3:1b
```

**Terminal 3 - Submit Inference Request:**
```bash
# Install dependencies
npm install @polkadot/api

# Submit inference request
node scripts/submit_inference.js
```

## 🔧 How to Run

### Running Worker Nodes

Workers are built into the node binary with signature-based identity:

```bash
# Build the chain
cargo build --release

# Start worker node (no registration needed!)
./target/release/qxchain --dev --tmp \
  --node-role worker \
  --ai-endpoint http://localhost:11434 \
  --ai-model gemma3:1b
```

The worker will:
- Start on `ws://localhost:9944`
- Automatically identify itself via transaction signatures
- Connect to Ollama for AI model inference
- Poll for requests every 5 seconds
- Submit inference results with cryptographic identity proof

### Running Validator Nodes

Validators are also built into the node binary:

```bash
# Start validator node (separate chain for testing)
./target/release/qxchain --dev \
  --node-role validator \
  --rpc-port 9945 \
  --port 30334 \
  --ai-endpoint http://localhost:11434 \
  --ai-model gemma3:1b
```

The validator will:
- Monitor pending inferences
- Challenge incorrect results using signature-based identity
- No pre-registration required!

### Submitting Inference Requests

Use the JavaScript test scripts:

```bash
# Install dependencies (one-time)
npm install @polkadot/api

# Submit inference request to worker
node scripts/submit_inference.js

# Test validator challenge functionality
node scripts/test_validator_simple.js

# Check worker queue status
node scripts/check_bob_queue.js
```

## 🧪 How to Test

### Testing AI Inference Pipeline

**Step 1: Start a Worker Node**

```bash
./target/release/qxchain --dev --tmp \
  --node-role worker \
  --ai-endpoint http://localhost:11434 \
  --ai-model gemma3:1b
```

**Step 2: Submit Inference Request**

```bash
node scripts/submit_inference.js
```

This will:
- Submit a request to Bob's worker account (using Alice as customer)
- Worker automatically processes with signature-based identity
- No pre-registration needed!

**Step 3: Check Results**

The script automatically checks for results after 10 seconds. You can also check manually:

```bash
node scripts/check_bob_queue.js
```

### Testing Validator Challenges

**Start a validator and test challenging:**

```bash
# Terminal 1: Worker
./target/release/qxchain --dev --tmp --node-role worker

# Terminal 2: Submit inference
node scripts/submit_inference.js

# Terminal 3: Validator challenge (uses signature-based identity)
node scripts/test_validator_simple.js
```

## 🌐 Service Endpoints

### Docker Services
- **Blockchain WebSocket**: `ws://localhost:9933` (shared by all nodes)
- **Blockchain HTTP**: `http://localhost:9933` (shared by all nodes)
- **Ollama API**: `http://localhost:11434`

### Native Services
- **Worker Node RPC**: `ws://localhost:9944`
- **Validator Node RPC**: `ws://localhost:9945` (if running separate validator)
- **Ollama API**: `http://localhost:11434`

### Testing Scripts
- **Submit Inference**: `node scripts/submit_inference.js`
- **Check Worker Queue**: `node scripts/check_bob_queue.js`
- **Test Validator**: `node scripts/test_validator_simple.js`

## 📁 Project Structure

```
qxchain/
├── node/                           # Blockchain node implementation
│   ├── src/
│   │   ├── service.rs             # Node service and consensus
│   │   ├── chain_spec.rs          # Chain specification
│   │   ├── ml_worker.rs           # ML Worker with signature-based identity
│   │   ├── ml_validator.rs        # ML Validator with signature-based identity
│   │   ├── ai_client.rs           # Ollama AI client integration
│   │   └── node_identity.rs       # P2P node identity registry
│   └── Cargo.toml                 # Node dependencies (no Subxt needed!)
├── runtime/                        # Runtime logic and configuration
│   ├── src/lib.rs                 # Runtime definition with ML pallets
│   └── Cargo.toml                 # Runtime dependencies
├── pallets/                        # Custom FRAME pallets
│   ├── pallet-ml-inference/       # ML inference with signature-based identity
│   │   ├── src/lib.rs             # Pallet logic (no registration extrinsics)
│   │   └── src/types.rs           # Data structures
│   └── pallet-ml-models/          # Model registry and capabilities
├── scripts/                        # Testing and demo scripts
│   ├── submit_inference.js        # Submit inference request
│   ├── test_validator_simple.js   # Test validator challenge
│   └── test_validator_challenge.js # Test validator workflow
└── logs/                          # Service logs (development)
```

### 🔑 Key Architecture Points

- **No Registration Scripts**: Workers/validators don't need `register_worker.js` or similar
- **Rust-Native Workers**: ML worker logic integrated directly into node binary
- **Signature-Based**: Identity proven by Ed25519/Sr25519 signatures on transactions
- **Activity Tracking**: `WorkerLastActivity` and `ValidatorLastActivity` storage in pallet
- **Automatic Queues**: Worker queues created on-demand when first request assigned

## 🎯 opML Workflow (Signature-Based)

1. **Zero Setup**: Workers and validators start nodes - no registration required!
2. **Request Submission**: Customers submit inference requests to any worker account
3. **Automatic Queue**: Worker queue created automatically on first request
4. **Inference Processing**: Workers process requests and submit results via signed transactions
5. **Identity Proven**: Worker identity automatically verified by transaction signature
6. **Challenge Period**: Validators can challenge incorrect inferences using their signatures
7. **Activity Tracking**: System records last active block for workers and validators
8. **Consensus & Slashing**: If 51%+ validators agree on challenge, worker is banned

## 🔄 Request Lifecycle

1. **Queued**: Request submitted to worker's queue (queue created if first request)
2. **Processing**: Worker executing AI inference
3. **Completed**: Result submitted via signed transaction (worker identity proven automatically)
4. **Pending Validation**: Challenge period begins
5. **Validated/Challenged**: Validators review and either accept or challenge
6. **Finalized**: Request marked complete or worker slashed if challenged successfully

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

# Test pallets specifically
cargo test -p pallet-ml-inference
cargo test -p pallet-ml-models
```

## 🔍 Monitoring

### Node Logs

Monitor node output in the terminal where you started it, or check logs:

```bash
# Worker node shows inference processing
# Look for: "📋 Found X request(s) in queue"
# Look for: "Processing inference request: X"
# Look for: "Submitting inference result for request X"

# Validator node shows challenge activity
# Look for: "🛡️ Starting ML Validator"
# Look for: "Challenge submitted"
```

### Chain Status

Check chain status via RPC:
```bash
# Check chain health
curl -X POST http://localhost:9944 \
  -H "Content-Type: application/json" \
  -d '{"id":1,"jsonrpc":"2.0","method":"system_health","params":[]}'

# Check current block number
curl -X POST http://localhost:9944 \
  -H "Content-Type: application/json" \
  -d '{"id":1,"jsonrpc":"2.0","method":"chain_getHeader","params":[]}'
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
To stop native nodes:
- Press `Ctrl+C` in each terminal running the node
- Or kill processes: `pkill -f qxchain`

## 🔧 Troubleshooting

### Common Issues

1. **Build Issues**: Run `cargo build --release` and check for compilation errors
2. **Ollama Issues**: Ensure Ollama is running: `ollama serve` or check Docker container
3. **Port Conflicts**: Stop nodes with `Ctrl+C` or `pkill -f qxchain` and restart
4. **Missing Dependencies**: Ensure Rust toolchain and Ollama are properly installed

### Workers Not Processing Requests

**Problem**: Worker receives requests but doesn't process them

**Root Cause**:
- Ollama not running or model not pulled
- Worker node not started with correct flags

**Solution**:
```bash
# Ensure Ollama is running
ollama serve

# Pull AI model
ollama pull gemma3:1b

# Start worker with all required flags
./target/release/qxchain --dev --tmp \
  --node-role worker \
  --ai-endpoint http://localhost:11434 \
  --ai-model gemma3:1b
```

### Validators Not Challenging

**Problem**: Validators don't challenge inferences

**Root Cause**: Validator node not monitoring pending inferences

**Solution**:
- Ensure validator started with `--node-role validator`
- Check validator logs for "Starting ML Validator" message
- Validators don't need registration - identity proven by signature

**Pre-funded Test Accounts** (for testing):
- `//Alice` - Root/Sudo account
- `//Bob` - Default worker account
- `//Charlie` - Default validator account
- `//Dave`, `//Eve`, `//Ferdie` - Additional test accounts

**Note**: With signature-based identity, there's no "registration failed" error - accounts just sign transactions!

## 🎉 Quick Summary

**🚀 Get Started in 3 Commands:**
```bash
# 1. Start Ollama
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
docker exec -it ollama ollama pull gemma3:1b

# 2. Build Images  
DOCKER_BUILDKIT=1 docker build --platform linux/arm64 -f Dockerfile.node -t qxchain-node .
docker build -f Dockerfile.client -t qxchain-client .

# 3. Run Network
docker run -it --rm -p 9933:9933 --name worker qxchain-node /home/qxuser/start_node.sh --type worker --seed //Bob
docker run -it --rm --name validator qxchain-node /home/qxuser/start_node.sh --type validator --seed //Charlie  
docker run -it --rm --name client qxchain-client
```

**✨ What You Get:**
- **Signature-Based Identity**: No registration needed - just start nodes with keypairs!
- **Permissionless**: Workers and validators participate by signing transactions
- **Auto-Mode**: Both workers and validators run continuously monitoring the chain
- **Single Port**: Everything uses `ws://localhost:9933`
- **Activity Tracking**: System automatically tracks participation by block number
- **Zero Setup**: No registration scripts, no complex configuration

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