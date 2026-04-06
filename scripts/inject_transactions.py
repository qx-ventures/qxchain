#!/usr/bin/env python3
"""Inject balance transfer transactions for power measurement testing"""

import sys
import time
import argparse
from substrateinterface import SubstrateInterface, Keypair

def main():
    parser = argparse.ArgumentParser(description='Inject transactions into QXChain')
    parser.add_argument('--count', type=int, default=10, help='Number of transactions to send')
    parser.add_argument('--delay', type=float, default=0.1, help='Delay between transactions (seconds)')
    parser.add_argument('--url', type=str, default='ws://127.0.0.1:9944', help='Node WebSocket URL')
    parser.add_argument('--amount', type=int, default=1000000000000, help='Amount to transfer (in smallest unit)')
    parser.add_argument('--wait', action='store_true', help='Wait for each tx to be included in block')
    args = parser.parse_args()

    print(f"Connecting to {args.url}...")
    substrate = SubstrateInterface(url=args.url)

    # Alice's seed (dev account)
    alice = Keypair.create_from_uri('//Alice')
    bob = Keypair.create_from_uri('//Bob')

    print(f"Alice: {alice.ss58_address}")
    print(f"Bob: {bob.ss58_address}")
    print(f"Sending {args.count} transfers of {args.amount} units...")
    print()

    successful = 0
    failed = 0

    # Track nonces manually to avoid conflicts
    alice_nonce = substrate.get_account_nonce(alice.ss58_address)
    bob_nonce = substrate.get_account_nonce(bob.ss58_address)

    for i in range(args.count):
        try:
            # Alternate between Alice->Bob and Bob->Alice
            if i % 2 == 0:
                sender, recipient = alice, bob.ss58_address
                sender_name = "Alice"
                nonce = alice_nonce
                alice_nonce += 1
            else:
                sender, recipient = bob, alice.ss58_address
                sender_name = "Bob"
                nonce = bob_nonce
                bob_nonce += 1

            call = substrate.compose_call(
                call_module='Balances',
                call_function='transfer_keep_alive',
                call_params={
                    'dest': recipient,
                    'value': args.amount
                }
            )

            extrinsic = substrate.create_signed_extrinsic(
                call=call,
                keypair=sender,
                nonce=nonce
            )

            receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=args.wait)

            print(f"[{i+1}/{args.count}] {sender_name} -> {recipient[:8]}... hash: {receipt.extrinsic_hash}")
            successful += 1

        except Exception as e:
            print(f"[{i+1}/{args.count}] FAILED: {e}")
            failed += 1

        if args.delay > 0 and i < args.count - 1:
            time.sleep(args.delay)

    print()
    print(f"Done! Successful: {successful}, Failed: {failed}")
    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
