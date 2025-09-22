#!/usr/bin/env python3
"""
Script to check account balance and worker registration status
"""

import sys
from substrateinterface import SubstrateInterface, Keypair

def check_account(seed="//Bob"):
    try:
        # Connect to chain
        substrate = SubstrateInterface(url="ws://localhost:9944")
        keypair = Keypair.create_from_uri(seed)
        
        print(f"Checking account: {keypair.ss58_address}")
        print(f"Seed: {seed}")
        
        # Check account balance
        try:
            account_info = substrate.query('System', 'Account', [keypair.ss58_address])
            if account_info:
                free_balance = account_info['data']['free'].value
                reserved_balance = account_info['data']['reserved'].value
                frozen_balance = account_info['data']['frozen'].value
                
                print(f"Free balance: {free_balance}")
                print(f"Reserved balance: {reserved_balance}")
                print(f"Frozen balance: {frozen_balance}")
                print(f"Total balance: {free_balance + reserved_balance}")
            else:
                print("Account not found on chain")
        except Exception as e:
            print(f"Error getting account balance: {e}")
        
        # Check if already registered as worker
        try:
            worker_info = substrate.query('QxAi', 'Workers', [keypair.ss58_address])
            if worker_info:
                print(f"Worker registered with stake: {worker_info.value}")
            else:
                print("Not registered as worker")
        except Exception as e:
            print(f"Error checking worker status: {e}")
        
        # Check if already registered as validator  
        try:
            validator_info = substrate.query('QxAi', 'Validators', [keypair.ss58_address])
            if validator_info:
                print(f"Validator registered with stake: {validator_info.value}")
            else:
                print("Not registered as validator")
        except Exception as e:
            print(f"Error checking validator status: {e}")
            
    except Exception as e:
        print(f"Error connecting to chain: {e}")

if __name__ == "__main__":
    seed = sys.argv[1] if len(sys.argv) > 1 else "//Bob"
    check_account(seed)
