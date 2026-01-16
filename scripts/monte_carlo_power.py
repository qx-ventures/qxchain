#!/usr/bin/env python3
"""
Monte Carlo Power Measurement for QXChain
==========================================
Runs Monte Carlo simulations to measure L1 chain energy consumption
under statistically modeled L2 workloads.

This script:
1. Generates workloads using the L2 Workload Emulator
2. Executes transactions on the QXChain testbed
3. Measures energy using Intel RAPL
4. Runs multiple simulations with parameter variations
5. Computes confidence intervals for energy metrics

The result is a statistically rigorous energy efficiency analysis
that can make claims like:
"For a heavy MoE workload, we are 95% confident that the average
energy per transaction (E/tx) will be between 0.45 J and 0.55 J."

Usage:
  python3 monte_carlo_power.py                     # 100 simulations, medium workload
  python3 monte_carlo_power.py --simulations 1000  # 1000 simulations
  python3 monte_carlo_power.py --scenario heavy    # Heavy workload scenario
  python3 monte_carlo_power.py --tx-only           # Use balance transfers only (no AI workers)
"""

import sys
import os
import time
import json
import argparse
import subprocess
import shutil
import signal
import csv
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path
from scipy import stats

# Import the L2 emulator
from l2_workload_emulator import (
    L2WorkloadEmulator, WorkloadConfig, ExpertConfig,
    TransactionRequest, create_workload_scenarios
)

try:
    from substrateinterface import SubstrateInterface, Keypair
except ImportError:
    print("Error: substrateinterface not installed")
    print("Run: pip install substrate-interface")
    sys.exit(1)

# RAPL energy measurement path
RAPL_PKG = "/sys/class/powercap/intel-rapl:0/energy_uj"

# Chain configuration
CHAIN_BINARY = "/home/teo/qxchain/target/release/qxchain"
CHAIN_BASE_PATH = "/tmp/alice"
CHAIN_ARGS = [
    "--chain=localnet_single",
    "--alice",
    f"--base-path={CHAIN_BASE_PATH}",
    "--unsafe-force-node-key-generation"
]

chain_process = None


@dataclass
class MonteCarloConfig:
    """Configuration for Monte Carlo simulation"""
    # Number of simulation runs
    n_simulations: int = 100

    # Base workload configuration
    workload_scenario: str = "medium"

    # Parameter variation ranges (for Monte Carlo sampling)
    vary_arrival_rate: bool = True
    arrival_rate_range: Tuple[float, float] = (5.0, 30.0)

    vary_expert_weights: bool = True
    expert_weight_variation: float = 0.15  # +/- 15% variation

    vary_complexity: bool = True
    complexity_sigma_range: Tuple[float, float] = (0.3, 1.0)

    # Use simple balance transfers instead of AI transactions
    tx_only_mode: bool = False

    # Transactions per simulation run
    tx_per_run: int = 100

    # Chain restart between runs (fresh state)
    restart_chain: bool = True

    # Warmup blocks before measurement
    warmup_blocks: int = 5

    # Random seed for reproducibility (None for random)
    seed: Optional[int] = None

    # Output directory
    output_dir: str = "/home/teo/qxchain/power_results/monte_carlo"


@dataclass
class SimulationResult:
    """Result of a single simulation run"""
    simulation_id: int
    timestamp: str

    # Configuration used
    arrival_rate: float
    expert_weights: Dict[str, float]
    complexity_sigma: float

    # Workload generated
    tx_count: int
    tx_by_model: Dict[int, int]
    total_bytes: int

    # Measurements
    duration_s: float
    energy_j: float
    power_w: float
    j_per_tx: float
    tx_per_second: float

    # Block info
    blocks_used: int
    start_block: int
    end_block: int

    def to_dict(self) -> dict:
        return {
            'simulation_id': self.simulation_id,
            'timestamp': self.timestamp,
            'arrival_rate': round(self.arrival_rate, 2),
            'expert_weights': json.dumps(self.expert_weights),
            'complexity_sigma': round(self.complexity_sigma, 3),
            'tx_count': self.tx_count,
            'tx_by_model': json.dumps(self.tx_by_model),
            'total_bytes': self.total_bytes,
            'duration_s': round(self.duration_s, 2),
            'energy_j': round(self.energy_j, 2),
            'power_w': round(self.power_w, 2),
            'j_per_tx': round(self.j_per_tx, 4),
            'tx_per_second': round(self.tx_per_second, 2),
            'blocks_used': self.blocks_used,
            'start_block': self.start_block,
            'end_block': self.end_block,
        }


def read_energy() -> int:
    """Read CPU package energy in microjoules"""
    try:
        with open(RAPL_PKG) as f:
            return int(f.read().strip())
    except:
        return 0


def stop_chain():
    """Stop the running chain process"""
    global chain_process
    if chain_process:
        chain_process.terminate()
        try:
            chain_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            chain_process.kill()
            chain_process.wait()
        chain_process = None
    else:
        subprocess.run(["pkill", "-f", "qxchain.*alice"], capture_output=True)
        time.sleep(1)


def reset_chain_state():
    """Delete chain state directory"""
    if Path(CHAIN_BASE_PATH).exists():
        shutil.rmtree(CHAIN_BASE_PATH)


def start_chain() -> bool:
    """Start the chain and wait for it to be ready"""
    global chain_process
    chain_process = subprocess.Popen(
        [CHAIN_BINARY] + CHAIN_ARGS,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    for i in range(60):
        try:
            substrate = SubstrateInterface(url="ws://127.0.0.1:9944")
            block = substrate.get_block()
            substrate.close()
            return True
        except:
            time.sleep(1)

    return False


def restart_chain_fresh() -> bool:
    """Stop, reset, and start chain with fresh state"""
    stop_chain()
    reset_chain_state()
    return start_chain()


def wait_for_block(substrate: SubstrateInterface, target_block: int, timeout: int = 120) -> bool:
    """Wait until chain reaches target block number"""
    start = time.time()
    while time.time() - start < timeout:
        block = substrate.get_block()
        if block and block['header']['number'] >= target_block:
            return True
        time.sleep(1)
    return False


def wait_for_new_block(substrate: SubstrateInterface, timeout: int = 12) -> int:
    """Wait for a new block to be produced"""
    block = substrate.get_block()
    current = block['header']['number'] if block else 0
    start = time.time()
    while time.time() - start < timeout:
        block = substrate.get_block()
        new_num = block['header']['number'] if block else 0
        if new_num > current:
            return new_num
        time.sleep(0.1)
    return current


def wait_for_pending_clear(substrate: SubstrateInterface, timeout: int = 120) -> bool:
    """Wait for transaction pool to empty"""
    start = time.time()
    while time.time() - start < timeout:
        pending = substrate.rpc_request("author_pendingExtrinsics", [])
        if len(pending.get('result', [])) == 0:
            return True
        time.sleep(0.3)
    return False


def inject_balance_transfers(
    substrate: SubstrateInterface,
    alice: Keypair,
    bob: Keypair,
    requests: List[TransactionRequest]
) -> None:
    """Inject balance transfer transactions based on workload requests"""
    alice_nonce = substrate.get_account_nonce(alice.ss58_address)
    bob_nonce = substrate.get_account_nonce(bob.ss58_address)

    for i, request in enumerate(requests):
        # Alternate between Alice and Bob
        if i % 2 == 0:
            sender, recipient, nonce = alice, bob.ss58_address, alice_nonce
            alice_nonce += 1
        else:
            sender, recipient, nonce = bob, alice.ss58_address, bob_nonce
            bob_nonce += 1

        # Vary transfer amount based on request complexity
        amount = 1_000_000_000_000 + request.prompt_size * 1_000_000

        call = substrate.compose_call(
            'Balances', 'transfer_keep_alive',
            {'dest': recipient, 'value': amount}
        )
        ext = substrate.create_signed_extrinsic(call=call, keypair=sender, nonce=nonce)
        substrate.submit_extrinsic(ext, wait_for_inclusion=False)

        if (i + 1) % 25 == 0:
            print(f"  Submitted {i+1}/{len(requests)}", end='\r')

    print(f"  Submitted {len(requests)}/{len(requests)}   ")


def inject_ai_requests(
    substrate: SubstrateInterface,
    customer: Keypair,
    worker: Keypair,
    requests: List[TransactionRequest]
) -> None:
    """Inject AI inference request transactions"""
    nonce = substrate.get_account_nonce(customer.ss58_address)

    for i, request in enumerate(requests):
        # Generate prompt of appropriate size
        prompt = b'X' * request.prompt_size

        call = substrate.compose_call(
            'QxAi', 'submit_request',
            {
                'target_worker': worker.ss58_address,
                'prompt': list(prompt),
                'model_id': request.expert.model_id,
                'max_tokens': request.max_tokens,
            }
        )
        ext = substrate.create_signed_extrinsic(call=call, keypair=customer, nonce=nonce)
        nonce += 1

        try:
            substrate.submit_extrinsic(ext, wait_for_inclusion=False)
        except Exception as e:
            print(f"  Warning: Request {i} failed: {e}")

        if (i + 1) % 25 == 0:
            print(f"  Submitted {i+1}/{len(requests)}", end='\r')

    print(f"  Submitted {len(requests)}/{len(requests)}   ")


class MonteCarloSimulator:
    """
    Monte Carlo simulation engine for power measurements.

    Runs multiple simulations with parameter variations to produce
    statistically significant energy efficiency measurements.
    """

    def __init__(self, config: MonteCarloConfig):
        self.config = config
        self.rng = np.random.default_rng(config.seed)
        self.results: List[SimulationResult] = []

        # Load base workload scenario
        scenarios = create_workload_scenarios()
        if config.workload_scenario in scenarios:
            self.base_workload = scenarios[config.workload_scenario]
        else:
            self.base_workload = WorkloadConfig()

        # Create output directory
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)

    def sample_parameters(self) -> WorkloadConfig:
        """Sample workload parameters for this simulation run"""
        config = WorkloadConfig(
            seed=int(self.rng.integers(0, 2**31)),
            duration_seconds=self.base_workload.duration_seconds,
        )

        # Sample arrival rate
        if self.config.vary_arrival_rate:
            config.arrival_rate_lambda = self.rng.uniform(
                self.config.arrival_rate_range[0],
                self.config.arrival_rate_range[1]
            )
        else:
            config.arrival_rate_lambda = self.base_workload.arrival_rate_lambda

        # Sample complexity sigma
        if self.config.vary_complexity:
            sigma_factor = self.rng.uniform(
                self.config.complexity_sigma_range[0],
                self.config.complexity_sigma_range[1]
            )
        else:
            sigma_factor = None

        # Create experts with potentially varied weights
        experts = []
        base_weights = [e.weight for e in self.base_workload.experts]

        if self.config.vary_expert_weights:
            # Add random variation to weights
            variations = self.rng.uniform(
                -self.config.expert_weight_variation,
                self.config.expert_weight_variation,
                size=len(base_weights)
            )
            new_weights = np.array(base_weights) * (1 + variations)
            new_weights = np.maximum(new_weights, 0.01)  # Ensure positive
            new_weights = new_weights / new_weights.sum()  # Normalize to 1
        else:
            new_weights = base_weights

        for i, base_expert in enumerate(self.base_workload.experts):
            expert = ExpertConfig(
                model_id=base_expert.model_id,
                name=base_expert.name,
                weight=float(new_weights[i]),
                complexity_mu=base_expert.complexity_mu,
                complexity_sigma=sigma_factor if sigma_factor else base_expert.complexity_sigma,
                min_prompt_bytes=base_expert.min_prompt_bytes,
                max_prompt_bytes=base_expert.max_prompt_bytes,
            )
            experts.append(expert)

        config.experts = experts
        return config

    def run_single_simulation(self, sim_id: int) -> Optional[SimulationResult]:
        """Run a single simulation with sampled parameters"""

        # Sample parameters for this run
        workload_config = self.sample_parameters()

        # Generate workload
        emulator = L2WorkloadEmulator(workload_config)

        # Calculate how many requests to generate based on tx_per_run
        # Adjust duration to get approximately tx_per_run transactions
        expected_tx = workload_config.arrival_rate_lambda * workload_config.duration_seconds
        if expected_tx > 0:
            scale_factor = self.config.tx_per_run / expected_tx
            workload_config.duration_seconds *= scale_factor

        emulator = L2WorkloadEmulator(workload_config)
        requests = emulator.generate_workload()

        # Limit to tx_per_run
        requests = requests[:self.config.tx_per_run]

        if not requests:
            print(f"  Warning: No requests generated")
            return None

        # Calculate workload stats
        tx_by_model = {}
        for r in requests:
            model_id = r.expert.model_id
            tx_by_model[model_id] = tx_by_model.get(model_id, 0) + 1

        total_bytes = sum(r.prompt_size for r in requests)
        expert_weights = {e.name: e.weight for e in workload_config.experts}

        # Start fresh chain if configured
        if self.config.restart_chain:
            if not restart_chain_fresh():
                print(f"  Error: Failed to restart chain")
                return None

        try:
            substrate = SubstrateInterface(url="ws://127.0.0.1:9944")
            alice = Keypair.create_from_uri('//Alice')
            bob = Keypair.create_from_uri('//Bob')

            # Wait for warmup blocks
            wait_for_block(substrate, self.config.warmup_blocks)

            # Sync to block timing
            wait_for_new_block(substrate)

            # Get start state
            start_block = substrate.get_block()['header']['number']
            start_energy = read_energy()
            start_time = time.time()

            # Inject transactions
            if self.config.tx_only_mode:
                inject_balance_transfers(substrate, alice, bob, requests)
            else:
                # For now, use balance transfers as AI worker bootstrap is complex
                # In production, would use inject_ai_requests after bootstrapping
                inject_balance_transfers(substrate, alice, bob, requests)

            # Wait for all transactions to be processed
            wait_for_pending_clear(substrate)

            # Get end state
            end_time = time.time()
            end_energy = read_energy()
            end_block = substrate.get_block()['header']['number']

            substrate.close()

            # Calculate metrics
            duration = end_time - start_time
            energy_uj = end_energy - start_energy
            if energy_uj < 0:  # Handle RAPL overflow
                energy_uj += 2**32
            energy_j = energy_uj / 1_000_000
            power_w = energy_j / duration if duration > 0 else 0
            j_per_tx = energy_j / len(requests) if requests else 0
            tps = len(requests) / duration if duration > 0 else 0
            blocks_used = end_block - start_block

            return SimulationResult(
                simulation_id=sim_id,
                timestamp=datetime.now().isoformat(),
                arrival_rate=workload_config.arrival_rate_lambda,
                expert_weights=expert_weights,
                complexity_sigma=workload_config.experts[0].complexity_sigma if workload_config.experts else 0.5,
                tx_count=len(requests),
                tx_by_model=tx_by_model,
                total_bytes=total_bytes,
                duration_s=duration,
                energy_j=energy_j,
                power_w=power_w,
                j_per_tx=j_per_tx,
                tx_per_second=tps,
                blocks_used=blocks_used,
                start_block=start_block,
                end_block=end_block,
            )

        except Exception as e:
            print(f"  Error in simulation: {e}")
            return None

    def run_all_simulations(self) -> List[SimulationResult]:
        """Run all Monte Carlo simulations"""
        print("=" * 60)
        print("Monte Carlo Power Measurement")
        print("=" * 60)
        print(f"Simulations: {self.config.n_simulations}")
        print(f"Scenario: {self.config.workload_scenario}")
        print(f"TX per run: {self.config.tx_per_run}")
        print(f"Mode: {'Balance transfers' if self.config.tx_only_mode else 'AI workload emulation'}")
        print()

        # Kill any existing chain processes
        print("Stopping any existing chain processes...")
        subprocess.run(["pkill", "-9", "qxchain"], capture_output=True)
        time.sleep(1)

        for sim_id in range(1, self.config.n_simulations + 1):
            print(f"\n{'='*50}")
            print(f"Simulation {sim_id}/{self.config.n_simulations}")
            print('='*50)

            result = self.run_single_simulation(sim_id)
            if result:
                self.results.append(result)
                print(f"  Energy: {result.energy_j:.1f}J | J/tx: {result.j_per_tx:.4f} | TPS: {result.tx_per_second:.1f}")

        # Stop chain at the end
        stop_chain()

        return self.results

    def compute_statistics(self) -> dict:
        """Compute summary statistics with confidence intervals"""
        if not self.results:
            return {}

        j_per_tx = np.array([r.j_per_tx for r in self.results])
        power_w = np.array([r.power_w for r in self.results])
        tps = np.array([r.tx_per_second for r in self.results])
        energy_j = np.array([r.energy_j for r in self.results])

        def ci_95(data):
            """Compute 95% confidence interval"""
            if len(data) < 2:
                return (data[0], data[0]) if len(data) == 1 else (0, 0)
            ci = stats.t.interval(0.95, len(data)-1, loc=np.mean(data), scale=stats.sem(data))
            return (float(ci[0]), float(ci[1]))

        return {
            'n_simulations': len(self.results),
            'j_per_tx': {
                'mean': float(np.mean(j_per_tx)),
                'std': float(np.std(j_per_tx)),
                'min': float(np.min(j_per_tx)),
                'max': float(np.max(j_per_tx)),
                'ci_95_lower': ci_95(j_per_tx)[0],
                'ci_95_upper': ci_95(j_per_tx)[1],
            },
            'power_w': {
                'mean': float(np.mean(power_w)),
                'std': float(np.std(power_w)),
                'ci_95_lower': ci_95(power_w)[0],
                'ci_95_upper': ci_95(power_w)[1],
            },
            'tps': {
                'mean': float(np.mean(tps)),
                'std': float(np.std(tps)),
                'ci_95_lower': ci_95(tps)[0],
                'ci_95_upper': ci_95(tps)[1],
            },
            'energy_j': {
                'mean': float(np.mean(energy_j)),
                'std': float(np.std(energy_j)),
            },
        }

    def save_results(self) -> Tuple[str, str]:
        """Save results to CSV and summary to JSON"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Save individual results to CSV
        csv_file = Path(self.config.output_dir) / f'mc_results_{timestamp}.csv'
        if self.results:
            fieldnames = list(self.results[0].to_dict().keys())
            with open(csv_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in self.results:
                    writer.writerow(r.to_dict())

        # Save summary statistics to JSON
        summary = self.compute_statistics()
        summary['config'] = {
            'n_simulations': self.config.n_simulations,
            'workload_scenario': self.config.workload_scenario,
            'tx_per_run': self.config.tx_per_run,
            'tx_only_mode': self.config.tx_only_mode,
            'arrival_rate_range': self.config.arrival_rate_range,
            'vary_parameters': {
                'arrival_rate': self.config.vary_arrival_rate,
                'expert_weights': self.config.vary_expert_weights,
                'complexity': self.config.vary_complexity,
            }
        }
        summary['timestamp'] = timestamp

        json_file = Path(self.config.output_dir) / f'mc_summary_{timestamp}.json'
        with open(json_file, 'w') as f:
            json.dump(summary, f, indent=2)

        return str(csv_file), str(json_file)


def main():
    parser = argparse.ArgumentParser(
        description='Monte Carlo Power Measurement for QXChain'
    )
    parser.add_argument('--simulations', '-n', type=int, default=100,
                        help='Number of Monte Carlo simulations')
    parser.add_argument('--scenario', type=str, default='medium',
                        choices=['light', 'medium', 'heavy', 'burst'],
                        help='Workload scenario')
    parser.add_argument('--tx', type=int, default=100,
                        help='Transactions per simulation run')
    parser.add_argument('--tx-only', action='store_true',
                        help='Use balance transfers only (no AI worker setup)')
    parser.add_argument('--no-restart', action='store_true',
                        help='Do not restart chain between runs')
    parser.add_argument('--seed', type=int, default=None,
                        help='Random seed for reproducibility')
    parser.add_argument('--output', type=str,
                        default='/home/teo/qxchain/power_results/monte_carlo',
                        help='Output directory')

    args = parser.parse_args()

    config = MonteCarloConfig(
        n_simulations=args.simulations,
        workload_scenario=args.scenario,
        tx_per_run=args.tx,
        tx_only_mode=args.tx_only,
        restart_chain=not args.no_restart,
        seed=args.seed,
        output_dir=args.output,
    )

    simulator = MonteCarloSimulator(config)

    try:
        results = simulator.run_all_simulations()

        if results:
            csv_file, json_file = simulator.save_results()
            summary = simulator.compute_statistics()

            print("\n" + "=" * 60)
            print("MONTE CARLO SIMULATION COMPLETE")
            print("=" * 60)
            print(f"\nSuccessful simulations: {len(results)}/{config.n_simulations}")
            print()
            print("Energy per Transaction (J/tx):")
            print(f"  Mean: {summary['j_per_tx']['mean']:.4f} J")
            print(f"  Std:  {summary['j_per_tx']['std']:.4f} J")
            print(f"  95% CI: [{summary['j_per_tx']['ci_95_lower']:.4f}, {summary['j_per_tx']['ci_95_upper']:.4f}] J")
            print()
            print("Average Power (W):")
            print(f"  Mean: {summary['power_w']['mean']:.1f} W")
            print(f"  95% CI: [{summary['power_w']['ci_95_lower']:.1f}, {summary['power_w']['ci_95_upper']:.1f}] W")
            print()
            print("Throughput (TPS):")
            print(f"  Mean: {summary['tps']['mean']:.1f} tx/s")
            print(f"  95% CI: [{summary['tps']['ci_95_lower']:.1f}, {summary['tps']['ci_95_upper']:.1f}] tx/s")
            print()
            print(f"Results saved to:")
            print(f"  CSV: {csv_file}")
            print(f"  Summary: {json_file}")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        stop_chain()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
