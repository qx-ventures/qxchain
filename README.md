# QX Chain - Permissioned AI Inference

QX Chain is a Substrate-based blockchain designed as the infrastructure for permissioned AI execution. It provides blockchain infrastructure for cities, specializing in credential-based AI execution, identity management, and policy compliance.

## Key Features

- **KILT-Based Permissioning**: AIWorkers must possess verified KILT credentials to operate on the network.
- **Decentralized Identity**: Worker authorization via KILT DIDs ensures trusted civic entities.
- **Off-Chain Computation, On-Chain Registry**: Heavy AI inference executes off-chain while only worker credentials and status are tracked on-chain.
- **Application Layer Architecture**: AIWorkers are application-layer entities verified through KILT credentials. Blockchain consensus uses AURA + GRANDPA (Proof of Authority).
## Quick Start

### Prerequisites

- Rust toolchain (stable)
- Docker (optional, for containerized deployment)
- Git

### Local Development

```bash
# Clone and build
git clone https://github.com/qx-ventures/qxchain.git
cd qxchain
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

### Local Testnet

```bash
# Start 2-validator network (Alice + Bob)
./scripts/localnet.sh
```

- Alice: `ws://localhost:9944`
- Bob: `ws://localhost:9945`

## Docker Development 

```bash
# Build development image
docker build --target qxchain-local -t qxchain:local .

# Run validator
docker run -d \
  -p 30333:30333 \
  -p 9944:9944 \
  -v qxchain-data:/data \
  qxchain:local \
  --base-path /data \
  --chain /home/qxchain/chainspecs/raw_spec_localnet.json \
  --validator \
  --name "My Validator"
```

## Docker Deployment

```bash
# Build production image
docker build --platform linux/amd64 --target qxchain-production -t qxchain:production .

# Run validator
docker run -d \
  -p 30333:30333 \
  -p 9944:9944 \
  -v qxchain-data:/data \
  qxchain:production \
  --base-path /data \
  --chain /home/qxchain/chainspecs/raw_spec_mainnet.json \
  --validator \
  --name "My Validator"
```

> **⚠️ macOS Compatibility Note**: When running linux/amd64 containers on macOS (Apple Silicon or Intel), peer-to-peer connectivity between nodes may not work properly due to architecture emulation. This is a known limitation of cross-platform container networking. For local multi-node testing on macOS, consider using native builds or running nodes on the same architecture.

## Production Deployment

See [docs/production-deployment.md](docs/production-deployment.md) for complete production deployment guide.

Quick steps:
1. Generate validator keys: `./scripts/generate_keys.sh`
2. Update chain spec with your validator keys in `node/src/chain_spec/mainnet.rs`
3. Rebuild chain specs: `./scripts/build_all_chainspecs.sh` (removes existing specs and creates fresh ones)
4. Deploy validator nodes
5. Insert keys via RPC
6. Monitor and verify

## Interacting with the Chain

To interact with the blockchain (run workers, submit requests, validate results), use the **QX Chain Connect** CLI tool:

https://github.com/qx-ventures/qxchain_connect

## Documentation

- [Architecture](docs/architecture.md) - System architecture and workflow
- [Production Deployment](docs/production-deployment.md) - Complete deployment guide
- [Docker](docs/docker.md) - Docker deployment and management
- [Development](docs/development.md) - Development guide and testing

## License

This project is licensed under MIT-0 License. See [LICENSE](LICENSE) for details.

## Learn More

- [Polkadot SDK Documentation](https://paritytech.github.io/polkadot-sdk/)
- [FRAME Framework](https://paritytech.github.io/polkadot-sdk/master/polkadot_sdk_docs/polkadot_sdk/frame_runtime/index.html)
- [Substrate Development](https://docs.substrate.io/)