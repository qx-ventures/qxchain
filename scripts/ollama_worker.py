#!/usr/bin/env python3
"""
QX Chain Ollama Worker Script

This script runs an ML worker node that:
1. Registers as a worker on the QX Chain
2. Registers ML models (e.g., zoo assistant)
3. Listens for inference requests
4. Runs inference using Ollama
5. Submits results to the chain
"""

import json
import hashlib
import requests
import time
import asyncio
import argparse
from typing import Dict, Any, Optional
from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException

class OllamaWorker:
    def __init__(self, 
                 chain_endpoint: str = "ws://localhost:9944",
                 ollama_endpoint: str = "http://localhost:11434",
                 worker_seed: str = "//Alice//stash"):
        
        self.substrate = SubstrateInterface(url=chain_endpoint)
        self.ollama_endpoint = ollama_endpoint
        self.keypair = Keypair.create_from_uri(worker_seed)
        self.worker_address = self.keypair.ss58_address
        
        print(f"Worker initialized with address: {self.worker_address}")
        print(f"Chain endpoint: {chain_endpoint}")
        print(f"Ollama endpoint: {ollama_endpoint}")
        
        # Worker state
        self.registered = False
        self.models = {}  # model_id -> model_info
        self.running = False
    
    async def check_chain_connection(self):
        """Check if chain connection is healthy"""
        try:
            # Try to get the latest block
            latest_block = self.substrate.get_block_number(None)
            print(f"🔗 Chain connection healthy - Latest block: {latest_block}")
            return True
        except Exception as e:
            print(f"⚠️ Chain connection unhealthy: {e}")
            return False
        
    async def register_worker(self, stake_amount: int = 1000000):
        """Register this node as a worker on the chain"""
        try:
            call = self.substrate.compose_call(
                call_module='QxAi',
                call_function='register_worker',
                call_params={'stake': stake_amount}
            )
            
            extrinsic = self.substrate.create_signed_extrinsic(call=call, keypair=self.keypair)
            receipt = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            
            if receipt.is_success:
                block_hash = receipt.block_hash
                tx_hash = receipt.extrinsic_hash
                print(f"✅ Worker registered successfully with stake: {stake_amount}")
                print(f"📦 Block: {block_hash}")
                print(f"🧾 Transaction: {tx_hash}")
                self.registered = True
                return True
            else:
                print(f"❌ Worker registration failed: {receipt.error_message}")
                return False
                
        except Exception as e:
            print(f"❌ Error registering worker: {e}")
            return False
    
    async def register_model(self, model_name: str, ollama_model: str, endpoint: str):
        """Register a model on the chain"""
        try:
            # Generate model hash (simplified for MVP)
            model_hash = hashlib.sha256(f"{model_name}:{ollama_model}".encode()).digest()
            
            # Chain doesn't support register_model yet, register locally
            model_id = len(self.models)  # Simple ID assignment
            self.models[model_id] = {
                'name': model_name,
                'ollama_model': ollama_model,
                'endpoint': endpoint,
                'hash': model_hash
            }
            print(f"✅ Model registered locally: {model_name} (ID: {model_id})")
            return model_id
            
        except Exception as e:
            print(f"❌ Error registering model: {e}")
            return None
    
    async def run_inference(self, model_id: int, prompt: str) -> Optional[str]:
        """Run inference using Ollama"""
        try:
            if model_id not in self.models:
                print(f"❌ Model ID {model_id} not found")
                return None
                
            model_info = self.models[model_id]
            ollama_model = model_info['ollama_model']
            
            # Call Ollama API
            response = requests.post(
                f"{self.ollama_endpoint}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                output = result.get('response', '')
                print(f"✅ Inference completed for model {model_id}")
                return output
            else:
                print(f"❌ Ollama request failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error running inference: {e}")
            return None
    
    async def submit_inference(self, model_id: int, input_text: str, output_text: str):
        """Submit inference result to the chain"""
        try:
            # Generate hashes
            input_hash = hashlib.sha256(input_text.encode()).digest()
            output_hash = hashlib.sha256(output_text.encode()).digest()
            
            # Reconnect if connection is broken
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Check if substrate connection is still alive
                    try:
                        # Test the connection by getting a simple property
                        self.substrate.get_block_number(None)
                    except:
                        print(f"🔄 Reconnecting to chain (attempt {attempt + 1}/{max_retries})")
                        chain_url = getattr(self.substrate, 'url', "ws://localhost:9944")
                        self.substrate = SubstrateInterface(url=chain_url)
                    
                    call = self.substrate.compose_call(
                        call_module='QxAi',
                        call_function='request_inference'
                    )
                    
                    extrinsic = self.substrate.create_signed_extrinsic(call=call, keypair=self.keypair)
                    receipt = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
                    
                    if receipt.is_success:
                        block_hash = receipt.block_hash
                        tx_hash = receipt.extrinsic_hash
                        print(f"✅ Inference request recorded for model {model_id}")
                        print(f"📦 Block: {block_hash}")
                        print(f"🧾 Transaction: {tx_hash}")
                        return True
                    else:
                        print(f"❌ Failed to submit inference: {receipt.error_message}")
                        return False
                        
                except (ConnectionError, BrokenPipeError, SubstrateRequestException) as conn_err:
                    print(f"⚠️ Connection error (attempt {attempt + 1}/{max_retries}): {conn_err}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)  # Wait before retry
                        continue
                    else:
                        print(f"❌ Failed to submit after {max_retries} attempts")
                        return False
                        
                except Exception as e:
                    print(f"❌ Unexpected error submitting inference: {e}")
                    return False
            
        except Exception as e:
            print(f"❌ Error submitting inference: {e}")
            return False
    
    async def process_inference_request(self, prompt: str, model_id: int = 0):
        """Complete inference pipeline: run inference and submit to chain"""
        print(f"🔄 Processing inference request for model {model_id}")
        print(f"Input: {prompt[:100]}...")
        
        # Run inference
        output = await self.run_inference(model_id, prompt)
        if not output:
            return None
        
        print(f"Output: {output[:100]}...")
        
        # Submit to chain
        inference_id = await self.submit_inference(model_id, prompt, output)
        return inference_id
    
    async def start_api_server(self, port: int = 8000):
        """Start HTTP API server for receiving inference requests"""
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel
        import uvicorn
        
        app = FastAPI(title="QX Chain Ollama Worker API")
        
        class InferenceRequest(BaseModel):
            prompt: str
            model_id: int = 0
        
        @app.get("/")
        async def root():
            """Root endpoint redirects to API documentation"""
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/docs")
        
        @app.post("/inference")
        async def inference_endpoint(request: InferenceRequest):
            if not self.registered:
                raise HTTPException(status_code=400, detail="Worker not registered")
            
            if request.model_id not in self.models:
                raise HTTPException(status_code=400, detail="Model not found")
            
            inference_id = await self.process_inference_request(request.prompt, request.model_id)
            
            if inference_id is None:
                raise HTTPException(status_code=500, detail="Inference failed")
            
            return {
                "inference_id": inference_id,
                "status": "submitted",
                "message": "Inference submitted to chain for validation"
            }
        
        @app.get("/status")
        async def status_endpoint():
            return {
                "worker_address": self.worker_address,
                "registered": self.registered,
                "models": list(self.models.keys()),
                "chain_endpoint": self.substrate.url
            }
        
        @app.get("/models")
        async def models_endpoint():
            # Convert binary data to hex strings for JSON serialization
            serializable_models = {}
            for model_id, model_info in self.models.items():
                # Ensure hash is properly converted to hex string
                hash_value = model_info["hash"]
                if isinstance(hash_value, bytes):
                    hash_hex = hash_value.hex()
                else:
                    hash_hex = str(hash_value)
                
                serializable_models[model_id] = {
                    "name": model_info["name"],
                    "ollama_model": model_info["ollama_model"],
                    "endpoint": model_info["endpoint"],
                    "hash": hash_hex
                }
            return serializable_models
        
        print(f"🚀 Starting API server on port {port}")
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    
    async def setup_zoo_model(self):
        """Setup a zoo assistant model"""
        model_id = await self.register_model(
            model_name="zoo_assistant",
            ollama_model="gemma3:4b",  # Lightweight model for testing
            endpoint=f"http://localhost:8000/inference"
        )
        
        if model_id is not None:
            print(f"✅ Zoo assistant model setup complete (ID: {model_id})")
            print(f"💡 Model ready for inference requests via API")
        
        return model_id

async def main():
    parser = argparse.ArgumentParser(description='QX Chain Ollama Worker')
    parser.add_argument('--chain', default='ws://localhost:9944', help='Chain endpoint')
    parser.add_argument('--ollama', default='http://localhost:11434', help='Ollama endpoint')
    parser.add_argument('--seed', default='//Alice//stash', help='Worker account seed')
    parser.add_argument('--port', type=int, default=8000, help='API server port')
    parser.add_argument('--setup-zoo', action='store_true', help='Setup zoo assistant model')
    
    args = parser.parse_args()
    
    # Initialize worker
    worker = OllamaWorker(
        chain_endpoint=args.chain,
        ollama_endpoint=args.ollama,
        worker_seed=args.seed
    )
    
    print("🌟 QX Chain Ollama Worker Starting...")
    
    # Check chain connection first
    if not await worker.check_chain_connection():
        print("❌ Chain connection failed. Please ensure the chain is running.")
        return
    
    # Register worker
    if await worker.register_worker():
        if args.setup_zoo:
            await worker.setup_zoo_model()
        
        # Start API server
        await worker.start_api_server(args.port)
    else:
        print("❌ Failed to register worker. Exiting.")

if __name__ == "__main__":
    asyncio.run(main())
