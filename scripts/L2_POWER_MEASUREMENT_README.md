# L2 Statistical Power Measurement for QXChain

A rigorous Monte Carlo simulation framework for measuring the energy efficiency of QXChain L1 blockchain under realistic L2 (Mixture of Experts) AI workloads.

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Methodology](#methodology)
  - [The Problem](#the-problem)
  - [The Solution](#the-solution)
  - [Why Monte Carlo?](#why-monte-carlo)
- [Mathematical Foundations](#mathematical-foundations)
  - [Poisson Process for Arrivals](#poisson-process-for-arrivals)
  - [Categorical Distribution for Expert Selection](#categorical-distribution-for-expert-selection)
  - [Log-Normal Distribution for Complexity](#log-normal-distribution-for-complexity)
  - [Confidence Interval Calculation](#confidence-interval-calculation)
- [Architecture](#architecture)
- [Components](#components)
  - [L2 Workload Emulator](#1-l2-workload-emulator)
  - [Monte Carlo Power Measurement](#2-monte-carlo-power-measurement)
  - [Results Analyzer](#3-results-analyzer)
  - [AI Worker Bootstrap](#4-ai-worker-bootstrap)
- [Configuration Reference](#configuration-reference)
  - [Workload Scenarios](#workload-scenarios)
  - [Expert Configuration](#expert-configuration)
  - [Monte Carlo Parameters](#monte-carlo-parameters)
- [Output Files](#output-files)
- [Usage Examples](#usage-examples)
- [Interpreting Results](#interpreting-results)
- [Energy Measurement with Intel RAPL](#energy-measurement-with-intel-rapl)
- [Research Questions Addressed](#research-questions-addressed)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)
- [References](#references)

---

## Overview

This suite implements a statistically rigorous methodology for measuring the energy efficiency of the QXChain L1 blockchain under realistic L2 (Mixture of Experts) workloads, **without requiring a fully implemented MoE router**.

The approach uses **Monte Carlo simulation** with **statistical modeling** to:
1. Generate transaction patterns that are statistically identical to what a real MoE router would produce
2. Execute these transactions on the physical QXChain testbed
3. Measure actual energy consumption using Intel RAPL
4. Compute confidence intervals for energy efficiency metrics

**Key Output:** Statistically valid claims like:
> "For a heavy MoE workload, we are 95% confident that the average energy per transaction (E/tx) will be between 0.45 J and 0.55 J."

---

## Quick Start

### Prerequisites

```bash
# Install Python dependencies
pip install substrate-interface numpy scipy matplotlib

# Enable RAPL access (Linux only)
sudo chmod a+r /sys/class/powercap/intel-rapl:0/energy_uj

# Ensure QXChain binary is built
cd /path/to/qxchain
cargo build --release
```

### Run a Quick Test

```bash
cd scripts/

# Run 5 Monte Carlo simulations with 100 transactions each
python3 monte_carlo_power.py --simulations 5 --tx 100 --scenario medium

# Analyze the results
python3 analyze_mc_results.py
```

### Run a Full Research Study

```bash
# Run 100 simulations for statistical significance
python3 monte_carlo_power.py --simulations 100 --tx 200 --scenario heavy --seed 42

# Generate analysis and plots
python3 analyze_mc_results.py --json
```

---

## Methodology

### The Problem

To prove energy efficiency of the L1 chain under L2 workloads, we need to test with **realistic transaction patterns**. However:

- Building a complete MoE router orchestration system is complex and time-consuming
- Real L2 workloads are variable and hard to reproduce
- Single-point measurements don't capture the uncertainty in energy consumption

### The Solution

We separate the problem into two independent parts:

```
┌────────────────────────────────────────────────────────────────────┐
│                      STATISTICAL DOMAIN                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  L2 Workload Emulator                                         │  │
│  │  - Generates transaction patterns using statistical models    │  │
│  │  - Matches real MoE router behavior probabilistically         │  │
│  │  - Produces: arrival times, expert selections, prompt sizes   │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────┐
│                      PHYSICAL DOMAIN                                │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  QXChain L1 Testbed                                           │  │
│  │  - Executes real transactions on actual blockchain            │  │
│  │  - Measures CPU energy via Intel RAPL                         │  │
│  │  - Records: energy (J), duration (s), throughput (tx/s)       │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

### Why Monte Carlo?

Instead of running **one simulation** with fixed parameters, we run **many simulations** with **varied parameters**:

| Aspect | Single Simulation | Monte Carlo (N=100+) |
|--------|-------------------|----------------------|
| Parameters | Fixed | Sampled from ranges |
| Result | Point estimate | Distribution |
| Uncertainty | Unknown | Quantified via CI |
| Reproducibility | Depends on conditions | Statistical guarantees |
| Scientific validity | Limited | Peer-review ready |

**Parameter Variations:**
- **Arrival rate:** 5-30 requests/second (uniform sampling)
- **Expert weights:** ±15% variation (simulates changing user preferences)
- **Complexity sigma:** 0.3-1.0 (simulates varying prompt length distributions)

---

## Mathematical Foundations

### Poisson Process for Arrivals

Request arrivals follow a **Poisson process** with rate λ (requests/second).

**Inter-arrival times** are exponentially distributed:
```
T ~ Exponential(λ)
P(T > t) = e^(-λt)
E[T] = 1/λ
```

**Implementation:**
```python
inter_arrivals = rng.exponential(scale=1.0/λ, size=n)
arrival_times = np.cumsum(inter_arrivals)
```

**Why Poisson?**
- Standard model for independent random events
- Memoryless property matches real request patterns
- Well-understood statistical properties

### Categorical Distribution for Expert Selection

Each request selects an expert according to a **categorical distribution**:
```
P(Expert = i) = w_i,  where Σw_i = 1
```

**Default weights (medium scenario):**
| Expert | Weight | Description |
|--------|--------|-------------|
| Fast-Inference | 50% | Quick, small prompts |
| Standard-Inference | 30% | Balanced workload |
| Complex-Inference | 15% | Large prompts, complex tasks |
| Ensemble-Inference | 5% | Multi-model coordination |

**Monte Carlo variation:** Weights are perturbed by ±15% and renormalized:
```python
variations = rng.uniform(-0.15, 0.15, size=n_experts)
new_weights = base_weights * (1 + variations)
new_weights = new_weights / new_weights.sum()  # Normalize
```

### Log-Normal Distribution for Complexity

Prompt sizes follow a **log-normal distribution**:
```
X ~ LogNormal(μ, σ)
ln(X) ~ Normal(μ, σ)
Median = e^μ
```

**Why log-normal?**
- Non-negative values only (sizes can't be negative)
- Right-skewed (most prompts small, some very large)
- Matches empirical text length distributions

**Per-expert parameters:**
| Expert | μ | σ | Median Size | Range |
|--------|---|---|-------------|-------|
| Fast | 5.0 | 0.5 | ~148 bytes | 50-256 |
| Standard | 6.0 | 0.6 | ~403 bytes | 128-1024 |
| Complex | 6.8 | 0.7 | ~898 bytes | 512-2048 |
| Ensemble | 7.2 | 0.4 | ~1339 bytes | 1024-2048 |

### Confidence Interval Calculation

The 95% confidence interval uses the **Student's t-distribution**:
```
CI = x̄ ± t(α/2, n-1) × (s/√n)
```

Where:
- `x̄` = sample mean
- `s` = sample standard deviation
- `n` = number of simulations
- `t(α/2, n-1)` = t-distribution critical value

**Implementation:**
```python
from scipy import stats
ci = stats.t.interval(0.95, len(data)-1, loc=np.mean(data), scale=stats.sem(data))
```

**Sample size guidance:**
| Simulations | CI Width (relative) | Use Case |
|-------------|---------------------|----------|
| 5 | Very wide | Quick sanity check |
| 30 | Moderate | Development testing |
| 100 | Narrow | Research publication |
| 1000 | Very narrow | High-precision claims |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MONTE CARLO ENGINE                                   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ For each simulation i = 1..N:                                            ││
│  │                                                                          ││
│  │  1. PARAMETER SAMPLING                                                   ││
│  │     ┌─────────────────┐                                                  ││
│  │     │ Sample:         │                                                  ││
│  │     │ - arrival_rate  │──┐                                               ││
│  │     │ - expert_weights│  │                                               ││
│  │     │ - complexity_σ  │  │                                               ││
│  │     └─────────────────┘  │                                               ││
│  │                          ▼                                               ││
│  │  2. WORKLOAD GENERATION                                                  ││
│  │     ┌─────────────────────────────────────────┐                          ││
│  │     │ L2WorkloadEmulator                      │                          ││
│  │     │ - Generate arrival times (Poisson)      │                          ││
│  │     │ - Select experts (Categorical)          │──┐                       ││
│  │     │ - Sample prompt sizes (Log-Normal)      │  │                       ││
│  │     └─────────────────────────────────────────┘  │                       ││
│  │                                                   │                       ││
│  │                          ┌────────────────────────┘                       ││
│  │                          ▼                                               ││
│  │  3. CHAIN EXECUTION                                                      ││
│  │     ┌─────────────────────────────────────────────────────────────┐      ││
│  │     │ QXChain L1 Testbed                                          │      ││
│  │     │                                                             │      ││
│  │     │  ┌──────────┐   ┌──────────────┐   ┌────────────────┐      │      ││
│  │     │  │ Restart  │──▶│ Inject TXs   │──▶│ Wait for       │      │      ││
│  │     │  │ Chain    │   │ (no wait)    │   │ Pool Empty     │      │      ││
│  │     │  └──────────┘   └──────────────┘   └────────────────┘      │      ││
│  │     │       │                                    │                │      ││
│  │     │       ▼                                    ▼                │      ││
│  │     │  ┌──────────┐                        ┌──────────┐          │      ││
│  │     │  │ RAPL     │                        │ RAPL     │          │      ││
│  │     │  │ Start    │                        │ End      │          │      ││
│  │     │  └──────────┘                        └──────────┘          │      ││
│  │     └─────────────────────────────────────────────────────────────┘      ││
│  │                          │                                               ││
│  │                          ▼                                               ││
│  │  4. METRICS CALCULATION                                                  ││
│  │     ┌─────────────────────────────────────────┐                          ││
│  │     │ energy_j = (end - start) / 1,000,000    │                          ││
│  │     │ j_per_tx = energy_j / tx_count          │                          ││
│  │     │ power_w  = energy_j / duration          │                          ││
│  │     │ tps      = tx_count / duration          │                          ││
│  │     └─────────────────────────────────────────┘                          ││
│  │                          │                                               ││
│  │                          ▼                                               ││
│  │  5. STORE RESULT[i]                                                      ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ STATISTICAL ANALYSIS                                                     ││
│  │ - Compute mean, std, min, max for all metrics                           ││
│  │ - Calculate 95% confidence intervals (t-distribution)                   ││
│  │ - Compute percentiles (p5, p25, p50, p75, p95)                          ││
│  │ - Calculate correlations (arrival_rate vs j_per_tx, etc.)               ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. L2 Workload Emulator

**File:** `l2_workload_emulator.py`

Generates statistically realistic transaction patterns that emulate MoE router behavior.

**Key Classes:**

```python
@dataclass
class ExpertConfig:
    model_id: int           # Unique identifier (0-3)
    name: str               # Human-readable name
    weight: float           # Selection probability (0-1, must sum to 1)
    complexity_mu: float    # Log-normal mean for prompt size
    complexity_sigma: float # Log-normal std dev
    min_prompt_bytes: int   # Minimum allowed prompt size
    max_prompt_bytes: int   # Maximum allowed prompt size

@dataclass
class WorkloadConfig:
    arrival_rate_lambda: float  # Poisson rate (requests/second)
    duration_seconds: float     # Simulation duration
    experts: List[ExpertConfig] # Expert configurations
    seed: Optional[int]         # Random seed for reproducibility

@dataclass
class TransactionRequest:
    request_id: int             # Sequential identifier
    arrival_time: float         # Seconds from simulation start
    expert: ExpertConfig        # Selected expert
    prompt_size: int            # Generated prompt size (bytes)
    max_tokens: int             # Max response tokens
```

**Usage:**

```bash
# Generate sample workload
python3 l2_workload_emulator.py --scenario medium

# Save to JSON
python3 l2_workload_emulator.py --scenario heavy --output workload.json

# Custom parameters
python3 l2_workload_emulator.py --arrival-rate 20 --duration 60 --seed 42

# Statistics only
python3 l2_workload_emulator.py --scenario burst --stats-only
```

**Example Output:**

```
============================================================
L2 Workload Emulator
============================================================
Arrival Rate (λ): 15.0 req/s
Duration: 60.0s
Seed: random

Expert Configuration:
  [0] Fast: 50% weight, 50-256 bytes
  [1] Standard: 30% weight, 128-1024 bytes
  [2] Complex: 15% weight, 512-2048 bytes
  [3] Ensemble: 5% weight, 1024-2048 bytes

Generated Workload Statistics:
----------------------------------------
  Total Requests: 912
  Total Bytes: 421,847
  Duration: 59.98s
  Measured Arrival Rate: 15.2 req/s
  Average Prompt Size: 462.5 bytes

  Requests per Expert:
    Fast: 458 (50.2%)
    Standard: 271 (29.7%)
    Complex: 139 (15.2%)
    Ensemble: 44 (4.8%)
```

---

### 2. Monte Carlo Power Measurement

**File:** `monte_carlo_power.py`

Orchestrates Monte Carlo simulations with energy measurements.

**Key Classes:**

```python
@dataclass
class MonteCarloConfig:
    n_simulations: int = 100              # Number of simulation runs
    workload_scenario: str = "medium"     # Base scenario

    # Parameter variation toggles
    vary_arrival_rate: bool = True
    arrival_rate_range: Tuple[float, float] = (5.0, 30.0)

    vary_expert_weights: bool = True
    expert_weight_variation: float = 0.15  # ±15%

    vary_complexity: bool = True
    complexity_sigma_range: Tuple[float, float] = (0.3, 1.0)

    # Execution settings
    tx_only_mode: bool = False            # Use balance transfers only
    tx_per_run: int = 100                 # Transactions per simulation
    restart_chain: bool = True            # Fresh state between runs
    warmup_blocks: int = 5                # Warmup before measurement

    seed: Optional[int] = None            # Master random seed
    output_dir: str = "power_results/monte_carlo"

@dataclass
class SimulationResult:
    simulation_id: int
    timestamp: str

    # Sampled parameters
    arrival_rate: float
    expert_weights: Dict[str, float]
    complexity_sigma: float

    # Workload characteristics
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
```

**Usage:**

```bash
# Quick test
python3 monte_carlo_power.py --simulations 5 --tx 100

# Standard research run
python3 monte_carlo_power.py --simulations 100 --tx 200 --scenario heavy

# Reproducible run
python3 monte_carlo_power.py --simulations 50 --seed 42

# Balance transfers only (no AI worker setup)
python3 monte_carlo_power.py --simulations 20 --tx-only

# Don't restart chain between runs
python3 monte_carlo_power.py --simulations 10 --no-restart

# Custom output directory
python3 monte_carlo_power.py --output /path/to/results
```

**Command Line Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--simulations`, `-n` | 100 | Number of Monte Carlo simulations |
| `--scenario` | medium | Workload scenario (light/medium/heavy/burst) |
| `--tx` | 100 | Transactions per simulation run |
| `--tx-only` | False | Use balance transfers only |
| `--no-restart` | False | Don't restart chain between runs |
| `--seed` | None | Random seed for reproducibility |
| `--output` | `power_results/monte_carlo` | Output directory |

---

### 3. Results Analyzer

**File:** `analyze_mc_results.py`

Analyzes Monte Carlo results and generates publication-ready visualizations.

**Features:**
- Comprehensive statistical analysis
- Distribution plots with confidence intervals
- Parameter sensitivity analysis
- Correlation analysis
- Scientific claim generation

**Usage:**

```bash
# Analyze most recent results
python3 analyze_mc_results.py

# Analyze specific file
python3 analyze_mc_results.py /path/to/mc_results.csv

# Output statistics as JSON
python3 analyze_mc_results.py --json

# Skip plot generation
python3 analyze_mc_results.py --no-plots

# Custom output directory for plots
python3 analyze_mc_results.py --output /path/to/plots
```

**Generated Plots:**

1. **`mc_distributions.png`** - Histograms showing:
   - Energy per transaction (J/tx) with 95% CI
   - Average power (W)
   - Throughput (tx/s)

2. **`mc_sensitivity.png`** - Scatter plots showing:
   - Arrival rate vs J/tx (with trend line)
   - Complexity sigma vs J/tx (with trend line)
   - Arrival rate vs TPS
   - TPS vs J/tx (with trend line)

3. **`mc_confidence_intervals.png`** - Visual representation of 95% CIs for all metrics

**Statistics Computed:**

```python
{
    'n_samples': 100,
    'j_per_tx': {
        'mean': 1.0234,
        'std': 0.0567,
        'min': 0.8901,
        'max': 1.2345,
        'ci_95': (0.9987, 1.0481),
        'percentiles': {'p5': 0.92, 'p25': 0.98, 'p50': 1.02, 'p75': 1.07, 'p95': 1.13}
    },
    'power_w': {...},
    'tps': {...},
    'parameters': {
        'arrival_rate': {'min': 5.1, 'max': 29.8, 'mean': 17.2},
        'complexity_sigma': {'min': 0.31, 'max': 0.98, 'mean': 0.64}
    },
    'correlations': {
        'arrival_rate_vs_j_per_tx': -0.234,
        'complexity_vs_j_per_tx': 0.156,
        'tps_vs_j_per_tx': -0.412
    }
}
```

---

### 4. AI Worker Bootstrap

**File:** `bootstrap_ai_workers.py`

Sets up KILT DIDs and AI worker credentials required for AI pallet transactions.

**Usage:**

```bash
# Bootstrap with default 2 workers
python3 bootstrap_ai_workers.py

# Check current state
python3 bootstrap_ai_workers.py --check
```

**Note:** Currently, the Monte Carlo framework uses balance transfers as a proxy for AI transactions, since the full AI worker bootstrap is complex. This provides valid energy measurements for transaction processing overhead.

---

## Configuration Reference

### Workload Scenarios

| Scenario | Arrival Rate | Duration | Expert Distribution | Use Case |
|----------|--------------|----------|---------------------|----------|
| `light` | 5 req/s | 60s | 70/25/5% | Low-traffic periods |
| `medium` | 15 req/s | 60s | 50/30/15/5% | Normal operation |
| `heavy` | 30 req/s | 60s | 30/35/25/10% | Peak load |
| `burst` | 50 req/s | 10s | 60/30/10% | Traffic spikes |

### Expert Configuration

**Default Experts (Medium Scenario):**

```python
experts = [
    ExpertConfig(
        model_id=0,
        name="Fast-Inference",
        weight=0.50,
        complexity_mu=5.2,      # ~181 bytes median
        complexity_sigma=0.5,
        min_prompt_bytes=50,
        max_prompt_bytes=256
    ),
    ExpertConfig(
        model_id=1,
        name="Standard-Inference",
        weight=0.30,
        complexity_mu=6.0,      # ~403 bytes median
        complexity_sigma=0.6,
        min_prompt_bytes=128,
        max_prompt_bytes=1024
    ),
    ExpertConfig(
        model_id=2,
        name="Complex-Inference",
        weight=0.15,
        complexity_mu=6.8,      # ~898 bytes median
        complexity_sigma=0.7,
        min_prompt_bytes=512,
        max_prompt_bytes=2048
    ),
    ExpertConfig(
        model_id=3,
        name="Ensemble-Inference",
        weight=0.05,
        complexity_mu=7.0,      # ~1097 bytes median
        complexity_sigma=0.4,
        min_prompt_bytes=1024,
        max_prompt_bytes=2048
    ),
]
```

### Monte Carlo Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `n_simulations` | 100 | 1-10000 | Number of independent runs |
| `tx_per_run` | 100 | 10-1000 | Transactions per simulation |
| `arrival_rate_range` | (5, 30) | (1, 100) | Poisson λ sampling range |
| `expert_weight_variation` | 0.15 | 0-0.5 | Weight perturbation factor |
| `complexity_sigma_range` | (0.3, 1.0) | (0.1, 2.0) | Log-normal σ range |
| `warmup_blocks` | 5 | 1-20 | Blocks before measurement |

---

## Output Files

### CSV Results (`mc_results_TIMESTAMP.csv`)

Each row represents one simulation:

| Column | Type | Description |
|--------|------|-------------|
| `simulation_id` | int | Sequential run number |
| `timestamp` | str | ISO timestamp |
| `arrival_rate` | float | Sampled arrival rate (req/s) |
| `expert_weights` | JSON | Sampled expert weights |
| `complexity_sigma` | float | Sampled complexity sigma |
| `tx_count` | int | Actual transactions executed |
| `tx_by_model` | JSON | Transactions per expert model |
| `total_bytes` | int | Total prompt bytes |
| `duration_s` | float | Execution time (seconds) |
| `energy_j` | float | Total energy consumed (Joules) |
| `power_w` | float | Average power (Watts) |
| `j_per_tx` | float | Energy per transaction |
| `tx_per_second` | float | Throughput |
| `blocks_used` | int | Blockchain blocks consumed |
| `start_block` | int | Starting block number |
| `end_block` | int | Ending block number |

### JSON Summary (`mc_summary_TIMESTAMP.json`)

```json
{
  "n_simulations": 100,
  "j_per_tx": {
    "mean": 1.0234,
    "std": 0.0567,
    "min": 0.8901,
    "max": 1.2345,
    "ci_95_lower": 0.9987,
    "ci_95_upper": 1.0481
  },
  "power_w": {
    "mean": 25.3,
    "std": 1.2,
    "ci_95_lower": 25.1,
    "ci_95_upper": 25.5
  },
  "tps": {
    "mean": 24.7,
    "std": 1.8,
    "ci_95_lower": 24.3,
    "ci_95_upper": 25.1
  },
  "config": {
    "n_simulations": 100,
    "workload_scenario": "medium",
    "tx_per_run": 200,
    "arrival_rate_range": [5.0, 30.0],
    "vary_parameters": {
      "arrival_rate": true,
      "expert_weights": true,
      "complexity": true
    }
  },
  "timestamp": "20260116_143218"
}
```

---

## Usage Examples

### Example 1: Quick Validation Test

```bash
# Run minimal test to verify setup
python3 monte_carlo_power.py --simulations 3 --tx 50 --scenario light

# Expected output:
# - 3 simulations complete in ~2-3 minutes
# - Results saved to power_results/monte_carlo/
```

### Example 2: Research Publication Run

```bash
# Run statistically significant study
python3 monte_carlo_power.py \
    --simulations 100 \
    --tx 200 \
    --scenario heavy \
    --seed 42

# Analyze and generate plots
python3 analyze_mc_results.py --json

# Expected output:
# - Narrow 95% confidence intervals
# - Publication-ready PNG plots
# - Complete statistical analysis
```

### Example 3: Reproducibility Verification

```bash
# Run with fixed seed
python3 monte_carlo_power.py --simulations 20 --seed 12345

# Run again with same seed
python3 monte_carlo_power.py --simulations 20 --seed 12345

# Results should be identical (deterministic workload generation)
```

### Example 4: Scenario Comparison

```bash
# Run all scenarios
for scenario in light medium heavy burst; do
    python3 monte_carlo_power.py \
        --simulations 50 \
        --tx 150 \
        --scenario $scenario \
        --output power_results/mc_${scenario}
done

# Compare results across scenarios
```

---

## Interpreting Results

### Key Metrics

| Metric | Good Range | Interpretation |
|--------|------------|----------------|
| **J/tx** | 0.5-2.0 J | Energy cost per transaction |
| **Power** | 20-40 W | Average CPU power draw |
| **TPS** | 15-30 tx/s | Transaction throughput |

### Confidence Interval Interpretation

```
95% CI for J/tx: [0.95, 1.05] J
```

This means: "We are 95% confident that the true mean energy per transaction lies between 0.95 J and 1.05 J."

### Correlation Interpretation

| Correlation | Value | Meaning |
|-------------|-------|---------|
| arrival_rate vs j_per_tx | Negative | Higher load = better efficiency |
| complexity vs j_per_tx | Positive | Larger prompts = more energy |
| tps vs j_per_tx | Negative | Higher throughput = better efficiency |

### Warning Signs

- **Negative energy values:** RAPL counter overflow (handled automatically)
- **Very wide CI:** Insufficient simulations (increase N)
- **High variance:** System instability or background processes

---

## Energy Measurement with Intel RAPL

### What is RAPL?

**Running Average Power Limit (RAPL)** is Intel's interface for monitoring CPU energy consumption.

**Location:** `/sys/class/powercap/intel-rapl:0/energy_uj`

**Value:** Cumulative energy in microjoules (μJ) since boot

### Setup

```bash
# Check RAPL availability
cat /sys/class/powercap/intel-rapl:0/name
# Should output: package-0

# Enable read access
sudo chmod a+r /sys/class/powercap/intel-rapl:0/energy_uj

# Verify
cat /sys/class/powercap/intel-rapl:0/energy_uj
# Should output a large integer
```

### Measurement Method

```python
# Read start energy
start_energy_uj = int(open(RAPL_PATH).read())

# ... execute transactions ...

# Read end energy
end_energy_uj = int(open(RAPL_PATH).read())

# Calculate (handle overflow)
energy_uj = end_energy_uj - start_energy_uj
if energy_uj < 0:
    energy_uj += 2**32  # 32-bit counter overflow

energy_joules = energy_uj / 1_000_000
```

### Limitations

- **CPU package only:** Doesn't include disk, network, memory
- **Overflow:** Counter wraps around at max value (~4.3 GJ)
- **Resolution:** ~1 ms sampling resolution
- **Accuracy:** ±5% typical, varies by CPU model

---

## Research Questions Addressed

### Q1: Do you consider AI compute in L2 alongside chain compute?

**No.** This methodology measures **only L1 chain compute**:
- Transaction processing
- State storage
- Consensus operations

The L2 AI inference compute:
- Runs off-chain on worker nodes
- Is highly variable (depends on model, hardware)
- Can be measured separately if needed

The statistical model generates the *transaction pattern* an L2 would produce, not the L2 compute itself.

### Q2: How does model selection affect energy?

For L1 measurements, different "experts" affect:
- **Prompt size** stored on-chain (50-2048 bytes)
- **Output size** stored on-chain (up to 4096 bytes)
- **Selection probability** (some models used more frequently)

This is captured in the Categorical + Log-Normal distributions.

### Q3: What can we claim from these results?

After running sufficient simulations:

> "Based on N Monte Carlo simulations with varied MoE workload parameters, we are 95% confident that the average energy per transaction (E/tx) on QXChain L1 will be between X and Y Joules."

### Q4: How does this compare to other blockchains?

| Blockchain | Energy per Transaction |
|------------|------------------------|
| Bitcoin | ~700 kWh (~2.5 GJ) |
| Ethereum (PoW) | ~100 kWh (~360 MJ) |
| Ethereum (PoS) | ~0.03 kWh (~108 kJ) |
| **QXChain** | **~1 J** |

QXChain's Proof-of-Authority consensus is orders of magnitude more efficient than PoW chains.

---

## Limitations

1. **L1 Only:** Does not measure L2 AI inference energy
2. **CPU Only:** RAPL measures CPU package, not total system
3. **Single Node:** Measurements on single validator, not full network
4. **Balance Transfers:** Currently uses transfers, not full AI transactions
5. **Local Testbed:** Results may differ on production hardware
6. **Background Noise:** System processes may affect measurements

### Mitigation Strategies

- Run on dedicated hardware with minimal background processes
- Use many simulations to average out noise
- Restart chain between runs for independence
- Use warmup period before measurement

---

## Troubleshooting

### RAPL Permission Denied

```bash
# Error: Permission denied reading RAPL
sudo chmod a+r /sys/class/powercap/intel-rapl:0/energy_uj

# Make permanent (add to /etc/rc.local or systemd)
```

### Chain Won't Start

```bash
# Kill existing processes
pkill -9 qxchain

# Clear state
rm -rf /tmp/alice

# Verify binary exists
ls -la /path/to/qxchain/target/release/qxchain
```

### Negative Energy Values

RAPL counter overflow - handled automatically in code:
```python
if energy_uj < 0:
    energy_uj += 2**32
```

### Very High Variance

- Increase number of simulations
- Check for background processes
- Ensure consistent system state
- Use `--restart` flag (default)

### No Results Generated

- Check Python dependencies: `pip install substrate-interface numpy scipy`
- Verify chain is accessible: `curl http://127.0.0.1:9944`
- Check output directory permissions

---

## References

### Intel RAPL

- [Intel RAPL Documentation](https://www.intel.com/content/www/us/en/developer/articles/technical/software-security-guidance/advisory-guidance/running-average-power-limit-energy-reporting.html)
- Khan, K. N., et al. "RAPL in Action: Experiences in Using RAPL for Power Measurements." ACM TOMPECS, 2018.

### Monte Carlo Methods

- Robert, C. P., & Casella, G. "Monte Carlo Statistical Methods." Springer, 2004.
- Gentle, J. E. "Random Number Generation and Monte Carlo Methods." Springer, 2003.

### Statistical Distributions

- **Poisson Process:** Ross, S. M. "Introduction to Probability Models." Academic Press, 2014.
- **Log-Normal Distribution:** Limpert, E., et al. "Log-normal distributions across the sciences." BioScience, 2001.

### Blockchain Energy

- Sedlmeir, J., et al. "The Energy Consumption of Blockchain Technology: Beyond Myth." Business & Information Systems Engineering, 2020.
- Platt, M., et al. "Energy Footprint of Blockchain Consensus Mechanisms Beyond Proof-of-Work." IEEE Access, 2021.

---

## License

This measurement framework is part of the QXChain project.

## Authors

QXChain Development Team

---

*Last updated: January 2026*
