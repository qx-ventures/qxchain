# Architecture

QX Chain has a three-layer architecture that separates blockchain consensus from AI verification.

## Consensus Layer

**AURA + GRANDPA Consensus (Proof of Authority)**
- Authority nodes secure the blockchain using AURA for block production and GRANDPA for finality
- Designed for permissioned networks with pre-selected authority validators
- Mainnet runs with 4 production validators
- Standard Substrate consensus nodes (NOT AIWorkers/AIValidators)

## Application Layer

**AIWorkers**: Civic entities (e.g., zoo department, parks office) that run off-chain AI inference using domain-specific models. They:
- Register services on-chain with metadata (service type, model hash, stake collateral)
- Submit cryptographic commitments immediately after inference
- Stake collateral to ensure honest behavior

**AIValidators**: Independent entities that audit worker submissions during 7-day challenge windows. They:
- Reproduce inference using committed model hash and input
- Compare outputs to detect discrepancies
- Submit challenges if errors are found
- Earn rewards for successful challenges

## AI Verification Protocol

QX introduces an **optimistic worker-validator verification protocol** that operates at the application layer, separate from blockchain consensus.

### How It Works

1. **Immediate Submission**: AIWorkers perform AI inference off-chain and immediately submit cryptographic commitments on-chain
2. **Challenge Window**: AIValidators have a 7-day challenge window to audit and dispute incorrect submissions
3. **Stake-Based Resolution**: If over 51% of validators reject a submission, the worker's stake is slashed and the result marked invalid
4. **Economic Security**: Challenge-based validation with stake slashing ensures honest participation

### Key Parameters

- **Challenge Period**: 7 days (100,800 blocks at 6-second block time)
- **Slash Threshold**: 51% of total validator stake weight
- **MinAIWorkerStake**: 1 token (configurable in runtime)
- **MinChallengeStake**: 1 token (configurable in runtime)

## Workflow

1. **Worker Registration**: AI workers stake tokens and register on-chain with status tracking
2. **Request Submission**: Customers submit inference requests to specific workers
3. **Queue Management**: Workers maintain queues of pending requests (max 100 per worker)
4. **Inference Processing**: Workers process requests and submit results to blockchain
5. **Challenge Period**: Validators can challenge incorrect inferences within 7 days
6. **Validation**: Consensus determines if inference is correct
7. **Rewards/Slashing**: Honest participants earn rewards, malicious actors are slashed

## Request Lifecycle

1. **Queued**: Request submitted to worker's queue
2. **Assigned**: Request assigned to worker for processing
3. **Completed**: Result submitted to blockchain with 7-day challenge period
4. **Pending**: Awaiting potential validator challenges during dispute window
5. **Challenged**: Under dispute by validators (if challenged)
6. **Finalized**: Challenge period passed, result accepted as valid
7. **Slashed**: Challenge succeeded, worker penalized and banned

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