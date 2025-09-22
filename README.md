<div align="center">

# QX Chain

<img height="70px" alt="Polkadot SDK Logo" src="https://github.com/paritytech/polkadot-sdk/raw/master/docs/images/Polkadot_Logo_Horizontal_Pink_White.png#gh-dark-mode-only"/>

> QX Chain - A blockchain for optimistic machine learning based on Polkadot SDK.
>
> Built with Polkadot SDK for decentralized AI inference and validation.

</div>

## Table of Contents

- [Intro](#intro)

- [Template Structure](#template-structure)

- [Getting Started](#getting-started)

- [QX Chain Quick Start](#qx-chain-quick-start)

- [Starting QX Chain](#starting-qx-chain)

  - [Omni Node](#omni-node)
  - [QX Chain Node](#qx-chain-node)
  - [Zombienet with Omni Node](#zombienet-with-omni-node)
  - [Zombienet with QX Chain Node](#zombienet-with-qx-chain-node)
  - [Connect with the Polkadot-JS Apps Front-End](#connect-with-the-polkadot-js-apps-front-end)
  - [Takeaways](#takeaways)

- [Contributing](#contributing)

- [Getting Help](#getting-help)

## Intro

- 🧠 QX Chain is an optimistic machine learning blockchain for decentralized AI inference.

- 🔧 Its runtime is configured with custom pallets for ML workloads and standard pallets
such as a [Balances pallet](https://paritytech.github.io/polkadot-sdk/master/pallet_balances/index.html).

- 🤖 QX Chain supports AI model inference through workers and validators in a decentralized network.


## QX Chain Structure

QX Chain is a Polkadot SDK based project that consists of:

- 🧮 the [Runtime](./runtime/README.md) - the core logic of the blockchain.
- 🎨 the [Pallets](./pallets/README.md) - from which the runtime is constructed.
- 💿 a [Node](./node/README.md) - the binary application (which is not part of the cargo default-members list and is not
compiled unless building the entire workspace).

## Getting Started

- 🦀 The template is using the Rust language.

- 👉 Check the
[Rust installation instructions](https://www.rust-lang.org/tools/install) for your system.

- 🛠️ Depending on your operating system and Rust version, there might be additional
packages required to compile this template - please take note of the Rust compiler output.

Fetch QX Chain code.

```sh
git clone <qx-chain-repository-url> qxchain

cd qxchain
```

## QX Chain Quick Start

### Using QX Chain Scripts (Recommended)

For a complete QX Chain opML environment setup:

```bash
# Complete setup (one time)
./scripts/setup_qx_chain.sh

# Run services in separate terminals:
# Terminal 1
./scripts/start_chain.sh

# Terminal 2  
./scripts/start_worker.sh

# Terminal 3
./scripts/start_validator.sh
```

**Service Information:**
- **QX Chain**: `ws://localhost:9944`
- **Ollama API**: `http://localhost:11434`  
- **Worker API**: `http://localhost:8000`

**Test the setup:**
```bash
./scripts/test_inference.py
```

See [scripts/README.md](./scripts/README.md) for detailed script documentation.

## Starting QX Chain

### Omni Node

[Omni Node](https://paritytech.github.io/polkadot-sdk/master/polkadot_sdk_docs/reference_docs/omni_node/index.html) can
be used to run the QX Chain runtime. `polkadot-omni-node` binary crate usage is described at a high-level
[on crates.io](https://crates.io/crates/polkadot-omni-node).

#### Install `polkadot-omni-node`

Please see installation section on [crates.io/omni-node](https://crates.io/crates/polkadot-omni-node).

#### Build `qxchain-runtime`

```sh
cargo build -p qxchain-runtime --release
```

#### Install `staging-chain-spec-builder`

Please see the installation section at [`crates.io/staging-chain-spec-builder`](https://crates.io/crates/staging-chain-spec-builder).

#### Use chain-spec-builder to generate the chain_spec.json file

```sh
chain-spec-builder create --relay-chain "dev" --para-id 1000 --runtime \
    target/release/wbuild/qxchain-runtime/qxchain_runtime.wasm named-preset development
```

**Note**: the `relay-chain` and `para-id` flags are extra bits of information required to
configure the node for the case of representing a parachain that is connected to a relay chain.
They are not relevant to QX Chain business logic, but they are mandatory information for
Omni Node, nonetheless.

#### Run Omni Node

Start Omni Node in development mode (sets up block production and finalization based on manual seal,
sealing a new block every 3 seconds), with a QX Chain runtime chain spec.

```sh
polkadot-omni-node --chain <path/to/chain_spec.json> --dev
```

### QX Chain Node

#### Build both node & runtime

```sh
cargo build --workspace --release
```

🐳 Alternatively, build the docker image which builds all the workspace members,
and has as entry point the node binary:

```sh
docker build . -t qxchain
```

#### Start the `qxchain`

The `qxchain` has dependency on the `qxchain-runtime`. It will use
the `qxchain_runtime::WASM_BINARY` constant (which holds the WASM blob as a byte
array) for chain spec building, while starting. This is in contrast to Omni Node which doesn't
depend on a specific runtime, but asks for the chain spec at startup.

```sh
target/release/qxchain --tmp --consensus manual-seal-3000
# or via docker
docker run --rm qxchain
```

### Zombienet with Omni Node

#### Install `zombienet`

We can install `zombienet` as described [here](https://paritytech.github.io/zombienet/install.html#installation),
and `zombienet-omni-node.toml` contains the network specification we want to start.


#### Update `zombienet-omni-node.toml` with a valid chain spec path

To simplify the process of starting QX Chain with ZombieNet and Omni Node, we've included a
pre-configured development chain spec (dev_chain_spec.json) in QX Chain. The zombienet-omni-node.toml
file points to it, but you can update it to a new path for the chain spec generated on your machine.
To generate a chain spec refer to [staging-chain-spec-builder](https://crates.io/crates/staging-chain-spec-builder)

Then make the changes in the network specification like so:

```toml
# ...
chain = "dev"
chain_spec_path = "<TO BE UPDATED WITH A VALID PATH>"
default_args = ["--dev"]
# ..
```

#### Start the network

```sh
zombienet --provider native spawn zombienet-omni-node.toml
```

### Zombienet with `qxchain`

For this one we just need to have `zombienet` installed and run:

```sh
zombienet --provider native spawn zombienet-multi-node.toml
```

### Connect with the Polkadot-JS Apps Front-End

- 🌐 You can interact with your local node using the
hosted version of the [Polkadot/Substrate
Portal](https://polkadot.js.org/apps/#/explorer?rpc=ws://localhost:9944).

- 🪐 A hosted version is also
available on [IPFS](https://dotapps.io/).

- 🧑‍🔧 You can also find the source code and instructions for hosting your own instance in the
[`polkadot-js/apps`](https://github.com/polkadot-js/apps) repository.

### Takeaways

Previously QX Chain development chains:

- ❌ Started in a multi-node setup will produce forks because QX Chain lacks consensus.
- 🧹 Do not persist the state.
- 💰 Are pre-configured with a genesis state that includes several pre-funded development accounts.
- 🧑‍⚖️ One development account (`ALICE`) is used as `sudo` accounts.

## Contributing

- 🔄 QX Chain is built on the Polkadot SDK framework.

- ➡️ For QX Chain specific contributions, please check the project repository.

- 😇 Please refer to the monorepo's
[contribution guidelines](https://github.com/paritytech/polkadot-sdk/blob/master/docs/contributor/CONTRIBUTING.md) and
[Code of Conduct](https://github.com/paritytech/polkadot-sdk/blob/master/docs/contributor/CODE_OF_CONDUCT.md).

## Getting Help

- 🧑‍🏫 To learn about Polkadot in general, [docs.Polkadot.com](https://docs.polkadot.com/) website is a good starting point.

- 🧑‍🔧 For technical introduction, [here](https://github.com/paritytech/polkadot-sdk#-documentation) are
the Polkadot SDK documentation resources.

- 👥 Additionally, there are [GitHub issues](https://github.com/paritytech/polkadot-sdk/issues) and
[Substrate StackExchange](https://substrate.stackexchange.com/).
- 👥You can also reach out on the [Official Polkdot discord server](https://polkadot-discord.w3f.tools/)
- 🧑Reach out on [Telegram](https://t.me/substratedevs) for more questions and discussions
