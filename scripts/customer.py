#!/usr/bin/env python3
"""
QX Chain Customer Interface

Interactive script for customers to:
1. Browse available workers and their models
2. Submit inference requests to specific workers
3. Monitor request status and get results
"""

import json
import time
import asyncio
import argparse
from typing import Dict, List, Optional
from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException

class QXCustomer:
    def __init__(self, 
                 chain_endpoint: str = "ws://host.docker.internal:9933",
                 customer_seed: str = "//Alice"):
        
        self.substrate = SubstrateInterface(url=chain_endpoint)
        self.keypair = Keypair.create_from_uri(customer_seed)
        self.customer_address = self.keypair.ss58_address
        
        print(f"Customer initialized with address: {self.customer_address}")
        print(f"Chain endpoint: {chain_endpoint}")
        
        # Track submitted requests
        self.submitted_requests = {}
        
    async def check_chain_connection(self):
        """Check if chain connection is healthy"""
        try:
            latest_block = self.substrate.get_block_number(None)
            print(f"🔗 Chain connection healthy - Latest block: {latest_block}")
            return True
        except Exception as e:
            print(f"⚠️ Chain connection unhealthy: {e}")
            return False
    
    async def get_workers(self) -> List[Dict]:
        """Get list of registered workers from chain"""
        try:
            # Query all workers from storage
            workers_query = self.substrate.query_map('QxAi', 'Workers')
            workers = []
            
            for worker_account, stake in workers_query:
                worker_addr = worker_account.value
                
                # Check worker status
                status_query = self.substrate.query('QxAi', 'WorkerStatus', [worker_addr])
                online = status_query.value if status_query.value is not None else False
                
                # Get worker queue length
                queue_query = self.substrate.query('QxAi', 'WorkerQueues', [worker_addr])
                queue_length = len(queue_query.value) if queue_query.value else 0
                
                workers.append({
                    'address': worker_addr,
                    'stake': stake.value,
                    'online': online,
                    'queue_length': queue_length
                })
            
            return workers
        except Exception as e:
            print(f"❌ Error getting workers: {e}")
            return []

    async def get_validators(self) -> List[Dict]:
        """Get list of registered validators from chain"""
        try:
            # Query validators from the correct storage
            validators_query = self.substrate.query_map('QxAi', 'Validators')
            validators = []
            
            for validator_account, stake in validators_query:
                validator_addr = validator_account.value
                
                # Check if validator has node identity info
                try:
                    identity_query = self.substrate.query('QxAi', 'NodeIdentities', [validator_addr])
                    has_identity = identity_query.value is not None
                except Exception:
                    has_identity = False
                
                validators.append({
                    'address': validator_addr,
                    'stake': stake.value,
                    'online': has_identity,  # Assume online if has node identity
                    'challenges_processed': 0,  # Could be extended to track this
                    'validations_done': 0       # Could be extended to track this
                })
            
            return validators
        except Exception as e:
            print(f"❌ Error getting validators: {e}")
            return []
    
    async def get_worker_models(self, worker_address: str) -> List[Dict]:
        """Get available models for a worker"""
        # We assume workers have standard models
        # This could be extended to query on-chain model storage
        return [
            {"id": 0, "name": "assistant", "ollama_model": "gemma3:1b"}
        ]
    
    async def submit_request(self, worker_address: str, prompt: str, model_id: int = 0) -> Optional[int]:
        """Submit an inference request to a specific worker"""
        try:
            # Convert prompt to bounded vec format
            prompt_bytes = prompt.encode('utf-8')
            if len(prompt_bytes) > 2048:
                raise ValueError("Prompt too long (max 2048 bytes)")
            
            call = self.substrate.compose_call(
                call_module='QxAi',
                call_function='submit_request',
                call_params={
                    'target_worker': worker_address,
                    'prompt': prompt_bytes,  # Use bytes directly, not list
                    'model_id': model_id
                }
            )
            
            extrinsic = self.substrate.create_signed_extrinsic(call=call, keypair=self.keypair)
            receipt = self.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            
            if receipt.is_success:
                print(f"✅ Request submitted successfully!")
                print(f"📦 Block: {receipt.block_hash}")
                print(f"🧾 Transaction: {receipt.extrinsic_hash}")
                
                # Try to extract request ID from events, but don't fail if we can't
                request_id = None
                try:
                    for event in receipt.triggered_events or []:
                        if (hasattr(event, 'event') and 
                            hasattr(event.event, 'module') and 
                            hasattr(event.event, 'event') and
                            event.event.module and 
                            event.event.module.name == 'QxAi' and 
                            event.event.event.name == 'RequestSubmitted'):
                            request_id = event.event.attributes[0]['value']
                            break
                except Exception as e:
                    print(f"⚠️ Could not extract request ID from events: {e}")
                
                # If we can't get ID from events, get next request ID from chain
                if request_id is None:
                    try:
                        next_id_query = self.substrate.query('QxAi', 'NextRequestId')
                        request_id = next_id_query.value - 1 if next_id_query.value else 0
                        print(f"📋 Inferred request ID: {request_id}")
                    except Exception as e:
                        print(f"⚠️ Could not infer request ID: {e}")
                        request_id = int(time.time()) % 10000  # Fallback
                
                print(f"📋 Request ID: {request_id}")
                print(f"👤 Worker: {worker_address}")
                
                self.submitted_requests[request_id] = {
                    'worker': worker_address,
                    'prompt': prompt,
                    'model_id': model_id,
                    'submitted_at': time.time(),
                    'status': 'submitted'
                }
                
                return request_id
            else:
                print(f"❌ Request submission failed: {receipt.error_message}")
                return None
                
        except Exception as e:
            print(f"❌ Error submitting request: {e}")
            return None
    
    async def get_request_status(self, request_id: int) -> Optional[Dict]:
        """Get status of a submitted request"""
        try:
            # Query request from chain
            request_query = self.substrate.query('QxAi', 'InferenceRequests', [request_id])
            if not request_query.value:
                return None
            
            request_data = request_query.value
            
            # Check if there's a corresponding result
            result_query = self.substrate.query_map('QxAi', 'InferenceResults')
            result_data = None
            
            for result_id, result in result_query:
                if result.value['request_id'] == request_id:
                    result_data = result.value
                    break
            
            return {
                'request_id': request_id,
                'status': request_data['status'],
                'target_worker': request_data['target_worker'],
                'model_id': request_data['model_id'],
                'created_at': request_data['created_at'],
                'result': result_data
            }
            
        except Exception as e:
            print(f"❌ Error getting request status: {e}")
            return None
    
    async def monitor_requests(self):
        """Monitor all submitted requests"""
        if not self.submitted_requests:
            print("📭 No requests to monitor")
            return
        
        print(f"🔍 Monitoring {len(self.submitted_requests)} requests...")
        
        for request_id, local_data in self.submitted_requests.items():
            status = await self.get_request_status(request_id)
            if status:
                print(f"\n📋 Request {request_id}:")
                print(f"   Status: {status['status']}")
                print(f"   Worker: {status['target_worker']}")
                print(f"   Model: {status['model_id']}")
                
                if status['result']:
                    result = status['result']
                    # Handle output data which comes as a list of bytes from the chain
                    output_data = result['output']
                    if isinstance(output_data, list):
                        output = bytes(output_data).decode('utf-8', errors='ignore')
                    elif isinstance(output_data, bytes):
                        output = output_data.decode('utf-8', errors='ignore')
                    else:
                        output = str(output_data)
                    print(f"   Result: {output[:100]}..." if len(output) > 100 else f"   Result: {output}")
                    print(f"   Inference Status: {result['status']}")
            else:
                print(f"\n📋 Request {request_id}: Not found or error")

    async def interactive_menu(self):
        """Main interactive menu"""
        while True:
            print("\n" + "="*60)
            print("🎯 QX Chain Customer Interface")
            print("="*60)
            print("1. 👥 List available workers")
            print("2. 🛡️ List registered validators")
            print("3. 📝 Submit inference request")
            print("4. 📊 Monitor my requests")
            print("5. 🔍 Check specific request status")
            print("6. 🚪 Exit")
            print("-"*60)
            
            try:
                choice = input("Select option (1-6): ").strip()
                
                if choice == "1":
                    await self.list_workers()
                elif choice == "2":
                    await self.list_validators()
                elif choice == "3":
                    await self.submit_request_interactive()
                elif choice == "4":
                    await self.monitor_requests()
                elif choice == "5":
                    await self.check_request_interactive()
                elif choice == "6":
                    print("👋 Goodbye!")
                    break
                else:
                    print("❌ Invalid option. Please try again.")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    async def list_workers(self):
        """List all available workers with their status"""
        print("\n🔍 Fetching workers...")
        workers = await self.get_workers()
        
        if not workers:
            print("❌ No workers found or error fetching workers")
            return
        
        print(f"\n👥 Found {len(workers)} registered workers:")
        print("-"*80)
        print(f"{'Address':<50} {'Status':<8} {'Queue':<6} {'Stake':<10}")
        print("-"*80)
        
        for worker in workers:
            status = "🟢 Online" if worker['online'] else "🔴 Offline"
            queue_str = f"{worker['queue_length']} reqs"
            stake_str = f"{worker['stake']:,}"
            
            print(f"{worker['address']:<50} {status:<8} {queue_str:<6} {stake_str:<10}")
            
            # Try to get models for online workers
            if worker['online']:
                models = await self.get_worker_models(worker['address'])
                if models:
                    model_list = ', '.join([f"{m['name']} (ID: {m['id']})" for m in models])
                    print(f"   📚 Available models: {model_list}")

    async def list_validators(self):
        """List all registered validators with their status"""
        print("\n🔍 Fetching validators...")
        validators = await self.get_validators()
        
        if not validators:
            print("❌ No validators found or error fetching validators")
            return
        
        print(f"\n🛡️ Found {len(validators)} registered validators:")
        print("-"*90)
        print(f"{'Address':<50} {'Status':<8} {'Stake':<10} {'Challenges':<10} {'Validations':<12}")
        print("-"*90)
        
        for validator in validators:
            status = "🟢 Online" if validator['online'] else "🔴 Offline"
            stake_str = f"{validator['stake']:,}"
            challenges_str = f"{validator['challenges_processed']}"
            validations_str = f"{validator['validations_done']}"
            
            print(f"{validator['address']:<50} {status:<8} {stake_str:<10} {challenges_str:<10} {validations_str:<12}")
            
        print(f"\n📊 Network Summary:")
        online_count = sum(1 for v in validators if v['online'])
        total_stake = sum(v['stake'] for v in validators)
        print(f"   Online validators: {online_count}/{len(validators)}")
        print(f"   Total staked: {total_stake:,}")
        print(f"   Network security: {'🟢 High' if online_count >= 3 else '🟡 Medium' if online_count >= 2 else '🔴 Low'}")
    
    async def submit_request_interactive(self):
        """Interactive request submission"""
        print("\n📝 Submit Inference Request")
        print("-"*40)
        
        # Get workers
        workers = await self.get_workers()
        online_workers = [w for w in workers if w['online']]
        
        if not online_workers:
            print("❌ No online workers available")
            return
        
        # Select worker
        print("👥 Available workers:")
        for i, worker in enumerate(online_workers):
            print(f"{i+1}. {worker['address']} (Queue: {worker['queue_length']} requests)")
        
        try:
            worker_idx = int(input(f"Select worker (1-{len(online_workers)}): ")) - 1
            if worker_idx < 0 or worker_idx >= len(online_workers):
                print("❌ Invalid worker selection")
                return
            
            selected_worker = online_workers[worker_idx]
            worker_address = selected_worker['address']
            
            # Get models for this worker
            models = await self.get_worker_models(worker_address)
            model_id = 0  # Default
            
            if models:
                print(f"\n📚 Available models for {worker_address}:")
                for model in models:
                    print(f"   {model['id']}. {model['name']} ({model['ollama_model']})")
                
                try:
                    model_id = int(input(f"Select model ID (default 0): ") or "0")
                except ValueError:
                    model_id = 0
            
            # Get prompt
            prompt = input("\n💬 Enter your prompt: ").strip()
            if not prompt:
                print("❌ Prompt cannot be empty")
                return
            
            # Submit request
            print(f"\n📤 Submitting request to {worker_address}...")
            request_id = await self.submit_request(worker_address, prompt, model_id)
            
            if request_id:
                print(f"✅ Request {request_id} submitted successfully!")
                
                # Ask if user wants to wait for result
                wait = input("\n⏳ Wait for result? (y/N): ").lower().startswith('y')
                if wait:
                    await self.wait_for_result(request_id)
            
        except ValueError:
            print("❌ Invalid input")
        except KeyboardInterrupt:
            print("\n❌ Cancelled")
    
    async def wait_for_result(self, request_id: int, timeout: int = 300):
        """Wait for a specific request to complete"""
        print(f"⏳ Waiting for request {request_id} to complete (timeout: {timeout}s)...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = await self.get_request_status(request_id)
            if status and status['result']:
                result = status['result']
                # Handle output data which comes as a list of bytes from the chain
                output_data = result['output']
                if isinstance(output_data, list):
                    output = bytes(output_data).decode('utf-8', errors='ignore')
                elif isinstance(output_data, bytes):
                    output = output_data.decode('utf-8', errors='ignore')
                else:
                    output = str(output_data)
                
                print(f"\n✅ Request {request_id} completed!")
                print(f"📤 Output:")
                print("-" * 50)
                print(output)
                print("-" * 50)
                return
            
            await asyncio.sleep(5)
        
        print(f"⏰ Timeout waiting for request {request_id}")
    
    async def check_request_interactive(self):
        """Check status of a specific request"""
        try:
            request_id = int(input("Enter request ID: "))
            status = await self.get_request_status(request_id)
            
            if not status:
                print(f"❌ Request {request_id} not found")
                return
            
            print(f"\n📋 Request {request_id} Status:")
            print(f"   Status: {status['status']}")
            print(f"   Worker: {status['target_worker']}")
            print(f"   Model: {status['model_id']}")
            print(f"   Created: Block {status['created_at']}")
            
            if status['result']:
                result = status['result']
                # Handle output data which comes as a list of bytes from the chain
                output_data = result['output']
                if isinstance(output_data, list):
                    output = bytes(output_data).decode('utf-8', errors='ignore')
                elif isinstance(output_data, bytes):
                    output = output_data.decode('utf-8', errors='ignore')
                else:
                    output = str(output_data)
                print(f"   Result: {output}")
                print(f"   Inference Status: {result['status']}")
            else:
                print("   Result: Pending...")
                
        except ValueError:
            print("❌ Invalid request ID")

async def main():
    parser = argparse.ArgumentParser(description='QX Chain Customer Interface')
    parser.add_argument('--chain', default='ws://host.docker.internal:9933', help='Chain endpoint')
    parser.add_argument('--seed', default='//Alice', help='Customer account seed')
    
    args = parser.parse_args()
    
    customer = QXCustomer(
        chain_endpoint=args.chain,
        customer_seed=args.seed
    )
    
    print("🌟 QX Chain Customer Interface Starting...")
    
    if not await customer.check_chain_connection():
        print("❌ Chain connection failed. Please ensure the chain is running.")
        return
    
    await customer.interactive_menu()

if __name__ == "__main__":
    asyncio.run(main())
