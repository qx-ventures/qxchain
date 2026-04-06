# QX Chain API Reference

This document provides a comprehensive reference for all public APIs, extrinsics, storage queries, and RPC endpoints available in QX Chain.

## Table of Contents

- [Overview](#overview)
- [Runtime Information](#runtime-information)
- [Pallets](#pallets)
  - [QX AI Pallet](#qx-ai-pallet)
  - [QX KILT Permissions Pallet](#qx-kilt-permissions-pallet)
  - [QX Faucet Pallet](#qx-faucet-pallet)
- [RPC Endpoints](#rpc-endpoints)
- [Data Types](#data-types)
- [Configuration Parameters](#configuration-parameters)
- [Authentication Flow](#authentication-flow)

---

## Overview

QX Chain is a Substrate-based blockchain designed for permissioned AI execution infrastructure. It specializes in credential-based AI inference for civic applications with KILT-based worker authorization.

**Key Features:**
- KILT DID-based worker authentication
- AI inference request/response system
- Faucet for user onboarding
- Proof of Authority consensus (AURA + GRANDPA)

---

## Runtime Information

| Property | Value |
|----------|-------|
| Spec Name | `qxchain` |
| Spec Version | `103` |
| Block Time | 6 seconds |
| SS58 Prefix | 42 |
| Existential Deposit | 500 units |

### Core Types

```rust
BlockNumber = u32
Balance = u128
Nonce = u32
Hash = H256
AccountId = sr25519 public key
DidIdentifier = [u8; 32]
```

### Time Constants

| Duration | Blocks |
|----------|--------|
| 1 Minute | 10 |
| 1 Hour | 600 |
| 1 Day | 14,400 |

---

## Pallets

### QX AI Pallet

The core pallet for AI inference request management and execution.

**Pallet Index:** 8

#### Extrinsics

##### `submit_request`

Submit an AI inference request to a specific worker.

```rust
fn submit_request(
    origin: OriginFor<T>,
    target_worker: T::AccountId,
    prompt: BoundedVec<u8, ConstU32<2048>>,
    max_tokens: u32
) -> DispatchResult
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `target_worker` | `AccountId` | The worker to process the request |
| `prompt` | `Vec<u8>` | The inference prompt (max 2048 bytes) |
| `max_tokens` | `u32` | Maximum tokens for response |

**Requirements:**
- Caller must be signed
- Target worker must have valid credentials
- Worker queue must not be full (max 100 requests)

**Events:** `RequestSubmitted { request_id, customer, worker }`

---

##### `update_ai_worker_status`

Update the online/offline status of an AI worker.

```rust
fn update_ai_worker_status(
    origin: OriginFor<T>,
    online: bool
) -> DispatchResult
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `online` | `bool` | Whether the worker is available |

**Requirements:**
- Caller must be a credentialed worker
- **Fee:** FREE (no transaction fee)

**Events:** `AIWorkerStatusUpdated { worker, online }`

---

##### `submit_inference`

Submit the result of an AI inference request.

```rust
fn submit_inference(
    origin: OriginFor<T>,
    request_id: u32,
    output: BoundedVec<u8, ConstU32<4096>>
) -> DispatchResult
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `request_id` | `u32` | The request being fulfilled |
| `output` | `Vec<u8>` | The inference output (max 4096 bytes) |

**Requirements:**
- Caller must be the assigned worker
- Caller must have valid credentials
- Request must exist and be assigned
- **Fee:** FREE (no transaction fee)

**Events:** `InferenceSubmitted { inference_id, request_id, worker, worker_did }`

---

##### `add_allowed_model` (Root Only)

Add a model to the allowed models registry.

```rust
fn add_allowed_model(
    origin: OriginFor<T>,
    model_id: u32,
    model_name: BoundedVec<u8, ConstU32<128>>,
    model_hash: BoundedVec<u8, ConstU32<64>>
) -> DispatchResult
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_id` | `u32` | Unique model identifier |
| `model_name` | `Vec<u8>` | Human-readable model name (max 128 bytes) |
| `model_hash` | `Vec<u8>` | Model hash for verification (max 64 bytes) |

**Requirements:**
- Origin must be Root (sudo)

**Events:** `ModelAdded { model_id, model_name }`

---

#### Storage

| Storage Item | Key | Value | Description |
|--------------|-----|-------|-------------|
| `InferenceRequests` | `u32` | `InferenceRequest` | All submitted requests |
| `InferenceResults` | `u32` | `InferenceResult` | Completed inference results |
| `AIWorkerQueues` | `AccountId` | `BoundedVec<u32, 100>` | Request queue per worker |
| `AIWorkerStatus` | `AccountId` | `bool` | Worker online status |
| `AllowedModels` | `u32` | `AllowedModel` | Model registry |
| `RequestWorkerMap` | `u32` | `AccountId` | Request to worker mapping |
| `NextRequestId` | - | `u32` | Request ID counter |
| `NextInferenceId` | - | `u32` | Inference ID counter |

#### Errors

| Error | Description |
|-------|-------------|
| `AIWorkerNotFound` | Worker account not found |
| `InferenceNotFound` | Inference result not found |
| `RequestNotFound` | Request ID does not exist |
| `AIWorkerQueueFull` | Worker queue at max capacity (100) |
| `RequestAlreadyAssigned` | Request already being processed |
| `RequestNotAssigned` | Request not assigned to caller |
| `InvalidWorkerCredential` | Worker credential invalid or expired |
| `WorkerDIDNotFound` | Worker has no DID registered |

---

### QX KILT Permissions Pallet

Manages KILT-based decentralized identities and worker credentials.

**Pallet Index:** 7

#### Extrinsics

##### `set_governance_did` (Root Only)

Initialize the governance DID for credential issuance.

```rust
fn set_governance_did(
    origin: OriginFor<T>,
    did: DidIdentifier
) -> DispatchResult
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `did` | `[u8; 32]` | The governance DID identifier |

**Events:** `GovernanceDIDSet { did }`

---

##### `create_worker_did`

Create a decentralized identity for the calling account.

```rust
fn create_worker_did(
    origin: OriginFor<T>,
    name: Vec<u8>,
    description: Vec<u8>
) -> DispatchResult
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `Vec<u8>` | Worker name (max 128 bytes) |
| `description` | `Vec<u8>` | Worker description (max 512 bytes) |

**Requirements:**
- Caller must not already have a DID

**Events:** `WorkerDIDCreated { account, did }`

---

##### `issue_worker_credential` (Root Only)

Issue an AI worker credential to a DID.

```rust
fn issue_worker_credential(
    origin: OriginFor<T>,
    worker_did: DidIdentifier,
    models: Vec<ModelId>,
    validity_period: Option<BlockNumber>
) -> DispatchResult
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `worker_did` | `[u8; 32]` | Target worker's DID |
| `models` | `Vec<u32>` | List of allowed model IDs (max 100) |
| `validity_period` | `Option<u32>` | Credential validity in blocks (default: 30 days) |

**Events:** `WorkerCredentialIssued { did, expires_at }`

---

##### `revoke_worker_credential` (Root Only)

Permanently revoke a worker's credential.

```rust
fn revoke_worker_credential(
    origin: OriginFor<T>,
    worker_did: DidIdentifier
) -> DispatchResult
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `worker_did` | `[u8; 32]` | DID to revoke |

**Events:** `WorkerCredentialRevoked { did }`

---

##### `suspend_worker` (Root Only)

Temporarily suspend a worker's credential.

```rust
fn suspend_worker(
    origin: OriginFor<T>,
    worker_did: DidIdentifier,
    duration: Option<BlockNumber>
) -> DispatchResult
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `worker_did` | `[u8; 32]` | DID to suspend |
| `duration` | `Option<u32>` | Suspension duration in blocks (default: 1 day) |

**Events:** `WorkerSuspended { did, until }`

---

#### Storage

| Storage Item | Key | Value | Description |
|--------------|-----|-------|-------------|
| `WorkerDIDs` | `AccountId` | `WorkerDID` | Account to DID mapping |
| `WorkerCredentials` | `DidIdentifier` | `AIWorkerCredential` | DID credentials |
| `AccountToDID` | `AccountId` | `DidIdentifier` | Reverse lookup |
| `GovernanceDID` | - | `DidIdentifier` | System governance DID |

#### Errors

| Error | Description |
|-------|-------------|
| `WorkerDIDAlreadyExists` | Account already has a DID |
| `WorkerDIDNotFound` | DID not found |
| `WorkerCredentialNotFound` | No credential for DID |
| `InvalidCredentialIssuer` | Issuer not authorized |
| `CredentialExpired` | Credential past expiry |
| `CredentialSuspended` | Credential temporarily suspended |
| `CredentialRevoked` | Credential permanently revoked |
| `GovernanceDIDNotSet` | Governance DID not initialized |
| `AccountHasNoDID` | Account has no associated DID |

---

### QX Faucet Pallet

Token distribution system for user onboarding.

**Pallet Index:** 9

#### Extrinsics

##### `claim`

Claim tokens from the faucet.

```rust
fn claim(origin: OriginFor<T>) -> DispatchResult
```

**Requirements:**
- Must wait 24 hours (14,400 blocks) between claims
- Maximum 5 lifetime claims per account
- Faucet must have sufficient balance
- **Fee:** FREE (no transaction fee)

**Claim Amount:** 10 QX per claim

**Events:** `Claimed { who, amount }`

---

##### `fund_faucet`

Contribute tokens to the faucet pot.

```rust
fn fund_faucet(
    origin: OriginFor<T>,
    amount: T::Balance
) -> DispatchResult
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `amount` | `Balance` | Amount to contribute |

**Events:** `FaucetFunded { funder, amount }`

---

#### Storage

| Storage Item | Key | Value | Description |
|--------------|-----|-------|-------------|
| `LastClaim` | `AccountId` | `BlockNumber` | Last claim block per account |
| `ClaimCount` | `AccountId` | `u32` | Total lifetime claims per account |

#### Errors

| Error | Description |
|-------|-------------|
| `ClaimTooSoon` | Cooldown period not elapsed |
| `MaxClaimsReached` | Account reached 5 lifetime claims |
| `FaucetEmpty` | Faucet has insufficient balance |

#### Helper Functions

```rust
// Check remaining claims for an account
fn remaining_claims(account: &AccountId) -> u32

// Get current faucet balance
fn faucet_balance() -> Balance

// Check if account can claim
fn can_claim(account: &AccountId) -> bool
```

---

## RPC Endpoints

### Connection URLs

| Network | WebSocket | HTTP |
|---------|-----------|------|
| Local Dev | `ws://localhost:9944` | `http://localhost:9933` |
| Alice Node | `ws://localhost:9944` | `http://localhost:9933` |
| Bob Node | `ws://localhost:9945` | `http://localhost:9934` |

### Standard Substrate RPC Methods

#### System

| Method | Description |
|--------|-------------|
| `system_properties` | Get chain properties |
| `system_chain` | Get chain name |
| `system_name` | Get node name |
| `system_version` | Get node version |
| `system_health` | Get node health status |
| `system_accountNextIndex` | Get next nonce for account |

#### Chain

| Method | Description |
|--------|-------------|
| `chain_getHeader` | Get block header by hash |
| `chain_getBlock` | Get full block by hash |
| `chain_getBlockHash` | Get block hash by number |
| `chain_getFinalizedHead` | Get finalized block hash |
| `chain_subscribeAllHeads` | Subscribe to all new headers |
| `chain_subscribeFinalizedHeads` | Subscribe to finalized headers |

#### State

| Method | Description |
|--------|-------------|
| `state_getStorage` | Query storage at key |
| `state_getStorageAt` | Query storage at specific block |
| `state_getMetadata` | Get runtime metadata |
| `state_getRuntimeVersion` | Get runtime version |
| `state_subscribeStorage` | Subscribe to storage changes |
| `state_queryStorage` | Query storage changes over range |

#### Author

| Method | Description |
|--------|-------------|
| `author_submitExtrinsic` | Submit signed transaction |
| `author_pendingExtrinsics` | Get pending transactions |
| `author_insertKey` | Insert validator key (privileged) |
| `author_hasKey` | Check if key exists in keystore |

#### Payment

| Method | Description |
|--------|-------------|
| `payment_queryInfo` | Estimate transaction fee |
| `payment_queryFeeDetails` | Get detailed fee breakdown |

---

## Data Types

### InferenceRequest

```rust
pub struct InferenceRequest<AccountId> {
    pub customer: AccountId,
    pub target_worker: AccountId,
    pub prompt: BoundedVec<u8, ConstU32<2048>>,
    pub max_tokens: u32,
    pub status: RequestStatus,
    pub created_at: u32,
}

pub enum RequestStatus {
    Queued,
    Assigned,
    Completed,
    Failed,
}
```

### InferenceResult

```rust
pub struct InferenceResult<AccountId> {
    pub request_id: u32,
    pub worker: AccountId,
    pub worker_did: DidIdentifier,
    pub output: BoundedVec<u8, ConstU32<4096>>,
    pub status: InferenceStatus,
    pub submitted_at: u32,
}

pub enum InferenceStatus {
    Completed,
    Failed,
}
```

### WorkerDID

```rust
pub struct WorkerDID<AccountId, BlockNumber> {
    pub did: DidIdentifier,
    pub account: AccountId,
    pub metadata: WorkerMetadata<BlockNumber>,
    pub status: CredentialStatus<BlockNumber>,
}

pub struct WorkerMetadata<BlockNumber> {
    pub name: BoundedVec<u8, ConstU32<128>>,
    pub description: BoundedVec<u8, ConstU32<512>>,
    pub registered_at: BlockNumber,
}

pub enum CredentialStatus<BlockNumber> {
    Active,
    Suspended { until: BlockNumber },
    Revoked,
}
```

### AIWorkerCredential

```rust
pub struct AIWorkerCredential<BlockNumber> {
    pub issuer: DidIdentifier,
    pub subject: DidIdentifier,
    pub models: BoundedVec<ModelId, ConstU32<100>>,
    pub issued_at: BlockNumber,
    pub expires_at: Option<BlockNumber>,
}
```

### AllowedModel

```rust
pub struct AllowedModel {
    pub model_name: BoundedVec<u8, ConstU32<128>>,
    pub model_hash: BoundedVec<u8, ConstU32<64>>,
    pub active: bool,
}
```

---

## Configuration Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `MaxQueueSize` | 100 | Maximum requests per worker queue |
| `DripAmount` | 10 QX | Tokens per faucet claim |
| `ClaimCooldown` | 14,400 blocks (24h) | Time between faucet claims |
| `MaxClaimsPerAccount` | 5 | Lifetime faucet claims per account |
| `DefaultCredentialValidity` | 432,000 blocks (30 days) | Default credential expiry |
| `WorkerSuspensionPeriod` | 14,400 blocks (1 day) | Default suspension duration |
| `MaxAuthorities` | 32 | Maximum validators |
| `BlockHashCount` | 2,400 | Blocks of hash history retained |

---

## Authentication Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Worker Onboarding Flow                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. New User                                                    │
│     │                                                           │
│     ▼                                                           │
│  2. claim() ─────────────► Receive 10 QX (FREE, no fees)       │
│     │                                                           │
│     ▼                                                           │
│  3. create_worker_did(name, description)                        │
│     │                                                           │
│     ▼                                                           │
│  4. [Governance] issue_worker_credential(did, models)           │
│     │                                                           │
│     ▼                                                           │
│  5. update_ai_worker_status(true) ──► Worker Online (FREE)     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Inference Request Flow                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Customer                          Worker                       │
│     │                                 │                         │
│     │  submit_request(worker,         │                         │
│     │      prompt, max_tokens)        │                         │
│     │ ───────────────────────────────►│                         │
│     │                                 │                         │
│     │                          [Process request]                │
│     │                                 │                         │
│     │     submit_inference(           │                         │
│     │◄─────request_id, output)────────│ (FREE)                  │
│     │                                 │                         │
│     │  [Verify credential + Record result]                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Example Usage

### Using Polkadot.js API

```javascript
import { ApiPromise, WsProvider } from '@polkadot/api';

// Connect to local node
const provider = new WsProvider('ws://localhost:9944');
const api = await ApiPromise.create({ provider });

// Query worker status
const status = await api.query.qxAi.aIWorkerStatus(workerAddress);
console.log('Worker online:', status.toHuman());

// Query inference result
const result = await api.query.qxAi.inferenceResults(inferenceId);
console.log('Result:', result.toHuman());

// Submit a request
const tx = api.tx.qxAi.submitRequest(
  workerAddress,
  'What is the capital of France?',
  100
);
await tx.signAndSend(customerKeyPair);

// Claim from faucet (new user)
const claimTx = api.tx.qxFaucet.claim();
await claimTx.signAndSend(newUserKeyPair);
```

### Using CLI (subxt or similar)

```bash
# Query runtime version
curl -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"state_getRuntimeVersion","params":[],"id":1}' \
  http://localhost:9933

# Get account nonce
curl -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"system_accountNextIndex","params":["5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"],"id":1}' \
  http://localhost:9933
```

---

## Network Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 30333 | TCP | P2P networking |
| 9933 | HTTP | JSON-RPC |
| 9944 | WebSocket | JSON-RPC subscriptions |
| 9615 | HTTP | Prometheus metrics (optional) |

---

## Related Documentation

- [Architecture Overview](./architecture.md)
- [Development Guide](./development.md)
- [Production Deployment](./production-deployment.md)
- [Docker Guide](./docker.md)
- [QX Chain Connect CLI](https://github.com/qx-ventures/qxchain_connect)
