// ML Worker functionality for processing inference requests

use polkadot_sdk::sp_runtime::traits::Block as BlockT;
use polkadot_sdk::sc_client_api::{Backend, BlockBackend};
use polkadot_sdk::sp_api::ProvideRuntimeApi;
use polkadot_sdk::sp_blockchain::HeaderBackend;
use polkadot_sdk::sc_transaction_pool_api::TransactionPool;
use std::sync::Arc;
use std::time::Duration;
use log::{info, error, warn};
use crate::ai_client::{AiClient, AiConfig};

/// ML Worker that processes inference requests
pub struct MlWorker<Block, Client, Backend, Pool> {
    client: Arc<Client>,
    backend: Arc<Backend>,
    ai_client: AiClient,
    keypair: polkadot_sdk::sp_core::sr25519::Pair,
    transaction_pool: Arc<Pool>,
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
    ) -> Self {
        let ai_client = AiClient::new(ai_config);
        Self {
            client,
            backend,
            ai_client,
            keypair,
            transaction_pool,
            _phantom: std::marker::PhantomData,
        }
    }

    /// Start the ML worker task
    pub async fn start(self) {
        info!("🤖 Starting ML Worker");

        // Auto-register as worker on startup
        if let Err(e) = self.register_worker().await {
            error!("Failed to register as worker: {:?}", e);
            warn!("Worker will continue but won't receive requests until registered");
        }

        // Register AI models this worker supports
        if let Err(e) = self.register_models().await {
            error!("Failed to register models: {:?}", e);
        }

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

    /// Check the worker's queue for pending requests
    async fn check_queue(&self) -> Result<Vec<InferenceRequest>, Box<dyn std::error::Error + Send + Sync>> {
        // Query the runtime storage for pending requests
        // This would interact with the QxAi pallet's WorkerQueues storage

        // Placeholder for now - actual implementation would query chain state
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
    async fn submit_inference(&self, request_id: u32, _output: String) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        info!("Submitting inference result for request {}", request_id);

        // This would create and submit an extrinsic to the QxAi pallet
        // Placeholder for now - actual implementation would submit transaction

        Ok(())
    }

    /// Register this node as a worker
    async fn register_worker(&self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        info!("Registering as ML worker...");

        // TODO: Implement proper on-chain registration
        // This requires constructing and submitting an extrinsic transaction
        // For now, simulating registration to allow testing

        info!("✅ Successfully registered as ML worker (simulated)");
        Ok(())
    }

    /// Register AI models this worker supports
    async fn register_models(&self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        info!("Registering supported AI models...");

        // Register the model based on the AI config
        let model_name = "ai-model";
        info!("Registering model: {} at {}", model_name, self.ai_client.config.endpoint);

        // TODO: Implement actual model registration transaction
        // Similar to worker registration, this needs proper extrinsic construction

        info!("✅ Successfully registered AI models (simulated)");
        Ok(())
    }
}

#[derive(Debug, Clone)]
pub struct InferenceRequest {
    pub id: u32,
    pub customer: Vec<u8>,
    pub prompt: String,
    pub model_id: u32,
}