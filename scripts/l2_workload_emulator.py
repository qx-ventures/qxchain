#!/usr/bin/env python3
"""
L2 Workload Emulator for QXChain
================================
Generates statistically realistic transaction patterns that emulate
a Mixture of Experts (MoE) router behavior using Monte Carlo methods.

Statistical Models:
- Request Arrival Rate: Poisson Process
- Expert Selection: Categorical Distribution (weighted model selection)
- Request Complexity: Log-Normal Distribution (prompt/payload sizes)

This allows rigorous energy efficiency testing of the L1 chain under
realistic L2 workloads without implementing actual router logic.

Usage:
  python3 l2_workload_emulator.py                    # Generate sample workload
  python3 l2_workload_emulator.py --duration 30      # 30 second workload
  python3 l2_workload_emulator.py --arrival-rate 20  # 20 requests/sec average

"""

import sys
import json
import argparse
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# Ensure reproducibility when needed
DEFAULT_SEED = None  # Set to integer for reproducible runs


@dataclass
class ExpertConfig:
    """Configuration for a single expert (AI model)"""
    model_id: int
    name: str
    weight: float  # Selection probability (0-1)
    complexity_mu: float  # Log-normal mean for prompt size
    complexity_sigma: float  # Log-normal std dev
    min_prompt_bytes: int = 50
    max_prompt_bytes: int = 2048


@dataclass
class WorkloadConfig:
    """Configuration for L2 workload generation"""
    # Arrival rate (Poisson process parameter)
    arrival_rate_lambda: float = 10.0  # Average requests per second

    # Simulation duration
    duration_seconds: float = 60.0

    # Expert configurations with default MoE setup
    experts: List[ExpertConfig] = field(default_factory=lambda: [
        ExpertConfig(
            model_id=0,
            name="Fast-Inference",
            weight=0.50,  # 50% of requests
            complexity_mu=5.0,  # ~148 bytes median
            complexity_sigma=0.5,
            min_prompt_bytes=50,
            max_prompt_bytes=256
        ),
        ExpertConfig(
            model_id=1,
            name="Standard-Inference",
            weight=0.30,  # 30% of requests
            complexity_mu=6.0,  # ~403 bytes median
            complexity_sigma=0.6,
            min_prompt_bytes=128,
            max_prompt_bytes=1024
        ),
        ExpertConfig(
            model_id=2,
            name="Complex-Inference",
            weight=0.15,  # 15% of requests
            complexity_mu=6.8,  # ~898 bytes median
            complexity_sigma=0.7,
            min_prompt_bytes=512,
            max_prompt_bytes=2048
        ),
        ExpertConfig(
            model_id=3,
            name="Ensemble-Inference",
            weight=0.05,  # 5% of requests
            complexity_mu=7.2,  # ~1339 bytes median
            complexity_sigma=0.4,
            min_prompt_bytes=1024,
            max_prompt_bytes=2048
        ),
    ])

    # Random seed for reproducibility (None for random)
    seed: Optional[int] = None

    def validate(self):
        """Validate configuration"""
        weights = [e.weight for e in self.experts]
        if abs(sum(weights) - 1.0) > 0.01:
            raise ValueError(f"Expert weights must sum to 1.0, got {sum(weights)}")
        if self.arrival_rate_lambda <= 0:
            raise ValueError("Arrival rate must be positive")
        if self.duration_seconds <= 0:
            raise ValueError("Duration must be positive")


@dataclass
class TransactionRequest:
    """A single emulated transaction request"""
    request_id: int
    arrival_time: float  # Seconds from simulation start
    expert: ExpertConfig
    prompt_size: int  # Bytes
    max_tokens: int = 256

    def to_dict(self) -> dict:
        return {
            'request_id': self.request_id,
            'arrival_time': round(self.arrival_time, 4),
            'model_id': self.expert.model_id,
            'model_name': self.expert.name,
            'prompt_size': self.prompt_size,
            'max_tokens': self.max_tokens,
        }


class L2WorkloadEmulator:
    """
    Generates statistically realistic L2 workloads using Monte Carlo methods.

    The emulator produces transaction request patterns that are statistically
    identical to what a real MoE router would generate, allowing energy
    measurements of the L1 chain under various L2 workload conditions.
    """

    def __init__(self, config: WorkloadConfig):
        self.config = config
        config.validate()

        # Initialize random generator
        self.rng = np.random.default_rng(config.seed)

        # Pre-compute expert selection probabilities
        self.expert_weights = np.array([e.weight for e in config.experts])
        self.expert_indices = np.arange(len(config.experts))

    def generate_arrival_times(self) -> np.ndarray:
        """
        Generate request arrival times using a Poisson process.

        In a Poisson process, inter-arrival times follow an exponential
        distribution with rate parameter lambda.
        """
        # Expected number of arrivals
        expected_count = int(self.config.arrival_rate_lambda * self.config.duration_seconds)

        # Generate more than needed, then truncate
        n_samples = int(expected_count * 1.5) + 100

        # Inter-arrival times ~ Exponential(lambda)
        inter_arrivals = self.rng.exponential(
            scale=1.0 / self.config.arrival_rate_lambda,
            size=n_samples
        )

        # Cumulative sum gives arrival times
        arrival_times = np.cumsum(inter_arrivals)

        # Keep only arrivals within duration
        arrival_times = arrival_times[arrival_times <= self.config.duration_seconds]

        return arrival_times

    def select_expert(self) -> ExpertConfig:
        """
        Select an expert using categorical distribution with configured weights.
        """
        idx = self.rng.choice(self.expert_indices, p=self.expert_weights)
        return self.config.experts[idx]

    def generate_complexity(self, expert: ExpertConfig) -> int:
        """
        Generate request complexity (prompt size) using log-normal distribution.

        Log-normal is appropriate for non-negative, right-skewed values like
        text lengths, where most requests are small but some are large.
        """
        # Generate log-normal value
        raw_size = self.rng.lognormal(
            mean=expert.complexity_mu,
            sigma=expert.complexity_sigma
        )

        # Clamp to expert's valid range
        size = int(np.clip(raw_size, expert.min_prompt_bytes, expert.max_prompt_bytes))

        return size

    def generate_workload(self) -> List[TransactionRequest]:
        """
        Generate a complete workload of transaction requests.

        Returns a list of TransactionRequest objects with arrival times,
        expert assignments, and prompt sizes.
        """
        arrival_times = self.generate_arrival_times()
        requests = []

        for i, arrival_time in enumerate(arrival_times):
            expert = self.select_expert()
            prompt_size = self.generate_complexity(expert)

            request = TransactionRequest(
                request_id=i,
                arrival_time=arrival_time,
                expert=expert,
                prompt_size=prompt_size,
            )
            requests.append(request)

        return requests

    def get_workload_statistics(self, requests: List[TransactionRequest]) -> dict:
        """
        Compute statistics for a generated workload.
        """
        if not requests:
            return {'error': 'No requests generated'}

        # Overall stats
        total_requests = len(requests)
        total_bytes = sum(r.prompt_size for r in requests)
        duration = requests[-1].arrival_time if requests else 0

        # Per-expert breakdown
        expert_counts = {}
        expert_bytes = {}
        for expert in self.config.experts:
            expert_requests = [r for r in requests if r.expert.model_id == expert.model_id]
            expert_counts[expert.name] = len(expert_requests)
            expert_bytes[expert.name] = sum(r.prompt_size for r in expert_requests)

        # Arrival rate analysis
        if len(requests) > 1:
            inter_arrivals = np.diff([r.arrival_time for r in requests])
            measured_rate = 1.0 / np.mean(inter_arrivals) if len(inter_arrivals) > 0 else 0
        else:
            measured_rate = 0

        return {
            'total_requests': total_requests,
            'total_bytes': total_bytes,
            'duration_seconds': round(duration, 2),
            'configured_arrival_rate': self.config.arrival_rate_lambda,
            'measured_arrival_rate': round(measured_rate, 2),
            'avg_prompt_size': round(total_bytes / total_requests, 1),
            'requests_per_expert': expert_counts,
            'bytes_per_expert': expert_bytes,
        }


def create_workload_scenarios() -> Dict[str, WorkloadConfig]:
    """
    Create predefined workload scenarios for testing.
    """
    scenarios = {}

    # Light workload - mostly fast inference
    scenarios['light'] = WorkloadConfig(
        arrival_rate_lambda=5.0,
        duration_seconds=60.0,
        experts=[
            ExpertConfig(0, "Fast", 0.70, 5.0, 0.4, 50, 256),
            ExpertConfig(1, "Standard", 0.25, 5.8, 0.5, 128, 512),
            ExpertConfig(2, "Complex", 0.05, 6.5, 0.6, 256, 1024),
        ]
    )

    # Medium workload - balanced
    scenarios['medium'] = WorkloadConfig(
        arrival_rate_lambda=15.0,
        duration_seconds=60.0,
        experts=[
            ExpertConfig(0, "Fast", 0.50, 5.2, 0.5, 50, 256),
            ExpertConfig(1, "Standard", 0.30, 6.0, 0.6, 128, 1024),
            ExpertConfig(2, "Complex", 0.15, 6.8, 0.7, 512, 2048),
            ExpertConfig(3, "Ensemble", 0.05, 7.0, 0.4, 1024, 2048),
        ]
    )

    # Heavy workload - high rate, more complex requests
    scenarios['heavy'] = WorkloadConfig(
        arrival_rate_lambda=30.0,
        duration_seconds=60.0,
        experts=[
            ExpertConfig(0, "Fast", 0.30, 5.5, 0.5, 100, 512),
            ExpertConfig(1, "Standard", 0.35, 6.2, 0.6, 256, 1024),
            ExpertConfig(2, "Complex", 0.25, 6.9, 0.7, 512, 2048),
            ExpertConfig(3, "Ensemble", 0.10, 7.2, 0.5, 1024, 2048),
        ]
    )

    # Burst workload - very high arrival rate, short duration
    scenarios['burst'] = WorkloadConfig(
        arrival_rate_lambda=50.0,
        duration_seconds=10.0,
        experts=[
            ExpertConfig(0, "Fast", 0.60, 5.0, 0.4, 50, 256),
            ExpertConfig(1, "Standard", 0.30, 5.8, 0.5, 128, 512),
            ExpertConfig(2, "Complex", 0.10, 6.5, 0.6, 256, 1024),
        ]
    )

    # Balanced research workload - equal weight on complex/ensemble types
    # Weights: Fast 40%, Standard 20%, Complex 20%, Ensemble 20%
    scenarios['balanced_research'] = WorkloadConfig(
        arrival_rate_lambda=15.0,
        duration_seconds=60.0,
        experts=[
            ExpertConfig(0, "Fast-Inference", 0.40, 5.0, 0.5, 50, 256),
            ExpertConfig(1, "Standard-Inference", 0.20, 6.0, 0.6, 128, 1024),
            ExpertConfig(2, "Complex-Inference", 0.20, 6.8, 0.7, 512, 2048),
            ExpertConfig(3, "Ensemble-Inference", 0.20, 7.2, 0.4, 1024, 2048),
        ]
    )

    return scenarios


def main():
    parser = argparse.ArgumentParser(
        description='L2 Workload Emulator - Generate statistically realistic MoE workloads'
    )
    parser.add_argument('--scenario', type=str, choices=['light', 'medium', 'heavy', 'burst'],
                        help='Use predefined scenario')
    parser.add_argument('--arrival-rate', type=float, default=10.0,
                        help='Average requests per second (Poisson lambda)')
    parser.add_argument('--duration', type=float, default=60.0,
                        help='Simulation duration in seconds')
    parser.add_argument('--seed', type=int, default=None,
                        help='Random seed for reproducibility')
    parser.add_argument('--output', type=str, default=None,
                        help='Output JSON file path')
    parser.add_argument('--stats-only', action='store_true',
                        help='Only print statistics, not full request list')

    args = parser.parse_args()

    # Create configuration
    if args.scenario:
        scenarios = create_workload_scenarios()
        config = scenarios[args.scenario]
        if args.seed is not None:
            config.seed = args.seed
    else:
        config = WorkloadConfig(
            arrival_rate_lambda=args.arrival_rate,
            duration_seconds=args.duration,
            seed=args.seed,
        )

    print("=" * 60)
    print("L2 Workload Emulator")
    print("=" * 60)
    print(f"Arrival Rate (λ): {config.arrival_rate_lambda} req/s")
    print(f"Duration: {config.duration_seconds}s")
    print(f"Seed: {config.seed or 'random'}")
    print()
    print("Expert Configuration:")
    for expert in config.experts:
        print(f"  [{expert.model_id}] {expert.name}: {expert.weight*100:.0f}% weight, "
              f"{expert.min_prompt_bytes}-{expert.max_prompt_bytes} bytes")
    print()

    # Generate workload
    emulator = L2WorkloadEmulator(config)
    requests = emulator.generate_workload()
    stats = emulator.get_workload_statistics(requests)

    # Print statistics
    print("Generated Workload Statistics:")
    print("-" * 40)
    print(f"  Total Requests: {stats['total_requests']}")
    print(f"  Total Bytes: {stats['total_bytes']:,}")
    print(f"  Duration: {stats['duration_seconds']}s")
    print(f"  Measured Arrival Rate: {stats['measured_arrival_rate']} req/s")
    print(f"  Average Prompt Size: {stats['avg_prompt_size']} bytes")
    print()
    print("  Requests per Expert:")
    for name, count in stats['requests_per_expert'].items():
        pct = count / stats['total_requests'] * 100 if stats['total_requests'] > 0 else 0
        print(f"    {name}: {count} ({pct:.1f}%)")
    print()

    # Output results
    if not args.stats_only:
        if args.output:
            output_data = {
                'config': {
                    'arrival_rate_lambda': config.arrival_rate_lambda,
                    'duration_seconds': config.duration_seconds,
                    'seed': config.seed,
                    'experts': [asdict(e) for e in config.experts],
                },
                'statistics': stats,
                'requests': [r.to_dict() for r in requests],
            }
            with open(args.output, 'w') as f:
                json.dump(output_data, f, indent=2)
            print(f"Saved to: {args.output}")
        else:
            print("Sample Requests (first 10):")
            print("-" * 40)
            for r in requests[:10]:
                print(f"  [{r.request_id:3d}] t={r.arrival_time:6.2f}s | "
                      f"model={r.expert.model_id} ({r.expert.name}) | "
                      f"prompt={r.prompt_size} bytes")
            if len(requests) > 10:
                print(f"  ... and {len(requests) - 10} more requests")

    return 0


if __name__ == '__main__':
    sys.exit(main())
