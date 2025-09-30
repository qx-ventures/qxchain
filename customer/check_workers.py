#!/usr/bin/env python3
"""
Check registered workers on the chain - REAL CHAIN STATE ONLY
"""
from substrateinterface import SubstrateInterface, Keypair
import json

def main():
    print("=" * 60)
    print("QxChain - Check Registered Workers (REAL CHAIN STATE)")
    print("=" * 60)
    print()

    # Connect to the chain
    substrate = SubstrateInterface(
        url="ws://localhost:9944",
        type_registry_preset='substrate-node-template'
    )

    print(f"✅ Connected to chain: {substrate.chain}")
    print(f"📦 Current block: #{substrate.get_block_number(substrate.get_chain_head())}")
    print()

    # Query Workers storage map from MlInference pallet
    print("📋 Querying MlInference.Workers storage map...")
    print("-" * 40)

    try:
        # Query all entries in the Workers storage map
        result = substrate.query_map(
            module='MlInference',
            storage_function='Workers'
        )

        workers = list(result)

        if len(workers) == 0:
            print("❌ NO WORKERS REGISTERED ON CHAIN")
            print()
            print("This is the REAL chain state - no workers are registered.")
            print("The Workers storage map in the MlInference pallet is empty.")
        else:
            print(f"✅ Found {len(workers)} registered workers:")
            print()
            for worker_account, is_registered in workers:
                # worker_account.value contains the AccountId
                # is_registered.value contains the boolean flag
                print(f"  Worker Account: {worker_account.value}")
                print(f"  Registered: {is_registered.value}")
                print()

    except Exception as e:
        print(f"❌ Error querying Workers storage: {e}")
        print("This might mean the pallet is not deployed or has different structure")

    print("-" * 40)

    # Also check WorkerStatus storage map
    print("\n📋 Querying MlInference.WorkerStatus storage map...")
    print("-" * 40)

    try:
        result = substrate.query_map(
            module='MlInference',
            storage_function='WorkerStatus'
        )

        statuses = list(result)

        if len(statuses) == 0:
            print("❌ NO WORKER STATUSES RECORDED")
            print("The WorkerStatus storage map is empty.")
        else:
            print(f"✅ Found {len(statuses)} worker status entries:")
            print()
            for worker_account, is_online in statuses:
                print(f"  Worker: {worker_account.value}")
                print(f"  Online: {is_online.value}")
                print()

    except Exception as e:
        print(f"❌ Error querying WorkerStatus storage: {e}")

    print("-" * 40)

    # Check WorkerQueues storage map
    print("\n📋 Querying MlInference.WorkerQueues storage map...")
    print("-" * 40)

    try:
        result = substrate.query_map(
            module='MlInference',
            storage_function='WorkerQueues'
        )

        queues = list(result)

        if len(queues) == 0:
            print("❌ NO WORKER QUEUES INITIALIZED")
            print("The WorkerQueues storage map is empty.")
        else:
            print(f"✅ Found {len(queues)} worker queue entries:")
            print()
            for worker_account, queue in queues:
                print(f"  Worker: {worker_account.value}")
                print(f"  Queue size: {len(queue.value) if queue.value else 0} requests")
                if queue.value and len(queue.value) > 0:
                    print(f"  Queued requests: {queue.value}")
                print()

    except Exception as e:
        print(f"❌ Error querying WorkerQueues storage: {e}")

    print("-" * 40)

    # Check some other storage values
    print("\n📊 Other MlInference Storage Values:")
    print("-" * 40)

    try:
        next_request = substrate.query(
            module='MlInference',
            storage_function='NextRequestId'
        )
        print(f"  NextRequestId: {next_request.value if next_request else 0}")
    except:
        print("  NextRequestId: Error reading")

    try:
        next_inference = substrate.query(
            module='MlInference',
            storage_function='NextInferenceId'
        )
        print(f"  NextInferenceId: {next_inference.value if next_inference else 0}")
    except:
        print("  NextInferenceId: Error reading")

    # Check for any validators
    print("\n📋 Checking for registered validators...")
    print("-" * 40)

    try:
        result = substrate.query_map(
            module='MlInference',
            storage_function='Validators'
        )

        validators = list(result)

        if len(validators) == 0:
            print("❌ No validators registered")
        else:
            print(f"✅ Found {len(validators)} validators:")
            for validator_account, is_registered in validators:
                print(f"  Validator: {validator_account.value}")

    except Exception as e:
        print(f"❌ Error querying Validators storage: {e}")

    print()
    print("=" * 60)
    print("END OF REAL CHAIN STATE QUERY")
    print("=" * 60)

if __name__ == "__main__":
    main()