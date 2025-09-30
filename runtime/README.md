# Runtime

ℹ️ The runtime (in other words, a state transition function), refers to the core logic of the blockchain that is
responsible for validating blocks and executing the state changes they define.

💁 The runtime in this template is constructed using ready-made FRAME pallets that ship with
[Polkadot SDK](https://github.com/paritytech/polkadot-sdk), and custom pallets for ML inference validation.

👉 Learn more about FRAME
[here](https://paritytech.github.io/polkadot-sdk/master/polkadot_sdk_docs/polkadot_sdk/frame_runtime/index.html).

## 🎯 QX Chain Runtime

The QX Chain runtime implements **Optimistic Machine Learning (opML)** with signature-based identity:

### Included Pallets

**Core Pallets (from Polkadot SDK):**
- `System`: Core blockchain functionality
- `Timestamp`: Block timestamp tracking
- `Balances`: Account balance management
- `TransactionPayment`: Transaction fee handling
- `Sudo`: Superuser access for development

**Custom ML Pallets:**
- `MlInference`: ML inference request queue and validation with signature-based identity
- `MlModels`: Model registry and worker-model mapping

### 🔑 Key Features

- **Signature-Based Identity**: Workers/validators don't need registration extrinsics
- **Activity Tracking**: Automatic tracking via `WorkerLastActivity` and `ValidatorLastActivity`
- **Permissionless**: Anyone can participate by signing transactions
- **Optimistic Validation**: Assume correctness unless challenged
- **Consensus Slashing**: 51%+ validator agreement triggers worker banning

### 📊 Pallet Configuration

```rust
impl pallet_ml_inference::Config for Runtime {
    type RuntimeEvent = RuntimeEvent;
    type ChallengePeriod = ConstU32<100>;      // 100 blocks
    type SlashThreshold = ConstU32<51>;        // 51% consensus
    type MaxQueueSize = ConstU32<100>;         // Max 100 requests per worker
}
```

### 🔄 State Transition Functions

**Customer Functions:**
- `submit_request(target_worker, prompt, model_id)`: Submit AI inference request

**Worker Functions:**
- `submit_inference(request_id, output)`: Submit result (identity proven by signature)

**Validator Functions:**
- `challenge_inference(inference_id, expected_output)`: Challenge incorrect result
- `validate_inference(inference_id)`: Validate correct result

All functions use **signature-based identity** - no pre-registration required!

## 🚀 Learn More

- [Custom Pallets Documentation](../pallets/README.md)
- [Node Implementation](../node/README.md)
- [Main Project README](../README.md)
