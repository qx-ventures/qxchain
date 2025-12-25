# QXChain Power Measurement Suite

Comprehensive power/energy measurement tests for QXChain blockchain functions using Intel RAPL (Running Average Power Limit).

## Test Overview

| # | Test Name | Category | Description |
|---|-----------|----------|-------------|
| 01 | `idle_baseline` | Baseline | System idle with chain running, minimal activity between blocks |
| 02 | `idle_consensus_running` | Baseline | Chain running normally with consensus active, no external load |
| 03 | `block_production_aura` | Consensus | Measures power during AURA block authoring (new blocks created every ~6s) |
| 04 | `finalization_grandpa` | Consensus | Measures power during GRANDPA block finalization process |
| 05 | `tx_pool_pending` | Transaction Pool | Continuous `author_pendingExtrinsics` queries (~50 req/s) |
| 06 | `account_info_query` | Account | Account nonce queries via `AccountNonceApi_account_nonce` runtime call |
| 07 | `balance_query` | Account | Direct storage reads for Alice & Bob account balances |
| 08 | `state_read_simple` | State Storage | Simple `state_getStorage` reads with minimal key |
| 09 | `state_read_keys` | State Storage | `state_getKeys` queries for System pallet storage keys |
| 10 | `state_runtime_version` | State Storage | `state_getRuntimeVersion` queries |
| 11 | `chain_get_block` | Chain Query | Full block retrieval: get hash then `chain_getBlock` |
| 12 | `chain_get_header` | Chain Query | Block header queries via `chain_getHeader` |
| 13 | `rpc_metadata_fetch` | RPC | Heavy `state_getMetadata` calls (returns full chain metadata ~500KB) |
| 14 | `rpc_system_info` | RPC | System queries: `system_health`, `system_peers`, `system_version`, `system_chain` |
| 15 | `runtime_api_calls` | Runtime API | Runtime API calls: `Core_version` and `Metadata_metadata` |
| 16 | `mixed_workload` | Mixed | Combined realistic workload simulating typical dApp usage |

## Detailed Test Descriptions

### Baseline Tests (01-02)

**`idle_baseline`**
- Measures system power with chain running but no external RPC load
- Captures baseline power consumption during normal block intervals
- Used as reference point for comparing other tests

**`idle_consensus_running`**
- Second baseline measurement to ensure consistency
- Both baseline tests should show similar power levels
- Any significant difference indicates measurement variance

### Consensus Tests (03-04)

**`block_production_aura`**
- AURA (Authority Round) is the block authoring mechanism
- Measures power during the cycle of proposing and producing new blocks
- Block time is approximately 6 seconds in QXChain
- Captures periodic spikes when new blocks are authored

**`finalization_grandpa`**
- GRANDPA (GHOST-based Recursive Ancestor Deriving Prefix Agreement) handles finalization
- Measures power during block finalization voting
- Finalization may lag behind block production by a few blocks

### Transaction Pool Tests (05)

**`tx_pool_pending`**
- Queries `author_pendingExtrinsics` at ~50 requests/second
- Tests the performance of transaction pool queries
- RPC calls made: `author_pendingExtrinsics`
- **Approx. 500 RPC calls** during test

### Account & Balance Tests (06-07)

**`account_info_query`**
- Queries account nonce via runtime API call
- Uses `AccountNonceApi_account_nonce` with Alice's public key
- Tests runtime API execution overhead
- **Approx. 300-500 RPC calls** during test

**`balance_query`**
- Direct state storage reads for account balances
- Queries both Alice and Bob accounts each iteration
- Storage key: `System.Account` storage map
- **Approx. 500-800 RPC calls** (2 per iteration)

### State Storage Tests (08-10)

**`state_read_simple`**
- Minimal storage read with empty key prefix
- Tests baseline state query overhead
- **Approx. 500 RPC calls** during test

**`state_read_keys`**
- Queries storage keys for System pallet (`0x26aa394eea5630e07c48ae0c9558cef7`)
- Returns list of storage keys matching prefix
- More expensive than simple reads
- **Approx. 300-500 RPC calls** during test

**`state_runtime_version`**
- Fetches runtime version information
- Returns spec version, impl version, APIs, etc.
- **Approx. 500 RPC calls** during test

### Chain Query Tests (11-12)

**`chain_get_block`**
- Two-step process: get block hash, then fetch full block
- Returns complete block with header and extrinsics
- **Approx. 250-400 RPC calls** (2 per iteration)

**`chain_get_header`**
- Lightweight header-only queries
- Returns block number, parent hash, state root, extrinsics root
- **Approx. 500 RPC calls** during test

### RPC Tests (13-14)

**`rpc_metadata_fetch`**
- Fetches full chain metadata (~500KB response)
- Most expensive RPC call - tests heavy serialization
- **Approx. 50-100 RPC calls** (slow due to response size)

**`rpc_system_info`**
- Multiple system queries per iteration:
  - `system_health` - node health status
  - `system_peers` - connected peers
  - `system_version` - node version
  - `system_chain` - chain name
- **Approx. 400-600 RPC calls** (4 per iteration)

### Runtime API Tests (15)

**`runtime_api_calls`**
- Direct runtime API calls via `state_call`:
  - `Core_version` - core runtime version
  - `Metadata_metadata` - runtime metadata
- Tests WebAssembly execution overhead
- **Approx. 200-400 RPC calls** (2 per iteration)

### Mixed Workload Test (16)

**`mixed_workload`**
- Simulates realistic dApp usage pattern
- Each iteration executes:
  1. `chain_getHeader` - check latest block
  2. `system_health` - health check
  3. `state_getRuntimeVersion` - version check
  4. `author_pendingExtrinsics` - pending tx check
- 10ms sleep between iterations
- **Approx. 1,000-1,500 RPC calls** total (4 per iteration, ~10 iterations/second over 10s)

## Measurement Details

### Sampling Configuration
- **Sample interval**: 100ms
- **Samples per test**: 100
- **Total test duration**: ~10 seconds per function
- **Full suite duration**: ~3 minutes (16 tests)

### Metrics Collected

Each CSV file contains:

| Column | Description |
|--------|-------------|
| `timestamp_ns` | Unix timestamp in nanoseconds |
| `elapsed_ms` | Milliseconds since test start |
| `block` | Current best block number |
| `finalized` | Current finalized block number |
| `pkg_uj` | Cumulative package energy (microjoules) |
| `core_uj` | Cumulative core energy (microjoules) |
| `delta_pkg_uj` | Package energy delta since last sample |
| `delta_core_uj` | Core energy delta since last sample |
| `pkg_mw` | Instantaneous package power (milliwatts) |
| `core_mw` | Instantaneous core power (milliwatts) |

### Power Domains

- **Package Power**: Total CPU package power including cores, cache, memory controller
- **Core Power**: CPU cores only (compute-bound workload indicator)
