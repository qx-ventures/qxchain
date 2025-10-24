# Architecture

QX Chain has a three-layer architecture that separates blockchain consensus from AI verification.

## Consensus Layer

**AURA + GRANDPA Consensus (Proof of Authority)**
- Authority nodes secure the blockchain using AURA for block production and GRANDPA for finality
- Designed for permissioned networks with pre-selected authority validators
- Mainnet runs with 4 production validators
- Standard Substrate consensus nodes (NOT AIWorkers/AIValidators)

## Application Layer

**AIWorkers**: Civic entities (e.g., zoo department, parks office) that run off-chain AI inference using allowed models. They:
- Register services on-chain with stake collateral
- Run inference using HuggingFace models from the allowed registry
- Capture SHA-256 hashes of logits at every token during generation
- Submit complete cryptographic proofs immediately after inference
- Stake collateral to ensure honest behavior

**AIValidators**: Independent entities that audit worker submissions by verifying random checkpoints. They:
- Download allowed models from HuggingFace on-demand
- Select random checkpoints (5-10% of tokens) to verify
- Re-run inference up to each checkpoint and compare logit hashes
- Submit challenges if mismatches are found
- Economic incentive: validators with stake weight > 51% can slash dishonest workers

## AI Verification Protocol

QX uses **logit-based verification** - a cryptographic proof system that operates at the application layer, separate from blockchain consensus.

### How It Works

1. **Inference with Proof Generation**: AIWorkers run AI inference using allowed HuggingFace models and capture SHA-256 hashes of logits at every token
2. **Immediate Submission**: Workers submit the generated output along with complete cryptographic proof on-chain (result available immediately)
3. **Checkpoint Validation**: AIValidators download required models and verify random checkpoints (typically 5-10% of tokens)
4. **Challenge Period**: Validators have a configurable window to audit and dispute incorrect submissions
5. **Stake-Based Resolution**: If over 51% of validators find mismatches, the worker's stake is slashed
6. **Economic Security**: Cryptographic proofs combined with stake slashing ensures honest participation

### Key Parameters

- **Challenge Period**: Configurable in blocks (default: 100,800 blocks = 7 days at 6-second block time)
- **Checkpoint Percentage**: 5-10% of tokens verified (10-20x cheaper than full re-generation)
- **Slash Threshold**: 51% of total validator stake weight
- **MinAIWorkerStake**: 1 token (configurable in runtime)
- **MinChallengeStake**: 1 token (configurable in runtime)

### Allowed Models

Workers must use models from the allowed registry (hardcoded in runtime, updated via governance):
- **Model 0**: TinyLlama/TinyLlama-1.1B-Chat-v1.0
- **Model 1**: meta-llama/Llama-3.2-1B
- (Additional models will be added)

Validators download models on-demand from HuggingFace for verification.

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