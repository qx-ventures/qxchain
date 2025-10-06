# QX Chain - Trust and Compliance Backbone for Civic AI

QX Chain is a Substrate-based blockchain designed as the trust and compliance backbone for civic AI applications. It provides enterprise-grade blockchain infrastructure for cities, specializing in verifiable AI execution, identity management, and policy compliance.

QX introduces an **optimistic worker-validator verification protocol** that operates at the application layer, separate from blockchain consensus. AIWorkers perform AI inference off-chain and immediately submit cryptographic commitments on-chain. AIValidators have a 7-day challenge window to audit and dispute incorrect submissions. If over 51% of validators reject a submission, the worker's stake is slashed and the result marked invalid.

**Key Distinction**: AIWorkers and AIValidators are **application-layer entities**, The blockchain consensus is handled by standard Substrate NPoS nodes.

## 🔑 Key Features

- **Optimistic AI Verification**: AIWorkers submit results immediately with cryptographic commitments. Results are considered valid unless challenged within a 7-day dispute window.
- **Economic Security Model**: Challenge-based validation with stake slashing ensures honest participation. AIWorkers stake collateral; if 51%+ of AIValidators successfully challenge a result, the worker loses stake.
- **Off-Chain Computation, On-Chain Trust**: Heavy AI inference executes off-chain (e.g., domain-specific LLMs for civic services), while only cryptographic proofs, hashes, and attestations are stored on-chain.
- **Blockchain-Routed Queries**: Citizens query AIWorkers through the blockchain, which routes requests to registered workers and returns verified AI responses.
- **Application Layer Architecture**: AIWorkers and AIValidators are NOT consensus nodes—they're application-layer entities. Blockchain consensus uses standard Substrate NPoS.
- **7-Day Challenge Period**: Validators have 100,800 blocks (~7 days) to audit and challenge worker submissions before automatic finalization.
- **Stake-Weighted Consensus**: 51% of total validator stake weight must agree to slash a worker, ensuring fair dispute resolution.
- **Multiple AI Models**: Support for various AI models through Ollama integration for civic AI services.

## 🏗️ Architecture

QX Chain has a three-layer architecture that separates blockchain consensus from AI verification:

### Consensus Layer
- **Substrate NPoS Nodes**: Secure the blockchain using Nominated Proof-of-Stake (NPoS)
- Handle block production (BABE), finality (GRANDPA), and network state
- Standard Substrate consensus nodes (NOT AIWorkers/AIValidators)

### Application Layer
- **AIWorkers**: Civic entities (e.g., zoo department, parks office) that run off-chain AI inference using domain-specific models. They register services on-chain with metadata (service type, model hash, stake collateral) and submit cryptographic commitments immediately after inference.
- **AIValidators**: Independent entities that audit worker submissions during 7-day challenge windows. They reproduce inference using committed model hash and input, then compare outputs. If discrepancy found, they submit challenges.

### Interaction Layer
- **Citizens/Customers**: Query AIWorkers through the blockchain for verified AI responses
- **QX AI Pallet**: Custom Substrate pallet implementing optimistic AI verification with challenge-based validation

## 📋 Prerequisites

- **Rust** (stable toolchain)
- **Python 3.8+**
- **Git**

## 🔧 How to Run

### Running the Main Chain

To start the QX Chain node:

```bash
# Navigate to qxchain scripts directory
cd qxchain/scripts

# Build the chain (if not already built)
./build_chain.sh

# Start the blockchain node
./start_node.sh
```

This will:
- Start the QX Chain node on `ws://localhost:9944`
- Enable instant-seal consensus (blocks created only when transactions occur)
- Set up pre-funded test accounts (Alice, Bob, Charlie, Dave, Eve, Ferdie)
- Show logs in terminal

### Interacting with the Chain

To interact with the blockchain (run workers, submit requests, validate results), use the **QX Chain Connect** CLI tool:

https://github.com/qx-ventures/qxchain_connect

## 🌐 Service Endpoints

- **QX Chain WebSocket**: `ws://localhost:9944`
- **QX Chain HTTP**: `http://localhost:9944`

## 📁 Project Structure

```
qxchain/
├── node/                    # Blockchain node implementation
├── runtime/                 # Runtime logic and configuration
├── pallets/
│   └── pallet-qx-ai/       # Custom opML pallet
├── scripts/                # Blockchain management scripts
│   ├── build_chain.sh      # Build blockchain binary
│   ├── start_node.sh       # Start blockchain node
│   └── kill_all.sh         # Kill all services
└── logs/                   # Service logs
```

## 🎯 Workflow

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
3. **Completed**: Result submitted to blockchain with 7-day challenge period
4. **Pending**: Awaiting potential validator challenges during dispute window
5. **Challenged**: Under dispute by validators (if challenged)
6. **Finalized**: Challenge period passed, result accepted as valid
7. **Slashed**: Challenge succeeded, worker penalized and banned

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
```

## 🔍 Monitoring

### Chain Status

Check chain status via RPC:
```bash
curl -X POST http://localhost:9944 \
  -H "Content-Type: application/json" \
  -d '{"id":1,"jsonrpc":"2.0","method":"system_health","params":[]}'
```

## 🛑 Stopping Services

To stop the blockchain node:
- Press `Ctrl+C` in the terminal running the node
- Or use: `./scripts/kill_all.sh` to stop all services

## 🔧 Troubleshooting

### Common Issues

1. **Build Issues**: Ensure Rust toolchain is installed correctly
2. **Port Conflicts**: Stop services with `Ctrl+C` and restart
3. **Missing Dependencies**: Ensure Rust is properly installed

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

## 📚 Learn More

- [Polkadot SDK Documentation](https://paritytech.github.io/polkadot-sdk/)
- [FRAME Framework](https://paritytech.github.io/polkadot-sdk/master/polkadot_sdk_docs/polkadot_sdk/frame_runtime/index.html)
- [Substrate Development](https://docs.substrate.io/)