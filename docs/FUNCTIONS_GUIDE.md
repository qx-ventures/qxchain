# QXChain Functions Guide

**Explanation of All Blockchain Functions**

This guide explains every function available in the QXChain blockchain in simple, easy-to-understand terms.

---

## Table of Contents

1. [Overview](#overview)
2. [QX AI Pallet - AI Inference Management](#qx-ai-pallet---ai-inference-management)
3. [QX KILT Permissions Pallet - Worker Authorization](#qx-kilt-permissions-pallet---worker-authorization)
4. [QX Faucet Pallet - Free Tokens for New Users](#qx-faucet-pallet---free-tokens-for-new-users)
5. [Standard Blockchain Functions](#standard-blockchain-functions)
6. [Data Structures Explained](#data-structures-explained)
7. [Events - What Gets Logged](#events---what-gets-logged)
8. [Common Workflows](#common-workflows)

---

## Overview

**QXChain** is a blockchain designed for decentralized AI inference. It connects:
- **Customers** who want AI predictions
- **AI Workers** who run AI models and provide predictions
- **Validators** who maintain the blockchain

The chain has **6 second block times** and uses **proof-of-authority (PoA)** consensus with AURA (block production) and GRANDPA (finality).

**Key Features:**
- ✅ Free transactions for authorized workers
- ✅ KILT DID-based worker credentials
- ✅ Faucet for onboarding new users (no initial funds needed)
- ✅ Request queuing system for managing AI workload
- ✅ On-chain model registry

---

## QX AI Pallet - AI Inference Management

This is the core pallet that handles all AI inference requests and results.

### Functions (Extrinsics)

#### 1. `submit_request`
**What it does:** Submit an AI inference request to a specific worker.

**Who can call it:** Any user with tokens.

**Parameters:**
- `target_worker` - The account address of the AI worker you want to process your request
- `prompt` - Your text prompt (max 2048 bytes, about 2KB)
- `max_tokens` - Maximum number of tokens the AI should generate in response

**What happens:**
1. Checks if the target worker has a valid KILT DID credential
2. Creates a new request with status "Queued"
3. Adds the request to the worker's queue
4. Emits events: `RequestSubmitted` and `RequestAssigned`

**Costs:** Regular transaction fee (charged in QX tokens).

**Example use case:** "I want the AI worker at address ABC123 to analyze this text: 'Explain blockchain in simple terms' with max 100 tokens response."

---

#### 2. `update_ai_worker_status`
**What it does:** Worker announces whether they are online or offline.

**Who can call it:** Only workers with valid KILT credentials.

**Parameters:**
- `online` - Boolean: `true` if going online, `false` if going offline

**What happens:**
1. Verifies the caller has a valid worker credential
2. Updates the worker's online status in storage
3. Emits `AIWorkerStatusUpdated` event

**Costs:** **FREE** - This transaction costs nothing (Pays::No) because it's for credentialed workers.

**Example use case:** "I'm an AI worker and I just started my software, so I'll call this with online=true to let customers know I'm ready to process requests."

---

#### 3. `submit_inference`
**What it does:** Worker submits the AI-generated result for a request.

**Who can call it:** Only the worker assigned to the specific request, must have valid credentials.

**Parameters:**
- `request_id` - The ID number of the request you're responding to
- `output` - The AI-generated text response (max 4096 bytes, about 4KB)

**What happens:**
1. Verifies caller has valid KILT worker credential
2. Checks that this worker was assigned this specific request
3. Verifies request status is still "Queued" (not already processed)
4. Creates an InferenceResult record with status "Completed"
5. Updates the original request status to "Completed"
6. Removes the request from the worker's queue
7. Emits events: `InferenceSubmitted` and `RequestCompleted`

**Costs:** **FREE** - Workers don't pay for submitting results (Pays::No).

**Example use case:** "I'm a worker, I processed request #42, and here's my AI-generated output: 'Blockchain is a distributed ledger...'"

---

#### 4. `add_allowed_model`
**What it does:** Add a new AI model to the approved registry.

**Who can call it:** **Only sudo/governance** (requires root privileges).

**Parameters:**
- `model_id` - Unique ID number for this model
- `model_name` - Name of the model (max 128 bytes) - e.g., "TinyLlama-1.1B"
- `model_hash` - Cryptographic hash of the model file (max 64 bytes) for verification

**What happens:**
1. Checks that caller has root/sudo privileges
2. Creates an AllowedModel entry marked as `active: true`
3. Stores it in the AllowedModels registry
4. Emits `ModelAdded` event

**Costs:** Regular transaction fee (sudo pays).

**Example use case:** "The governance wants to approve a new AI model called 'Llama-3.2-1B' with hash 'abc123...' so workers can start using it."

---

### Storage Items (What Data is Stored)

#### `InferenceRequests`
- **What:** All submitted AI inference requests
- **Key:** Request ID (number)
- **Value:** InferenceRequest struct containing:
  - `customer` - Who submitted the request
  - `target_worker` - Which worker should process it
  - `prompt` - The text prompt
  - `max_tokens` - Token limit
  - `status` - Current status (Queued/Completed)
  - `created_at` - Block number when created

#### `InferenceResults`
- **What:** All completed AI inference results
- **Key:** Inference ID (number)
- **Value:** InferenceResult struct containing:
  - `request_id` - Which request this answers
  - `worker` - Account that processed it
  - `worker_did` - Worker's DID identifier
  - `output` - The AI-generated text
  - `status` - Status (Completed)
  - `submitted_at` - Block number when submitted

#### `AIWorkerQueues`
- **What:** Each worker's pending request queue
- **Key:** Worker account address
- **Value:** List of request IDs (max 100 per worker)

#### `AIWorkerStatus`
- **What:** Whether each worker is online or offline
- **Key:** Worker account address
- **Value:** Boolean (true = online, false = offline)

#### `AllowedModels`
- **What:** Registry of approved AI models
- **Key:** Model ID (number)
- **Value:** AllowedModel struct containing:
  - `model_name` - Name like "TinyLlama"
  - `model_hash` - File hash for verification
  - `active` - Whether it's currently allowed

#### `RequestWorkerMap`
- **What:** Maps each request to its assigned worker
- **Key:** Request ID
- **Value:** Worker account address

#### `NextRequestId` / `NextInferenceId`
- **What:** Counters for generating new IDs
- **Value:** Next available ID number

---

## QX KILT Permissions Pallet - Worker Authorization

This pallet manages worker identity and credentials using KILT DIDs (Decentralized Identifiers).

### Functions (Extrinsics)

#### 1. `set_governance_did`
**What it does:** Initialize the governance DID that will issue all worker credentials.

**Who can call it:** **Only sudo/root** (one-time setup).

**Parameters:**
- `did` - 32-byte DID identifier for governance

**What happens:**
1. Checks caller has root privileges
2. Stores the governance DID
3. Emits `GovernanceDIDSet` event

**Costs:** Regular transaction fee.

**Example use case:** "During chain setup, governance sets its DID as the 'issuer' for all worker credentials."

---

#### 2. `create_worker_did`
**What it does:** Register as a new AI worker and get a DID.

**Who can call it:** Anyone who wants to become a worker.

**Parameters:**
- `name` - Worker name (max 128 bytes) - e.g., "Alice's AI Server"
- `description` - Description (max 512 bytes) - e.g., "Running TinyLlama on GPU"

**What happens:**
1. Checks you don't already have a DID
2. Generates a unique DID from your account address
3. Creates WorkerDID record with status "Active"
4. Stores mappings (account → DID, DID → account)
5. Emits `WorkerDIDCreated` event

**Costs:** Regular transaction fee.

**Example use case:** "I want to become an AI worker, so I create my DID with name 'Bob's ML Node' to start the registration process."

---

#### 3. `issue_worker_credential`
**What it does:** Governance officially authorizes a worker by issuing them a credential.

**Who can call it:** **Only sudo/root**.

**Parameters:**
- `worker_did` - The DID of the worker to authorize
- `models` - List of model IDs this worker is allowed to use (max 100)
- `validity_period` - Optional: how many blocks until credential expires (None = never expires)

**What happens:**
1. Checks caller has root privileges
2. Creates AIWorkerCredential with:
   - Issuer = governance DID
   - Subject = worker DID
   - Approved models
   - Issue date and optional expiry
3. Stores the credential
4. Emits `WorkerCredentialIssued` event

**Costs:** Regular transaction fee (sudo pays).

**Default validity:** 30 days (configurable, see runtime config: `DefaultCredentialValidity`).

**Example use case:** "Governance approves worker DID xyz123 to use models [1, 2] with a 30-day credential."

---

#### 4. `revoke_worker_credential`
**What it does:** Permanently remove a worker's authorization.

**Who can call it:** **Only sudo/root**.

**Parameters:**
- `worker_did` - The DID of the worker to revoke

**What happens:**
1. Checks caller has root privileges
2. Removes the worker's credential from storage
3. Emits `WorkerCredentialRevoked` event

**Costs:** Regular transaction fee.

**Example use case:** "Worker violated terms, so governance revokes their credential. They can no longer process requests."

---

#### 5. `suspend_worker`
**What it does:** Temporarily suspend a worker (not permanent like revoke).

**Who can call it:** **Only sudo/root**.

**Parameters:**
- `worker_did` - The DID of the worker to suspend
- `duration` - Optional: number of blocks to suspend (None = use default 1 day)

**What happens:**
1. Checks caller has root privileges
2. Sets worker's status to "Suspended" with an "until" block number
3. Emits `WorkerSuspended` event

**Costs:** Regular transaction fee.

**Default duration:** 1 day worth of blocks (14,400 blocks at 6s each = 24 hours).

**Example use case:** "Worker is under investigation, suspend for 3 days (43,200 blocks) until we review."

---

### Storage Items

#### `WorkerDIDs`
- **What:** Complete worker information
- **Key:** Worker account address
- **Value:** WorkerDID struct containing:
  - `did` - 32-byte DID identifier
  - `account` - Account address
  - `metadata` - Name, description, registration date
  - `status` - Active/Suspended/Revoked

#### `WorkerCredentials`
- **What:** Valid credentials issued to workers
- **Key:** Worker DID (32 bytes)
- **Value:** AIWorkerCredential containing:
  - `issuer` - Governance DID
  - `subject` - Worker DID
  - `models` - List of approved model IDs
  - `issued_at` - Block number of issuance
  - `expires_at` - Optional expiry block

#### `AccountToDID`
- **What:** Quick lookup from account to DID
- **Key:** Account address
- **Value:** DID identifier (32 bytes)

#### `GovernanceDID`
- **What:** The single governance DID for the chain
- **Value:** 32-byte DID identifier

---

### Helper Functions (Internal)

These aren't directly callable but are used by other pallets:

#### `verify_worker_credential(did)`
- **Purpose:** Check if a worker's credential is valid
- **Returns:** true/false
- **Checks:**
  - Credential exists
  - Not expired
  - Status is Active (not Suspended or Revoked)
  - If suspended, check if suspension period ended

#### `get_worker_did(account)`
- **Purpose:** Get DID from account address
- **Returns:** DID identifier or error

#### `generate_did(account)`
- **Purpose:** Generate unique DID from account (used during registration)
- **Returns:** 32-byte DID

---

## QX Faucet Pallet - Free Tokens for New Users

This pallet gives free tokens to new users so they can start using the chain without needing to buy tokens first.

### Functions (Extrinsics)

#### 1. `claim`
**What it does:** Get free tokens from the faucet.

**Who can call it:** Anyone!

**Parameters:** None

**What happens:**
1. Checks you haven't claimed too recently (cooldown period)
2. Checks you haven't reached lifetime claim limit
3. Checks faucet pot has enough tokens
4. Transfers tokens from faucet pot to your account
5. Updates your last claim time and claim count
6. Emits `Claimed` event

**Costs:** **FREE!** This transaction costs nothing (Pays::No) so new users with zero balance can still claim.

**Limits:**
- **Amount per claim:** 10 QX tokens (10,000,000,000,000 units)
- **Cooldown:** 24 hours between claims (14,400 blocks)
- **Lifetime limit:** 5 claims per account (total 50 QX)

**Example use case:** "I'm a new user with no tokens. I call claim() for free and receive 10 QX tokens to start using the chain. I can claim again tomorrow."

---

#### 2. `fund_faucet`
**What it does:** Donate tokens to the faucet so it can help more users.

**Who can call it:** Anyone with tokens.

**Parameters:**
- `amount` - How many tokens to donate

**What happens:**
1. Transfers tokens from your account to faucet pot
2. Emits `FaucetFunded` event

**Costs:** Regular transaction fee.

**Example use case:** "I want to support new user onboarding, so I donate 1000 QX tokens to the faucet."

---

### Storage Items

#### `LastClaim`
- **What:** When each account last claimed tokens
- **Key:** Account address
- **Value:** Block number of last claim

#### `ClaimCount`
- **What:** How many times each account has claimed
- **Key:** Account address
- **Value:** Number of claims (0-5)

---

### Helper Functions (Query)

#### `remaining_claims(account)`
- **Purpose:** Check how many claims an account has left
- **Returns:** Number (0-5)

#### `faucet_balance()`
- **Purpose:** Check how many tokens are in the faucet pot
- **Returns:** Balance amount

#### `can_claim(account)`
- **Purpose:** Check if account can claim right now
- **Returns:** true/false
- **Checks:** Cooldown passed, limit not reached, faucet has funds

---

## Standard Blockchain Functions

These are built-in Substrate/Polkadot SDK functions available on all chains.

### Balances Pallet

#### `transfer(dest, value)`
- Send tokens to another account
- **Parameters:**
  - `dest` - Destination account
  - `value` - Amount to send
- **Cost:** Transaction fee
- **Minimum to keep account alive:** 500 units (EXISTENTIAL_DEPOSIT)

#### `transfer_keep_alive(dest, value)`
- Send tokens but ensure your account doesn't fall below minimum balance
- Safer than regular transfer

#### `transfer_all(dest, keep_alive)`
- Send all your tokens to another account

---

### Sudo Pallet

#### `sudo(call)`
- Execute a privileged call as root/admin
- **Who can use:** Only the sudo account (usually Alice in dev mode)

#### `sudo_as(who, call)`
- Execute a call as if it came from another account (powerful!)

---

### System Functions (Automatic)

These happen automatically, you don't call them:

#### `on_initialize(block_number)`
- Runs at the start of every block

#### `on_finalize(block_number)`
- Runs at the end of every block

---

## Data Structures Explained

### InferenceRequest
```
{
  customer: AccountId,           // Who wants the AI prediction
  target_worker: AccountId,      // Which worker will process it
  prompt: Text (max 2KB),        // The AI prompt
  max_tokens: Number,            // Max response length
  status: Queued/Completed,      // Current state
  created_at: BlockNumber        // When it was created
}
```

### InferenceResult
```
{
  request_id: Number,            // Which request this answers
  worker: AccountId,             // Who processed it
  worker_did: DID (32 bytes),    // Worker's credential ID
  output: Text (max 4KB),        // AI-generated response
  status: Completed,             // Status
  submitted_at: BlockNumber      // When submitted
}
```

### WorkerDID
```
{
  did: DID (32 bytes),           // Unique identifier
  account: AccountId,            // Blockchain account
  metadata: {
    name: Text (max 128 bytes),  // Worker name
    description: Text (max 512 bytes), // Description
    registered_at: BlockNumber   // Registration time
  },
  status: Active/Suspended/Revoked  // Current authorization status
}
```

### AIWorkerCredential
```
{
  issuer: DID (governance),      // Who issued the credential
  subject: DID (worker),         // Who the credential is for
  models: [ModelId],             // Approved model IDs (max 100)
  issued_at: BlockNumber,        // When issued
  expires_at: Optional BlockNumber  // Optional expiry (None = never)
}
```

### AllowedModel
```
{
  model_name: Text (max 128),    // e.g., "TinyLlama-1.1B"
  model_hash: Hash (max 64),     // File verification hash
  active: Boolean                // Whether currently allowed
}
```

---

## Events - What Gets Logged

Events are notifications that get emitted when important things happen. Applications can listen for these.

### QX AI Events

- **`RequestSubmitted { request_id, customer, worker }`**
  - Fired when customer submits new AI request

- **`RequestAssigned { request_id, worker }`**
  - Fired when request is assigned to worker's queue

- **`InferenceSubmitted { inference_id, request_id, worker, worker_did }`**
  - Fired when worker submits AI result

- **`RequestCompleted { request_id, inference_id }`**
  - Fired when request is fully processed

- **`AIWorkerStatusUpdated { worker, online }`**
  - Fired when worker changes online/offline status

- **`ModelAdded { model_id, model_name }`**
  - Fired when governance adds new allowed model

### QX KILT Permissions Events

- **`WorkerDIDCreated { account, did }`**
  - Fired when worker registers and gets DID

- **`WorkerCredentialIssued { did, expires_at }`**
  - Fired when governance authorizes a worker

- **`WorkerCredentialRevoked { did }`**
  - Fired when credential is permanently revoked

- **`WorkerSuspended { did, until }`**
  - Fired when worker is temporarily suspended

- **`GovernanceDIDSet { did }`**
  - Fired when governance DID is initialized

### QX Faucet Events

- **`Claimed { who, amount }`**
  - Fired when user claims free tokens

- **`FaucetFunded { funder, amount }`**
  - Fired when someone donates to faucet

---

## Common Workflows

### 1. New User Gets Started

```
1. User calls: faucet.claim()
   → Receives 10 QX tokens for FREE

2. User can now pay for transactions!
   → Can submit AI requests
   → Can transfer tokens
```

### 2. Becoming an AI Worker

```
1. Worker calls: kilt_permissions.create_worker_did(name, description)
   → Gets assigned a DID
   → Status: Active but not yet credentialed

2. Worker applies to governance (off-chain)
   → Provides evidence they can run models

3. Governance calls: kilt_permissions.issue_worker_credential(worker_did, [model_ids], validity)
   → Worker now has official credential
   → Can start processing requests

4. Worker calls: qx_ai.update_ai_worker_status(true)
   → Announces "I'm online and ready!"
```

### 3. Customer Gets AI Prediction

```
1. Customer calls: qx_ai.submit_request(worker_account, "Explain quantum computing", 200)
   → Chain verifies worker has valid credential
   → Request added to worker's queue
   → Events: RequestSubmitted, RequestAssigned

2. Worker software monitors chain for new requests
   → Sees new request in their queue
   → Runs AI model locally to generate response

3. Worker calls: qx_ai.submit_inference(request_id, "Quantum computing uses qubits...")
   → Chain verifies worker was assigned this request
   → Stores inference result
   → Marks request as Completed
   → Events: InferenceSubmitted, RequestCompleted

4. Customer queries chain for result
   → Reads InferenceResults storage
   → Gets AI-generated output
```

### 4. Governance Manages Models

```
1. New AI model is developed and tested

2. Governance calls: qx_ai.add_allowed_model(5, "Llama-3.2-1B", "sha256:abc123...")
   → Model ID 5 is now approved
   → Workers can start using it

3. Workers update their credentials
   → Governance calls: kilt_permissions.issue_worker_credential(worker_did, [1,2,3,5], 30_days)
   → Worker now authorized for models 1, 2, 3, and 5
```

### 5. Handling Misbehaving Worker

```
Option A - Temporary Suspension:
1. Governance calls: kilt_permissions.suspend_worker(worker_did, duration)
   → Worker's credential status = Suspended
   → Worker cannot process requests during suspension
   → After duration passes, worker automatically reactivated

Option B - Permanent Revocation:
1. Governance calls: kilt_permissions.revoke_worker_credential(worker_did)
   → Worker's credential is deleted
   → Worker permanently banned from processing requests
   → Would need to re-apply and get new credential to return
```

---

## Configuration Parameters

These are set in the runtime and can be changed via runtime upgrade:

### Block Production
- **Block Time:** 6 seconds (6000 milliseconds)
- **Block Hash History:** 2400 blocks kept
- **Max Block Weight:** 2 seconds of computation time
- **Max Block Size:** 5 MB

### Balances
- **Existential Deposit:** 500 units (minimum to keep account alive)
- **Max Locks:** 50 per account

### QX AI
- **Max Queue Size:** 100 requests per worker

### QX Faucet
- **Drip Amount:** 10 QX tokens (10,000,000,000,000 units)
- **Claim Cooldown:** 24 hours (14,400 blocks)
- **Max Claims:** 5 per account (lifetime)

### QX KILT Permissions
- **Default Credential Validity:** 30 days (432,000 blocks)
- **Worker Suspension Period:** 1 day (14,400 blocks)

---

## Error Messages

When transactions fail, you'll see these error messages:

### QX AI Errors
- `AIWorkerNotFound` - Worker account doesn't exist
- `InferenceNotFound` - Inference ID doesn't exist
- `RequestNotFound` - Request ID doesn't exist
- `AIWorkerQueueFull` - Worker already has 100 pending requests
- `RequestAlreadyAssigned` - This request was already processed
- `RequestNotAssigned` - You're not the worker for this request
- `InvalidWorkerCredential` - Your credential is invalid/expired/revoked
- `WorkerDIDNotFound` - Worker doesn't have a DID

### QX KILT Permissions Errors
- `WorkerDIDAlreadyExists` - You already have a DID
- `WorkerDIDNotFound` - DID doesn't exist
- `WorkerCredentialNotFound` - No credential for this DID
- `InvalidCredentialIssuer` - Credential wasn't issued by governance
- `CredentialExpired` - Credential expired
- `CredentialSuspended` - Worker is currently suspended
- `CredentialRevoked` - Worker's credential was revoked
- `NotAuthorizedToIssue` - Only governance can issue credentials
- `NotAuthorizedToRevoke` - Only governance can revoke credentials
- `GovernanceDIDNotSet` - Governance DID not initialized
- `AccountHasNoDID` - Account doesn't have a DID
- `InvalidBoundedVec` - Input data too long

### QX Faucet Errors
- `ClaimTooSoon` - Wait longer between claims (24 hour cooldown)
- `MaxClaimsReached` - Already claimed 5 times (lifetime limit)
- `FaucetEmpty` - Faucet pot doesn't have enough tokens

---

## Security Features

### 1. Credential Verification
- Every AI request/response verifies worker credentials
- Expired, suspended, or revoked workers are rejected
- Prevents unauthorized AI responses

### 2. Request Assignment
- Workers can only submit results for requests assigned to them
- Prevents workers from stealing each other's work
- Ensures accountability

### 3. Rate Limiting
- Workers limited to 100 pending requests (queue size)
- Prevents spam and ensures fair distribution
- Faucet limited to prevent abuse

### 4. Free Transactions for Workers
- Workers don't pay fees for status updates and submissions
- Encourages participation
- Funded by customer request fees

### 5. Governance Controls
- Only sudo can approve models
- Only sudo can issue/revoke credentials
- Only sudo can suspend workers
- Prevents unauthorized changes

---

## Technical Details

### Substrate Framework
- **Runtime Version:** Spec 102
- **Framework:** Polkadot SDK (FRAME)
- **Consensus:** AURA (Authority Round) for block production
- **Finality:** GRANDPA (GHOST-based Recursive ANcestor Deriving Prefix Agreement)
- **Network Type:** Proof of Authority (PoA)

### Pallets Included
```
Index 0: System (core blockchain logic)
Index 1: Timestamp (block timestamps)
Index 2: Aura (block authoring)
Index 3: Grandpa (finality gadget)
Index 4: Balances (token transfers)
Index 5: TransactionPayment (fee handling)
Index 6: Sudo (governance)
Index 7: QxKiltPermissions (worker credentials)
Index 8: QxAi (AI inference logic)
Index 9: QxFaucet (token distribution)
Index 10: SkipFeelessPayment (free transactions)
```

### Network Endpoints
- **WebSocket RPC:** ws://localhost:9944
- **HTTP RPC:** http://localhost:9933
- **P2P:** tcp://localhost:30333

### Account Format
- **Address Format:** SS58 (Substrate)
- **SS58 Prefix:** 42 (generic Substrate)
- **Signature Scheme:** Sr25519 (Schnorr signatures)
- **Hash Algorithm:** Blake2 256-bit

---

## Need Help?

- **General Questions:** See main README.md
- **Architecture:** See docs/architecture.md
- **Development Setup:** See docs/development.md
- **Docker Deployment:** See docs/docker.md
- **Production Deployment:** See docs/production-deployment.md

---

**Last Updated:** Based on runtime spec version 102

**Document Version:** 1.0

**Contributors:** QXChain Development Team
