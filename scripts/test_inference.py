#!/usr/bin/env python3
"""
QX Chain Inference Test Script

Test the complete opML pipeline:
1. Submit inference request to worker
2. Monitor chain for inference submission
3. Wait for validation/challenge
4. Display results
"""

import json
import requests
import time
import argparse
from substrateinterface import SubstrateInterface

def test_inference(worker_endpoint: str = "http://localhost:8000", 
                  chain_endpoint: str = "ws://localhost:9944",
                  prompt: str = "What are the zoo's operating hours?",
                  model_id: int = 0):
    
    print(f"🧪 Testing QX Chain opML Inference")
    print(f"Worker: {worker_endpoint}")
    print(f"Chain: {chain_endpoint}")
    print(f"Prompt: {prompt}")
    print(f"Model ID: {model_id}")
    print("-" * 50)
    
    # Connect to chain
    substrate = SubstrateInterface(url=chain_endpoint)
    
    # Submit inference request
    print("📤 Submitting inference request...")
    response = requests.post(
        f"{worker_endpoint}/inference",
        json={
            "prompt": prompt,
            "model_id": model_id
        }
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to submit inference: {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    inference_id = result['inference_id']
    print(f"✅ Inference submitted with ID: {inference_id}")
    
    # Monitor inference status
    print("👀 Monitoring inference status...")
    start_time = time.time()
    timeout = 300  # 5 minutes
    
    while time.time() - start_time < timeout:
        try:
            # Query inference from chain
            inference_result = substrate.query(
                module='OpML',
                storage_function='Inferences',
                params=[inference_id]
            )
            
            if inference_result and inference_result.value:
                inference = inference_result.value
                status = inference['status']
                
                print(f"📊 Current status: {status}")
                
                if status in ['Validated', 'Invalid']:
                    print(f"🎯 Final status: {status}")
                    
                    if status == 'Validated':
                        print("✅ Inference was validated by the city validator!")
                        output = bytes(inference['output']).decode('utf-8', errors='ignore')
                        print(f"💬 Output: {output}")
                    else:
                        print("❌ Inference was marked as invalid and worker was slashed!")
                    
                    return
                
            time.sleep(5)
            
        except Exception as e:
            print(f"❌ Error monitoring inference: {e}")
            time.sleep(5)
    
    print("⏰ Timeout waiting for inference validation")

def main():
    parser = argparse.ArgumentParser(description='Test QX Chain opML Inference')
    parser.add_argument('--worker', default='http://localhost:8000', help='Worker API endpoint')
    parser.add_argument('--chain', default='ws://localhost:9944', help='Chain endpoint')
    parser.add_argument('--prompt', default='What are the zoo operating hours?', help='Inference prompt')
    parser.add_argument('--model', type=int, default=0, help='Model ID')
    
    args = parser.parse_args()
    
    test_inference(
        worker_endpoint=args.worker,
        chain_endpoint=args.chain,
        prompt=args.prompt,
        model_id=args.model
    )

if __name__ == "__main__":
    main()
