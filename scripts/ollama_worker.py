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
from typing import Dict, Any, Optional, List
from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException

class OllamaWorker:
    def __init__(self, 
                 chain_endpoint: str = "ws://localhost:9944",
                 ollama_endpoint: str = "http://localhost:11434",
                 worker_seed: str = "//Bob"):
        
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
        self.queue_listener_running = False
    
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
                        chain_url = getattr(self.substrate, 'url', "ws://localhost:9944")
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
    
    
    async def setup_zoo_model(self):
        """Setup a zoo assistant model with deterministic parameters"""
        model_id = await self.register_model(
            model_name="zoo_assistant",
            ollama_model="gemma3:4b",  # Lightweight model for testing
            endpoint="terminal",  # Terminal-only mode
            seed=42,  # Fixed seed for deterministic inference
            temperature=0.7,  # Consistent temperature
            max_tokens=512  # Consistent max tokens
        )
        
        if model_id is not None:
            print(f"✅ Zoo assistant model setup complete (ID: {model_id})")
            print(f"💡 Model ready for deterministic inference requests")
        
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
        self.queue_listener_running = True
        
        # Set worker as online
        await self.update_worker_status(True)
        
        try:
            while self.queue_listener_running:
                try:
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
                        print(f"💤 No requests found in queue for worker {self.worker_address}")
                    
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
                print("5. 🔄 Refresh worker status on chain")
                print("6. 🚪 Exit interactive mode")
                print("-" * 60)
                
                choice = input("Select option (1-6): ").strip()
                
                if choice == "1":
                    await self.show_pending_requests()
                elif choice == "2":
                    await self.show_request_details()
                elif choice == "3":
                    await self.execute_request_interactive()
                elif choice == "4":
                    await self.show_worker_status()
                elif choice == "5":
                    await self.refresh_worker_status()
                elif choice == "6":
                    print("🚪 Exiting interactive mode...")
                    break
                else:
                    print("❌ Invalid option. Please choose 1-6.")
                    
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
            print("-" * 40)
            print(f"Address: {self.worker_address}")
            print(f"Registered: {self.registered}")
            print(f"Models: {list(self.models.keys())}")
            print(f"Queue Listener Running: {self.queue_listener_running}")
            print(f"Chain Endpoint: {self.substrate.url}")
            
            # Check on-chain status
            worker_status = self.substrate.query('QxAi', 'WorkerStatus', [self.worker_address])
            online_status = worker_status.value if worker_status else "Unknown"
            print(f"On-chain Status: {'🟢 Online' if online_status else '🔴 Offline'}")
            
            # Check queue size
            queue_query = self.substrate.query('QxAi', 'WorkerQueues', [self.worker_address])
            queue_size = len(queue_query.value) if queue_query and queue_query.value else 0
            print(f"Queue Size: {queue_size} requests")
            print("-" * 40)
            
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
    
    def stop_queue_listener(self):
        """Stop the queue listener"""
        self.queue_listener_running = False

async def main():
    print("🌟 QX Chain Ollama Worker Starting...")
    
    parser = argparse.ArgumentParser(description='QX Chain Ollama Worker')
    parser.add_argument('--chain', default='ws://localhost:9944', help='Chain endpoint')
    parser.add_argument('--ollama', default='http://localhost:11434', help='Ollama endpoint')
    parser.add_argument('--seed', default='//Bob', help='Worker account seed')
    parser.add_argument('--setup-zoo', action='store_true', help='Setup zoo assistant model')
    parser.add_argument('--interactive', action='store_true', help='Start in interactive mode')
    
    args = parser.parse_args()
    
    # Initialize worker
    worker = OllamaWorker(
        chain_endpoint=args.chain,
        ollama_endpoint=args.ollama,
        worker_seed=args.seed
    )
    
    # Check chain connection first
    if not await worker.check_chain_connection():
        print("❌ Chain connection failed. Please ensure the chain is running.")
        return
    
    # Register worker and setup models BEFORE starting servers
    if not await worker.register_worker():
        print("❌ Failed to register worker. Exiting.")
        return
    
    if args.setup_zoo:
        await worker.setup_zoo_model()
    
    print("✅ Worker initialization complete!")
    
    if args.interactive:
        print("🎮 Starting interactive mode...")
        try:
            await worker.interactive_mode()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down worker...")
    else:
        print("🎧 Starting queue listener...")
        
        # Start queue listener
        try:
            await worker.queue_listener()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down worker...")
            worker.stop_queue_listener()
        except Exception as e:
            print(f"❌ Worker error: {e}")
            worker.stop_queue_listener()

if __name__ == "__main__":
    print("📋 Starting main function...")
    asyncio.run(main())
