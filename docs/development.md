# Development Guide

Guide for developers working on QXChain.

## Prerequisites

- **Rust**: Stable toolchain (managed by `rust-toolchain.toml`)
- **Git**: For version control
- **Docker**: Optional, for containerized testing
- **Subkey**: Substrate key generation tool

## Project Setup

```bash
# Clone repository
git clone https://github.com/qx-ventures/qxchain.git
cd qxchain

# Rust toolchain will be automatically installed based on rust-toolchain.toml
# Build the node
cargo build --release
```

## Building

### Development Build

```bash
# Fast build for testing
cargo build

# With all features
cargo build --all-features
```

### Production Build

```bash
# Optimized build with LTO
cargo build --profile production

# Or use the build script
./scripts/build.sh
```

### Building Specific Components

```bash
# Build only the node
cargo build -p qxchain --release

# Build only the runtime
cargo build -p qxchain-runtime --release

# Build only the AI pallet
cargo build -p pallet-qx-ai --release
```

## Testing

### Run All Tests

```bash
cargo test
```

### Run Specific Pallet Tests

```bash
# AI pallet tests
cargo test -p pallet-qx-ai

# With output
cargo test -p pallet-qx-ai -- --nocapture

# Specific test
cargo test -p pallet-qx-ai test_worker_registration
```

### Runtime Tests

```bash
cargo test -p qxchain-runtime
```

## Local Development Networks

### Single-Node Development Chain

Quick setup for testing:

```bash
./target/release/qxchain \
  --dev \
  --base-path /tmp/dev \
  --unsafe-force-node-key-generation
```

Access at `ws://localhost:9944`

### Two-Validator Local Network

Using the automated script:

```bash
# Build and start
./scripts/localnet.sh

# Start without rebuilding
./scripts/localnet.sh --no-purge
```

This starts:
- **Alice** (validator): `ws://localhost:9944`
- **Bob** (validator): `ws://localhost:9945`

### Manual Multi-Node Setup

```bash
# Node 1 (Alice)
./target/release/qxchain \
  --chain=localnet \
  --alice \
  --base-path /tmp/alice \
  --port 30333 \
  --rpc-port 9944 \
  --unsafe-force-node-key-generation

# Node 2 (Bob) - in another terminal
./target/release/qxchain \
  --chain=localnet \
  --bob \
  --base-path /tmp/bob \
  --port 30334 \
  --rpc-port 9945 \
  --bootnodes /ip4/127.0.0.1/tcp/30333/p2p/<ALICE_PEER_ID>
```

## Chain Specifications

### Modifying Chain Specs

Chain spec source files are in `node/src/chain_spec/`:

- `mod.rs` - Common utilities
- `mainnet.rs` - Production network
- `localnet.rs` - Local test network

After modifying, rebuild:

```bash
./scripts/build_all_chainspecs.sh
```

### Creating Custom Chain Spec

```bash
# Generate plain spec
./target/release/qxchain build-spec --chain mainnet > custom_spec.json

# Edit custom_spec.json as needed

# Convert to raw format
./target/release/qxchain build-spec --chain custom_spec.json --raw > custom_spec_raw.json

# Use it
./target/release/qxchain --chain custom_spec_raw.json
```

## Pallet Development

### Adding a New Pallet

1. Create pallet directory:
```bash
mkdir -p pallets/pallet-my-feature
cd pallets/pallet-my-feature
cargo init --lib
```

2. Add to workspace `Cargo.toml`:
```toml
[workspace]
members = [
    "node",
    "runtime",
    "pallets/pallet-qx-ai",
    "pallets/pallet-my-feature",  # Add this
]
```

3. Add dependency to runtime `Cargo.toml`

4. Add to runtime construct macro in `runtime/src/lib.rs`

### Pallet Structure

```rust
#[frame_support::pallet]
pub mod pallet {
    use frame_support::pallet_prelude::*;
    use frame_system::pallet_prelude::*;

    #[pallet::config]
    pub trait Config: frame_system::Config {
        type RuntimeEvent: From<Event<Self>> + IsType<<Self as frame_system::Config>::RuntimeEvent>;
    }

    #[pallet::pallet]
    pub struct Pallet<T>(_);

    #[pallet::storage]
    pub type MyStorage<T> = StorageValue<_, u32, ValueQuery>;

    #[pallet::event]
    #[pallet::generate_deposit(pub(super) fn deposit_event)]
    pub enum Event<T: Config> {
        SomethingHappened { value: u32 },
    }

    #[pallet::error]
    pub enum Error<T> {
        InvalidInput,
    }

    #[pallet::call]
    impl<T: Config> Pallet<T> {
        #[pallet::weight(10_000)]
        pub fn do_something(origin: OriginFor<T>, value: u32) -> DispatchResult {
            let _who = ensure_signed(origin)?;
            MyStorage::<T>::put(value);
            Self::deposit_event(Event::SomethingHappened { value });
            Ok(())
        }
    }
}
```

## Runtime Upgrades

### Building New Runtime

```bash
# Build WASM runtime
cargo build --release -p qxchain-runtime

# Runtime WASM is at:
# target/release/wbuild/qxchain-runtime/qxchain_runtime.wasm
```

### Testing Runtime Upgrade

1. Increment `spec_version` in `runtime/src/lib.rs`
2. Build new runtime
3. Submit via sudo:

```bash
# Using polkadot.js
# 1. Go to Developer -> Sudo
# 2. Select: system.setCode(code)
# 3. Upload: target/release/wbuild/qxchain-runtime/qxchain_runtime.compact.compressed.wasm
```

## Code Quality

### Format Code

```bash
cargo fmt --all
```

### Linting

```bash
cargo clippy --all-targets --all-features
```

### Check Without Building

```bash
cargo check
```

## Benchmarking

### Run Benchmarks

```bash
# Build with benchmarking feature
cargo build --release --features runtime-benchmarks

# Run specific pallet benchmarks
./target/release/qxchain benchmark pallet \
  --chain=dev \
  --pallet=pallet_qx_ai \
  --extrinsic='*' \
  --steps=50 \
  --repeat=20 \
  --output=pallets/pallet-qx-ai/src/weights.rs
```

## Debugging

### Enable Debug Logging

```bash
RUST_LOG=debug ./target/release/qxchain --dev
```

### Specific Module Logging

```bash
# Log only AI pallet
RUST_LOG=pallet_qx_ai=debug ./target/release/qxchain --dev

# Multiple modules
RUST_LOG=pallet_qx_ai=debug,runtime=trace ./target/release/qxchain --dev
```

### Backtrace

```bash
RUST_BACKTRACE=1 ./target/release/qxchain --dev
```

## Interacting with the Chain

### Using QXChain Connect CLI

The primary tool for interacting with the chain:

https://github.com/qx-ventures/qxchain_connect

### Using Polkadot.js Apps

```bash
# Run UI locally
docker run --rm -p 80:80 jacogr/polkadot-js-apps:latest
```

Then connect to `ws://localhost:9944`

Or use hosted version: https://polkadot.js.org/apps

### Using Curl

```bash
# Query system info
curl -H "Content-Type: application/json" \
  -d '{"id":1, "jsonrpc":"2.0", "method":"system_properties"}' \
  http://localhost:9944

# Query chain head
curl -H "Content-Type: application/json" \
  -d '{"id":1, "jsonrpc":"2.0", "method":"chain_getHead"}' \
  http://localhost:9944
```

## Git Workflow

### Branch Strategy

- `master` - Stable production code
- `develop` - Integration branch
- `feature/*` - Feature branches
- `fix/*` - Bug fix branches

### Commit Messages

Follow conventional commits:

```
feat: add worker queue limit
fix: correct KILT credential verification
docs: update deployment guide
refactor: simplify chain spec generation
test: add worker authorization tests
```

## CI/CD

The project uses GitHub Actions for:
- Building on multiple platforms
- Running tests
- Linting and formatting checks
- Docker image builds

## Performance Profiling

### Using `perf`

```bash
# Build with debug symbols
cargo build --release --profile production-with-debug

# Run with perf
perf record -g ./target/production/qxchain --dev

# Analyze
perf report
```

### Using `cargo-flamegraph`

```bash
# Install
cargo install flamegraph

# Generate flamegraph
cargo flamegraph --bin qxchain -- --dev
```

## Useful Resources

- [Substrate Documentation](https://docs.substrate.io/)
- [FRAME Documentation](https://paritytech.github.io/polkadot-sdk/master/polkadot_sdk_docs/polkadot_sdk/frame_runtime/index.html)
- [Polkadot SDK Docs](https://paritytech.github.io/polkadot-sdk/)
- [Rust Book](https://doc.rust-lang.org/book/)