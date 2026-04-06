#!/usr/bin/env python3
"""
Bootstrap AI Workers for QXChain
================================
Sets up KILT DIDs, worker credentials, and allowed AI models
required for running L2 workload simulations.

This script must be run after the chain is started to:
1. Set the governance DID
2. Create worker DIDs for test accounts (Bob, Charlie)
3. Issue worker credentials
4. Register allowed AI models

Usage:
  python3 bootstrap_ai_workers.py              # Bootstrap with defaults
  python3 bootstrap_ai_workers.py --workers 3  # Set up 3 workers
  python3 bootstrap_ai_workers.py --check      # Check current state
"""

import sys
import time
import argparse
from typing import List, Tuple, Optional

try:
    from substrateinterface import SubstrateInterface, Keypair
    from substrateinterface.exceptions import SubstrateRequestException
except ImportError:
    print("Error: substrateinterface not installed")
    print("Run: pip install substrate-interface")
    sys.exit(1)


# Default AI models to register
DEFAULT_MODELS = [
    {"id": 0, "name": "TinyLlama-1.1B-Fast", "hash": "a1b2c3d4e5f6"},
    {"id": 1, "name": "Llama-3.2-1B-Standard", "hash": "b2c3d4e5f6a1"},
    {"id": 2, "name": "Llama-3.2-3B-Complex", "hash": "c3d4e5f6a1b2"},
    {"id": 3, "name": "MoE-Ensemble-8x1B", "hash": "d4e5f6a1b2c3"},
]

# Worker accounts (derived from seed phrases)
WORKER_URIS = [
    "//Bob",
    "//Charlie",
    "//Dave",
    "//Eve",
]


def get_substrate(url: str = "ws://127.0.0.1:9944") -> SubstrateInterface:
    """Connect to the substrate node"""
    return SubstrateInterface(url=url)


def wait_for_inclusion(substrate: SubstrateInterface, receipt, timeout: int = 30) -> bool:
    """Wait for extrinsic to be included in a block"""
    if hasattr(receipt, 'is_success'):
        return receipt.is_success
    return True


def set_governance_did(substrate: SubstrateInterface, alice: Keypair) -> bool:
    """Set the governance DID using sudo"""
    print("Setting governance DID...")

    # Generate a governance DID (32 bytes)
    governance_did = bytes.fromhex("00" * 16 + "01" * 16)  # Simple pattern

    # Create the inner call
    inner_call = substrate.compose_call(
        call_module='QxKiltPermissions',
        call_function='set_governance_did',
        call_params={'did': list(governance_did)}
    )

    # Wrap in sudo
    sudo_call = substrate.compose_call(
        call_module='Sudo',
        call_function='sudo',
        call_params={'call': inner_call}
    )

    extrinsic = substrate.create_signed_extrinsic(call=sudo_call, keypair=alice)

    try:
        receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
        print(f"  Governance DID set: {governance_did.hex()[:32]}...")
        return True
    except SubstrateRequestException as e:
        print(f"  Error: {e}")
        return False


def create_worker_did(substrate: SubstrateInterface, worker: Keypair, name: str) -> Optional[bytes]:
    """Create a worker DID"""
    print(f"Creating DID for {name} ({worker.ss58_address[:16]}...)...")

    call = substrate.compose_call(
        call_module='QxKiltPermissions',
        call_function='create_worker_did',
        call_params={
            'name': name.encode(),
            'description': f"{name} AI Worker Node".encode()
        }
    )

    extrinsic = substrate.create_signed_extrinsic(call=call, keypair=worker)

    try:
        receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
        # Get the DID from storage
        did_info = substrate.query(
            module='QxKiltPermissions',
            storage_function='AccountToDID',
            params=[worker.ss58_address]
        )
        if did_info.value:
            did_bytes = bytes(did_info.value)
            print(f"  DID created: {did_bytes.hex()[:32]}...")
            return did_bytes
        return None
    except SubstrateRequestException as e:
        if "WorkerDIDAlreadyExists" in str(e):
            print(f"  DID already exists, fetching...")
            did_info = substrate.query(
                module='QxKiltPermissions',
                storage_function='AccountToDID',
                params=[worker.ss58_address]
            )
            if did_info.value:
                return bytes(did_info.value)
        else:
            print(f"  Error: {e}")
        return None


def issue_worker_credential(
    substrate: SubstrateInterface,
    alice: Keypair,
    worker_did: bytes,
    model_ids: List[int]
) -> bool:
    """Issue credential to a worker DID"""
    print(f"Issuing credential for DID {worker_did.hex()[:16]}...")

    inner_call = substrate.compose_call(
        call_module='QxKiltPermissions',
        call_function='issue_worker_credential',
        call_params={
            'worker_did': list(worker_did),
            'models': model_ids,
            'validity_period': None  # No expiry
        }
    )

    sudo_call = substrate.compose_call(
        call_module='Sudo',
        call_function='sudo',
        call_params={'call': inner_call}
    )

    extrinsic = substrate.create_signed_extrinsic(call=sudo_call, keypair=alice)

    try:
        receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
        print(f"  Credential issued for models: {model_ids}")
        return True
    except SubstrateRequestException as e:
        print(f"  Error: {e}")
        return False


def add_allowed_model(
    substrate: SubstrateInterface,
    alice: Keypair,
    model_id: int,
    model_name: str,
    model_hash: str
) -> bool:
    """Add an allowed model to the registry"""
    print(f"Adding model {model_id}: {model_name}...")

    inner_call = substrate.compose_call(
        call_module='QxAi',
        call_function='add_allowed_model',
        call_params={
            'model_id': model_id,
            'model_name': model_name.encode()[:128],
            'model_hash': model_hash.encode()[:64]
        }
    )

    sudo_call = substrate.compose_call(
        call_module='Sudo',
        call_function='sudo',
        call_params={'call': inner_call}
    )

    extrinsic = substrate.create_signed_extrinsic(call=sudo_call, keypair=alice)

    try:
        receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
        print(f"  Model added successfully")
        return True
    except SubstrateRequestException as e:
        print(f"  Error: {e}")
        return False


def update_worker_status(substrate: SubstrateInterface, worker: Keypair, online: bool) -> bool:
    """Update worker online status"""
    print(f"Setting worker {worker.ss58_address[:16]}... status to {'online' if online else 'offline'}...")

    call = substrate.compose_call(
        call_module='QxAi',
        call_function='update_ai_worker_status',
        call_params={'online': online}
    )

    extrinsic = substrate.create_signed_extrinsic(call=call, keypair=worker)

    try:
        receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
        print(f"  Status updated")
        return True
    except SubstrateRequestException as e:
        print(f"  Error: {e}")
        return False


def check_state(substrate: SubstrateInterface):
    """Check current bootstrap state"""
    print("\n" + "=" * 50)
    print("Current State")
    print("=" * 50)

    # Check governance DID
    gov_did = substrate.query(
        module='QxKiltPermissions',
        storage_function='GovernanceDID',
        params=[]
    )
    print(f"\nGovernance DID: {bytes(gov_did.value).hex()[:32] if gov_did.value else 'Not set'}...")

    # Check registered models
    print("\nRegistered Models:")
    for model_id in range(10):
        model = substrate.query(
            module='QxAi',
            storage_function='AllowedModels',
            params=[model_id]
        )
        if model.value:
            name = bytes(model.value['model_name']).decode('utf-8', errors='ignore')
            active = model.value['active']
            print(f"  [{model_id}] {name} (active={active})")

    # Check worker DIDs
    print("\nWorker DIDs:")
    for uri in WORKER_URIS:
        worker = Keypair.create_from_uri(uri)
        did_info = substrate.query(
            module='QxKiltPermissions',
            storage_function='AccountToDID',
            params=[worker.ss58_address]
        )
        if did_info.value:
            did_hex = bytes(did_info.value).hex()[:16]
            # Check credential
            cred = substrate.query(
                module='QxKiltPermissions',
                storage_function='WorkerCredentials',
                params=[list(did_info.value)]
            )
            has_cred = "with credential" if cred.value else "no credential"
            print(f"  {uri}: DID={did_hex}... ({has_cred})")
        else:
            print(f"  {uri}: No DID")


def bootstrap(substrate: SubstrateInterface, num_workers: int = 2) -> bool:
    """Run the full bootstrap process"""
    print("=" * 50)
    print("QXChain AI Worker Bootstrap")
    print("=" * 50)

    alice = Keypair.create_from_uri('//Alice')
    print(f"Alice (sudo): {alice.ss58_address}")
    print(f"Workers to set up: {num_workers}")
    print()

    # Step 1: Set governance DID
    print("\n[Step 1/4] Setting Governance DID")
    print("-" * 40)
    if not set_governance_did(substrate, alice):
        print("Warning: Could not set governance DID (may already be set)")

    # Step 2: Add allowed models
    print("\n[Step 2/4] Registering AI Models")
    print("-" * 40)
    for model in DEFAULT_MODELS:
        add_allowed_model(substrate, alice, model['id'], model['name'], model['hash'])

    # Step 3: Create worker DIDs
    print("\n[Step 3/4] Creating Worker DIDs")
    print("-" * 40)
    worker_dids = []
    all_model_ids = [m['id'] for m in DEFAULT_MODELS]

    for i, uri in enumerate(WORKER_URIS[:num_workers]):
        worker = Keypair.create_from_uri(uri)
        name = uri.replace('//', '')

        did = create_worker_did(substrate, worker, name)
        if did:
            worker_dids.append((worker, did))

    # Step 4: Issue credentials
    print("\n[Step 4/4] Issuing Worker Credentials")
    print("-" * 40)
    for worker, did in worker_dids:
        issue_worker_credential(substrate, alice, did, all_model_ids)
        time.sleep(0.5)  # Small delay between transactions
        update_worker_status(substrate, worker, online=True)

    print("\n" + "=" * 50)
    print("Bootstrap Complete!")
    print("=" * 50)

    return True


def main():
    parser = argparse.ArgumentParser(description='Bootstrap AI workers for QXChain')
    parser.add_argument('--url', type=str, default='ws://127.0.0.1:9944',
                        help='Substrate node WebSocket URL')
    parser.add_argument('--workers', type=int, default=2,
                        help='Number of workers to set up (1-4)')
    parser.add_argument('--check', action='store_true',
                        help='Only check current state, do not bootstrap')

    args = parser.parse_args()

    try:
        substrate = get_substrate(args.url)
        print(f"Connected to {args.url}")

        if args.check:
            check_state(substrate)
        else:
            bootstrap(substrate, min(args.workers, len(WORKER_URIS)))
            check_state(substrate)

        substrate.close()
        return 0

    except ConnectionRefusedError:
        print(f"Error: Could not connect to {args.url}")
        print("Make sure the chain is running")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
