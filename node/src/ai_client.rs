// Generic AI client that supports OpenAI-compatible APIs

use serde::{Deserialize, Serialize};
use std::time::Duration;
use log::{info, debug};

#[derive(Clone, Debug)]
pub struct AiConfig {
    pub endpoint: String,
    pub provider: String,
    pub api_key: Option<String>,
    pub model: String,
}

impl AiConfig {
    pub fn new(endpoint: String, provider: String, api_key: Option<String>, model: String) -> Self {
        Self {
            endpoint,
            provider,
            api_key,
            model,
        }
    }

    /// Get the appropriate API path for the provider
    pub fn get_api_path(&self) -> &str {
        "/v1/chat/completions" // Use OpenAI-compatible format
    }

    /// Check if this provider uses chat completion format (OpenAI-style)
    pub fn uses_chat_format(&self) -> bool {
        true // Always use OpenAI-compatible format
    }
}

// OpenAI-compatible request/response structures
#[derive(Debug, Serialize)]
pub struct ChatCompletionRequest {
    pub model: String,
    pub messages: Vec<ChatMessage>,
    pub temperature: f32,
    pub max_tokens: u32,
    pub seed: Option<u32>,
    pub top_p: f32,
    pub frequency_penalty: f32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Deserialize)]
pub struct ChatCompletionResponse {
    pub choices: Vec<ChatChoice>,
}

#[derive(Debug, Deserialize)]
pub struct ChatChoice {
    pub message: ChatMessage,
}


/// Generic AI client that handles different providers
pub struct AiClient {
    pub config: AiConfig,
    client: reqwest::Client,
}

impl AiClient {
    pub fn new(config: AiConfig) -> Self {
        Self {
            config,
            client: reqwest::Client::new(),
        }
    }

    /// Run inference with deterministic parameters
    pub async fn generate(&self, prompt: &str, seed: u32) -> Result<String, Box<dyn std::error::Error + Send + Sync>> {
        info!("Generating AI response");
        debug!("Model: {}, Seed: {}", self.config.model, seed);

        self.generate_chat_completion(prompt, seed).await
    }

    /// Generate using OpenAI-compatible chat completion API
    async fn generate_chat_completion(&self, prompt: &str, seed: u32) -> Result<String, Box<dyn std::error::Error + Send + Sync>> {
        let url = format!("{}{}", self.config.endpoint, self.config.get_api_path());

        let mut request = self.client
            .post(&url)
            .json(&ChatCompletionRequest {
                model: self.config.model.clone(),
                messages: vec![
                    ChatMessage {
                        role: "system".to_string(),
                        content: "You are a helpful AI assistant.".to_string(),
                    },
                    ChatMessage {
                        role: "user".to_string(),
                        content: prompt.to_string(),
                    },
                ],
                temperature: 0.7,
                max_tokens: 512,
                seed: Some(seed),
                top_p: 0.9,
                frequency_penalty: 0.0,
            })
            .timeout(Duration::from_secs(60));

        // Add API key if provided
        if let Some(api_key) = &self.config.api_key {
            request = request.header("Authorization", format!("Bearer {}", api_key));
        }

        let response = request.send().await?;

        if !response.status().is_success() {
            let error_text = response.text().await?;
            return Err(format!("API request failed: {}", error_text).into());
        }

        let result: ChatCompletionResponse = response.json().await?;

        Ok(result.choices
            .first()
            .map(|c| c.message.content.clone())
            .unwrap_or_default())
    }

}