// ML Validator functionality for verifying inference results

use polkadot_sdk::sp_runtime::traits::Block as BlockT;
use polkadot_sdk::sc_client_api::{Backend, BlockBackend};
use polkadot_sdk::sp_api::ProvideRuntimeApi;
use polkadot_sdk::sp_blockchain::HeaderBackend;
use polkadot_sdk::sc_transaction_pool_api::TransactionPool;
use polkadot_sdk::sp_core::crypto::Pair;
use std::sync::Arc;
use std::time::Duration;
use std::collections::HashSet;
use log::{info, error, warn};
use crate::ai_client::{AiClient, AiConfig};
use crate::node_identity::{NodeIdentityRegistry, NodeType, NodeIdentity};
// Transaction construction will be added later
// use qxchain_runtime::{UncheckedExtrinsic, RuntimeCall, MlInferenceCall};

/// ML Validator that verifies inference results
pub struct MlValidator<Block, Client, Backend, Pool> {
    client: Arc<Client>,
    backend: Arc<Backend>,
    ai_client: AiClient,
    keypair: polkadot_sdk::sp_core::sr25519::Pair,
    transaction_pool: Arc<Pool>,
    processed_inferences: HashSet<u32>,
    identity_registry: Arc<NodeIdentityRegistry>,
    peer_id: String,
    endpoint: String,
    _phantom: std::marker::PhantomData<Block>,
}

impl<Block, Client, BE, Pool> MlValidator<Block, Client, BE, Pool>
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
            processed_inferences: HashSet::new(),
            identity_registry,
            peer_id,
            endpoint,
            _phantom: std::marker::PhantomData,
        }
    }

    /// Start the ML validator task
    pub async fn start(mut self) {
        info!("🛡️ Starting ML Validator");

        // Register self in the local identity registry
        let account_id = self.keypair.public().0.to_vec();
        if let Err(e) = self.identity_registry.register_self(
            self.peer_id.clone(),
            self.endpoint.clone(),
            NodeType::Validator,
            account_id.clone(),
        ) {
            error!("Failed to register node identity: {:?}", e);
        }

        // Announce availability as a validator through P2P network
        // No on-chain registration needed - permissionless network
        info!("📢 Broadcasting validator availability to network");
        self.identity_registry.announce_self();

        // Update status to online
        if let Err(e) = self.identity_registry.update_self_status(&account_id, true) {
            warn!("Failed to update node status: {:?}", e);
        }

        // Main validator loop
        let mut interval = tokio::time::interval(Duration::from_secs(10));

        loop {
            interval.tick().await;

            // Check for pending inferences to validate
            match self.get_pending_inferences().await {
                Ok(inferences) => {
                    for inference in inferences {
                        if !self.processed_inferences.contains(&inference.id) {
                            if let Err(e) = self.validate_inference(inference).await {
                                error!("Failed to validate inference: {:?}", e);
                            }
                        }
                    }
                },
                Err(e) => {
                    warn!("Failed to get pending inferences: {:?}", e);
                }
            }
        }
    }

    /// Get pending inferences that need validation
    async fn get_pending_inferences(&self) -> Result<Vec<PendingInference>, Box<dyn std::error::Error + Send + Sync>> {
        // Query the runtime storage for pending inferences
        // This would interact with the QxAi pallet's InferenceResults storage

        // Placeholder for now - actual implementation would query chain state
        Ok(vec![])
    }

    /// Validate a single inference
    async fn validate_inference(&mut self, inference: PendingInference) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        info!("Validating inference: {}", inference.id);

        // 1. Re-run the inference with deterministic parameters
        let expected_output = self.verify_inference(&inference).await?;

        // 2. Compare with submitted output
        let is_valid = expected_output == inference.output;

        // 3. Submit validation or challenge
        if is_valid {
            self.submit_validation(inference.id).await?;
            info!("Inference {} validated successfully", inference.id);
        } else {
            self.submit_challenge(inference.id, expected_output).await?;
            warn!("Inference {} challenged - output mismatch", inference.id);
        }

        // Mark as processed
        self.processed_inferences.insert(inference.id);

        Ok(())
    }

    /// Re-run inference for verification
    async fn verify_inference(&self, inference: &PendingInference) -> Result<String, Box<dyn std::error::Error + Send + Sync>> {
        // Get original request details
        let prompt = &inference.original_prompt;
        let model_id = inference.model_id;

        // Use same deterministic seed for verification
        let seed = 42u32;

        info!("Verifying inference with model_id: {}", model_id);

        // Generate with same parameters for deterministic output
        self.ai_client.generate(prompt, seed).await
    }

    /// Submit validation for correct inference
    async fn submit_validation(&self, inference_id: u32) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        info!("Submitting validation for inference {}", inference_id);

        // TODO: Implement proper transaction construction once runtime types are properly configured

        info!("✅ Validation ready for submission (transaction construction pending)");
        Ok(())
    }

    /// Submit challenge for incorrect inference
    async fn submit_challenge(&self, inference_id: u32, expected_output: String) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        info!("Submitting challenge for inference {}", inference_id);
        info!("Expected output: {}...", &expected_output[..expected_output.len().min(100)]);

        // TODO: Implement proper transaction construction once runtime types are properly configured

        info!("✅ Challenge ready for submission (transaction construction pending)");
        Ok(())
    }

    /// Get available validators from P2P network
    async fn discover_validators(&self) -> Vec<NodeIdentity> {
        // In a permissionless network, validators are discovered through P2P
        // No on-chain registration needed
        self.identity_registry.get_online_validators()
    }

    // Transaction construction will be implemented once runtime types are properly configured
    // This requires proper SignedExtension trait implementation
}

#[derive(Debug, Clone)]
pub struct PendingInference {
    pub id: u32,
    pub worker: Vec<u8>,
    pub request_id: u32,
    pub output: String,
    pub original_prompt: String,
    pub model_id: u32,
    pub submitted_at: u32,
}