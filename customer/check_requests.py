#!/usr/bin/env python3
"""
Check current requests and queue status
"""
from substrateinterface import SubstrateInterface, Keypair

substrate = SubstrateInterface(
    url="ws://localhost:9944",
    type_registry_preset='substrate-node-template'
)

print("=" * 60)
print("QxChain - Current Requests Status")
print("=" * 60)
print()

# Check counters
next_request = substrate.query('MlInference', 'NextRequestId').value
next_inference = substrate.query('MlInference', 'NextInferenceId').value

print(f"📊 Counters:")
print(f"   NextRequestId: {next_request}")
print(f"   NextInferenceId: {next_inference}")
print()

# Check requests
print(f"📋 Inference Requests:")
print("-" * 60)

if next_request > 0:
    for i in range(next_request):
        request = substrate.query('MlInference', 'InferenceRequests', [i])
        if request.value:
            print(f"Request #{i}:")
            print(f"   Customer: {request.value['customer']}")
            print(f"   Worker: {request.value['target_worker']}")
            try:
                prompt = bytes(request.value['prompt']).decode('utf-8') if isinstance(request.value['prompt'], (list, bytes)) else request.value['prompt']
            except:
                prompt = str(request.value['prompt'])
            print(f"   Prompt: {prompt}")
            print(f"   Model ID: {request.value['model_id']}")
            print(f"   Status: {request.value['status']}")
            print()
else:
    print("No requests found")
    print()

# Check Bob's queue
bob = Keypair.create_from_uri('//Bob')
queue = substrate.query('MlInference', 'WorkerQueues', [bob.ss58_address])

print(f"👷 Bob's Worker Queue:")
print("-" * 60)
if queue.value and len(queue.value) > 0:
    print(f"Queue size: {len(queue.value)}")
    print(f"Pending request IDs: {queue.value}")
else:
    print("Queue is empty")

print()
print("=" * 60)