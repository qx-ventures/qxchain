# QX Chain Pallets

This directory contains the custom pallets for the QX Chain, implementing the core logic for decentralized AI inference validation.

## 🎯 QX AI Pallet (`pallet-qx-ai`)

The QX AI pallet implements **Optimistic Machine Learning (opML)** consensus for decentralized AI inference validation. It provides a complete request-based system for AI inference with stake-based security.

### 🔑 Key Features

- **Worker Management**: Registration, staking, and status tracking for AI workers
- **Validator System**: Stake-based validator registration for inference validation
- **Request Queue System**: Workers maintain bounded queues of inference requests
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

#### Worker Functions
- `register_worker(stake)`: Register as AI worker with stake
- `update_worker_status(online)`: Update worker availability
- `submit_inference(request_id, output)`: Submit inference result

#### Customer Functions
- `submit_request(target_worker, prompt, model_id)`: Submit inference request

#### Validator Functions
- `register_validator(stake)`: Register as validator with stake
- `challenge_inference(inference_id)`: Challenge incorrect inference
- `validate_inference(inference_id)`: Validate correct inference

### 📡 Events

- `WorkerRegistered`: Worker successfully registered
- `ValidatorRegistered`: Validator successfully registered
- `RequestSubmitted`: New inference request created
- `RequestAssigned`: Request assigned to worker
- `InferenceSubmitted`: Inference result submitted
- `InferenceChallenged`: Inference challenged by validator
- `InferenceValidated`: Inference validated by consensus
- `WorkerSlashed`: Worker penalized for malicious behavior
- `WorkerStatusUpdated`: Worker online/offline status changed
- `RequestCompleted`: Request processing completed

### ⚙️ Configuration

```rust
impl pallet_qx_ai::Config for Runtime {
    type Currency = Balances;
    type MinWorkerStake = ConstU64<1000>;      // 1,000 tokens minimum
    type MinValidatorStake = ConstU64<100>;    // 100 tokens minimum
    type MinChallengeStake = ConstU64<100>;    // 100 tokens to challenge
    type ChallengePeriod = ConstU32<100>;      // 100 blocks challenge window
    type SlashThreshold = ConstU32<51>;        // 51% majority for slashing
    type MaxQueueSize = ConstU32<100>;         // 100 requests per worker max
}
```

### 🎯 Economic Model

#### Staking Requirements
- **Workers**: Minimum 1,000 tokens stake
- **Validators**: Minimum 100 tokens stake
- **Challenge**: 100 tokens to submit challenge

#### Slashing Conditions
- Incorrect inference results (validated by 51%+ of validators)
- Malicious behavior or unavailability
- Economic incentive for honest participation

### 🔧 Storage Items

- `Workers`: Map of worker accounts to their stakes
- `Validators`: Map of validator accounts to their stakes
- `WorkerQueues`: Worker request queues (bounded to MaxQueueSize)
- `WorkerStatus`: Worker online/offline status
- `InferenceRequests`: All submitted requests
- `InferenceResults`: All inference results
- `RequestWorkerMap`: Request ID to worker mapping

## 📚 Template Pallet

A basic template pallet is also included for reference and development of additional functionality.

## 🔗 Framework Information

💁 Pallets are units of encapsulated logic with clearly defined responsibilities, analogous to modules in the runtime.

👉 Learn more about FRAME: [Polkadot SDK Docs](https://paritytech.github.io/polkadot-sdk/master/polkadot_sdk_docs/polkadot_sdk/frame_runtime/index.html)

🧑‍🏫 Pallet development guide: [Your First Pallet](https://paritytech.github.io/polkadot-sdk/master/polkadot_sdk_docs/guides/your_first_pallet/index.html)
