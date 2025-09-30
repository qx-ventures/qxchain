# Node

ℹ️ A node - in Polkadot - is a binary executable, whose primary purpose is to execute the [runtime](../runtime/README.md).

🔗 It communicates with other nodes in the network, and aims for
[consensus](https://wiki.polkadot.network/docs/learn-consensus) among them.

⚙️ It acts as a remote procedure call (RPC) server, allowing interaction with the blockchain.

👉 Learn more about the architecture, and a difference between a node and a runtime
[here](https://paritytech.github.io/polkadot-sdk/master/polkadot_sdk_docs/reference_docs/wasm_meta_protocol/index.html).

## 🎯 QX Chain Node Features

The QX Chain node includes:

- **ML Worker Service**: Built-in AI worker that processes inference requests using Ollama
- **ML Validator Service**: Built-in validator that challenges incorrect inferences
- **Signature-Based Identity**: Workers and validators identified by transaction signatures
- **Native Backend Integration**: Direct state queries without HTTP RPC overhead
- **Activity Tracking**: Automatic tracking of worker/validator participation

## 🔧 Node Roles

Start the node with different roles using the `--node-role` flag:

```bash
# Start as worker
./target/release/qxchain --dev --node-role worker --ai-endpoint http://localhost:11434 --ai-model gemma3:1b

# Start as validator
./target/release/qxchain --dev --node-role validator --ai-endpoint http://localhost:11434 --ai-model gemma3:1b

# Start as full node (no ML services)
./target/release/qxchain --dev
```

## 📁 Important Files

- [`chain_spec.rs`](./src/chain_spec.rs): A chain specification is a source code file that defines the chain's
initial (genesis) state.
- [`service.rs`](./src/service.rs): This file defines the node implementation.
It's a place to configure consensus-related topics. In favor of minimalism, this template has no consensus configured.
- [`ml_worker.rs`](./src/ml_worker.rs): ML Worker implementation with signature-based identity
- [`ml_validator.rs`](./src/ml_validator.rs): ML Validator implementation with signature-based identity
- [`ai_client.rs`](./src/ai_client.rs): Ollama AI client for inference execution
- [`node_identity.rs`](./src/node_identity.rs): P2P node identity registry

## 🔐 Signature-Based Identity

Workers and validators in QX Chain use **signature-based identity**:

- **No Registration**: Nodes don't call registration extrinsics
- **Automatic Recognition**: Identity proven by signing transactions
- **Activity Tracking**: System tracks last active block for each participant
- **Permissionless**: Anyone with a keypair can participate immediately

### How It Works

1. Worker/validator starts with a keypair (e.g., `//Alice`, `//Bob`, `//Charlie`)
2. When submitting transactions, their signature proves their identity
3. Runtime automatically tracks their activity in `WorkerLastActivity` or `ValidatorLastActivity`
4. No upfront registration or staking required

## 🚀 Getting Started

See the main [README](../README.md) for complete setup and usage instructions.
