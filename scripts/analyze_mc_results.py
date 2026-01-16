#!/usr/bin/env python3
"""
Monte Carlo Results Analyzer for QXChain
========================================
Analyzes and visualizes Monte Carlo power measurement results.

Features:
- Distribution plots (histograms) for energy metrics
- Confidence interval visualization
- Parameter sensitivity analysis
- Comparative analysis across scenarios
- Publication-ready figures

Usage:
  python3 analyze_mc_results.py results.csv                    # Analyze single file
  python3 analyze_mc_results.py --dir monte_carlo/             # Analyze all in directory
  python3 analyze_mc_results.py results.csv --output plots/    # Custom output dir
"""

import sys
import json
import argparse
import csv
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from scipy import stats

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not installed, plots will not be generated")


@dataclass
class MCResult:
    """Parsed Monte Carlo result"""
    simulation_id: int
    arrival_rate: float
    complexity_sigma: float
    tx_count: int
    total_bytes: int
    duration_s: float
    energy_j: float
    power_w: float
    j_per_tx: float
    tx_per_second: float


def load_csv_results(csv_path: str) -> List[MCResult]:
    """Load results from CSV file"""
    results = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(MCResult(
                simulation_id=int(row['simulation_id']),
                arrival_rate=float(row['arrival_rate']),
                complexity_sigma=float(row['complexity_sigma']),
                tx_count=int(row['tx_count']),
                total_bytes=int(row['total_bytes']),
                duration_s=float(row['duration_s']),
                energy_j=float(row['energy_j']),
                power_w=float(row['power_w']),
                j_per_tx=float(row['j_per_tx']),
                tx_per_second=float(row['tx_per_second']),
            ))
    return results


def load_json_summary(json_path: str) -> dict:
    """Load summary from JSON file"""
    with open(json_path, 'r') as f:
        return json.load(f)


def compute_statistics(results: List[MCResult]) -> dict:
    """Compute comprehensive statistics"""
    if not results:
        return {}

    j_per_tx = np.array([r.j_per_tx for r in results])
    power_w = np.array([r.power_w for r in results])
    tps = np.array([r.tx_per_second for r in results])
    energy_j = np.array([r.energy_j for r in results])
    arrival_rates = np.array([r.arrival_rate for r in results])
    complexity = np.array([r.complexity_sigma for r in results])

    def ci_95(data):
        if len(data) < 2:
            return (data[0], data[0]) if len(data) == 1 else (0, 0)
        ci = stats.t.interval(0.95, len(data)-1, loc=np.mean(data), scale=stats.sem(data))
        return (float(ci[0]), float(ci[1]))

    def percentiles(data):
        return {
            'p5': float(np.percentile(data, 5)),
            'p25': float(np.percentile(data, 25)),
            'p50': float(np.percentile(data, 50)),
            'p75': float(np.percentile(data, 75)),
            'p95': float(np.percentile(data, 95)),
        }

    return {
        'n_samples': len(results),
        'j_per_tx': {
            'mean': float(np.mean(j_per_tx)),
            'std': float(np.std(j_per_tx)),
            'min': float(np.min(j_per_tx)),
            'max': float(np.max(j_per_tx)),
            'ci_95': ci_95(j_per_tx),
            'percentiles': percentiles(j_per_tx),
        },
        'power_w': {
            'mean': float(np.mean(power_w)),
            'std': float(np.std(power_w)),
            'ci_95': ci_95(power_w),
            'percentiles': percentiles(power_w),
        },
        'tps': {
            'mean': float(np.mean(tps)),
            'std': float(np.std(tps)),
            'ci_95': ci_95(tps),
            'percentiles': percentiles(tps),
        },
        'parameters': {
            'arrival_rate': {
                'min': float(np.min(arrival_rates)),
                'max': float(np.max(arrival_rates)),
                'mean': float(np.mean(arrival_rates)),
            },
            'complexity_sigma': {
                'min': float(np.min(complexity)),
                'max': float(np.max(complexity)),
                'mean': float(np.mean(complexity)),
            },
        },
        'correlations': {
            'arrival_rate_vs_j_per_tx': float(np.corrcoef(arrival_rates, j_per_tx)[0, 1]),
            'complexity_vs_j_per_tx': float(np.corrcoef(complexity, j_per_tx)[0, 1]),
            'tps_vs_j_per_tx': float(np.corrcoef(tps, j_per_tx)[0, 1]),
        }
    }


def print_statistics(stats: dict, title: str = "Monte Carlo Analysis"):
    """Print statistics in a formatted way"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)
    print(f"\nSamples: {stats['n_samples']}")

    print("\n--- Energy per Transaction (J/tx) ---")
    j = stats['j_per_tx']
    print(f"  Mean:     {j['mean']:.4f} J")
    print(f"  Std Dev:  {j['std']:.4f} J")
    print(f"  Range:    [{j['min']:.4f}, {j['max']:.4f}] J")
    print(f"  95% CI:   [{j['ci_95'][0]:.4f}, {j['ci_95'][1]:.4f}] J")
    print(f"  Median:   {j['percentiles']['p50']:.4f} J")
    print(f"  IQR:      [{j['percentiles']['p25']:.4f}, {j['percentiles']['p75']:.4f}] J")

    print("\n--- Average Power (W) ---")
    p = stats['power_w']
    print(f"  Mean:     {p['mean']:.1f} W")
    print(f"  Std Dev:  {p['std']:.1f} W")
    print(f"  95% CI:   [{p['ci_95'][0]:.1f}, {p['ci_95'][1]:.1f}] W")

    print("\n--- Throughput (TPS) ---")
    t = stats['tps']
    print(f"  Mean:     {t['mean']:.1f} tx/s")
    print(f"  Std Dev:  {t['std']:.1f} tx/s")
    print(f"  95% CI:   [{t['ci_95'][0]:.1f}, {t['ci_95'][1]:.1f}] tx/s")

    print("\n--- Parameter Ranges ---")
    params = stats['parameters']
    print(f"  Arrival Rate:     [{params['arrival_rate']['min']:.1f}, {params['arrival_rate']['max']:.1f}] req/s")
    print(f"  Complexity Sigma: [{params['complexity_sigma']['min']:.2f}, {params['complexity_sigma']['max']:.2f}]")

    print("\n--- Correlations ---")
    corr = stats['correlations']
    print(f"  Arrival Rate vs J/tx:  {corr['arrival_rate_vs_j_per_tx']:+.3f}")
    print(f"  Complexity vs J/tx:    {corr['complexity_vs_j_per_tx']:+.3f}")
    print(f"  TPS vs J/tx:           {corr['tps_vs_j_per_tx']:+.3f}")


def generate_claim_statement(stats: dict) -> str:
    """Generate a scientific claim statement from the statistics"""
    j = stats['j_per_tx']
    n = stats['n_samples']

    statement = f"""
Based on {n} Monte Carlo simulations with varied workload parameters:

"For an MoE-style L2 workload, we are 95% confident that the average
energy per transaction (E/tx) on QXChain L1 will be between
{j['ci_95'][0]:.3f} J and {j['ci_95'][1]:.3f} J."

Key metrics:
- Mean E/tx: {j['mean']:.4f} J (+/- {j['std']:.4f} J)
- Mean Power: {stats['power_w']['mean']:.1f} W
- Mean TPS: {stats['tps']['mean']:.1f} tx/s
"""
    return statement


def plot_distribution(results: List[MCResult], output_dir: str):
    """Generate distribution plots"""
    if not MATPLOTLIB_AVAILABLE:
        return

    j_per_tx = [r.j_per_tx for r in results]
    power_w = [r.power_w for r in results]
    tps = [r.tx_per_second for r in results]

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))

    # J/tx histogram
    ax = axes[0]
    ax.hist(j_per_tx, bins=30, density=True, alpha=0.7, color='steelblue', edgecolor='white')
    mean_val = np.mean(j_per_tx)
    ci = stats.t.interval(0.95, len(j_per_tx)-1, loc=mean_val, scale=stats.sem(j_per_tx))
    ax.axvline(mean_val, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_val:.4f}')
    ax.axvspan(ci[0], ci[1], alpha=0.2, color='red', label=f'95% CI')
    ax.set_xlabel('Energy per Transaction (J/tx)', fontsize=11)
    ax.set_ylabel('Density', fontsize=11)
    ax.set_title('Energy Efficiency Distribution', fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Power histogram
    ax = axes[1]
    ax.hist(power_w, bins=30, density=True, alpha=0.7, color='forestgreen', edgecolor='white')
    mean_val = np.mean(power_w)
    ax.axvline(mean_val, color='darkgreen', linestyle='--', linewidth=2, label=f'Mean: {mean_val:.1f} W')
    ax.set_xlabel('Average Power (W)', fontsize=11)
    ax.set_ylabel('Density', fontsize=11)
    ax.set_title('Power Consumption Distribution', fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # TPS histogram
    ax = axes[2]
    ax.hist(tps, bins=30, density=True, alpha=0.7, color='darkorange', edgecolor='white')
    mean_val = np.mean(tps)
    ax.axvline(mean_val, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_val:.1f} tx/s')
    ax.set_xlabel('Transactions per Second', fontsize=11)
    ax.set_ylabel('Density', fontsize=11)
    ax.set_title('Throughput Distribution', fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = Path(output_dir) / 'mc_distributions.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")


def plot_sensitivity(results: List[MCResult], output_dir: str):
    """Generate parameter sensitivity plots"""
    if not MATPLOTLIB_AVAILABLE:
        return

    arrival_rates = [r.arrival_rate for r in results]
    complexity = [r.complexity_sigma for r in results]
    j_per_tx = [r.j_per_tx for r in results]
    tps = [r.tx_per_second for r in results]

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # Arrival Rate vs J/tx
    ax = axes[0, 0]
    ax.scatter(arrival_rates, j_per_tx, alpha=0.5, s=20, c='steelblue')
    z = np.polyfit(arrival_rates, j_per_tx, 1)
    p = np.poly1d(z)
    x_line = np.linspace(min(arrival_rates), max(arrival_rates), 100)
    ax.plot(x_line, p(x_line), 'r--', linewidth=2, label='Trend')
    ax.set_xlabel('Arrival Rate (req/s)', fontsize=11)
    ax.set_ylabel('Energy per Transaction (J/tx)', fontsize=11)
    ax.set_title('Arrival Rate Sensitivity', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend()

    # Complexity vs J/tx
    ax = axes[0, 1]
    ax.scatter(complexity, j_per_tx, alpha=0.5, s=20, c='forestgreen')
    z = np.polyfit(complexity, j_per_tx, 1)
    p = np.poly1d(z)
    x_line = np.linspace(min(complexity), max(complexity), 100)
    ax.plot(x_line, p(x_line), 'r--', linewidth=2, label='Trend')
    ax.set_xlabel('Complexity Sigma', fontsize=11)
    ax.set_ylabel('Energy per Transaction (J/tx)', fontsize=11)
    ax.set_title('Complexity Sensitivity', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend()

    # Arrival Rate vs TPS
    ax = axes[1, 0]
    ax.scatter(arrival_rates, tps, alpha=0.5, s=20, c='darkorange')
    ax.set_xlabel('Arrival Rate (req/s)', fontsize=11)
    ax.set_ylabel('Throughput (tx/s)', fontsize=11)
    ax.set_title('Arrival Rate vs Throughput', fontsize=12)
    ax.grid(True, alpha=0.3)

    # TPS vs J/tx
    ax = axes[1, 1]
    ax.scatter(tps, j_per_tx, alpha=0.5, s=20, c='purple')
    z = np.polyfit(tps, j_per_tx, 1)
    p = np.poly1d(z)
    x_line = np.linspace(min(tps), max(tps), 100)
    ax.plot(x_line, p(x_line), 'r--', linewidth=2, label='Trend')
    ax.set_xlabel('Throughput (tx/s)', fontsize=11)
    ax.set_ylabel('Energy per Transaction (J/tx)', fontsize=11)
    ax.set_title('Throughput vs Energy Efficiency', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend()

    plt.tight_layout()
    output_path = Path(output_dir) / 'mc_sensitivity.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")


def plot_confidence_intervals(stats: dict, output_dir: str):
    """Generate confidence interval visualization"""
    if not MATPLOTLIB_AVAILABLE:
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    metrics = [
        ('J/tx', stats['j_per_tx']['mean'], stats['j_per_tx']['ci_95'], 'J'),
        ('Power', stats['power_w']['mean'], stats['power_w']['ci_95'], 'W'),
        ('TPS', stats['tps']['mean'], stats['tps']['ci_95'], 'tx/s'),
    ]

    y_pos = np.arange(len(metrics))
    colors = ['steelblue', 'forestgreen', 'darkorange']

    for i, (name, mean, ci, unit) in enumerate(metrics):
        # Normalize to percentage of mean for visualization
        ci_lower = ci[0]
        ci_upper = ci[1]
        error_lower = mean - ci_lower
        error_upper = ci_upper - mean

        ax.barh(i, mean, height=0.5, color=colors[i], alpha=0.7, edgecolor='black')
        ax.errorbar(mean, i, xerr=[[error_lower], [error_upper]], fmt='none',
                    color='black', capsize=5, capthick=2, linewidth=2)

        # Add value labels
        ax.text(mean + error_upper + mean * 0.02, i,
                f'{mean:.3f} [{ci_lower:.3f}, {ci_upper:.3f}] {unit}',
                va='center', fontsize=10)

    ax.set_yticks(y_pos)
    ax.set_yticklabels([m[0] for m in metrics], fontsize=12)
    ax.set_xlabel('Value', fontsize=11)
    ax.set_title('95% Confidence Intervals for Key Metrics', fontsize=13)
    ax.grid(True, alpha=0.3, axis='x')

    plt.tight_layout()
    output_path = Path(output_dir) / 'mc_confidence_intervals.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze Monte Carlo power measurement results'
    )
    parser.add_argument('input', nargs='?', type=str,
                        help='Input CSV file or directory')
    parser.add_argument('--dir', type=str,
                        default='/home/teo/qxchain/power_results/monte_carlo',
                        help='Directory containing MC results')
    parser.add_argument('--output', type=str, default=None,
                        help='Output directory for plots')
    parser.add_argument('--no-plots', action='store_true',
                        help='Skip plot generation')
    parser.add_argument('--json', action='store_true',
                        help='Output statistics as JSON')

    args = parser.parse_args()

    # Find input file
    if args.input:
        input_path = Path(args.input)
    else:
        # Find most recent CSV in directory
        mc_dir = Path(args.dir)
        if not mc_dir.exists():
            print(f"Error: Directory not found: {mc_dir}")
            return 1

        csv_files = list(mc_dir.glob('mc_results_*.csv'))
        if not csv_files:
            print(f"No MC result files found in {mc_dir}")
            return 1

        input_path = max(csv_files, key=lambda p: p.stat().st_mtime)
        print(f"Using most recent: {input_path}")

    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        return 1

    # Load results
    print(f"\nLoading results from: {input_path}")
    results = load_csv_results(str(input_path))
    print(f"Loaded {len(results)} simulation results")

    # Compute statistics
    stats = compute_statistics(results)

    # Print statistics
    print_statistics(stats, f"Analysis: {input_path.name}")

    # Print claim statement
    print("\n" + "=" * 60)
    print("SCIENTIFIC CLAIM")
    print("=" * 60)
    print(generate_claim_statement(stats))

    # Output JSON if requested
    if args.json:
        json_output = input_path.with_suffix('.analysis.json')
        with open(json_output, 'w') as f:
            json.dump(stats, f, indent=2)
        print(f"\nStatistics saved to: {json_output}")

    # Generate plots
    if not args.no_plots and MATPLOTLIB_AVAILABLE:
        output_dir = args.output if args.output else str(input_path.parent / 'plots')
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        print(f"\nGenerating plots in: {output_dir}")
        plot_distribution(results, output_dir)
        plot_sensitivity(results, output_dir)
        plot_confidence_intervals(stats, output_dir)

    return 0


if __name__ == '__main__':
    sys.exit(main())
