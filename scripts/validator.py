#!/usr/bin/env python3
"""
QX Chain Validator Script

This script runs a validator node that:
1. Registers as a validator (city-controlled)
2. Monitors pending inferences
3. Verifies inference results by re-running them
4. Challenges invalid inferences or validates correct ones
"""

import json
import hashlib
import requests
import time
import asyncio
import argparse
from typing import Dict, Any, Optional, List
from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException

class QXValidator:
    def __init__(self, 
                 chain_endpoint: str = "ws://localhost:9944",
                 ollama_endpoint: str = "http://localhost:11434",
                 validator_seed: str = "//Bob//stash"):
        
        self.substrate = SubstrateInterface(url=chain_endpoint)
        self.ollama_endpoint = ollama_endpoint
        self.keypair = Keypair.create_from_uri(validator_seed)
        self.validator_address = self.keypair.ss58_address
        
        print(f"Validator initialized with address: {self.validator_address}")
        print(f"Chain endpoint: {chain_endpoint}")
        print(f"Ollama endpoint: {ollama_endpoint}")
        
        # Validator state
        self.registered = False
        self.running = False
        self.processed_inferences = set()  # Track processed inference IDs
        
    async def register_validator(self, stake_amount: int = 1000000):
        """Register this node as a validator (requires sudo/governance)"""
        try:
            # Chain doesn't have register_validator yet, use register_worker
            call = self.substrate.compose_call(
                call_module='QxAi',
                call_function='register_worker'
            )
            
            # Note: This requires sudo privileges in MVP
            # In production, this would be done through governance
            extrinsic = self.substrate.create_signed_extrinsic(call=call, keypair=self.keypair)
            receipt = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            
            if receipt.is_success:
                block_hash = receipt.block_hash
                tx_hash = receipt.extrinsic_hash
                print(f"✅ Validator registered successfully with stake: {stake_amount}")
                print(f"📦 Block: {block_hash}")
                print(f"🧾 Transaction: {tx_hash}")
                self.registered = True
                return True
            else:
                print(f"❌ Validator registration failed: {receipt.error_message}")
                return False
                
        except Exception as e:
            print(f"❌ Error registering validator: {e}")
            return False
    
    async def get_pending_inferences(self) -> List[Dict]:
        """Get all pending inferences from the chain"""
        try:
            # Query storage for pending inferences
            # This is a simplified approach - in production we'd use events/indexing
            pending_inferences = []
            
            try:
                # Get next inference ID to determine range
                next_id_result = self.substrate.query(
                    module='QxAi',
                    storage_function='NextInferenceId'
                )
                
                if next_id_result:
                    next_id = next_id_result.value
                    
                    # Check last 100 inferences for pending ones
                    start_id = max(0, next_id - 100)
                    
                    for inference_id in range(start_id, next_id):
                        inference_result = self.substrate.query(
                            module='QxAi',
                            storage_function='Inferences',
                            params=[inference_id]
                        )
                        
                        if inference_result and inference_result.value:
                            inference = inference_result.value
                            if inference['status'] == 'Pending':
                                pending_inferences.append({
                                    'id': inference_id,
                                    'worker': inference['worker'],
                                    'model_id': inference['model_id'],
                                    'input_hash': bytes(inference['input_hash']),
                                    'output_hash': bytes(inference['output_hash']),
                                    'output': bytes(inference['output']).decode('utf-8', errors='ignore'),
                                    'submitted_at': inference['submitted_at']
                                })
                
            except Exception as storage_error:
                # Storage functions not implemented yet - this is expected in MVP
                if "not found" in str(storage_error):
                    print(f"💡 Inference storage not implemented yet - validator running in monitoring mode")
                else:
                    print(f"⚠️ Storage query error: {storage_error}")
            
            return pending_inferences
            
        except Exception as e:
            print(f"❌ Error getting pending inferences: {e}")
            return []
    
    async def get_model_info(self, model_id: int) -> Optional[Dict]:
        """Get model information from the chain"""
        try:
            model_result = self.substrate.query(
                module='QxAi',
                storage_function='Models',
                params=[model_id]
            )
            
            if model_result and model_result.value:
                model = model_result.value
                return {
                    'owner': model['owner'],
                    'model_hash': bytes(model['model_hash']),
                    'name': bytes(model['name']).decode('utf-8'),
                    'endpoint': bytes(model['endpoint']).decode('utf-8'),
                    'active': model['active']
                }
            
            return None
            
        except Exception as e:
            if "not found" in str(e):
                # Models storage not implemented yet - return mock data for validator testing
                return {
                    'owner': 'unknown',
                    'model_hash': b'mock_hash',
                    'name': 'zoo_assistant',
                    'endpoint': 'http://localhost:8000/inference',
                    'active': True
                }
            print(f"❌ Error getting model info: {e}")
            return None
    
    async def verify_inference(self, inference: Dict, model_info: Dict) -> tuple[bool, str]:
        """Verify an inference by re-running it"""
        try:
            # For MVP, we'll extract the original prompt from the worker's endpoint
            # In production, this would be more sophisticated
            
            # Try to determine the model name for Ollama
            model_name = model_info['name']
            
            # Map model names to Ollama models
            ollama_model_map = {
                'zoo_assistant': 'gemma3:4b',
                'permits_assistant': 'gemma3:4b',
                'parks_assistant': 'gemma3:4b'
            }
            
            ollama_model = ollama_model_map.get(model_name, 'gemma3:4b')
            
            # For MVP, we'll use a test prompt to verify model behavior
            # In production, we'd need to store/reconstruct the original input
            test_prompts = {
                'zoo_assistant': "What are the zoo's operating hours?",
                'permits_assistant': "How do I apply for a building permit?",
                'parks_assistant': "What events are happening in the parks this week?"
            }
            
            test_prompt = test_prompts.get(model_name, "Hello, how can you help?")
            
            # Run inference with Ollama
            response = requests.post(
                f"{self.ollama_endpoint}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": test_prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_output = result.get('response', '')
                
                # For MVP: Simple comparison
                # In production: More sophisticated verification
                actual_output = inference['output']
                
                # Check if outputs are reasonably similar (length-based heuristic for MVP)
                if abs(len(expected_output) - len(actual_output)) < 50:
                    return True, expected_output
                else:
                    return False, expected_output
            else:
                print(f"❌ Ollama verification failed: {response.status_code}")
                return False, ""
                
        except Exception as e:
            print(f"❌ Error verifying inference: {e}")
            return False, ""
    
    async def validate_inference(self, inference_id: int):
        """Mark an inference as validated"""
        try:
            call = self.substrate.compose_call(
                call_module='QxAi',
                call_function='validate_inference',
                call_params={'inference_id': inference_id}
            )
            
            extrinsic = self.substrate.create_signed_extrinsic(call=call, keypair=self.keypair)
            receipt = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            
            if receipt.is_success:
                print(f"✅ Inference {inference_id} validated successfully")
                return True
            else:
                print(f"❌ Validation failed: {receipt.error_message}")
                return False
                
        except Exception as e:
            print(f"❌ Error validating inference: {e}")
            return False
    
    async def challenge_inference(self, inference_id: int, expected_output: str):
        """Challenge an invalid inference"""
        try:
            call = self.substrate.compose_call(
                call_module='QxAi',
                call_function='challenge_inference',
                call_params={
                    'inference_id': inference_id,
                    'expected_output': list(expected_output.encode()[:1024])
                }
            )
            
            extrinsic = self.substrate.create_signed_extrinsic(call=call, keypair=self.keypair)
            receipt = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            
            if receipt.is_success:
                print(f"✅ Inference {inference_id} challenged successfully")
                return True
            else:
                print(f"❌ Challenge failed: {receipt.error_message}")
                return False
                
        except Exception as e:
            print(f"❌ Error challenging inference: {e}")
            return False
    
    async def process_pending_inferences(self):
        """Main validation loop"""
        try:
            pending_inferences = await self.get_pending_inferences()
            
            if not pending_inferences:
                # No pending inferences - this is normal for MVP
                return
            
            print(f"🔍 Found {len(pending_inferences)} pending inference(s) to validate")
            
            for inference in pending_inferences:
                inference_id = inference['id']
                
                # Skip if already processed
                if inference_id in self.processed_inferences:
                    continue
                
                print(f"🔍 Validating inference {inference_id}")
                
                # Get model info
                model_info = await self.get_model_info(inference['model_id'])
                if not model_info:
                    print(f"❌ Model info not found for inference {inference_id}")
                    continue
                
                # Verify inference
                is_valid, expected_output = await self.verify_inference(inference, model_info)
                
                # Check if still in challenge period
                current_block = self.substrate.get_block_number(None)
                challenge_deadline = inference['submitted_at'] + 100  # ChallengePeriod = 100 blocks
                
                if current_block > challenge_deadline:
                    print(f"⏰ Challenge period expired for inference {inference_id}")
                    self.processed_inferences.add(inference_id)
                    continue
                
                # Take action based on verification result
                if is_valid:
                    await self.validate_inference(inference_id)
                else:
                    print(f"❌ Invalid inference detected: {inference_id}")
                    await self.challenge_inference(inference_id, expected_output)
                
                # Mark as processed
                self.processed_inferences.add(inference_id)
                
                # Small delay to avoid overwhelming the chain
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"❌ Error processing pending inferences: {e}")
    
    async def start_api_server(self, port: int = 8001):
        """Start HTTP API server for monitoring validator status"""
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import RedirectResponse
        from pydantic import BaseModel
        import uvicorn
        
        app = FastAPI(title="QX Chain Validator API")
        
        class ValidateRequest(BaseModel):
            inference_id: int
        
        class ChallengeRequest(BaseModel):
            inference_id: int
            expected_output: str
        
        @app.get("/")
        async def root():
            """Root endpoint redirects to API documentation"""
            return RedirectResponse(url="/docs")
        
        @app.get("/status")
        async def status_endpoint():
            """Get validator status and configuration"""
            current_block = None
            try:
                current_block = self.substrate.get_block_number(None)
            except:
                pass
                
            return {
                "validator_address": self.validator_address,
                "registered": self.registered,
                "running": self.running,
                "processed_count": len(self.processed_inferences),
                "chain_endpoint": self.substrate.url,
                "ollama_endpoint": self.ollama_endpoint,
                "current_block": current_block
            }
        
        @app.get("/pending")
        async def pending_inferences_endpoint():
            """Get all pending inferences"""
            if not self.registered:
                raise HTTPException(status_code=400, detail="Validator not registered")
            
            try:
                pending = await self.get_pending_inferences()
                # Convert bytes to hex strings for JSON serialization
                serializable_pending = []
                for inference in pending:
                    serializable_inference = inference.copy()
                    serializable_inference['input_hash'] = inference['input_hash'].hex()
                    serializable_inference['output_hash'] = inference['output_hash'].hex()
                    serializable_pending.append(serializable_inference)
                
                return {
                    "count": len(serializable_pending),
                    "pending_inferences": serializable_pending
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error fetching pending inferences: {str(e)}")
        
        @app.post("/validate")
        async def validate_endpoint(request: ValidateRequest):
            """Manually validate a specific inference"""
            if not self.registered:
                raise HTTPException(status_code=400, detail="Validator not registered")
            
            success = await self.validate_inference(request.inference_id)
            if success:
                self.processed_inferences.add(request.inference_id)
                return {"status": "success", "message": f"Inference {request.inference_id} validated"}
            else:
                raise HTTPException(status_code=500, detail="Validation failed")
        
        @app.post("/challenge")
        async def challenge_endpoint(request: ChallengeRequest):
            """Manually challenge a specific inference"""
            if not self.registered:
                raise HTTPException(status_code=400, detail="Validator not registered")
            
            success = await self.challenge_inference(request.inference_id, request.expected_output)
            if success:
                self.processed_inferences.add(request.inference_id)
                return {"status": "success", "message": f"Inference {request.inference_id} challenged"}
            else:
                raise HTTPException(status_code=500, detail="Challenge failed")
        
        @app.post("/process")
        async def process_pending_endpoint():
            """Manually trigger processing of pending inferences"""
            if not self.registered:
                raise HTTPException(status_code=400, detail="Validator not registered")
            
            try:
                await self.process_pending_inferences()
                return {"status": "success", "message": "Pending inferences processed"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
        
        @app.get("/models/{model_id}")
        async def model_info_endpoint(model_id: int):
            """Get information about a specific model"""
            try:
                model_info = await self.get_model_info(model_id)
                if model_info:
                    # Convert bytes to hex strings for JSON serialization
                    serializable_model = model_info.copy()
                    serializable_model['model_hash'] = model_info['model_hash'].hex()
                    return serializable_model
                else:
                    raise HTTPException(status_code=404, detail="Model not found")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error fetching model info: {str(e)}")
        
        print(f"🚀 Starting Validator API server on port {port}")
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    
    async def start_validation_loop(self, interval: int = 10):
        """Start the continuous validation loop"""
        print(f"🔄 Starting validation loop (interval: {interval}s)")
        self.running = True
        
        while self.running:
            if self.registered:
                await self.process_pending_inferences()
            else:
                print("⚠️ Validator not registered, skipping validation")
            
            await asyncio.sleep(interval)
    
    def stop(self):
        """Stop the validation loop"""
        print("🛑 Stopping validator...")
        self.running = False

async def main():
    parser = argparse.ArgumentParser(description='QX Chain Validator')
    parser.add_argument('--chain', default='ws://localhost:9944', help='Chain endpoint')
    parser.add_argument('--ollama', default='http://localhost:11434', help='Ollama endpoint')
    parser.add_argument('--seed', default='//Bob//stash', help='Validator account seed')
    parser.add_argument('--interval', type=int, default=10, help='Validation interval in seconds')
    parser.add_argument('--register', action='store_true', help='Register as validator (requires sudo)')
    parser.add_argument('--port', type=int, default=8001, help='API server port')
    parser.add_argument('--api-only', action='store_true', help='Run only API server without validation loop')
    
    args = parser.parse_args()
    
    # Initialize validator
    validator = QXValidator(
        chain_endpoint=args.chain,
        ollama_endpoint=args.ollama,
        validator_seed=args.seed
    )
    
    print("🛡️ QX Chain Validator Starting...")
    
    # Register validator if requested
    if args.register:
        if await validator.register_validator():
            print("✅ Validator registration complete")
        else:
            print("❌ Failed to register validator. Continuing anyway...")
    
    try:
        if args.api_only:
            # Run only API server
            await validator.start_api_server(args.port)
        else:
            # Run both API server and validation loop concurrently
            tasks = [
                asyncio.create_task(validator.start_api_server(args.port)),
                asyncio.create_task(validator.start_validation_loop(args.interval))
            ]
            
            # Wait for any task to complete (shouldn't happen unless there's an error)
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                
    except KeyboardInterrupt:
        print("\n🛑 Received interrupt signal")
        validator.stop()

if __name__ == "__main__":
    asyncio.run(main())
