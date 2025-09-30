# QX Chain Pallets

This directory contains the custom pallets for the QX Chain, implementing the core logic for decentralized AI inference validation.

## 🎯 ML Inference Pallet (`pallet-ml-inference`)

The ML Inference pallet implements **Optimistic Machine Learning (opML)** consensus for decentralized AI inference validation. It provides a **permissionless, signature-based** system where identity is proven cryptographically without pre-registration.

### 🔑 Key Features

- **Signature-Based Identity**: Workers and validators are identified by their transaction signatures - no registration needed!
- **Permissionless Participation**: Any account can become a worker or validator by simply signing transactions
- **Automatic Queue Creation**: Worker queues are created automatically when first request is assigned
- **Activity Tracking**: System tracks worker/validator activity by recording last active block number
- **Request Queue System**: Workers maintain bounded queues of inference requests (max 100)
- **Inference Tracking**: Complete lifecycle tracking from request to validation
- **Optimistic Consensus**: Assume correctness unless challenged by validators
- **Slashing Mechanism**: Economic penalties for malicious or incorrect behavior

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
    pub output: BoundedVec<u8, ConstU32<4096>>,
    pub status: InferenceStatus,
    pub submitted_at: u32,
}
```

### 🔄 Status Enums

#### RequestStatus
- `Queued`: Request submitted to worker queue
- `Assigned`: Request assigned to worker
- `Completed`: Result submitted to blockchain
- `Failed`: Request processing failed

#### InferenceStatus
- `Queued`: Inference waiting in queue
- `Processing`: Inference being processed
- `Pending`: Result submitted, awaiting validation
- `Challenged`: Result challenged by validator
- `Validated`: Result confirmed by consensus
- `Slashed`: Worker penalized for incorrect result

### 🎮 Extrinsics (Functions)

All functions use **signature-based identity** - no pre-registration required!

#### Customer Functions
- `submit_request(target_worker, prompt, model_id)`: Submit inference request to any worker

#### Worker Functions
- `submit_inference(request_id, output)`: Submit inference result (identity proven by signature)

#### Validator Functions
- `challenge_inference(inference_id, expected_output)`: Challenge incorrect inference (identity proven by signature)
- `validate_inference(inference_id)`: Validate correct inference (identity proven by signature)

### 📡 Events

- `RequestSubmitted`: New inference request created
- `RequestAssigned`: Request assigned to worker
- `InferenceSubmitted`: Inference result submitted by worker
- `InferenceChallenged`: Inference challenged by validator
- `InferenceValidated`: Inference validated by consensus
- `WorkerBanned`: Worker penalized for malicious behavior
- `ChallengeConsensusReached`: Validator consensus reached on challenge
- `RequestCompleted`: Request processing completed

### ⚙️ Configuration

```rust
impl pallet_ml_inference::Config for Runtime {
    type RuntimeEvent = RuntimeEvent;
    type ChallengePeriod = ConstU32<100>;      // 100 blocks challenge window
    type SlashThreshold = ConstU32<51>;        // 51% majority for slashing
    type MaxQueueSize = ConstU32<100>;         // 100 requests per worker max
}
```

### 🎯 Signature-Based Identity Model

#### How It Works
1. **No Registration**: Workers and validators don't need to call any registration function
2. **Automatic Recognition**: First transaction from an account creates their identity
3. **Activity Tracking**: `WorkerLastActivity` and `ValidatorLastActivity` track participation
4. **Queue Management**: Worker queues created automatically on first request assignment

#### Benefits
- **Lower Barriers**: Anyone can participate immediately with just a keypair
- **Less Storage**: No redundant registration data stored on-chain
- **Simplified UX**: Workers/validators just start their nodes and sign transactions
- **Cryptographic Security**: Identity proven by Ed25519/Sr25519 signatures

### 🔧 Storage Items

- `WorkerLastActivity<T>`: Tracks last block where each worker was active
- `ValidatorLastActivity<T>`: Tracks last block where each validator was active
- `WorkerQueues<T>`: Worker request queues (created automatically, bounded to MaxQueueSize)
- `InferenceRequests<T>`: All submitted requests
- `InferenceResults<T>`: All inference results
- `RequestWorkerMap<T>`: Request ID to worker mapping
- `InferenceChallenges<T>`: Challenges submitted by validators
- `BannedWorkers<T>`: Workers banned for malicious behavior

## 🤖 ML Models Pallet (`pallet-ml-models`)

The ML Models pallet provides a registry for AI models available on the network. It allows workers to register which models they support and enables customers to discover workers by model capabilities.

### Key Features
- **Model Registry**: On-chain registry of available AI models
- **Worker-Model Mapping**: Track which workers support which models
- **Model Metadata**: Store model information (name, version, parameters)
- **Discovery**: Enable customers to find workers by model type

## 🔗 Framework Information

💁 Pallets are units of encapsulated logic with clearly defined responsibilities, analogous to modules in the runtime.

👉 Learn more about FRAME: [Polkadot SDK Docs](https://paritytech.github.io/polkadot-sdk/master/polkadot_sdk_docs/polkadot_sdk/frame_runtime/index.html)

🧑‍🏫 Pallet development guide: [Your First Pallet](https://paritytech.github.io/polkadot-sdk/master/polkadot_sdk_docs/guides/your_first_pallet/index.html)
