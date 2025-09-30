#!/usr/bin/env python3
"""
Monitor inference requests and results in real-time
"""
from substrateinterface import SubstrateInterface
import time

def main():
    print("=" * 60)
    print("QxChain Inference Monitor")
    print("=" * 60)
    print()

    substrate = SubstrateInterface(
        url="ws://localhost:9944",
        type_registry_preset='substrate-node-template'
    )

    print(f"✅ Connected to chain: {substrate.chain}")
    print(f"📦 Starting block: #{substrate.get_block_number(substrate.get_chain_head())}")
    print()
    print("Monitoring for inference activity...")
    print("-" * 60)

    last_request_id = 0
    last_inference_id = 0

    while True:
        try:
            # Check requests
            next_request_id = substrate.query(
                module='MlInference',
                storage_function='NextRequestId'
            ).value

            if next_request_id > last_request_id:
                print(f"\n🆕 NEW REQUEST DETECTED! Request ID: {last_request_id}")

                # Query the request details
                request = substrate.query(
                    module='MlInference',
                    storage_function='InferenceRequests',
                    params=[last_request_id]
                )

                if request.value:
                    print(f"   Customer: {request.value['customer']}")
                    print(f"   Worker: {request.value['target_worker']}")
                    print(f"   Prompt: {bytes(request.value['prompt']).decode('utf-8')}")
                    print(f"   Model ID: {request.value['model_id']}")
                    print(f"   Status: {request.value['status']}")

                last_request_id = next_request_id

            # Check inference results
            next_inference_id = substrate.query(
                module='MlInference',
                storage_function='NextInferenceId'
            ).value

            if next_inference_id > last_inference_id:
                print(f"\n✅ INFERENCE COMPLETED! Inference ID: {last_inference_id}")

                # Query the result
                result = substrate.query(
                    module='MlInference',
                    storage_function='InferenceResults',
                    params=[last_inference_id]
                )

                if result.value:
                    print(f"   Request ID: {result.value['request_id']}")
                    print(f"   Worker: {result.value['worker']}")
                    print(f"   Status: {result.value['status']}")
                    output = bytes(result.value['output']).decode('utf-8', errors='replace')
                    print(f"   Output: {output[:200]}...")
                    print(f"   Submitted at block: {result.value['submitted_at']}")

                last_inference_id = next_inference_id

            time.sleep(3)

        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()