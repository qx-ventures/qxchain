# QX Chain Pallets

This directory contains the custom pallets for the QX Chain, implementing the application layer for civic AI infrastructure.

## 🎯 QX AI Pallet (`pallet-qx-ai`)

The QX AI pallet implements **optimistic AI inference verification** with challenge-based validation for civic AI applications. AIWorkers and AIValidators are **application-layer entities, NOT blockchain consensus nodes**. They interact with the chain to provide and verify AI services while consensus is handled by standard Substrate NPoS nodes.

### 🔑 Key Features

- **AIWorker Management**: Registration, staking, and status tracking for application-layer AIWorkers (not consensus nodes)
- **AIValidator System**: Stake-based validator registration for challenge-based verification (not consensus nodes)
- **Request Queue System**: AIWorkers maintain bounded queues of inference requests
- **Inference Tracking**: Complete lifecycle tracking from request submission to finalization/slashing
- **Optimistic Verification**: Results assumed valid unless challenged within 7-day dispute window (100,800 blocks)
- **Challenge Mechanism**: AIValidators reproduce inference and challenge discrepancies
- **Stake-Weighted Consensus**: 51% of validator stake weight must agree to slash workers
- **Automatic Finalization**: Results auto-finalize after challenge period if no valid disputes
- **Slashing Mechanism**: Economic penalties for malicious or incorrect worker behavior

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
    pub model_hash: BoundedVec<u8, ConstU32<64>>, // Cryptographic commitment
    pub status: InferenceStatus,
    pub submitted_at: u32,
    pub challenge_deadline: u32, // Block number when 7-day period ends
}
```

### 🔄 Status Enums

#### RequestStatus
- `Queued`: Request submitted to worker queue
- `Assigned`: Request assigned to worker
- `Completed`: Result submitted to blockchain
- `Failed`: Request processing failed

#### InferenceStatus
- `Pending`: Result submitted, awaiting 7-day challenge period (optimistically valid)
- `Challenged`: Result disputed by AIValidator(s)
- `Finalized`: Challenge period passed without valid dispute, result confirmed
- `Slashed`: 51%+ validators agreed on invalidity, worker penalized

### 🎮 Extrinsics (Functions)

#### AIWorker Functions
- `register_ai_worker(stake)`: Register as AIWorker (application layer, not consensus node) with stake
- `update_ai_worker_status(online)`: Update AIWorker availability status
- `submit_inference(request_id, output, model_hash)`: Submit inference result with cryptographic commitment

#### Customer Functions
- `submit_request(target_worker, prompt, model_id)`: Submit inference request to specific AIWorker

#### AIValidator Functions
- `register_ai_validator(stake)`: Register as AIValidator (application layer, not consensus node) with stake
- `challenge_inference(inference_id, expected_output)`: Challenge incorrect inference during 7-day window
- `finalize_inference(inference_id)`: Trigger automatic finalization after challenge period ends

### 📡 Events

- `AIWorkerRegistered`: AIWorker successfully registered (application layer entity)
- `AIValidatorRegistered`: AIValidator successfully registered (application layer entity)
- `RequestSubmitted`: New inference request created
- `RequestAssigned`: Request assigned to AIWorker
- `InferenceSubmitted`: Inference result submitted with challenge deadline
- `InferenceChallenged`: Inference challenged by AIValidator
- `InferenceFinalized`: Inference automatically finalized after challenge period
- `AIWorkerSlashed`: AIWorker penalized after 51%+ validator consensus
- `AIWorkerBanned`: AIWorker removed from network after slashing
- `ChallengeConsensusReached`: 51%+ validator stake weight agreed on invalidity
- `AIWorkerStatusUpdated`: AIWorker online/offline status changed
- `RequestCompleted`: Request processing completed

### ⚙️ Configuration

```rust
impl pallet_qx_ai::Config for Runtime {
    type Currency = Balances;
    type MinAIWorkerStake = ConstU64<900>;     // 900 tokens minimum for AIWorkers
    type MinChallengeStake = ConstU64<100>;    // 100 tokens minimum for AIValidators
    type ChallengePeriod = ConstU32<100800>;   // 100,800 blocks = 7 days @ 6 sec/block
    type SlashThreshold = ConstU32<51>;        // 51% of validator stake weight for slashing
    type MaxQueueSize = ConstU32<100>;         // 100 requests per AIWorker queue max
}
```

### 🎯 Economic Model

#### Staking Requirements
- **AIWorkers**: Minimum 900 tokens stake (reserved on registration)
- **AIValidators**: Minimum 100 tokens stake (reserved on registration)
- **Challenge Weight**: Validator stake determines voting power in consensus

#### Slashing Conditions
- **Trigger**: 51%+ of total validator stake weight agrees on incorrect inference
- **Penalty**: Full stake confiscation + permanent ban from network
- **Process**: AIValidators reproduce inference, compare outputs, submit challenges
- **Economic incentive**: Honest AIWorkers rewarded, malicious actors permanently removed

### 🔧 Storage Items

- `AIWorkers`: Map of AIWorker accounts to their stakes (application layer, not consensus nodes)
- `AIValidators`: Map of AIValidator accounts to their stakes (application layer, not consensus nodes)
- `AIWorkerQueues`: AIWorker request queues (bounded to MaxQueueSize)
- `AIWorkerStatus`: AIWorker online/offline availability
- `InferenceRequests`: All submitted inference requests
- `InferenceResults`: All inference results with commitments and challenge deadlines
- `InferenceChallenges`: Map of inference ID to list of challenges
- `BannedAIWorkers`: Permanently banned workers after slashing
- `RequestWorkerMap`: Request ID to AIWorker mapping

## 🔗 Framework Information

💁 Pallets are units of encapsulated logic with clearly defined responsibilities, analogous to modules in the runtime.

👉 Learn more about FRAME: [Polkadot SDK Docs](https://paritytech.github.io/polkadot-sdk/master/polkadot_sdk_docs/polkadot_sdk/frame_runtime/index.html)

🧑‍🏫 Pallet development guide: [Your First Pallet](https://paritytech.github.io/polkadot-sdk/master/polkadot_sdk_docs/guides/your_first_pallet/index.html)
