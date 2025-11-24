# Architecture

QX Chain has a two-layer architecture that separates blockchain consensus from permissioned AI execution.

## Consensus Layer

**AURA + GRANDPA Consensus (Proof of Authority)**
- Authority nodes secure the blockchain using AURA for block production and GRANDPA for finality
- Designed for permissioned networks with pre-selected authority validators
- Mainnet runs with 4 production validators

## Application Layer

**AIWorkers**: Trusted civic entities (e.g., zoo department, parks office) that run off-chain AI inference using allowed models. They:
- Must possess verified KILT credentials (DIDs) to register
- Credentials are issued by trusted attestors (city authorities, civic organizations)
- Run inference using HuggingFace models from the allowed registry
- Submit inference results directly to the blockchain

## Identity & Permission Protocol

QX uses **KILT-based credential verification** - a decentralized identity system that operates at the application layer, separate from blockchain consensus.

### How It Works

1. **Credential Issuance**: Civic entities receive KILT credentials from trusted attestors (e.g., city government)
2. **Worker Registration**: AIWorkers register on-chain by presenting valid KILT credentials
3. **Credential Verification**: The `pallet-qx-kilt-permissions` pallet verifies worker credentials on-chain
4. **Request Processing**: Only workers with valid credentials can receive and process inference requests
5. **Inference Submission**: Workers submit results directly
6. **Trust Model**: Trust is established through credential verification at the identity layer

### Key Components

- **KILT DIDs**: Decentralized identifiers for AIWorkers
- **Verifiable Credentials**: Attestations proving worker authorization
- **pallet-qx-kilt-permissions**: On-chain credential verification

### Allowed Models

Workers must use models from the allowed registry (hardcoded in runtime, updated via governance):
- **Model 0**: TinyLlama/TinyLlama-1.1B-Chat-v1.0
- **Model 1**: meta-llama/Llama-3.2-1B
- (Additional models will be added)

Workers can only use models they are authorized for in their KILT credentials.

## Workflow

1. **Credential Issuance**: Civic entities receive KILT credentials from trusted attestors
2. **Worker Authorization**: AIWorkers verify their KILT credentials on-chain to gain authorization
3. **Request Submission**: Customers submit inference requests to specific authorized workers
4. **Queue Management**: Workers maintain queues of pending requests (max 100 per worker)
5. **Inference Processing**: Workers process requests off-chain using allowed models
6. **Result Submission**: Workers submit results directly to blockchain with their KILT DID
7. **Immediate Completion**: Results are immediately available

## Request Lifecycle

1. **Queued**: Request submitted to worker's queue
2. **Processing**: Worker processes the request off-chain
3. **Completed**: Result submitted to blockchain and immediately available to customer
4. **Failed**: Request fails if worker encounters an error

## Project Structure

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
│   ├── pallet-qx-ai/               # AI inference execution and request management
│   └── pallet-qx-kilt-permissions/ # KILT DID credential verification
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