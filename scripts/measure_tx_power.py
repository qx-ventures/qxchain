#!/usr/bin/env python3
"""
QXChain Transaction Power Measurement
======================================
Measures power consumption for processing a controlled number of transactions.

What this script does:
1. Injects N transactions as fast as possible
2. Waits for all transactions to be included in blocks
3. Measures total energy consumed
4. Reports exactly how many transactions went into each block

Output: Simple CSV with one row per test run
  tx_count, blocks_used, duration_s, energy_j, power_w, joules_per_tx, tx_per_second

Usage:
  python3 measure_tx_power.py                    # Default: 5 runs of 10,25,50,100 txs
  python3 measure_tx_power.py --tx-counts 50     # Single test with 50 txs
  python3 measure_tx_power.py --runs 3           # 3 runs for statistics

"""

import sys
import time
import argparse
import csv
from datetime import datetime
from pathlib import Path

try:
    from substrateinterface import SubstrateInterface, Keypair
except ImportError:
    print("Error: substrateinterface not installed")
    print("Run: pip install substrate-interface")
    sys.exit(1)

# RAPL paths
RAPL_PKG = "/sys/class/powercap/intel-rapl:0/energy_uj"

def read_energy():
    """Read CPU package energy in microjoules"""
    try:
        with open(RAPL_PKG) as f:
            return int(f.read().strip())
    except:
        return 0

def get_block_info(substrate, block_hash=None):
    """Get block number and extrinsic count"""
    block = substrate.get_block(block_hash)
    if not block:
        return 0, 0
    number = block['header']['number']
    extrinsics = len(block['extrinsics']) if 'extrinsics' in block else 0
    return number, extrinsics

def get_extrinsics_in_range(substrate, start_block, end_block):
    """Count all extrinsics in blocks from start to end (inclusive)"""
    total = 0
    block_details = []
    for block_num in range(start_block, end_block + 1):
        try:
            block_hash = substrate.get_block_hash(block_num)
            block = substrate.get_block(block_hash)
            ext_count = len(block['extrinsics']) if block and 'extrinsics' in block else 0
            # Subtract 1 for inherent (timestamp) if present
            user_exts = max(0, ext_count - 1)
            total += user_exts
            block_details.append(f"#{block_num}:{user_exts}")
        except:
            pass
    return total, block_details

def inject_transactions(substrate, alice, bob, count):
    """Inject transactions as fast as possible, return when done submitting"""
    alice_nonce = substrate.get_account_nonce(alice.ss58_address)
    bob_nonce = substrate.get_account_nonce(bob.ss58_address)

    for i in range(count):
        if i % 2 == 0:
            sender, recipient, nonce = alice, bob.ss58_address, alice_nonce
            alice_nonce += 1
        else:
            sender, recipient, nonce = bob, alice.ss58_address, bob_nonce
            bob_nonce += 1

        call = substrate.compose_call('Balances', 'transfer_keep_alive',
                                      {'dest': recipient, 'value': 1000000000000})
        ext = substrate.create_signed_extrinsic(call=call, keypair=sender, nonce=nonce)
        substrate.submit_extrinsic(ext, wait_for_inclusion=False)

        if (i + 1) % 25 == 0:
            print(f"    Submitted {i+1}/{count}", end='\r')

    print(f"    Submitted {count}/{count}   ")

def wait_for_pending_clear(substrate, timeout=120):
    """Wait for transaction pool to empty"""
    start = time.time()
    while time.time() - start < timeout:
        pending = substrate.rpc_request("author_pendingExtrinsics", [])
        if len(pending.get('result', [])) == 0:
            return True
        time.sleep(0.3)
    return False

def run_test(substrate, alice, bob, tx_count, run_num):
    """Run a single power measurement test"""
    print(f"\n  Run {run_num}: {tx_count} transactions")

    # Get start state
    start_block, _ = get_block_info(substrate)
    start_energy = read_energy()
    start_time = time.time()

    # Inject all transactions
    inject_transactions(substrate, alice, bob, tx_count)

    # Wait for all to be processed
    print("    Waiting for inclusion...")
    wait_for_pending_clear(substrate)

    # Get end state
    end_time = time.time()
    end_energy = read_energy()
    end_block, _ = get_block_info(substrate)

    # Wait 2 more blocks for finalization
    time.sleep(12)
    final_block, _ = get_block_info(substrate)

    # Calculate metrics
    duration = end_time - start_time
    energy_uj = end_energy - start_energy
    if energy_uj < 0:  # Handle RAPL overflow
        energy_uj += 2**32
    energy_j = energy_uj / 1_000_000
    power_w = energy_j / duration if duration > 0 else 0
    j_per_tx = energy_j / tx_count if tx_count > 0 else 0
    tps = tx_count / duration if duration > 0 else 0
    blocks_used = end_block - start_block

    # Count actual extrinsics in blocks
    actual_exts, block_details = get_extrinsics_in_range(substrate, start_block + 1, end_block)

    print(f"    Duration: {duration:.1f}s | Energy: {energy_j:.1f}J | Power: {power_w:.1f}W")
    print(f"    Blocks: {blocks_used} ({start_block}->{end_block}) | J/tx: {j_per_tx:.3f}")
    print(f"    Extrinsics per block: {', '.join(block_details)}")

    return {
        'run': run_num,
        'tx_count': tx_count,
        'blocks_used': blocks_used,
        'start_block': start_block,
        'end_block': end_block,
        'actual_extrinsics': actual_exts,
        'duration_s': round(duration, 2),
        'energy_j': round(energy_j, 2),
        'power_w': round(power_w, 2),
        'joules_per_tx': round(j_per_tx, 4),
        'tx_per_second': round(tps, 2),
        'block_details': '|'.join(block_details)
    }

def main():
    parser = argparse.ArgumentParser(description='Measure power for transaction processing')
    parser.add_argument('--tx-counts', type=str, default='10,25,50,100',
                        help='Transaction counts to test (comma-separated)')
    parser.add_argument('--runs', type=int, default=5, help='Number of runs per tx count')
    parser.add_argument('--url', type=str, default='ws://127.0.0.1:9944', help='Node URL')
    parser.add_argument('--output', type=str, help='Output directory')
    args = parser.parse_args()

    tx_counts = [int(x.strip()) for x in args.tx_counts.split(',')]

    # Setup output
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if args.output:
        out_dir = Path(args.output)
    else:
        out_dir = Path(f'/home/teo/qxchain/power_results/tx_power_{timestamp}')
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("QXChain Transaction Power Measurement")
    print("=" * 60)
    print(f"TX counts: {tx_counts}")
    print(f"Runs per count: {args.runs}")
    print(f"Output: {out_dir}")
    print()

    # Connect
    substrate = SubstrateInterface(url=args.url)
    alice = Keypair.create_from_uri('//Alice')
    bob = Keypair.create_from_uri('//Bob')

    current_block, _ = get_block_info(substrate)
    print(f"Connected. Current block: #{current_block}")

    results = []

    for tx_count in tx_counts:
        print(f"\n{'='*60}")
        print(f"Testing {tx_count} transactions ({args.runs} runs)")
        print('='*60)

        for run in range(1, args.runs + 1):
            result = run_test(substrate, alice, bob, tx_count, run)
            results.append(result)

            if run < args.runs:
                print("    Cooldown 5s...")
                time.sleep(5)

        if tx_count != tx_counts[-1]:
            print("\n  Cooldown 10s before next tx count...")
            time.sleep(10)

    # Save results
    csv_file = out_dir / 'results.csv'
    with open(csv_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    # Print summary
    print("\n" + "=" * 60)
    print("=" * 60)
    print(f"\n{'TX Count':<10} {'Runs':<6} {'Avg Power (W)':<15} {'Avg J/tx':<12} {'Avg TPS':<10}")
    print("-" * 55)

    import statistics
    summary_rows = []
    for tc in tx_counts:
        runs = [r for r in results if r['tx_count'] == tc]
        power_avg = statistics.mean([r['power_w'] for r in runs])
        power_std = statistics.stdev([r['power_w'] for r in runs]) if len(runs) > 1 else 0
        jptx_avg = statistics.mean([r['joules_per_tx'] for r in runs])
        jptx_std = statistics.stdev([r['joules_per_tx'] for r in runs]) if len(runs) > 1 else 0
        tps_avg = statistics.mean([r['tx_per_second'] for r in runs])

        print(f"{tc:<10} {len(runs):<6} {power_avg:.1f} +/- {power_std:.1f}    {jptx_avg:.3f} +/- {jptx_std:.3f}  {tps_avg:.1f}")

        summary_rows.append({
            'tx_count': tc,
            'runs': len(runs),
            'power_mean': round(power_avg, 2),
            'power_std': round(power_std, 2),
            'joules_per_tx_mean': round(jptx_avg, 4),
            'joules_per_tx_std': round(jptx_std, 4),
            'tps_mean': round(tps_avg, 2)
        })

    # Save summary
    summary_file = out_dir / 'summary.csv'
    with open(summary_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\nResults saved to: {out_dir}")
    print(f"  - results.csv  : All individual runs")
    print(f"  - summary.csv  : Statistics per tx count")

    return 0

if __name__ == '__main__':
    sys.exit(main())
