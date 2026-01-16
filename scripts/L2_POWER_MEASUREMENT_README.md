# L2 Statistical Power Measurement for QXChain

## Overview

This suite implements a rigorous methodology for measuring the energy efficiency of the QXChain L1 blockchain under realistic L2 (Mixture of Experts) workloads, without requiring a fully implemented MoE router.

The approach uses **Monte Carlo simulation** with **statistical modeling** to generate transaction patterns that are statistically identical to what a real MoE router would produce, then measures actual energy consumption on the physical testbed using Intel RAPL.

## Methodology

### The Problem

To prove energy efficiency of the L1 chain under L2 workloads, we need to test with realistic transaction patterns. However, building a complete MoE router orchestration system is complex and time-consuming.

### The Solution

We separate the problem into two parts:

1. **L2 Workload Generation (Emulation)**: A Python-based emulator generates transaction streams using statistical models that match real MoE router behavior.

2. **L1 Energy Measurement (Physical Testbed)**: These emulated transactions are executed on the QXChain testbed, and we measure actual energy using Intel RAPL.

### Statistical Models

| Feature | Description | Statistical Model |
|---------|-------------|-------------------|
| **Request Arrival Rate** | How frequently new AI inference requests arrive | Poisson Process (λ = requests/second) |
| **Expert Selection** | Probability of choosing each AI model/expert | Categorical Distribution (weighted) |
| **Request Complexity** | Computational cost / data size of each request | Log-Normal Distribution |

### Monte Carlo Approach

Instead of running one simulation with fixed parameters, we run **thousands of simulations** with varied parameters:

- Arrival rate varies within a defined range (e.g., 5-30 req/s)
- Expert weights vary by ±15%
- Complexity sigma varies within a range

This produces a **distribution of possible energy costs**, allowing us to make statistically valid claims like:

> "For a heavy MoE workload, we are 95% confident that the average energy per transaction (E/tx) will be between 0.45 J and 0.55 J."

## Scripts

### 1. L2 Workload Emulator (`l2_workload_emulator.py`)

Generates statistically realistic transaction patterns.

```bash
# Generate sample workload (prints to console)
python3 l2_workload_emulator.py --scenario medium

# Save workload to JSON file
python3 l2_workload_emulator.py --scenario heavy --output workload.json

# Custom parameters
python3 l2_workload_emulator.py --arrival-rate 20 --duration 60 --seed 42
```

**Predefined Scenarios:**
- `light`: Low arrival rate, mostly fast inference (5 req/s, 70% fast model)
- `medium`: Balanced workload (15 req/s, 50/30/15/5% model distribution)
- `heavy`: High rate, complex requests (30 req/s, more complex models)
- `burst`: Very high rate, short duration (50 req/s, 10 seconds)

### 2. Monte Carlo Power Measurement (`monte_carlo_power.py`)

Runs Monte Carlo simulations with energy measurements.

```bash
# Quick test (5 simulations)
python3 monte_carlo_power.py --simulations 5 --tx 100 --scenario medium

# Full research run (100+ simulations)
python3 monte_carlo_power.py --simulations 100 --tx 200 --scenario heavy

# Reproducible run with seed
python3 monte_carlo_power.py --simulations 50 --seed 42
```

**Output:**
- `mc_results_TIMESTAMP.csv`: Individual simulation results
- `mc_summary_TIMESTAMP.json`: Summary statistics with confidence intervals

### 3. Results Analyzer (`analyze_mc_results.py`)

Analyzes Monte Carlo results and generates visualizations.

```bash
# Analyze most recent results
python3 analyze_mc_results.py

# Analyze specific file
python3 analyze_mc_results.py /path/to/mc_results.csv

# Output statistics as JSON
python3 analyze_mc_results.py --json
```

**Generated Plots:**
- `mc_distributions.png`: Histograms of J/tx, Power, TPS with confidence intervals
- `mc_sensitivity.png`: Parameter sensitivity analysis
- `mc_confidence_intervals.png`: Visual representation of 95% CIs

### 4. AI Worker Bootstrap (`bootstrap_ai_workers.py`)

Sets up KILT DIDs and AI worker credentials (required for AI pallet transactions).

```bash
# Bootstrap with 2 workers
python3 bootstrap_ai_workers.py

# Check current state
python3 bootstrap_ai_workers.py --check
```

## Example Results

From a 5-simulation test run:

```
Energy per Transaction (J/tx):
  Mean: 1.7874 J
  Std:  0.1329 J
  95% CI: [1.6029, 1.9719] J

Average Power (W):
  Mean: 28.0 W
  95% CI: [27.7, 28.2] W

Throughput (TPS):
  Mean: 15.7 tx/s
  95% CI: [14.1, 17.4] tx/s
```

## Scientific Claim Format

After running sufficient simulations, results can be stated as:

> "Based on N Monte Carlo simulations with varied MoE workload parameters, we are 95% confident that the average energy per transaction on QXChain L1 will be between X and Y Joules."

## Requirements

```bash
pip install substrate-interface numpy scipy matplotlib
```

**RAPL Access:** Energy measurement requires read access to RAPL:
```bash
sudo chmod a+r /sys/class/powercap/intel-rapl:0/energy_uj
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Monte Carlo Engine                        │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │ Parameter       │───▶│ L2 Workload     │                 │
│  │ Sampler         │    │ Emulator        │                 │
│  └─────────────────┘    └────────┬────────┘                 │
│                                  │                           │
│                                  ▼                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              QXChain L1 Testbed                      │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐           │    │
│  │  │ Chain    │  │ TX       │  │ RAPL     │           │    │
│  │  │ Manager  │  │ Injector │  │ Monitor  │           │    │
│  │  └──────────┘  └──────────┘  └──────────┘           │    │
│  └─────────────────────────────────────────────────────┘    │
│                                  │                           │
│                                  ▼                           │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │ Statistics      │◀───│ Results         │                 │
│  │ Analyzer        │    │ Collector       │                 │
│  └─────────────────┘    └─────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

## Addressing Research Questions

### Q1: Do you consider AI compute in L2 alongside chain compute?

**No.** This methodology measures **only L1 chain compute** (transaction processing, storage, consensus). The L2 AI inference compute:
- Runs off-chain on worker nodes
- Is highly variable (depends on model, hardware)
- Can be measured separately if needed

The statistical model generates the *transaction pattern* an L2 would produce, not the L2 compute itself.

### Q2: Model selection for AI compute?

For L1 measurements, different "experts" affect:
- **Prompt size** stored on-chain (50-2048 bytes)
- **Output size** stored on-chain (up to 4096 bytes)
- **Selection probability** (some models used more frequently)

This is captured in the Categorical + Log-Normal distributions.

## References

- Intel RAPL: Running Average Power Limit interface for CPU energy measurement
- Monte Carlo Methods: Statistical simulation technique for uncertainty quantification
- Poisson Process: Standard model for random arrival events
- Log-Normal Distribution: Common model for non-negative, right-skewed values (like text lengths)
