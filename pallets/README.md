# QX Chain Pallets

This directory contains the custom pallets for the QX Chain, implementing the application layer for civic AI infrastructure.

## 🎯 QX AI Pallet (`pallet-qx-ai`)

The QX AI pallet implements **permissioned AI inference** with KILT credential-based authorization for civic AI applications. AIWorkers are **application-layer entities, NOT blockchain consensus nodes**. They interact with the chain to provide AI services while consensus is handled by standard Substrate AURA + GRANDPA nodes.

### 🔑 Key Features

- **KILT-Based Authorization**: Workers must possess verified KILT credentials (DIDs) to operate
- **Request Queue System**: AIWorkers maintain bounded queues of inference requests
- **Inference Tracking**: Complete lifecycle tracking from request submission to completion
- **Trust Through Identity**: Authorization via KILT credentials instead of economic stakes

### 📊 Core Data Structures

#### InferenceRequest
```rust
pub struct InferenceRequest<AccountId> {
    pub customer: AccountId,
    pub target_worker: AccountId,
    pub prompt: BoundedVec<u8, ConstU32<2048>>,
    pub model_id: u32,
    pub status: RequestStatus,
    pub created_at: u32,
}
```

#### InferenceResult
```rust
pub struct InferenceResult<AccountId> {
    pub request_id: u32,
    pub worker: AccountId,
    pub worker_did: DidIdentifier,  // KILT DID for worker
    pub output: BoundedVec<u8, ConstU32<4096>>,
    pub model_id: u32,
    pub status: InferenceStatus,
    pub submitted_at: u32,
}
```

### 🔄 Status Enums

#### RequestStatus
- `Queued`: Request submitted to worker queue
- `Completed`: Result submitted to blockchain
- `Failed`: Request processing failed

#### InferenceStatus
- `Completed`: Inference completed successfully
- `Failed`: Inference failed

### 🎮 Extrinsics (Functions)

#### AIWorker Functions
- `update_ai_worker_status(online)`: Update AIWorker availability status
- `submit_inference(request_id, output, model_id)`: Submit inference result directly (no proof required)

#### Customer Functions
- `submit_request(target_worker, prompt, model_id, max_tokens)`: Submit inference request to specific authorized AIWorker

#### Governance Functions (via pallet-qx-kilt-permissions)
- Worker authorization managed through KILT credentials
- No direct registration extrinsics - workers verified via DID credentials

### 📡 Events

- `RequestSubmitted`: New inference request created
- `RequestAssigned`: Request assigned to AIWorker
- `InferenceSubmitted`: Inference result submitted with worker DID
- `AIWorkerStatusUpdated`: AIWorker online/offline status changed
- `RequestCompleted`: Request processing completed
- `ModelAdded`: New model added to allowed registry

### ⚙️ Configuration

```rust
impl pallet_qx_ai::Config for Runtime {
    type Currency = Balances;
    type KiltPermissions = QxKiltPermissions;  // KILT credential verification
    type MaxQueueSize = ConstU32<100>;         // 100 requests per AIWorker queue max
}
```

### 🎯 Authorization Model

#### KILT Credential Requirements
- **AIWorkers**: Must possess verified KILT DID credentials
- **Credential Issuance**: Managed by trusted attestors (e.g., city authorities)
- **Verification**: On-chain verification via `pallet-qx-kilt-permissions`

### 🔧 Storage Items (pallet-qx-ai)

- `AIWorkerQueues`: AIWorker request queues (bounded to MaxQueueSize)
- `AIWorkerStatus`: AIWorker online/offline availability
- `InferenceRequests`: All submitted inference requests
- `InferenceResults`: All inference results with worker DIDs
- `RequestWorkerMap`: Request ID to AIWorker mapping
- `AllowedModels`: Registry of permitted HuggingFace models
- `NextRequestId`: Counter for request IDs
- `NextInferenceId`: Counter for inference IDs

## 🆔 KILT Permissions Pallet (`pallet-qx-kilt-permissions`)

The KILT Permissions pallet manages decentralized identity and credential verification for AIWorkers.

### 🔑 Key Features

- **DID Management**: Associate accounts with KILT DIDs
- **Credential Verification**: On-chain verification of worker credentials
- **Flexible Authorization**: Support for credential expiry and revocation
- **Model Permissions**: Credentials specify which models workers can use

### 🔧 Storage Items (pallet-qx-kilt-permissions)

- `AuthorizedWorkers`: Map of DIDs to worker accounts
- `WorkerCredentials`: Map of DIDs to credential status
- `AccountToDID`: Reverse mapping from accounts to DIDs

## 🔗 Framework Information

💁 Pallets are units of encapsulated logic with clearly defined responsibilities, analogous to modules in the runtime.

👉 Learn more about FRAME: [Polkadot SDK Docs](https://paritytech.github.io/polkadot-sdk/master/polkadot_sdk_docs/polkadot_sdk/frame_runtime/index.html)

🧑‍🏫 Pallet development guide: [Your First Pallet](https://paritytech.github.io/polkadot-sdk/master/polkadot_sdk_docs/guides/your_first_pallet/index.html)
