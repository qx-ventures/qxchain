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
import signal
import sys
from typing import Dict, Any, Optional, List
from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException
from node_manager import NodeManager, create_validator_node_manager, get_auto_ports

class QXValidator:
    def __init__(self, 
                 chain_endpoint: str = "ws://localhost:9933",
                 ollama_endpoint: str = "http://localhost:11434",
                 validator_seed: str = "//Charlie",
                 node_manager: Optional[NodeManager] = None):
        
        self.chain_endpoint = chain_endpoint
        self.substrate = None  # Will be initialized after node starts
        self.ollama_endpoint = ollama_endpoint
        self.keypair = Keypair.create_from_uri(validator_seed)
        self.validator_address = self.keypair.ss58_address
        self.node_manager = node_manager
        
        print(f"Validator initialized with address: {self.validator_address}")
        print(f"Chain endpoint: {chain_endpoint}")
        print(f"Ollama endpoint: {ollama_endpoint}")
        if self.node_manager:
            print(f"Blockchain node: {self.node_manager.node_name}")
        
        # Validator state
        self.registered = False
        self.running = False
        self.processed_inferences = set()  # Track processed inference IDs
    
    async def initialize_chain_connection(self):
        """Initialize connection to the blockchain"""
        try:
            print(f"🔗 Connecting to chain at: {self.chain_endpoint}")
            self.substrate = SubstrateInterface(url=self.chain_endpoint)
            return True
        except Exception as e:
            print(f"❌ Failed to connect to chain: {e}")
            return False
    
    def _ensure_substrate_connection(self):
        """Ensure substrate connection is initialized"""
        if self.substrate is None:
            raise RuntimeError("Substrate connection not initialized. Call initialize_chain_connection() first.")
        
    async def register_validator(self, stake_amount: int = 1000):
        """Register this node as a validator (requires sudo/governance)"""
        try:
            self._ensure_substrate_connection()
            
            # First check if already registered
            try:
                validator_result = self.substrate.query(
                    module='QxAi',
                    storage_function='Validators',
                    params=[self.validator_address]
                )
                if validator_result and validator_result.value:
                    print("ℹ️ Validator already registered. Continuing.")
                    self.registered = True
                    return True
            except Exception as query_error:
                # Storage might not exist yet, continue with registration attempt
                pass
            
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
    
    async def register_node_identity(self, peer_id: str, endpoint: str, node_type: int = 1):
        """Register node identity for this validator"""
        try:
            self._ensure_substrate_connection()
            # Convert peer_id string to bytes
            peer_id_bytes = peer_id.encode('utf-8')[:64]  # Limit to 64 bytes
            endpoint_bytes = endpoint.encode('utf-8')[:256]  # Limit to 256 bytes
            
            call = self.substrate.compose_call(
                call_module='QxAi',
                call_function='register_node_identity',
                call_params={
                    'peer_id': peer_id_bytes,
                    'endpoint': endpoint_bytes,
                    'node_type': node_type  # 0=Worker, 1=Validator, 2=WorkerValidator
                }
            )
            
            extrinsic = self.substrate.create_signed_extrinsic(call=call, keypair=self.keypair)
            receipt = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            
            if receipt.is_success:
                print(f"✅ Node identity registered: {peer_id}")
                print(f"   Endpoint: {endpoint}")
                print(f"   Node type: {['Worker', 'Validator', 'WorkerValidator'][node_type]}")
                return True
            else:
                print(f"❌ Node identity registration failed: {receipt.error_message}")
                return False
                
        except Exception as e:
            print(f"❌ Error registering node identity: {e}")
            return False
    
    async def check_node_slashed_status(self, peer_id: str) -> bool:
        """Check if this node has been slashed"""
        try:
            peer_id_bytes = peer_id.encode('utf-8')[:64]
            
            # Query the SlashedNodes storage map
            slashed_result = self.substrate.query(
                module='QxAi',
                storage_function='SlashedNodes',
                params=[peer_id_bytes]
            )
            
            if slashed_result and slashed_result.value:
                return slashed_result.value
            return False
            
        except Exception as e:
            print(f"❌ Error checking slashed status: {e}")
            return False
    
    async def get_node_identity(self) -> dict:
        """Get node identity information for this validator"""
        try:
            identity_result = self.substrate.query(
                module='QxAi',
                storage_function='NodeIdentities',
                params=[self.validator_address]
            )
            
            if identity_result and identity_result.value:
                identity = identity_result.value
                return {
                    'peer_id': bytes(identity['peer_id']).decode('utf-8', errors='ignore'),
                    'endpoint': bytes(identity['endpoint']).decode('utf-8', errors='ignore'),
                    'node_type': identity['node_type']
                }
            return {}
            
        except Exception as e:
            print(f"❌ Error getting node identity: {e}")
            return {}
    
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
                        try:
                            inference_result = self.substrate.query(
                                module='QxAi',
                                storage_function='InferenceResults',
                                params=[inference_id]
                            )
                        except Exception as query_error:
                            if "not found" in str(query_error) or "encoding" in str(query_error):
                                continue
                            else:
                                raise query_error
                        
                        if inference_result and inference_result.value:
                            inference = inference_result.value
                            status = inference['status']
                            
                            # Handle status enum
                            if isinstance(status, dict):
                                status_key = list(status.keys())[0] if status else 'Unknown'
                            else:
                                status_key = str(status)
                            
                            if status_key in ['Pending', 'Challenged']:
                                # Get challenge information
                                challenges = await self.get_inference_challenges(inference_id)
                                
                                pending_inferences.append({
                                    'id': inference_id,
                                    'worker': inference['worker'],
                                    'request_id': inference['request_id'],
                                    'output': bytes(inference['output']).decode('utf-8', errors='ignore'),
                                    'status': status_key,
                                    'submitted_at': inference['submitted_at'],
                                    'challenges': challenges,
                                    'challenge_count': len(challenges)
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
    
    async def get_inference_challenges(self, inference_id: int) -> List[Dict]:
        """Get challenges for a specific inference"""
        try:
            challenges_result = self.substrate.query(
                module='QxAi',
                storage_function='InferenceChallenges',
                params=[inference_id]
            )
            
            if challenges_result and challenges_result.value:
                challenges = []
                for challenge_data in challenges_result.value:
                    expected_output = bytes(challenge_data['expected_output']).decode('utf-8', errors='ignore')
                    challenges.append({
                        'validator': challenge_data['validator'],
                        'expected_output': expected_output,
                        'submitted_at': challenge_data['submitted_at']
                    })
                return challenges
            return []
            
        except Exception as e:
            if "not found" not in str(e):
                print(f"❌ Error getting challenges: {e}")
            return []
    
    async def get_validator_count(self) -> int:
        """Get total number of registered validators"""
        try:
            validators_result = self.substrate.query_map('QxAi', 'Validators')
            return len(list(validators_result))
        except Exception as e:
            if "not found" not in str(e):
                print(f"❌ Error getting validator count: {e}")
            return 0
    
    async def check_challenge_consensus(self, inference_id: int, challenges: List[Dict]) -> Dict:
        """Check if challenge consensus is reached for an inference"""
        total_validators = await self.get_validator_count()
        if total_validators == 0:
            return {'consensus_reached': False, 'required': 0, 'actual': 0}
        
        # Group challenges by expected output
        output_groups = {}
        for challenge in challenges:
            output = challenge['expected_output']
            if output not in output_groups:
                output_groups[output] = []
            output_groups[output].append(challenge)
        
        # Find the group with the most validators
        max_group_size = max(len(group) for group in output_groups.values()) if output_groups else 0
        required_consensus = (total_validators * 2 + 2) // 3  # Ceiling of 2/3
        
        return {
            'consensus_reached': max_group_size >= required_consensus,
            'required': required_consensus,
            'actual': max_group_size,
            'total_validators': total_validators,
            'output_groups': {output: len(group) for output, group in output_groups.items()}
        }
    
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
                    'name': 'assistant',
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
                'assistant': 'gemma3:1b',
                'permits_assistant': 'gemma3:1b',
                'parks_assistant': 'gemma3:1b'
            }
            
            ollama_model = ollama_model_map.get(model_name, 'gemma3:1b')
            
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
                'assistant': "Hello, how can you help me today?",
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
                    'expected_output': expected_output.encode()[:4096]  # Use bytes directly, not list
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
            # Check if this validator node is slashed first
            node_identity = await self.get_node_identity()
            if node_identity and 'peer_id' in node_identity:
                is_slashed = await self.check_node_slashed_status(node_identity['peer_id'])
                if is_slashed:
                    print("🔥 VALIDATOR NODE HAS BEEN SLASHED! Stopping validation...")
                    print("   This node can no longer participate in validation")
                    self.running = False
                    return
            
            pending_inferences = await self.get_pending_inferences()
            
            if not pending_inferences:
                # No pending inferences - show status
                print("✅ No pending inferences to validate (all clear)")
                return
            
            print(f"🔍 Found {len(pending_inferences)} pending inference(s) to validate")
            
            for inference in pending_inferences:
                inference_id = inference['id']
                
                # Skip if already processed
                if inference_id in self.processed_inferences:
                    continue
                
                print(f"🔍 Validating inference {inference_id} (Status: {inference['status']})")
                
                # Show challenge status if any
                if inference['challenge_count'] > 0:
                    consensus_info = await self.check_challenge_consensus(inference_id, inference['challenges'])
                    print(f"   ⚖️ Challenges: {inference['challenge_count']}, Consensus: {consensus_info['actual']}/{consensus_info['required']} ({'✅' if consensus_info['consensus_reached'] else '❌'})")
                
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
        
        while True:
            print("\n" + "="*60)
            print("🛡️ QX Chain Validator Interactive Mode")
            print("="*60)
            print("1. 📋 Check pending inferences")
            print("2. 🔍 Show specific inference details")
            print("3. ✅ Validate specific inference")
            print("4. ❌ Challenge specific inference")
            print("5. 🔄 Process all pending inferences")
            print("6. ⚖️ Show challenge consensus status")
            print("7. 📊 Show validator status")
            print("8. 🔄 Refresh validator registration")
            print("9. 🚪 Exit interactive mode")
            print("-" * 60)
            
            try:
                choice = input("Select option (1-9): ").strip()
                
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
                    await self.show_challenge_consensus_status()
                elif choice == "7":
                    await self.show_validator_status()
                elif choice == "8":
                    await self.refresh_validator_registration()
                elif choice == "9":
                    print("🚪 Exiting interactive mode...")
                    break
                else:
                    print("❌ Invalid option. Please choose 1-9.")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                # Continue the loop instead of crashing
    
    async def show_pending_inferences(self):
        """Show all pending inferences"""
        try:
            print("\n🔍 Fetching pending inferences...")
            pending = await self.get_pending_inferences()
            
            if not pending:
                print("📭 No pending inferences found")
                return
            
            print(f"\n📋 Found {len(pending)} pending inferences:")
            print("-" * 120)
            print(f"{'ID':<4} {'Worker':<30} {'Status':<10} {'Challenges':<12} {'Consensus':<10} {'Submitted':<10} {'Output Preview'}")
            print("-" * 120)
            
            for inference in pending:
                worker_short = inference['worker'][:27] + "..." if len(inference['worker']) > 30 else inference['worker']
                output_preview = inference['output'][:25] + "..." if len(inference['output']) > 25 else inference['output']
                
                # Get consensus info
                consensus_info = await self.check_challenge_consensus(inference['id'], inference['challenges'])
                consensus_str = f"{consensus_info['actual']}/{consensus_info['required']}"
                consensus_status = "✅" if consensus_info['consensus_reached'] else "❌" if inference['challenge_count'] > 0 else "-"
                
                print(f"{inference['id']:<4} {worker_short:<30} {inference['status']:<10} {inference['challenge_count']:<12} {consensus_str:<6}{consensus_status:<4} {inference['submitted_at']:<10} {output_preview}")
            
            print("-" * 120)
            
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
            print("-" * 80)
            print(f"Worker: {inference['worker']}")
            print(f"Request ID: {inference.get('request_id', 'N/A')}")
            print(f"Status: {inference['status']}")
            print(f"Submitted: Block {inference['submitted_at']}")
            print(f"Challenge Count: {inference['challenge_count']}")
            
            if inference['challenge_count'] > 0:
                consensus_info = await self.check_challenge_consensus(inference_id, inference['challenges'])
                print(f"Consensus Status: {consensus_info['actual']}/{consensus_info['required']} ({'✅ Reached' if consensus_info['consensus_reached'] else '❌ Not reached'})")
                print(f"Total Validators: {consensus_info['total_validators']}")
                
                print("\nChallenges:")
                for i, challenge in enumerate(inference['challenges'], 1):
                    validator_short = challenge['validator'][:40] + "..." if len(challenge['validator']) > 40 else challenge['validator']
                    expected_preview = challenge['expected_output'][:50] + "..." if len(challenge['expected_output']) > 50 else challenge['expected_output']
                    print(f"  {i}. Validator: {validator_short}")
                    print(f"     Expected: {expected_preview}")
                    print(f"     Submitted: Block {challenge['submitted_at']}")
            
            print(f"\nActual Output:")
            print(f"  {inference['output']}")
            print("-" * 80)
            
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
            
            # Show blockchain node status
            if self.node_manager:
                node_info = self.node_manager.get_node_info()
                node_status = await self.get_node_status()
                print(f"Blockchain Node:")
                print(f"  Name: {node_info['name']}")
                print(f"  Running: {node_info['running']}")
                print(f"  WS Endpoint: {node_info['ws_endpoint']}")
                print(f"  HTTP Endpoint: {node_info['http_endpoint']}")
                print(f"  Status: {node_status.get('status', 'unknown')}")
                if 'health' in node_status:
                    health = node_status['health']
                    print(f"  Health: peers={health.get('peers', 0)}, syncing={health.get('isSyncing', False)}")
            else:
                print(f"Blockchain Node: Not managed (external)")
            
            # Show node identity info
            node_identity = await self.get_node_identity()
            if node_identity:
                print(f"Node Identity:")
                print(f"  Peer ID: {node_identity.get('peer_id', 'Not set')}")
                print(f"  Endpoint: {node_identity.get('endpoint', 'Not set')}")
                print(f"  Type: {['Worker', 'Validator', 'WorkerValidator'][node_identity.get('node_type', 1)]}")
                
                # Check if slashed
                if 'peer_id' in node_identity:
                    is_slashed = await self.check_node_slashed_status(node_identity['peer_id'])
                    if is_slashed:
                        print(f"  ⚠️  STATUS: 🔥 SLASHED")
                    else:
                        print(f"  ✅ STATUS: Active")
            else:
                print("Node Identity: Not registered")
            
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
    
    async def show_challenge_consensus_status(self):
        """Show challenge consensus status for all inferences"""
        try:
            print("\n⚖️ Challenge Consensus Status:")
            print("-" * 80)
            
            pending = await self.get_pending_inferences()
            total_validators = await self.get_validator_count()
            
            print(f"Total Registered Validators: {total_validators}")
            required_consensus = (total_validators * 2 + 2) // 3 if total_validators > 0 else 0
            print(f"Required for Consensus: {required_consensus} validators")
            print()
            
            challenged_inferences = [inf for inf in pending if inf['challenge_count'] > 0]
            
            if not challenged_inferences:
                print("📭 No challenged inferences found")
                return
            
            print(f"Found {len(challenged_inferences)} challenged inferences:")
            print("-" * 80)
            
            for inference in challenged_inferences:
                consensus_info = await self.check_challenge_consensus(inference['id'], inference['challenges'])
                status_icon = "🔥" if consensus_info['consensus_reached'] else "⏳"
                
                print(f"{status_icon} Inference {inference['id']}:")
                print(f"   Worker: {inference['worker'][:50]}..." if len(inference['worker']) > 50 else f"   Worker: {inference['worker']}")
                print(f"   Status: {inference['status']}")
                print(f"   Challenges: {inference['challenge_count']} total")
                print(f"   Consensus: {consensus_info['actual']}/{consensus_info['required']} ({'✅ REACHED' if consensus_info['consensus_reached'] else '❌ Not reached'})")
                
                if consensus_info['output_groups']:
                    print("   Challenge breakdown:")
                    for output_preview, count in consensus_info['output_groups'].items():
                        preview = output_preview[:40] + "..." if len(output_preview) > 40 else output_preview
                        print(f"     - '{preview}': {count} validator(s)")
                
                print()
            
            print("-" * 80)
            
        except Exception as e:
            print(f"❌ Error showing challenge consensus status: {e}")

    async def start_validation_loop(self, interval: int = 10):
        """Start the continuous validation loop"""
        print(f"🔄 Starting validation loop (interval: {interval}s)")
        print("🛡️ Validator will continuously monitor and validate inferences")
        print("📊 Status updates will be shown every 30 seconds")
        self.running = True
        
        status_counter = 0
        
        while self.running:
            if self.registered:
                # Show status every 3 iterations (30 seconds with 10s interval)
                if status_counter % 3 == 0:
                    print(f"\n{'='*50}")
                    print(f"🛡️ Validator Status Check (Cycle {status_counter + 1})")
                    print(f"📅 Time: {asyncio.get_event_loop().time():.0f}")
                    print(f"✅ Registered: {self.registered}")
                    print(f"🔗 Chain Connected: {self.substrate is not None}")
                    print(f"📊 Processed Inferences: {len(self.processed_inferences)}")
                    print(f"{'='*50}")
                
                await self.process_pending_inferences()
            else:
                print("⚠️ Validator not registered, attempting to register...")
                if await self.register_validator():
                    print("✅ Validator registration successful")
                else:
                    print("❌ Validator registration failed, retrying in next cycle")
            
            status_counter += 1
            await asyncio.sleep(interval)
    
    def stop(self):
        """Stop the validation loop"""
        print("🛑 Stopping validator...")
        self.running = False
    
    async def start_node(self) -> bool:
        """Start the blockchain node"""
        if not self.node_manager:
            print("⚠️ No node manager configured")
            return True  # Continue without node
        
        print(f"🚀 Starting blockchain node for validator...")
        success = await self.node_manager.start_node(validator=True)
        
        if success:
            # Get the peer ID and register node identity
            await asyncio.sleep(2)  # Wait for node to fully start
            peer_id = self.node_manager.get_peer_id()
            if peer_id:
                print(f"🔗 Auto-registering validator node identity with peer ID: {peer_id}")
                node_info = self.node_manager.get_node_info()
                await self.register_node_identity(
                    peer_id, 
                    node_info['ws_endpoint'], 
                    1  # Validator type
                )
        
        return success
    
    async def stop_node(self):
        """Stop the blockchain node"""
        if self.node_manager:
            print(f"🛑 Stopping blockchain node...")
            await self.node_manager.stop_node()
    
    async def get_node_status(self) -> Dict[str, Any]:
        """Get node status"""
        if not self.node_manager:
            return {"status": "no_node_manager"}
        
        return await self.node_manager.get_node_status()
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def shutdown(self):
        """Graceful shutdown of validator and node"""
        print("🛑 Shutting down validator and node...")
        
        # Stop validation loop
        self.stop()
        
        # Stop blockchain node
        await self.stop_node()
        
        print("✅ Shutdown complete")
        sys.exit(0)

async def main():
    parser = argparse.ArgumentParser(description='QX Chain Validator')
    parser.add_argument('--chain', default='ws://localhost:9933', help='Chain endpoint')
    parser.add_argument('--ollama', default='http://localhost:11434', help='Ollama endpoint')
    parser.add_argument('--seed', default='//Charlie', help='Validator account seed')
    parser.add_argument('--interval', type=int, default=10, help='Validation interval in seconds')
    parser.add_argument('--peer-id', default=None, help='Node peer ID for blockchain network (deprecated, auto-generated)')
    parser.add_argument('--node-endpoint', default='http://localhost:9966', help='Node endpoint (deprecated, auto-managed)')
    parser.add_argument('--no-node', action='store_true', help='Don\'t start blockchain node (use external node)')
    parser.add_argument('--node-name', default=None, help='Custom blockchain node name')
    
    args = parser.parse_args()
    
    # Setup node manager unless explicitly disabled
    node_manager = None
    if not args.no_node:
        # Get auto-assigned ports to avoid conflicts
        ws_port, http_port, p2p_port = get_auto_ports(9955)  # Different base port for validators
        
        # Create node name
        node_name = args.node_name or f"validator_{args.seed.replace('//', '').replace('/', '_')}"
        
        # Create node manager
        node_manager = NodeManager(
            node_name=node_name,
            ws_port=ws_port,
            http_port=http_port,
            p2p_port=p2p_port,
            consensus="instant-seal"
        )
        
        print(f"🔧 Will start blockchain node: {node_name}")
        print(f"   Ports: WS={ws_port}, HTTP={http_port}, P2P={p2p_port}")
        
        # Update chain endpoint to use our node
        args.chain = f"ws://localhost:{ws_port}"
    
    # Initialize validator
    validator = QXValidator(
        chain_endpoint=args.chain,
        ollama_endpoint=args.ollama,
        validator_seed=args.seed,
        node_manager=node_manager
    )
    
    # Setup signal handlers for graceful shutdown
    validator.setup_signal_handlers()
    
    print("🛡️ QX Chain Validator Starting...")
    
    try:
        # Start blockchain node first if managed
        if node_manager:
            if not await validator.start_node():
                print("❌ Failed to start blockchain node. Exiting.")
                return
        
        # Initialize chain connection after node is ready
        if not await validator.initialize_chain_connection():
            print("❌ Failed to connect to chain. Exiting.")
            return
        
        # Always attempt to register validator if not already registered
        if not validator.registered:
            print("🔄 Attempting to register validator...")
            if await validator.register_validator():
                print("✅ Validator registration complete")
            else:
                print("❌ Failed to register validator. Continuing anyway...")
        else:
            print("✅ Validator already registered")
        
        # Register node identity if peer_id provided (legacy support)
        if args.peer_id:
            print(f"🔗 Registering validator node identity...")
            await validator.register_node_identity(args.peer_id, args.node_endpoint, 1)  # 1 = Validator type
        
        print("🎮 Starting validator in interactive mode...")
        await validator.interactive_mode()
                
    except KeyboardInterrupt:
        print("\n🛑 Received interrupt signal")
        validator.stop()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
    finally:
        # Ensure cleanup
        await validator.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
