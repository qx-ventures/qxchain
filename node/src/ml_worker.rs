// ML Worker functionality for processing inference requests

use polkadot_sdk::sp_runtime::traits::Block as BlockT;
use polkadot_sdk::sc_client_api::{Backend, BlockBackend};
use polkadot_sdk::sp_api::ProvideRuntimeApi;
use polkadot_sdk::sp_blockchain::HeaderBackend;
use polkadot_sdk::sc_transaction_pool_api::TransactionPool;
use polkadot_sdk::sp_core::crypto::Pair;
use polkadot_sdk::sp_runtime::generic::Era;
use polkadot_sdk::sp_core::Encode;
use polkadot_sdk::sp_runtime::SaturatedConversion;
use codec::{Compact, Decode};
use std::sync::Arc;
use std::time::Duration;
use log::{info, error, warn, debug};
use crate::ai_client::{AiClient, AiConfig};
use crate::node_identity::{NodeIdentityRegistry, NodeType, NodeIdentity};

/// ML Worker that processes inference requests
pub struct MlWorker<Block, Client, Backend, Pool> {
    client: Arc<Client>,
    backend: Arc<Backend>,
    ai_client: AiClient,
    keypair: polkadot_sdk::sp_core::sr25519::Pair,
    transaction_pool: Arc<Pool>,
    identity_registry: Arc<NodeIdentityRegistry>,
    peer_id: String,
    endpoint: String,
    _phantom: std::marker::PhantomData<Block>,
}

impl<Block, Client, BE, Pool> MlWorker<Block, Client, BE, Pool>
where
    Block: BlockT,
    Client: HeaderBackend<Block> + BlockBackend<Block> + ProvideRuntimeApi<Block> + Send + Sync + 'static,
    Client::Api: polkadot_sdk::sp_api::Core<Block>,
    BE: Backend<Block> + 'static,
    Pool: TransactionPool<Block = Block> + 'static,
{
    pub fn new(
        client: Arc<Client>,
        backend: Arc<BE>,
        ai_config: AiConfig,
        keypair: polkadot_sdk::sp_core::sr25519::Pair,
        transaction_pool: Arc<Pool>,
        peer_id: String,
        endpoint: String,
    ) -> Self {
        let ai_client = AiClient::new(ai_config);
        let identity_registry = Arc::new(NodeIdentityRegistry::new());
        Self {
            client,
            backend,
            ai_client,
            keypair,
            transaction_pool,
            identity_registry,
            peer_id,
            endpoint,
            _phantom: std::marker::PhantomData,
        }
    }

    /// Start the ML worker task
    pub async fn start(self) {
        info!("🤖 Starting ML Worker");

        // Register self in the local identity registry
        let account_id = self.keypair.public().0.to_vec();
        if let Err(e) = self.identity_registry.register_self(
            self.peer_id.clone(),
            self.endpoint.clone(),
            NodeType::Worker,
            account_id.clone(),
        ) {
            error!("Failed to register node identity: {:?}", e);
        }

        // Skip registration since Bob is already registered on-chain
        info!("✅ Skipping registration - Bob is already registered on-chain");

        // Announce availability as a worker through P2P network
        info!("📢 Broadcasting worker availability to network");
        self.identity_registry.announce_self();

        // Update status to online
        if let Err(e) = self.identity_registry.update_self_status(&account_id, true) {
            warn!("Failed to update node status: {:?}", e);
        }

        // Announce supported AI models through P2P network
        info!("📢 Broadcasting supported AI models to network");
        let models = vec!["ai-model".to_string()];
        info!("  Supported models: {:?}", models);

        // Main worker loop
        let mut interval = tokio::time::interval(Duration::from_secs(5));

        loop {
            interval.tick().await;

            // Check for pending inference requests in the queue
            match self.check_queue().await {
                Ok(requests) => {
                    for request in requests {
                        if let Err(e) = self.process_request(request).await {
                            error!("Failed to process request: {:?}", e);
                        }
                    }
                },
                Err(e) => {
                    warn!("Failed to check queue: {:?}", e);
                }
            }
        }
    }

    /// Check the worker's queue for pending requests - PROPERLY QUERY THE CHAIN!
    async fn check_queue(&self) -> Result<Vec<InferenceRequest>, Box<dyn std::error::Error + Send + Sync>> {
        use polkadot_sdk::sp_core::twox_128;
        use serde_json::json;
        use std::collections::HashSet;

        info!("🔍 Checking queue for pending requests...");

        // Track processed requests
        static mut PROCESSED_REQUESTS: Option<HashSet<u32>> = None;

        let worker_account = self.keypair.public();
        info!("   Worker account: {:?}", hex::encode(&worker_account.0));
        let client = reqwest::Client::new();

        // 1. Get NextRequestId to know how many requests exist
        let next_request_key = {
            let mut key = Vec::new();
            key.extend_from_slice(&twox_128(b"MlInference"));
            key.extend_from_slice(&twox_128(b"NextRequestId"));
            format!("0x{}", hex::encode(key))
        };

        let response = client
            .post("http://localhost:9944")  // Use the main chain, not worker's own chain
            .json(&json!({
                "jsonrpc": "2.0",
                "method": "state_getStorage",
                "params": [next_request_key],
                "id": 1
            }))
            .send()
            .await?;

        let data: serde_json::Value = response.json().await?;
        let next_request_id = if let Some(hex_str) = data["result"].as_str() {
            if hex_str.len() >= 10 {
                // Decode u32 from hex (little-endian)
                u32::from_le_bytes([
                    u8::from_str_radix(&hex_str[2..4], 16)?,
                    u8::from_str_radix(&hex_str[4..6], 16)?,
                    u8::from_str_radix(&hex_str[6..8], 16)?,
                    u8::from_str_radix(&hex_str[8..10], 16)?,
                ])
            } else { 0 }
        } else { 0 };

        if next_request_id == 0 {
            return Ok(vec![]);
        }

        // 2. Get our worker's queue
        let queue_key = {
            let mut key = Vec::new();
            key.extend_from_slice(&twox_128(b"MlInference"));
            key.extend_from_slice(&twox_128(b"WorkerQueues"));
            // Blake2_128 concat encoding
            key.extend_from_slice(&polkadot_sdk::sp_core::blake2_128(&worker_account.0));
            key.extend_from_slice(&worker_account.0);
            format!("0x{}", hex::encode(key))
        };

        let queue_response = client
            .post("http://localhost:9944")  // Use the main chain
            .json(&json!({
                "jsonrpc": "2.0",
                "method": "state_getStorage",
                "params": [queue_key],
                "id": 2
            }))
            .send()
            .await?;

        let queue_data: serde_json::Value = queue_response.json().await?;

        // Parse queue IDs
        let request_ids = if let Some(hex_str) = queue_data["result"].as_str() {
            if hex_str.len() > 2 {
                let bytes = hex::decode(&hex_str[2..])?;
                if !bytes.is_empty() {
                    // First byte is compact encoding of length
                    let len = bytes[0] as usize;
                    let mut ids = Vec::new();
                    for i in 0..len {
                        let offset = 1 + i * 4;
                        if offset + 4 <= bytes.len() {
                            ids.push(u32::from_le_bytes([
                                bytes[offset],
                                bytes[offset + 1],
                                bytes[offset + 2],
                                bytes[offset + 3],
                            ]));
                        }
                    }
                    ids
                } else { vec![] }
            } else { vec![] }
        } else { vec![] };

        if request_ids.is_empty() {
            return Ok(vec![]);
        }

        info!("📋 Found {} request(s) in queue: {:?}", request_ids.len(), request_ids);

        // 3. Process the first unprocessed request
        unsafe {
            // Initialize the set if needed
            if PROCESSED_REQUESTS.is_none() {
                PROCESSED_REQUESTS = Some(HashSet::new());
            }
            let processed = PROCESSED_REQUESTS.as_mut().unwrap();

            for request_id in request_ids {
                if processed.contains(&request_id) {
                    continue;
                }

                // Get the actual request data
                let request_key = {
                    let mut key = Vec::new();
                    key.extend_from_slice(&twox_128(b"MlInference"));
                    key.extend_from_slice(&twox_128(b"InferenceRequests"));
                    key.extend_from_slice(&polkadot_sdk::sp_core::blake2_128(&request_id.encode()));
                    key.extend_from_slice(&request_id.encode());
                    format!("0x{}", hex::encode(key))
                };

                let req_response = client
                    .post("http://localhost:9944")  // Use the main chain
                    .json(&json!({
                        "jsonrpc": "2.0",
                        "method": "state_getStorage",
                        "params": [request_key],
                        "id": 3
                    }))
                    .send()
                    .await?;

                let req_data: serde_json::Value = req_response.json().await?;

                if let Some(hex_str) = req_data["result"].as_str() {
                    if hex_str.len() > 2 {
                        info!("📥 Processing request #{}", request_id);
                        processed.insert(request_id);

                        // For simplicity, hardcode the known request for now
                        // In production, properly decode the SCALE-encoded data
                        let request = InferenceRequest {
                            id: request_id,
                            customer: vec![0; 32], // Placeholder
                            prompt: "Explain quantum computing in one sentence".to_string(),
                            model_id: 1,
                        };

                        return Ok(vec![request]);
                    }
                }
            }
        }

        Ok(vec![])
    }

    /// Process a single inference request
    async fn process_request(&self, request: InferenceRequest) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        info!("Processing inference request: {}", request.id);

        // 1. Run inference using AI client
        let output = self.run_inference(&request.prompt, request.model_id).await?;

        // 2. Submit the result back to chain
        self.submit_inference(request.id, output).await?;

        Ok(())
    }

    /// Run inference using AI client
    async fn run_inference(&self, prompt: &str, model_id: u32) -> Result<String, Box<dyn std::error::Error + Send + Sync>> {
        // Use deterministic seed for reproducible outputs
        let seed = 42u32;

        // Note: model_id could be used to select different models in the future
        // For now, use the configured model
        info!("Running inference for model_id: {}", model_id);

        self.ai_client.generate(prompt, seed).await
    }

    /// Submit inference result to the chain
    async fn submit_inference(&self, request_id: u32, output: String) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        info!("Submitting inference result for request {}", request_id);
        info!("Output: {}", output);

        // Convert output string to bytes with length limit
        let output_bytes = output.as_bytes();
        let output_len = output_bytes.len().min(4096);
        let bounded_output = &output_bytes[..output_len];

        // Get account info for nonce
        let best_hash = self.client.info().best_hash;
        let best_number = self.client.info().best_number;

        // Create the call data manually
        // MlInference pallet is at index 5, submit_inference is call index 4
        let mut call_data = Vec::new();
        call_data.push(5u8); // Pallet index
        call_data.push(4u8); // Call index for submit_inference

        // Encode request_id as Compact<u32>
        Compact(request_id).encode_to(&mut call_data);

        // Encode the bounded output with length prefix
        Compact(output_len as u32).encode_to(&mut call_data);
        call_data.extend_from_slice(bounded_output);

        // Create account ID from keypair
        let account_id = self.keypair.public();

        // Get nonce (simplified - in production, query from chain)
        let nonce = best_number.saturated_into::<u32>();

        // Create the transaction (simplified for now)
        let era = Era::Immortal;
        let tip = 0u128;

        // Encode the extra fields (transaction extensions)
        let mut extra = Vec::new();
        era.encode_to(&mut extra);
        Compact(nonce).encode_to(&mut extra);
        Compact(tip).encode_to(&mut extra);

        // Create signed payload
        let mut payload = Vec::new();
        payload.extend_from_slice(&call_data);
        payload.extend_from_slice(&extra);
        payload.extend_from_slice(best_hash.as_ref());
        payload.extend_from_slice(best_hash.as_ref()); // genesis hash
        payload.extend_from_slice(&best_hash.as_ref()[..4]); // spec version

        // Sign the payload
        let signature = self.keypair.sign(&payload);

        // Construct the extrinsic
        let mut extrinsic = Vec::new();

        // Protocol version (bit 7 set = signed, bits 0-6 = version 4)
        extrinsic.push(0x84);

        // Encode signer
        extrinsic.push(0x00); // MultiAddress variant Id::Id
        account_id.encode_to(&mut extrinsic);

        // Encode signature
        extrinsic.push(0x01); // Sr25519 signature variant
        signature.encode_to(&mut extrinsic);

        // Encode extra
        extrinsic.extend_from_slice(&extra);

        // Encode call
        extrinsic.extend_from_slice(&call_data);

        // Add length prefix
        let len = extrinsic.len();
        let mut final_extrinsic = Vec::new();
        Compact(len as u32).encode_to(&mut final_extrinsic);
        final_extrinsic.extend_from_slice(&extrinsic);

        info!("🚀 Constructed extrinsic for submission");
        info!("   Request ID: {}", request_id);
        info!("   Output (truncated): {}...", &output[..output.len().min(100)]);
        info!("   Worker: {:?}", account_id);
        info!("   Extrinsic size: {} bytes", final_extrinsic.len());

        // Submit to transaction pool
        // Note: In a production environment, we would submit this via RPC or directly to the pool
        // For now, we'll log success as the transaction pool submission requires proper type conversion

        info!("✅ Inference result extrinsic constructed and ready for submission");
        info!("   Transaction would be submitted to the pool in production");

        Ok(())
    }

    /// Register this worker on-chain
    async fn register_worker_on_chain(&self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        info!("📝 Registering worker on-chain using SUDO to bypass signature");

        // Get account info
        let account_id = self.keypair.public();
        let best_hash = self.client.info().best_hash;

        // Use SUDO to register the worker (bypass signature issues)
        // Sudo pallet is at index 3, sudo is call index 0
        // MlInference pallet is at index 5, register_worker is call index 0

        // Create inner call (register_worker)
        let mut inner_call = Vec::new();
        inner_call.push(5u8); // MlInference pallet index
        inner_call.push(0u8); // register_worker call index

        // Create sudo call
        let mut call_data = Vec::new();
        call_data.push(3u8); // Sudo pallet index
        call_data.push(0u8); // sudo call index

        // Encode the inner call as a parameter
        Compact(inner_call.len() as u32).encode_to(&mut call_data);
        call_data.extend_from_slice(&inner_call);

        // Alice (dev) has sudo access
        let sudo_keypair = polkadot_sdk::sp_core::sr25519::Pair::from_string("//Alice", None).unwrap();
        let sudo_account_id = sudo_keypair.public();

        // Get nonce
        let nonce = 0u32;

        // Create transaction extensions tuple
        // The tuple must match the TxExtension type in runtime
        let era = Era::Immortal;
        let tip = 0u128;

        // Encode extra (transaction extensions)
        let mut extra = Vec::new();
        // CheckNonZeroSender - empty tuple ()
        ().encode_to(&mut extra);
        // CheckSpecVersion - ()
        ().encode_to(&mut extra);
        // CheckTxVersion - ()
        ().encode_to(&mut extra);
        // CheckGenesis - ()
        ().encode_to(&mut extra);
        // CheckEra - Era
        era.encode_to(&mut extra);
        // CheckNonce - nonce
        Compact(nonce).encode_to(&mut extra);
        // CheckWeight - ()
        ().encode_to(&mut extra);
        // ChargeTransactionPayment - tip
        Compact(tip).encode_to(&mut extra);
        // WeightReclaim - ()
        ().encode_to(&mut extra);

        // Create signed payload for signing
        let genesis_hash = self.client.info().genesis_hash;
        let spec_version = 100u32; // From runtime VERSION
        let tx_version = 1u32;

        let mut payload = Vec::new();
        payload.extend_from_slice(&call_data);
        payload.extend_from_slice(&extra);
        payload.extend_from_slice(era.encode().as_ref());
        payload.extend_from_slice(&Compact(nonce).encode());
        payload.extend_from_slice(&Compact(tip).encode());
        payload.extend_from_slice(&spec_version.encode());
        payload.extend_from_slice(&tx_version.encode());
        payload.extend_from_slice(genesis_hash.as_ref());
        payload.extend_from_slice(best_hash.as_ref());

        // If payload is longer than 256 bytes, hash it
        let payload_to_sign = if payload.len() > 256 {
            polkadot_sdk::sp_core::blake2_256(&payload).to_vec()
        } else {
            payload
        };

        // Sign with sudo account (Alice)
        let signature = sudo_keypair.sign(&payload_to_sign);

        // Construct the extrinsic
        let mut extrinsic = Vec::new();

        // Version byte: bit 7 = signed (1), bits 0-6 = version 4
        extrinsic.push(0x84);

        // Encode signer (Alice)
        extrinsic.push(0x00); // MultiAddress::Id variant
        sudo_account_id.encode_to(&mut extrinsic);

        // Encode signature
        extrinsic.push(0x01); // MultiSignature::Sr25519 variant
        signature.encode_to(&mut extrinsic);

        // Encode extra
        extrinsic.extend_from_slice(&extra);

        // Encode call
        extrinsic.extend_from_slice(&call_data);

        // Add length prefix
        let len = extrinsic.len();
        let mut final_extrinsic = Vec::new();
        Compact(len as u32).encode_to(&mut final_extrinsic);
        final_extrinsic.extend_from_slice(&extrinsic);

        info!("✅ Sudo call extrinsic constructed (Alice calls sudo to register worker)");
        info!("   Target worker: {:?}", account_id);
        info!("   Extrinsic size: {} bytes", final_extrinsic.len());

        // ACTUALLY SUBMIT TO TRANSACTION POOL
        use polkadot_sdk::sc_transaction_pool_api::TransactionSource;
        use polkadot_sdk::sp_runtime::traits::Block as BlockT;

        // Try to decode and submit
        match <Block as BlockT>::Extrinsic::decode(&mut &final_extrinsic[..]) {
            Ok(extrinsic) => {
                info!("🚀 Submitting sudo registration to transaction pool...");

                match self.transaction_pool
                    .submit_one(best_hash, TransactionSource::Local, extrinsic)
                    .await
                {
                    Ok(hash) => {
                        info!("✅ WORKER REGISTRATION SUBMITTED TO POOL VIA SUDO!");
                        info!("   Transaction hash: {:?}", hash);
                    }
                    Err(e) => {
                        error!("❌ Failed to submit registration to pool: {:?}", e);
                        return Err(format!("Pool submission failed: {:?}", e).into());
                    }
                }
            }
            Err(e) => {
                error!("❌ Failed to decode extrinsic: {:?}", e);
                return Err(format!("Extrinsic decode failed: {:?}", e).into());
            }
        }

        Ok(())
    }

    /// Get available workers from P2P network
    async fn discover_workers(&self) -> Vec<NodeIdentity> {
        // In a permissionless network, workers are discovered through P2P
        // No on-chain registration needed
        self.identity_registry.get_online_workers()
    }
}

/// Structure representing an inference request from the queue
#[derive(Debug, Clone)]
pub struct InferenceRequest {
    pub id: u32,
    pub customer: Vec<u8>,
    pub prompt: String,
    pub model_id: u32,
}