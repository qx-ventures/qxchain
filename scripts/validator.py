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
                 validator_seed: str = "//Charlie"):
        
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
        
    async def register_validator(self, stake_amount: int = 1000):
        """Register this node as a validator (requires sudo/governance)"""
        try:
            call = self.substrate.compose_call(
                call_module='QxAi',
                call_function='register_validator',
                call_params={'stake': stake_amount}
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
                # Handle already-registered case gracefully
                err = receipt.error_message
                err_str = str(err)
                already = False
                if isinstance(err, dict):
                    already = err.get('name') == 'ValidatorAlreadyRegistered'
                if 'ValidatorAlreadyRegistered' in err_str:
                    already = True
                if already:
                    print("ℹ️ Validator already registered. Continuing.")
                    self.registered = True
                    return True
                print(f"❌ Validator registration failed: {receipt.error_message}")
                return False
                
        except Exception as e:
            # If the error indicates already registered, proceed
            if 'ValidatorAlreadyRegistered' in str(e):
                print("ℹ️ Validator already registered (from exception). Continuing.")
                self.registered = True
                return True
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
    
    async def verify_inference_deterministic(self, inference: Dict, model_info: Dict, original_input: str) -> tuple[bool, str]:
        """Verify an inference by re-running it with deterministic parameters"""
        try:
            # Extract deterministic parameters from model info
            model_name = model_info['name']
            seed = model_info.get('seed', 42)
            temperature = model_info.get('temperature', 700) / 1000.0  # Convert back from stored format
            max_tokens = model_info.get('max_tokens', 512)
            
            # Map model names to Ollama models
            ollama_model_map = {
                'zoo_assistant': 'gemma3:4b',
                'permits_assistant': 'gemma3:4b',
                'parks_assistant': 'gemma3:4b'
            }
            
            ollama_model = ollama_model_map.get(model_name, 'gemma3:4b')
            
            print(f"🔍 Running deterministic inference verification:")
            print(f"   Model: {ollama_model}")
            print(f"   Seed: {seed}")
            print(f"   Temperature: {temperature}")
            print(f"   Max tokens: {max_tokens}")
            
            # Run inference with exact same parameters as worker should have used
            response = requests.post(
                f"{self.ollama_endpoint}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": original_input,
                    "stream": False,
                    "options": {
                        "seed": seed,
                        "temperature": temperature,
                        "num_predict": max_tokens,
                        "top_k": 40,
                        "top_p": 0.9,
                        "repeat_penalty": 1.1
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                expected_output = result.get('response', '')
                actual_output = inference['output']
                
                # Calculate output hash for comparison
                expected_hash = hashlib.sha256(expected_output.encode()).digest()
                actual_hash = inference['output_hash']
                
                print(f"   Expected hash: {expected_hash.hex()}")
                print(f"   Actual hash: {actual_hash.hex()}")
                
                # For deterministic verification, hashes should match exactly
                is_valid = expected_hash == actual_hash
                
                if not is_valid:
                    print(f"❌ Hash mismatch detected!")
                    print(f"   Expected output length: {len(expected_output)}")
                    print(f"   Actual output length: {len(actual_output)}")
                    print(f"   Expected preview: {expected_output[:100]}...")
                    print(f"   Actual preview: {actual_output[:100]}...")
                
                return is_valid, expected_output
            else:
                print(f"❌ Ollama verification failed: {response.status_code}")
                return False, ""
                
        except Exception as e:
            print(f"❌ Error verifying inference: {e}")
            return False, ""

    async def verify_inference(self, inference: Dict, model_info: Dict) -> tuple[bool, str]:
        """Legacy verify method - fallback for MVP testing"""
        try:
            # For MVP when we don't have the original input, use test prompts
            model_name = model_info['name']
            
            test_prompts = {
                'zoo_assistant': "What are the zoo's operating hours?",
                'permits_assistant': "How do I apply for a building permit?",
                'parks_assistant': "What events are happening in the parks this week?"
            }
            
            test_prompt = test_prompts.get(model_name, "Hello, how can you help?")
            
            # Use deterministic verification with test prompt
            return await self.verify_inference_deterministic(inference, model_info, test_prompt)
                
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
    
    
    async def interactive_mode(self):
        """Interactive mode for manual validation control"""
        print("🎮 Starting Interactive Validator Mode...")
        print("🎯 You can manually review and validate/challenge inferences")
        
        try:
            while True:
                print("\n" + "="*60)
                print("🛡️ QX Chain Validator Interactive Mode")
                print("="*60)
                print("1. 📋 Check pending inferences")
                print("2. 🔍 Show specific inference details")
                print("3. ✅ Validate specific inference")
                print("4. ❌ Challenge specific inference")
                print("5. 🔄 Process all pending inferences")
                print("6. 📊 Show validator status")
                print("7. 🔄 Refresh validator registration")
                print("8. 🚪 Exit interactive mode")
                print("-" * 60)
                
                choice = input("Select option (1-8): ").strip()
                
                if choice == "1":
                    await self.show_pending_inferences()
                elif choice == "2":
                    await self.show_inference_details()
                elif choice == "3":
                    await self.validate_inference_interactive()
                elif choice == "4":
                    await self.challenge_inference_interactive()
                elif choice == "5":
                    await self.process_pending_inferences()
                elif choice == "6":
                    await self.show_validator_status()
                elif choice == "7":
                    await self.refresh_validator_registration()
                elif choice == "8":
                    print("🚪 Exiting interactive mode...")
                    break
                else:
                    print("❌ Invalid option. Please choose 1-8.")
                    
        except KeyboardInterrupt:
            print("\n🛑 Interactive mode interrupted")
        except Exception as e:
            print(f"❌ Interactive mode error: {e}")
        finally:
            print("🎮 Interactive mode stopped")
    
    async def show_pending_inferences(self):
        """Show all pending inferences"""
        try:
            print("\n🔍 Fetching pending inferences...")
            pending = await self.get_pending_inferences()
            
            if not pending:
                print("📭 No pending inferences found")
                return
            
            print(f"\n📋 Found {len(pending)} pending inferences:")
            print("-" * 100)
            print(f"{'ID':<4} {'Worker':<50} {'Model':<6} {'Submitted':<10} {'Output Preview'}")
            print("-" * 100)
            
            for inference in pending:
                worker_short = inference['worker'][:47] + "..." if len(inference['worker']) > 50 else inference['worker']
                output_preview = inference['output'][:30] + "..." if len(inference['output']) > 30 else inference['output']
                print(f"{inference['id']:<4} {worker_short:<50} {inference['model_id']:<6} {inference['submitted_at']:<10} {output_preview}")
            
            print("-" * 100)
            
        except Exception as e:
            print(f"❌ Error showing pending inferences: {e}")
    
    async def show_inference_details(self):
        """Show detailed information for a specific inference"""
        try:
            inference_id = input("\n📋 Enter inference ID to view details: ").strip()
            if not inference_id.isdigit():
                print("❌ Invalid inference ID")
                return
                
            inference_id = int(inference_id)
            pending = await self.get_pending_inferences()
            inference = next((inf for inf in pending if inf['id'] == inference_id), None)
            
            if not inference:
                print(f"❌ Inference {inference_id} not found in pending list")
                return
            
            print(f"\n📄 Inference {inference_id} Details:")
            print("-" * 60)
            print(f"Worker: {inference['worker']}")
            print(f"Model ID: {inference['model_id']}")
            print(f"Submitted: Block {inference['submitted_at']}")
            print(f"Input Hash: {inference['input_hash'].hex()}")
            print(f"Output Hash: {inference['output_hash'].hex()}")
            print(f"Output:")
            print(f"  {inference['output']}")
            print("-" * 60)
            
        except Exception as e:
            print(f"❌ Error showing inference details: {e}")
    
    async def validate_inference_interactive(self):
        """Interactively validate a specific inference"""
        try:
            inference_id = input("\n✅ Enter inference ID to validate: ").strip()
            if not inference_id.isdigit():
                print("❌ Invalid inference ID")
                return
                
            inference_id = int(inference_id)
            
            confirm = input(f"Confirm validation of inference {inference_id}? (y/N): ").strip().lower()
            if confirm != 'y':
                print("❌ Validation cancelled")
                return
            
            success = await self.validate_inference(inference_id)
            if success:
                self.processed_inferences.add(inference_id)
                print(f"✅ Inference {inference_id} validated successfully")
            else:
                print(f"❌ Failed to validate inference {inference_id}")
            
        except Exception as e:
            print(f"❌ Error validating inference: {e}")
    
    async def challenge_inference_interactive(self):
        """Interactively challenge a specific inference"""
        try:
            inference_id = input("\n❌ Enter inference ID to challenge: ").strip()
            if not inference_id.isdigit():
                print("❌ Invalid inference ID")
                return
                
            inference_id = int(inference_id)
            expected_output = input("Enter expected output for challenge: ").strip()
            
            if not expected_output:
                print("❌ Expected output cannot be empty")
                return
            
            confirm = input(f"Confirm challenge of inference {inference_id}? (y/N): ").strip().lower()
            if confirm != 'y':
                print("❌ Challenge cancelled")
                return
            
            success = await self.challenge_inference(inference_id, expected_output)
            if success:
                self.processed_inferences.add(inference_id)
                print(f"✅ Inference {inference_id} challenged successfully")
            else:
                print(f"❌ Failed to challenge inference {inference_id}")
            
        except Exception as e:
            print(f"❌ Error challenging inference: {e}")
    
    async def show_validator_status(self):
        """Show current validator status"""
        try:
            print(f"\n📊 Validator Status:")
            print("-" * 50)
            print(f"Address: {self.validator_address}")
            print(f"Registered: {self.registered}")
            print(f"Running: {self.running}")
            print(f"Processed Count: {len(self.processed_inferences)}")
            print(f"Chain Endpoint: {self.substrate.url}")
            print(f"Ollama Endpoint: {self.ollama_endpoint}")
            
            try:
                current_block = self.substrate.get_block_number(None)
                print(f"Current Block: {current_block}")
            except:
                print("Current Block: Unable to fetch")
            
            print("-" * 50)
            
        except Exception as e:
            print(f"❌ Error showing validator status: {e}")
    
    async def refresh_validator_registration(self):
        """Refresh validator registration"""
        try:
            print("🔄 Refreshing validator registration...")
            success = await self.register_validator()
            if success:
                print("✅ Validator registration refreshed successfully")
            else:
                print("❌ Failed to refresh validator registration")
        except Exception as e:
            print(f"❌ Error refreshing registration: {e}")

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
    parser.add_argument('--seed', default='//Charlie', help='Validator account seed')
    parser.add_argument('--interval', type=int, default=10, help='Validation interval in seconds')
    parser.add_argument('--register', action='store_true', help='Register as validator (requires sudo)')
    parser.add_argument('--auto-mode', action='store_true', help='Start in automatic validation mode (default: interactive)')
    
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
        if args.auto_mode:
            print("🔄 Starting automatic validation mode...")
            # Run validation loop
            await validator.start_validation_loop(args.interval)
        else:
            print("🎮 Starting interactive mode (default)...")
            # Run interactive mode
            await validator.interactive_mode()
                
    except KeyboardInterrupt:
        print("\n🛑 Received interrupt signal")
        validator.stop()

if __name__ == "__main__":
    asyncio.run(main())
