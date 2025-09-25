#!/usr/bin/env python3
"""
QX Chain Ollama Worker Script

This script runs an ML worker node that:
1. Registers as a worker on the QX Chain
2. Registers ML models (e.g., zoo assistant...)
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
import signal
import sys
from typing import Dict, Any, Optional, List
from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException
from node_manager import NodeManager, create_worker_node_manager, get_auto_ports

class OllamaWorker:
    def __init__(self, 
                 chain_endpoint: str = "ws://localhost:9933",
                 ollama_endpoint: str = "http://localhost:11434",
                 worker_seed: str = "//Bob",
                 node_manager: Optional[NodeManager] = None):
        
        self.chain_endpoint = chain_endpoint
        self.substrate = None  # Will be initialized after node starts
        self.ollama_endpoint = ollama_endpoint
        self.keypair = Keypair.create_from_uri(worker_seed)
        self.worker_address = self.keypair.ss58_address
        self.node_manager = node_manager
        
        print(f"Worker initialized with address: {self.worker_address}")
        print(f"Chain endpoint: {chain_endpoint}")
        print(f"Ollama endpoint: {ollama_endpoint}")
        if self.node_manager:
            print(f"Blockchain node: {self.node_manager.node_name}")
        
        # Worker state
        self.registered = False
        self.models = {}  # model_id -> model_info
        self.running = False
        self.queue_listener_running = False
        self.submitted_inferences = {}  # Track submitted inferences by request_id
    
    async def initialize_chain_connection(self):
        """Initialize connection to the blockchain"""
        try:
            print(f"🔗 Connecting to chain at: {self.chain_endpoint}")
            self.substrate = SubstrateInterface(url=self.chain_endpoint)
            return True
        except Exception as e:
            print(f"❌ Failed to connect to chain: {e}")
            return False
    
    async def check_chain_connection(self):
        """Check if chain connection is healthy"""
        try:
            if not self.substrate:
                if not await self.initialize_chain_connection():
                    return False
            
            # Try to get the latest block
            latest_block = self.substrate.get_block_number(None)
            print(f"🔗 Chain connection healthy - Latest block: {latest_block}")
            return True
        except Exception as e:
            print(f"⚠️ Chain connection unhealthy: {e}")
            return False
        
    async def register_worker(self, stake_amount: int = 900):
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
                # Handle already-registered case gracefully
                err = receipt.error_message
                err_str = str(err)
                already = False
                if isinstance(err, dict):
                    already = err.get('name') == 'WorkerAlreadyRegistered'
                if 'WorkerAlreadyRegistered' in err_str:
                    already = True
                if already:
                    print("ℹ️ Worker already registered. Continuing.")
                    self.registered = True
                    return True
                print(f"❌ Worker registration failed: {receipt.error_message}")
                return False
                
        except Exception as e:
            # If the error indicates already registered, proceed
            if 'WorkerAlreadyRegistered' in str(e):
                print("ℹ️ Worker already registered (from exception). Continuing.")
                self.registered = True
                return True
            print(f"❌ Error registering worker: {e}")
            return False
    
    async def register_node_identity(self, peer_id: str, endpoint: str, node_type: int = 0):
        """Register node identity for this worker"""
        try:
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
        """Get node identity information for this worker"""
        try:
            identity_result = self.substrate.query(
                module='QxAi',
                storage_function='NodeIdentities',
                params=[self.worker_address]
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
    
    async def register_model(self, model_name: str, ollama_model: str, endpoint: str, seed: int = 42, temperature: float = 0.7, max_tokens: int = 512):
        """Register a model on the chain with deterministic parameters"""
        try:
            # Generate model hash (simplified for MVP)
            model_hash = hashlib.sha256(f"{model_name}:{ollama_model}:{seed}".encode()).digest()
            
            # Chain doesn't support register_model yet, register locally
            model_id = len(self.models)  # Simple ID assignment
            self.models[model_id] = {
                'name': model_name,
                'ollama_model': ollama_model,
                'endpoint': endpoint,
                'hash': model_hash,
                'seed': seed,
                'temperature': temperature,
                'max_tokens': max_tokens
            }
            print(f"✅ Model registered locally: {model_name} (ID: {model_id})")
            print(f"   Deterministic params - Seed: {seed}, Temperature: {temperature}, Max tokens: {max_tokens}")
            return model_id
            
        except Exception as e:
            print(f"❌ Error registering model: {e}")
            return None
    
    async def run_inference(self, model_id: int, prompt: str) -> Optional[str]:
        """Run inference using Ollama with deterministic parameters"""
        try:
            print(f"🔍 Checking for model ID {model_id}")
            print(f"📋 Available models: {list(self.models.keys())}")
            print(f"📋 Total models: {len(self.models)}")
            
            if model_id not in self.models:
                print(f"❌ Model ID {model_id} not found")
                return None
                
            model_info = self.models[model_id]
            ollama_model = model_info['ollama_model']
            seed = model_info.get('seed', 42)
            temperature = model_info.get('temperature', 0.7)
            max_tokens = model_info.get('max_tokens', 512)
            
            print(f"🤖 Running inference with deterministic parameters:")
            print(f"   Model: {ollama_model}")
            print(f"   Seed: {seed}")
            print(f"   Temperature: {temperature}")
            print(f"   Max tokens: {max_tokens}")
            
            # Call Ollama API with deterministic parameters
            response = requests.post(
                f"{self.ollama_endpoint}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": prompt,
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
                output = result.get('response', '')
                print(f"✅ Inference completed for model {model_id}")
                print(f"   Output length: {len(output)} characters")
                return output
            else:
                print(f"❌ Ollama request failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error running inference: {e}")
            return None
    
    async def submit_inference(self, request_id: int, output_text: str):
        """Submit inference result to the chain"""
        try:
            # Convert output to bounded vec format
            output_bytes = output_text.encode('utf-8')
            if len(output_bytes) > 4096:
                output_bytes = output_bytes[:4096]  # Truncate if too long
            
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
                        chain_url = getattr(self.substrate, 'url', "ws://localhost:9933")
                        self.substrate = SubstrateInterface(url=chain_url)
                    
                    call = self.substrate.compose_call(
                        call_module='QxAi',
                        call_function='submit_inference',
                        call_params={
                            'request_id': request_id,
                            'output': output_bytes  # Use bytes directly, not list
                        }
                    )
                    
                    extrinsic = self.substrate.create_signed_extrinsic(call=call, keypair=self.keypair)
                    receipt = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
                    
                    if receipt.is_success:
                        block_hash = receipt.block_hash
                        tx_hash = receipt.extrinsic_hash
                        print(f"✅ Request {request_id} completed and submitted to chain")
                        print(f"📦 Block: {block_hash}")
                        print(f"🧾 Transaction: {tx_hash}")
                        
                        # Track submitted inference
                        current_block = self.substrate.get_block_number(None)
                        self.submitted_inferences[request_id] = {
                            'output_text': output_text,
                            'submitted_at': current_block,
                            'block_hash': block_hash,
                            'tx_hash': tx_hash,
                            'status': 'submitted'
                        }
                        
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
        
        # Note: This method is for generic inference without a specific request ID
        # For actual chain submission, use process_queue_request instead
        print(f"✅ Inference completed for model {model_id}")
        print(f"   Output length: {len(output)} characters")
        return output
    
    
    async def setup_model(self):
        """Setup a model with deterministic parameters"""
        print("🔧 Setting up model...")
        print(f"📋 Current models count: {len(self.models)}")
        
        model_id = await self.register_model(
            model_name="assistant",
            ollama_model="gemma3:1b",  # Lightweight model for testing
            endpoint="terminal",  # Terminal-only mode
            seed=42,  # Fixed seed for deterministic inference
            temperature=0.7,  # Consistent temperature
            max_tokens=512  # Consistent max tokens
        )
        
        if model_id is not None:
            print(f"✅ Model setup complete (ID: {model_id})")
            print(f"💡 Model ready for deterministic inference requests")
            print(f"📋 Total models registered: {len(self.models)}")
            print(f"📋 Available models: {list(self.models.keys())}")
        else:
            print("❌ Failed to setup model")
        
        return model_id
    
    async def update_worker_status(self, online: bool):
        """Update worker online status on chain"""
        try:
            call = self.substrate.compose_call(
                call_module='QxAi',
                call_function='update_worker_status',
                call_params={'online': online}
            )
            
            extrinsic = self.substrate.create_signed_extrinsic(call=call, keypair=self.keypair)
            receipt = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            
            if receipt.is_success:
                status_str = "online" if online else "offline"
                print(f"✅ Worker status updated: {status_str}")
                return True
            else:
                print(f"❌ Failed to update worker status: {receipt.error_message}")
                return False
                
        except Exception as e:
            print(f"❌ Error updating worker status: {e}")
            return False
    
    async def get_queue_requests(self) -> List[Dict]:
        """Get queued requests for this worker"""
        try:
            # Get worker's queue
            queue_query = self.substrate.query('QxAi', 'WorkerQueues', [self.worker_address])
            
            # Handle cases where queue doesn't exist or is None
            if not queue_query or queue_query.value is None:
                print("🔍 No queue found for worker, initializing...")
                return []
            
            queue_value = queue_query.value
            
            # Handle empty list case
            if not queue_value or len(queue_value) == 0:
                print("📋 Worker queue is empty")
                return []
            
            print(f"📋 Found {len(queue_value)} request IDs in queue: {queue_value}")
            
            request_ids = queue_value
            requests = []
            
            for request_id in request_ids:
                try:
                    request_query = self.substrate.query('QxAi', 'InferenceRequests', [request_id])
                    if request_query and request_query.value:
                        request_data = request_query.value
                        
                        # Handle the prompt which might be stored as bytes or bounded vec
                        prompt_data = request_data['prompt']
                        if isinstance(prompt_data, list):
                            prompt = bytes(prompt_data).decode('utf-8', errors='ignore')
                        elif isinstance(prompt_data, bytes):
                            prompt = prompt_data.decode('utf-8', errors='ignore')
                        else:
                            prompt = str(prompt_data)
                        
                        # Handle status enum - it might come as a dict or string
                        status = request_data['status']
                        if isinstance(status, dict):
                            # Status comes as enum variant like {'Queued': None}
                            status_key = list(status.keys())[0] if status else 'Unknown'
                        else:
                            status_key = str(status)
                        
                        requests.append({
                            'id': request_id,
                            'customer': request_data['customer'],
                            'prompt': prompt,
                            'model_id': request_data['model_id'],
                            'status': status_key,
                            'created_at': request_data['created_at']
                        })
                        
                        print(f"📋 Request {request_id}: status={status_key}, model={request_data['model_id']}")
                    else:
                        print(f"⚠️ Request {request_id} not found in storage")
                        
                except Exception as req_error:
                    print(f"❌ Error processing request {request_id}: {req_error}")
                    continue
            
            return requests
            
        except Exception as e:
            print(f"❌ Error getting queue requests: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def process_queue_request(self, request: Dict):
        """Process a single queued request"""
        try:
            request_id = request['id']
            prompt = request['prompt']
            model_id = request['model_id']
            
            print(f"🔄 Processing request {request_id} from {request['customer']}")
            print(f"   Model: {model_id}")
            print(f"   Prompt: {prompt[:100]}...")
            
            # Run inference
            output = await self.run_inference(model_id, prompt)
            if not output:
                print(f"❌ Inference failed for request {request_id}")
                return False
            
            # Submit result to chain
            success = await self.submit_inference(request_id, output)
            return success
                
        except Exception as e:
            print(f"❌ Error processing request {request['id']}: {e}")
            return False
    
    async def queue_listener(self):
        """Main queue listener loop"""
        print("🎧 Starting queue listener...")
        print("🤖 Worker will continuously monitor and process inference requests")
        print("📊 Status updates will be shown every 30 seconds")
        self.queue_listener_running = True
        
        # Set worker as online
        await self.update_worker_status(True)
        
        status_counter = 0
        
        try:
            while self.queue_listener_running:
                try:
                    # Show status every 6 iterations (30 seconds with 5s interval)
                    if status_counter % 6 == 0:
                        print(f"\n{'='*50}")
                        print(f"🤖 Worker Status Check (Cycle {status_counter + 1})")
                        print(f"📅 Time: {asyncio.get_event_loop().time():.0f}")
                        print(f"🔗 Chain Connected: {self.substrate is not None}")
                        print(f"📊 Queue Listener Running: {self.queue_listener_running}")
                        print(f"🏠 Worker Address: {self.worker_address}")
                        print(f"{'='*50}")
                    
                    # Check if node is slashed first
                    node_identity = await self.get_node_identity()
                    if node_identity and 'peer_id' in node_identity:
                        is_slashed = await self.check_node_slashed_status(node_identity['peer_id'])
                        if is_slashed:
                            print("🔥 NODE HAS BEEN SLASHED! Stopping operations...")
                            print("   This node can no longer participate in the network")
                            self.queue_listener_running = False
                            break
                    
                    # Get queued requests
                    requests = await self.get_queue_requests()
                    
                    if requests:
                        print(f"📋 Found {len(requests)} queued requests")
                        
                        # Process requests in order (FIFO)
                        for request in requests:
                            if request['status'] in ['Queued', 'queued']:
                                await self.process_queue_request(request)
                            else:
                                print(f"⏭️ Skipping request {request['id']} with status: {request['status']}")
                            await asyncio.sleep(1)  # Small delay between requests
                    else:
                        print("✅ No requests in queue (all clear)")
                    
                    status_counter += 1
                    # Wait before checking again
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    print(f"❌ Error in queue listener: {e}")
                    await asyncio.sleep(10)  # Wait longer on error
                    
        except asyncio.CancelledError:
            print("🛑 Queue listener cancelled")
        except Exception as e:
            print(f"❌ Queue listener error: {e}")
        finally:
            # Set worker as offline
            await self.update_worker_status(False)
            self.queue_listener_running = False
            print("🎧 Queue listener stopped")
    
    async def interactive_mode(self):
        """Interactive mode for manual inference selection and execution"""
        print("🎮 Starting Interactive Worker Mode...")
        print("🎯 You can manually review and execute inference requests")
        
        # Set worker as online
        await self.update_worker_status(True)
        
        try:
            while True:
                print("\n" + "="*60)
                print("🤖 QX Chain Worker Interactive Mode")
                print("="*60)
                print("1. 📋 Check queue for pending requests")
                print("2. 🔍 Show detailed request info")
                print("3. ⚡ Execute specific request")
                print("4. 📊 Show worker status")
                print("5. 📋 Monitor submitted inferences")
                print("6. 🔄 Refresh worker status on chain")
                print("7. 🚪 Exit interactive mode")
                print("-" * 60)
                
                choice = input("Select option (1-7): ").strip()
                
                if choice == "1":
                    await self.show_pending_requests()
                elif choice == "2":
                    await self.show_request_details()
                elif choice == "3":
                    await self.execute_request_interactive()
                elif choice == "4":
                    await self.show_worker_status()
                elif choice == "5":
                    await self.monitor_submitted_inferences()
                elif choice == "6":
                    await self.refresh_worker_status()
                elif choice == "7":
                    print("🚪 Exiting interactive mode...")
                    break
                else:
                    print("❌ Invalid option. Please choose 1-7.")
                    
        except KeyboardInterrupt:
            print("\n🛑 Interactive mode interrupted")
        except Exception as e:
            print(f"❌ Interactive mode error: {e}")
        finally:
            # Set worker as offline
            await self.update_worker_status(False)
            print("🎮 Interactive mode stopped")
    
    async def show_pending_requests(self):
        """Show all pending requests in the queue"""
        try:
            print("\n🔍 Fetching pending requests...")
            requests = await self.get_queue_requests()
            
            if not requests:
                print("📭 No pending requests found")
                return
            
            print(f"\n📋 Found {len(requests)} pending requests:")
            print("-" * 80)
            print(f"{'ID':<4} {'Customer':<15} {'Model':<8} {'Status':<10} {'Created':<10} {'Prompt Preview'}")
            print("-" * 80)
            
            for req in requests:
                prompt_preview = req['prompt'][:40] + "..." if len(req['prompt']) > 40 else req['prompt']
                customer_short = req['customer'][:15] if len(req['customer']) > 15 else req['customer']
                print(f"{req['id']:<4} {customer_short:<15} {req['model_id']:<8} {req['status']:<10} {req['created_at']:<10} {prompt_preview}")
            
            print("-" * 80)
            
        except Exception as e:
            print(f"❌ Error showing pending requests: {e}")
    
    async def show_request_details(self):
        """Show detailed information for a specific request"""
        try:
            request_id = input("\n📋 Enter request ID to view details: ").strip()
            if not request_id.isdigit():
                print("❌ Invalid request ID")
                return
                
            requests = await self.get_queue_requests()
            request = next((r for r in requests if str(r['id']) == request_id), None)
            
            if not request:
                print(f"❌ Request {request_id} not found in queue")
                return
            
            print(f"\n📄 Request {request_id} Details:")
            print("-" * 50)
            print(f"Customer: {request['customer']}")
            print(f"Model ID: {request['model_id']}")
            print(f"Status: {request['status']}")
            print(f"Created: {request['created_at']}")
            print(f"Prompt:")
            print(f"  {request['prompt']}")
            print("-" * 50)
            
        except Exception as e:
            print(f"❌ Error showing request details: {e}")
    
    async def execute_request_interactive(self):
        """Interactively execute a specific request"""
        try:
            requests = await self.get_queue_requests()
            
            if not requests:
                print("📭 No pending requests to execute")
                return
            
            print(f"\n⚡ Available requests for execution:")
            print("-" * 60)
            for i, req in enumerate(requests, 1):
                prompt_preview = req['prompt'][:50] + "..." if len(req['prompt']) > 50 else req['prompt']
                print(f"{i}. Request {req['id']} - Model {req['model_id']} - {prompt_preview}")
            print("-" * 60)
            
            choice = input("Select request number to execute (or 'q' to cancel): ").strip()
            
            if choice.lower() == 'q':
                return
                
            if not choice.isdigit() or int(choice) < 1 or int(choice) > len(requests):
                print("❌ Invalid selection")
                return
            
            selected_request = requests[int(choice) - 1]
            
            print(f"\n🚀 Executing request {selected_request['id']}...")
            print(f"Prompt: {selected_request['prompt']}")
            print(f"Model: {selected_request['model_id']}")
            
            confirm = input("Proceed with execution? (y/N): ").strip().lower()
            if confirm != 'y':
                print("❌ Execution cancelled")
                return
            
            # Execute the request
            await self.process_queue_request(selected_request)
            
        except Exception as e:
            print(f"❌ Error executing request: {e}")
    
    async def show_worker_status(self):
        """Show current worker status"""
        try:
            print(f"\n📊 Worker Status:")
            print("-" * 50)
            print(f"Address: {self.worker_address}")
            print(f"Registered: {self.registered}")
            print(f"Models: {list(self.models.keys())}")
            print(f"Queue Listener Running: {self.queue_listener_running}")
            print(f"Chain Endpoint: {self.substrate.url}")
            
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
            
            # Check on-chain status
            worker_status = self.substrate.query('QxAi', 'WorkerStatus', [self.worker_address])
            online_status = worker_status.value if worker_status else "Unknown"
            print(f"On-chain Status: {'🟢 Online' if online_status else '🔴 Offline'}")
            
            # Check queue size
            queue_query = self.substrate.query('QxAi', 'WorkerQueues', [self.worker_address])
            queue_size = len(queue_query.value) if queue_query and queue_query.value else 0
            print(f"Queue Size: {queue_size} requests")
            
            # Show submitted inferences count
            print(f"Submitted Inferences: {len(self.submitted_inferences)}")
            
            # Show node identity info
            node_identity = await self.get_node_identity()
            if node_identity:
                print(f"Node Identity:")
                print(f"  Peer ID: {node_identity.get('peer_id', 'Not set')}")
                print(f"  Endpoint: {node_identity.get('endpoint', 'Not set')}")
                print(f"  Type: {['Worker', 'Validator', 'WorkerValidator'][node_identity.get('node_type', 0)]}")
                
                # Check if slashed
                if 'peer_id' in node_identity:
                    is_slashed = await self.check_node_slashed_status(node_identity['peer_id'])
                    if is_slashed:
                        print(f"  ⚠️  STATUS: 🔥 SLASHED")
                    else:
                        print(f"  ✅ STATUS: Active")
            else:
                print("Node Identity: Not registered")
            
            # Check for challenges
            challenged_count = 0
            for request_id in self.submitted_inferences:
                challenges = await self.get_inference_challenges_by_request(request_id)
                if challenges:
                    challenged_count += 1
            
            if challenged_count > 0:
                print(f"⚠️  Challenged Inferences: {challenged_count}")
            
            print("-" * 50)
            
        except Exception as e:
            print(f"❌ Error showing worker status: {e}")
    
    async def refresh_worker_status(self):
        """Refresh worker status on chain"""
        try:
            print("🔄 Refreshing worker status...")
            success = await self.update_worker_status(True)
            if success:
                print("✅ Worker status refreshed successfully")
            else:
                print("❌ Failed to refresh worker status")
        except Exception as e:
            print(f"❌ Error refreshing status: {e}")
    
    async def get_inference_challenges_by_request(self, request_id: int) -> List[Dict]:
        """Get challenges for an inference by request ID"""
        try:
            # Reconnect if needed
            try:
                self.substrate.get_block_number(None)
            except:
                chain_url = getattr(self.substrate, 'url', "ws://localhost:9933")
                self.substrate = SubstrateInterface(url=chain_url)
            
            # First find the inference ID for this request
            inference_results = self.substrate.query_map('QxAi', 'InferenceResults')
            inference_id = None
            
            for inf_id, result in inference_results:
                if result.value and result.value['request_id'] == request_id:
                    inference_id = inf_id.value
                    break
            
            if inference_id is None:
                return []
            
            # Get challenges for this inference
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
    
    async def get_inference_status_by_request(self, request_id: int) -> Optional[Dict]:
        """Get inference status by request ID"""
        try:
            # Reconnect if needed
            try:
                self.substrate.get_block_number(None)
            except:
                chain_url = getattr(self.substrate, 'url', "ws://localhost:9933")
                self.substrate = SubstrateInterface(url=chain_url)
            
            # Find the inference for this request
            inference_results = self.substrate.query_map('QxAi', 'InferenceResults')
            
            for inf_id, result in inference_results:
                if result.value and result.value['request_id'] == request_id:
                    inference_data = result.value
                    status = inference_data['status']
                    
                    # Handle status enum
                    if isinstance(status, dict):
                        status_key = list(status.keys())[0] if status else 'Unknown'
                    else:
                        status_key = str(status)
                    
                    return {
                        'inference_id': inf_id.value,
                        'status': status_key,
                        'worker': inference_data['worker'],
                        'output': bytes(inference_data['output']).decode('utf-8', errors='ignore'),
                        'submitted_at': inference_data['submitted_at']
                    }
            return None
            
        except Exception as e:
            if "not found" not in str(e):
                print(f"❌ Error getting inference status: {e}")
            return None
    
    async def monitor_submitted_inferences(self):
        """Monitor status of submitted inferences"""
        try:
            if not self.submitted_inferences:
                print("\n📭 No submitted inferences to monitor")
                return
            
            print(f"\n📋 Monitoring {len(self.submitted_inferences)} submitted inferences:")
            print("-" * 100)
            print(f"{'Req ID':<8} {'Status':<12} {'Challenges':<12} {'Submitted':<12} {'Output Preview'}")
            print("-" * 100)
            
            for request_id, submission_info in self.submitted_inferences.items():
                # Get current status from chain
                status_info = await self.get_inference_status_by_request(request_id)
                current_status = status_info['status'] if status_info else 'Unknown'
                
                # Get challenges
                challenges = await self.get_inference_challenges_by_request(request_id)
                challenge_count = len(challenges)
                
                # Show preview of output
                output_preview = submission_info['output_text'][:40] + "..." if len(submission_info['output_text']) > 40 else submission_info['output_text']
                
                # Status icon
                status_icon = {
                    'Pending': '⏳',
                    'Challenged': '⚠️',
                    'Validated': '✅',
                    'Slashed': '🔥',
                    'Unknown': '❓'
                }.get(current_status, '❓')
                
                challenge_str = f"{challenge_count} chal." if challenge_count > 0 else "None"
                
                print(f"{request_id:<8} {status_icon} {current_status:<10} {challenge_str:<12} Block {submission_info['submitted_at']:<8} {output_preview}")
                
                # Show challenge details if any
                if challenges:
                    print(f"         📋 Challenge details:")
                    for i, challenge in enumerate(challenges[:3], 1):  # Show max 3 challenges
                        validator_short = challenge['validator'][:30] + "..." if len(challenge['validator']) > 30 else challenge['validator']
                        expected_preview = challenge['expected_output'][:50] + "..." if len(challenge['expected_output']) > 50 else challenge['expected_output']
                        print(f"         {i}. {validator_short}: '{expected_preview}'")
                    
                    if len(challenges) > 3:
                        print(f"         ... and {len(challenges) - 3} more challenges")
            
            print("-" * 100)
            
            # Summary
            status_counts = {}
            challenged_count = 0
            for request_id in self.submitted_inferences:
                status_info = await self.get_inference_status_by_request(request_id)
                status = status_info['status'] if status_info else 'Unknown'
                status_counts[status] = status_counts.get(status, 0) + 1
                
                challenges = await self.get_inference_challenges_by_request(request_id)
                if challenges:
                    challenged_count += 1
            
            print(f"\n📊 Summary:")
            for status, count in status_counts.items():
                icon = {'Pending': '⏳', 'Challenged': '⚠️', 'Validated': '✅', 'Slashed': '🔥', 'Unknown': '❓'}.get(status, '❓')
                print(f"   {icon} {status}: {count}")
            
            if challenged_count > 0:
                print(f"   ⚠️  Total with challenges: {challenged_count}")
            
        except Exception as e:
            print(f"❌ Error monitoring submitted inferences: {e}")
    
    def stop_queue_listener(self):
        """Stop the queue listener"""
        self.queue_listener_running = False
    
    async def start_node(self) -> bool:
        """Start the blockchain node"""
        if not self.node_manager:
            print("⚠️ No node manager configured")
            return True  # Continue without node
        
        print(f"🚀 Starting blockchain node for worker...")
        success = await self.node_manager.start_node()
        
        if success:
            # Get the peer ID and register node identity
            await asyncio.sleep(2)  # Wait for node to fully start
            peer_id = self.node_manager.get_peer_id()
            if peer_id:
                print(f"🔗 Auto-registering node identity with peer ID: {peer_id}")
                node_info = self.node_manager.get_node_info()
                await self.register_node_identity(
                    peer_id, 
                    node_info['ws_endpoint'], 
                    0  # Worker type
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
        """Graceful shutdown of worker and node"""
        print("🛑 Shutting down worker and node...")
        
        # Stop queue listener
        self.stop_queue_listener()
        
        # Set worker offline
        if self.registered:
            await self.update_worker_status(False)
        
        # Stop blockchain node
        await self.stop_node()
        
        print("✅ Shutdown complete")
        sys.exit(0)

async def main():
    print("🌟 QX Chain Ollama Worker Starting...")
    
    parser = argparse.ArgumentParser(description='QX Chain Ollama Worker')
    parser.add_argument('--chain', default='ws://localhost:9933', help='Chain endpoint')
    parser.add_argument('--ollama', default='http://localhost:11434', help='Ollama endpoint')
    parser.add_argument('--seed', default='//Bob', help='Worker account seed')
    parser.add_argument('--setup-model', action='store_true', help='Setup model (always enabled)')
    parser.add_argument('--interactive', action='store_true', help='Start in interactive mode')
    parser.add_argument('--peer-id', default=None, help='Node peer ID for blockchain network (deprecated, auto-generated)')
    parser.add_argument('--node-endpoint', default='http://localhost:9933', help='Node endpoint (deprecated, auto-managed)')
    parser.add_argument('--start-node', action='store_true', help='Start blockchain node with worker (default: True)')
    parser.add_argument('--no-node', action='store_true', help='Don\'t start blockchain node (use external node)')
    parser.add_argument('--node-name', default=None, help='Custom blockchain node name')
    
    args = parser.parse_args()
    
    # Setup node manager unless explicitly disabled
    node_manager = None
    if not args.no_node:
        # Get auto-assigned ports to avoid conflicts
        ws_port, http_port, p2p_port = get_auto_ports(9933)
        
        # Create node name
        node_name = args.node_name or f"worker_{args.seed.replace('//', '').replace('/', '_')}"
        
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
    
    # Initialize worker
    worker = OllamaWorker(
        chain_endpoint=args.chain,
        ollama_endpoint=args.ollama,
        worker_seed=args.seed,
        node_manager=node_manager
    )
    
    # Setup signal handlers for graceful shutdown
    worker.setup_signal_handlers()
    
    try:
        # Start blockchain node first if managed
        if node_manager:
            if not await worker.start_node():
                print("❌ Failed to start blockchain node. Exiting.")
                return
        
        # Check chain connection
        if not await worker.check_chain_connection():
            print("❌ Chain connection failed. Please ensure the chain is running.")
            return
        
        # Register worker and setup models BEFORE starting servers
        if not await worker.register_worker():
            print("❌ Failed to register worker. Exiting.")
            return
        
        # Always setup model by default
        await worker.setup_model()
        
        # Register node identity if peer_id provided (legacy support)
        if args.peer_id:
            print(f"🔗 Registering node identity...")
            await worker.register_node_identity(args.peer_id, args.node_endpoint, 0)  # 0 = Worker type
        
        print("✅ Worker initialization complete!")
        
        print("🎧 Starting worker with automatic queue listening...")
        # Run only queue listener
        await worker.queue_listener()
                
    except Exception as e:
        print(f"❌ Fatal error: {e}")
    finally:
        # Ensure cleanup
        await worker.shutdown()

if __name__ == "__main__":
    print("📋 Starting main function...")
    asyncio.run(main())
