# QX Chain - Verifiable AI Inference

QX Chain is a Substrate-based blockchain designed as the infrastructure for verifiable AI execution. It provides blockchain infrastructure for cities, specializing in verifiable AI execution, identity management, and policy compliance.

QX introduces an **optimistic worker-validator verification protocol** that operates at the application layer, separate from blockchain consensus. AIWorkers perform AI inference off-chain and immediately submit cryptographic commitments on-chain. AIValidators have a 7-day challenge window to audit and dispute incorrect submissions. If over 51% of validators reject a submission, the worker's stake is slashed and the result marked invalid.

**Key Distinction**: AIWorkers and AIValidators are **application-layer entities**, The blockchain consensus is handled by standard Substrate NPoS nodes.

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
- Standard Substrate consensus nodes (NOT AIWorkers/AIValidators)

### Application Layer
- **AIWorkers**: Civic entities (e.g., zoo department, parks office) that run off-chain AI inference using domain-specific models. They register services on-chain with metadata (service type, model hash, stake collateral) and submit cryptographic commitments immediately after inference.
- **AIValidators**: Independent entities that audit worker submissions during 7-day challenge windows. They reproduce inference using committed model hash and input, then compare outputs. If discrepancy found, they submit challenges.


## 📁 Project Structure

```
qxchain/
├── node/                       # Blockchain node implementation
├── runtime/                    # Runtime logic and configuration
├── pallets/
│   └── pallet-qx-ai/          # Custom opML pallet
├── scripts/
│   └── build_chain.sh         # Build blockchain binary
├── zombienet.toml             # Multi-node test network (4 validators)
├── zombienet-single.toml      # Single-node development config/.
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

## 🔧 How to Run

**Install Zombienet:**
```bash
# macOS
curl -L -o zombienet https://github.com/paritytech/zombienet/releases/latest/download/zombienet-macos
chmod +x zombienet
sudo xattr -d com.apple.quarantine zombienet
sudo mv zombienet /usr/local/bin/

# Linux
curl -L -o zombienet https://github.com/paritytech/zombienet/releases/latest/download/zombienet-linux-x64
chmod +x zombienet
sudo mv zombienet /usr/local/bin/
```

**Build and run:**
```bash
# Build the blockchain binary
cargo build --release

# Generate chain specification files (required before first run)
./scripts/build_chain_specs.sh

# Single node (quick testing)
zombienet spawn --provider native zombienet-single.toml

# Multi-node network (4 validators)
zombienet spawn --provider native zombienet.toml
```

Pre-funded test accounts: Alice, Bob, Charlie, Dave, Eve, Ferdie
Network endpoint: `ws://localhost:9944`

## 🔗 Interacting with the Chain

To interact with the blockchain (run workers, submit requests, validate results), use the **QX Chain Connect** CLI tool:

https://github.com/qx-ventures/qxchain_connect

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

## 🔍 Monitoring

### Polkadot UI

Run the Polkadot.js Apps UI to interact with the chain:
```bash
docker run --name polkadot-ui -e WS_URL=ws://localhost:9944 -p 80:80 jacogr/polkadot-js-apps:latest
```

Access the UI at http://localhost


## 🔧 Troubleshooting

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
