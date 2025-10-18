# QX Chain - Verifiable AI Inference

QX Chain is a Substrate-based blockchain designed as the infrastructure for verifiable AI execution. It provides blockchain infrastructure for cities, specializing in verifiable AI execution, identity management, and policy compliance.

QX introduces an **optimistic worker-validator verification protocol** that operates at the application layer, separate from blockchain consensus. AIWorkers perform AI inference off-chain and immediately submit cryptographic commitments on-chain. AIValidators have a 7-day challenge window to audit and dispute incorrect submissions. If over 51% of validators reject a submission, the worker's stake is slashed and the result marked invalid.

**Key Distinction**: AIWorkers and AIValidators are **application-layer entities**. The blockchain consensus is handled by standard Substrate authority nodes using Aura + Grandpa (Proof of Authority).

## 🔑 Key Features

- **Optimistic AI Verification**: AIWorkers submit results immediately with cryptographic commitments. Results are considered valid unless challenged within a 7-day dispute window.
- **Economic Security Model**: Challenge-based validation with stake slashing ensures honest participation. AIWorkers stake collateral; if 51%+ of AIValidators successfully challenge a result, the worker loses stake.
- **Off-Chain Computation, On-Chain Trust**: Heavy AI inference executes off-chain (e.g., domain-specific LLMs for civic services), while only cryptographic proofs, hashes, and attestations are stored on-chain.
- **Blockchain-Routed Queries**: Citizens query AIWorkers through the blockchain, which routes requests to registered workers and returns verified AI responses.
- **Application Layer Architecture**: AIWorkers and AIValidators are NOT consensus nodes—they're application-layer entities. Blockchain consensus uses AURA + GRANDPA (Proof of Authority).
- **7-Day Challenge Period**: Validators have 100,800 blocks (~7 days) to audit and challenge worker submissions before automatic finalization.
- **Stake-Weighted Consensus**: 51% of total validator stake weight must agree to slash a worker, ensuring fair dispute resolution.
- **Multiple AI Models**: Support for various AI models through Ollama integration for civic AI services.

## 🏗️ Architecture

QX Chain has a three-layer architecture that separates blockchain consensus from AI verification:

### Consensus Layer
- **AURA + GRANDPA Consensus (Proof of Authority)**: Authority nodes secure the blockchain using AURA for block production and GRANDPA for finality
- Designed for permissioned networks with pre-selected authority validators
- Mainnet runs with 4 production validators
- Standard Substrate consensus nodes (NOT AIWorkers/AIValidators)

### Application Layer
- **AIWorkers**: Civic entities (e.g., zoo department, parks office) that run off-chain AI inference using domain-specific models. They register services on-chain with metadata (service type, model hash, stake collateral) and submit cryptographic commitments immediately after inference.
- **AIValidators**: Independent entities that audit worker submissions during 7-day challenge windows. They reproduce inference using committed model hash and input, then compare outputs. If discrepancy found, they submit challenges.

## 📁 Project Structure

```
qxchain/
├── node/                            # Blockchain node implementation
│   └── src/
│       ├── chain_spec/             # Chain specifications
│       │   ├── mainnet.rs          # Production network config (4 validators)
│       │   ├── localnet.rs         # Local test network config
│       │   └── mod.rs              # Common chain spec utilities
│       ├── command.rs              # CLI command handling
│       └── main.rs                 # Node entry point
├── runtime/                         # Runtime logic and configuration
├── pallets/
│   └── pallet-qx-ai/               # Custom opML pallet for AI verification
├── chainspecs/                      # Generated chain specification files
│   ├── raw_spec_mainnet.json       # Production network spec (use this)
│   ├── raw_spec_localnet.json      # Multi-validator local testnet
│   └── raw_spec_localnet_single.json # Single-validator dev mode
├── scripts/
│   ├── build.sh                    # Build production binary
│   ├── build_all_chainspecs.sh    # Generate chain specs with genesis preservation
│   ├── localnet.sh                 # Start local test network (Alice + Bob)
│   ├── generate_keys.sh            # Interactive validator key generation
│   ├── docker_entrypoint.sh        # Docker container entrypoint
│   └── node_keys/                  # Generated validator keys (gitignored)
├── Dockerfile                       # Production-ready Docker image
├── docker-compose.yml              # Multi-node Docker deployment
└── rust-toolchain.toml             # Rust toolchain configuration
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

## 🚀 Quick Start

### Prerequisites

- Rust toolchain (stable)
- Docker (optional, for containerized deployment)
- Git

### Local Development

```bash
# Clone the repository
git clone https://github.com/qx-ventures/qxchain.git
cd qxchain

# Build the node
cargo build --release

# Generate chain specifications
./scripts/build_all_chainspecs.sh

# Run single-node development chain
./target/release/qxchain \
  --chain=localnet_single \
  --alice \
  --base-path /tmp/alice \
  --unsafe-force-node-key-generation
```

Access the chain at `ws://localhost:9944`

### Local Testnet (Alice + Bob)

```bash
# Build and start 2-validator local network
./scripts/localnet.sh

# Or without rebuilding
./scripts/localnet.sh --no-purge
```

This starts two validator nodes (Alice and Bob) on:
- Alice: `ws://localhost:9944`
- Bob: `ws://localhost:9945`

## 🐳 Docker Deployment

### Production Image

```bash
# Build production image
docker build --target qxchain -t qxchain:latest .

# Run with mainnet chain spec
docker run -d \
  -p 30333:30333 \
  -p 9933:9933 \
  -p 9944:9944 \
  -v qxchain-data:/data \
  qxchain:latest \
  --base-path /data \
  --chain /home/qxchain/chainspecs/raw_spec_mainnet.json \
  --validator \
  --name "My Validator"
```

### Docker Compose (Multi-Node)

```bash
# Start 4-node network
docker-compose up -d

# View logs
docker-compose logs -f

# Stop network
docker-compose down
```

See [DOCKER.md](DOCKER.md) for detailed Docker documentation.

## 🔐 Production Deployment

### 1. Generate Validator Keys

```bash
# Interactive key generation tool
./scripts/generate_keys.sh
```

This will:
1. Install `subkey` (via Cargo or Docker)
2. Generate Aura (SR25519) and Grandpa (Ed25519) keys
3. Save keys to `scripts/node_keys/{validator-name}_{timestamp}.txt`
4. Provide chain spec code snippets and key insertion commands

**IMPORTANT**: Keep generated key files secure and never commit them to version control!

### 2. Add Validators to Chain Spec

Edit `node/src/chain_spec/mainnet.rs` and add your validator keys:

```rust
authority_keys_from_ss58(
    "5YourAuraPublicKey...",     // Aura (SR25519)
    "5YourGrandpaPublicKey...",  // Grandpa (Ed25519)
),
```

### 3. Rebuild Chain Specifications

```bash
# Regenerate chain specs with new validators
./scripts/build_all_chainspecs.sh
```

This preserves genesis blocks across updates to prevent chain forks.

### 4. Deploy Validator Nodes

Each validator must:

1. **Run the node**:
   ```bash
   ./target/production/qxchain \
     --chain chainspecs/raw_spec_mainnet.json \
     --validator \
     --base-path /data \
     --name "Validator-01"
   ```

2. **Insert keys** (from generated key file):
   ```bash
   # Insert Aura key
   curl -H "Content-Type: application/json" \
     --data '{"jsonrpc":"2.0","method":"author_insertKey","params":["aura","your secret phrase","0xYourPublicKey"],"id":1}' \
     http://localhost:9944

   # Insert Grandpa key
   curl -H "Content-Type: application/json" \
     --data '{"jsonrpc":"2.0","method":"author_insertKey","params":["gran","your secret phrase","0xYourPublicKey"],"id":1}' \
     http://localhost:9944
   ```

3. **Restart node** to activate validator

## 🔗 Chain Specifications

QXChain supports three network configurations:

- **mainnet**: Production network with 4 validators (Proof of Authority)
- **localnet**: Multi-validator local testnet (Alice + Bob)
- **localnet_single**: Single-validator development mode (Alice only)

### Chain Spec Files

Chain specifications are stored in the `chainspecs/` directory:

- `raw_spec_*.json` - Raw format for nodes (use this)
- `plain_spec_*.json` - Human-readable format for inspection

### Updating Chain Specs

```bash
# Rebuild all chain specs (preserves genesis)
./scripts/build_all_chainspecs.sh
```

This script:
- Builds the node in debug mode
- Generates new chain specs
- Preserves existing genesis blocks to prevent forks
- Outputs both raw and plain formats

## 🔗 Interacting with the Chain

To interact with the blockchain (run workers, submit requests, validate results), use the **QX Chain Connect** CLI tool:

https://github.com/qx-ventures/qxchain_connect

## 🛠️ Development

### Build Scripts

```bash
# Build production binary with LTO
./scripts/build.sh

# Build for development
cargo build --release

# Build specific components
cd node && cargo build --release
cd runtime && cargo build --release
cd pallets/pallet-qx-ai && cargo build --release
```

### Testing

```bash
# Run all tests
cargo test

# Run specific pallet tests
cargo test -p pallet-qx-ai

# Run with output
cargo test -- --nocapture
```

### Chain Spec Development

Chain specifications are located in `node/src/chain_spec/`:

- `mod.rs` - Common utilities (key generation helpers)
- `mainnet.rs` - Production network configuration
- `localnet.rs` - Local testnet configuration

After modifying chain specs, rebuild them:

```bash
./scripts/build_all_chainspecs.sh
```

## 🔍 Monitoring

### Polkadot.js Apps UI

Connect to your node using Polkadot.js Apps:

```bash
# Run UI in Docker
docker run --rm -p 80:80 -e WS_URL=ws://localhost:9944 jacogr/polkadot-js-apps:latest
```

Access at http://localhost

Or use the hosted version at https://polkadot.js.org/apps and connect to `ws://localhost:9944`

### Node Telemetry

QXChain nodes expose Prometheus metrics on port 9615:

```bash
# View metrics
curl http://localhost:9615/metrics
```

## 🔧 Troubleshooting

### Worker Registration Fails with "InsufficientBalance"

**Problem**: Worker fails to register with error `InsufficientBalance`

**Root Cause**: The worker account doesn't have enough tokens for staking

**Solution**: Each test account has exactly 1,000 tokens, which is the minimum required:
- Workers need minimum 1,000 tokens to stake
- Validators need minimum 100 tokens to stake
- Transaction fees are minimal (1 token per transaction)

**Pre-funded Test Accounts** (localnet only, each has 1,000 tokens):
- `//Alice` - Root/Sudo account
- `//Bob` - Default worker account
- `//Charlie` - Default validator account
- `//Dave`, `//Eve`, `//Ferdie` - Additional test accounts


## 📝 License

This project is licensed under MIT-0 License. See [LICENSE](LICENSE) for details.

## 📚 Learn More

- [Polkadot SDK Documentation](https://paritytech.github.io/polkadot-sdk/)
- [FRAME Framework](https://paritytech.github.io/polkadot-sdk/master/polkadot_sdk_docs/polkadot_sdk/frame_runtime/index.html)
- [Substrate Development](https://docs.substrate.io/)