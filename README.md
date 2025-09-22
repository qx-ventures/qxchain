# QX Chain - Decentralized AI Inference Network

QX Chain is a Polkadot SDK-based blockchain that implements **Optimistic Machine Learning (opML)** for decentralized AI inference validation. It provides a trustless environment where AI workers can submit inference results, and validators can challenge incorrect computations through a stake-based consensus mechanism.

## 🔑 Key Features

- **Decentralized AI Inference**: Workers submit AI model inference results to the blockchain
- **Optimistic Validation**: Inferences are assumed correct unless challenged by validators
- **Stake-based Security**: Workers stake 1,000+ tokens, validators stake 100+ tokens, with slashing for malicious behavior
- **Multiple AI Models**: Support for various AI models through Ollama integration
- **Real-time Validation**: Instant block production for immediate transaction processing

## 🏗️ Architecture

The QX Chain consists of several key components:

- **QX Chain Node**: Polkadot SDK-based blockchain node with custom opML pallet
- **AI Workers**: Python services that execute AI inference and submit results
- **Validators**: Network participants who validate inference correctness
- **opML Pallet**: Custom Substrate pallet implementing optimistic ML consensus

## 📋 Prerequisites

- **Rust** (stable toolchain)
- **Python 3.8+**
- **Ollama** (for AI model serving)
- **Git**

## 🚀 Quick Start

### 1. Complete Setup (One-time)

Run the complete setup script to install dependencies, build the chain, and configure Ollama:

```bash
cd scripts
./setup_qx_chain.sh
```

### 2. Start Services (In Separate Terminals)

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

## 🧪 How to Test

### Testing AI Inference Pipeline

To test the complete opML inference pipeline:

```bash
cd scripts

# Run the inference test script
python test_inference.py
```

This will:
1. Submit an inference request to a worker
2. Monitor the chain for inference submission
3. Wait for validator challenges/approvals
4. Display the final result

### Custom Test Parameters

You can customize the test with different parameters:

```bash
# Test with custom prompt
python test_inference.py --prompt "What is machine learning?" --model 0

# Test with different endpoints
python test_inference.py --worker http://localhost:8001 --chain ws://localhost:9944
```

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

### Testing Individual Components

**Test Setup:**
```bash
cd scripts
./test_setup.sh
```

**Test Dependencies:**
```bash
cd scripts
./check_dependencies.sh
```

## 🌐 Service Endpoints

- **QX Chain RPC**: `ws://localhost:9944`
- **QX Chain HTTP**: `http://localhost:9944`
- **Ollama API**: `http://localhost:11434`
- **Worker API**: `http://localhost:8000` (dynamic port assignment)

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
│   ├── test_inference.py   # Test inference pipeline
│   └── ollama_worker.py    # Worker implementation
└── logs/                   # Service logs
```

## 🎯 opML Workflow

1. **Worker Registration**: AI workers stake tokens and register on-chain
2. **Inference Submission**: Workers process AI requests and submit results
3. **Challenge Period**: Validators can challenge incorrect inferences
4. **Validation**: Consensus determines if inference is correct
5. **Rewards/Slashing**: Honest participants earn rewards, malicious actors are slashed

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

To stop all services:
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