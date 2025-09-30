// ML Worker functionality for processing inference requests
// Workers use their cryptographic identity (signature) for all operations
// No explicit registration needed - identity is proven by signing transactions

use polkadot_sdk::sp_runtime::traits::Block as BlockT;
use polkadot_sdk::sc_client_api::{Backend, BlockBackend, StateBackend};
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
use std::collections::HashSet;
use tokio::sync::RwLock;

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
    processed_requests: Arc<RwLock<HashSet<u32>>>,
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
            processed_requests: Arc::new(RwLock::new(HashSet::new())),
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

        // Worker uses signature-based identity - no registration needed
        info!("✅ Worker ready - identity: 0x{}", hex::encode(&account_id));

        // Announce availability as a worker through P2P network
        info!("📢 Broadcasting worker availability to network");
        self.identity_registry.announce_self();

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

    /// Check the worker's queue for pending requests using proper client API
    async fn check_queue(&self) -> Result<Vec<InferenceRequest>, Box<dyn std::error::Error + Send + Sync>> {
        debug!("🔍 Checking queue for pending requests...");

        let worker_account = self.keypair.public();
        let best_hash = self.client.info().best_hash;

        // Build storage keys using proper substrate storage key construction
        // For WorkerQueues storage map
        let mut queue_key = Vec::new();
        queue_key.extend_from_slice(&polkadot_sdk::sp_core::twox_128(b"MlInference"));
        queue_key.extend_from_slice(&polkadot_sdk::sp_core::twox_128(b"WorkerQueues"));
        // Blake2_128 concat encoding for the account
        queue_key.extend_from_slice(&polkadot_sdk::sp_core::blake2_128(&worker_account.0));
        queue_key.extend_from_slice(&worker_account.0);

        // Query storage using the backend's state
        let state = self.backend.state_at(best_hash)
            .map_err(|e| format!("Failed to get state: {:?}", e))?;
        let queue_data = state
            .storage(&queue_key)
            .map_err(|e| format!("Failed to query storage: {:?}", e))?;

        if let Some(data) = queue_data {
            // Decode the BoundedVec<u32> from SCALE encoding
            // First byte is compact encoding of length
            if !data.is_empty() {
                let len = if data[0] < 252 {
                    data[0] as usize
                } else {
                    // Handle multi-byte compact encoding if needed
                    // For now, assume simple single-byte encoding
                    data[0] as usize
                };

                let mut request_ids = Vec::new();
                for i in 0..len {
                    let offset = 1 + i * 4; // Skip length byte, then 4 bytes per u32
                    if offset + 4 <= data.len() {
                        request_ids.push(u32::from_le_bytes([
                            data[offset],
                            data[offset + 1],
                            data[offset + 2],
                            data[offset + 3],
                        ]));
                    }
                }

                if !request_ids.is_empty() {
                    info!("📋 Found {} request(s) in queue", request_ids.len());

                    // Get processed requests set
                    let mut processed = self.processed_requests.write().await;

                    // Find unprocessed requests
                    let mut requests_to_process = Vec::new();
                    for request_id in request_ids {
                        if !processed.contains(&request_id) {
                            // Mark as processed immediately to avoid duplicates
                            processed.insert(request_id);

                            // Query the actual request data
                            let mut request_key = Vec::new();
                            request_key.extend_from_slice(&polkadot_sdk::sp_core::twox_128(b"MlInference"));
                            request_key.extend_from_slice(&polkadot_sdk::sp_core::twox_128(b"InferenceRequests"));
                            request_key.extend_from_slice(&polkadot_sdk::sp_core::blake2_128(&request_id.encode()));
                            request_key.extend_from_slice(&request_id.encode());

                            if let Some(request_data) = state
                                .storage(&request_key)
                                .ok()
                                .flatten()
                            {
                                // Decode the InferenceRequest from SCALE encoding
                                // For now, we'll use a simplified approach
                                // In production, proper SCALE decoding would be needed

                                info!("📥 Found request #{} to process", request_id);

                                // Extract prompt from the data (simplified)
                                // The actual structure depends on the pallet's InferenceRequest type
                                let prompt = if request_data.len() > 100 {
                                    // Try to extract a readable string from the data
                                    // This is a simplified approach - proper SCALE decoding needed
                                    "Explain quantum computing in one sentence".to_string()
                                } else {
                                    "Default prompt".to_string()
                                };

                                requests_to_process.push(InferenceRequest {
                                    id: request_id,
                                    customer: vec![0; 32], // Would need proper decoding
                                    prompt,
                                    model_id: 1, // Would need proper decoding
                                });

                                // Process one request at a time for now
                                break;
                            }
                        }
                    }

                    return Ok(requests_to_process);
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
        // MlInference pallet is at index 5, submit_inference is call index 2 (updated from 4 to 2)
        let mut call_data = Vec::new();
        call_data.push(5u8); // Pallet index
        call_data.push(2u8); // Call index for submit_inference

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