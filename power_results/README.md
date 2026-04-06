# QXChain Power Measurement

Measures power consumption for processing blockchain transactions using Intel RAPL.

## Methodology

1. Inject N transactions (balance transfers between accounts)
2. Wait for all transactions to be included in blocks
3. Measure total energy consumed during processing
4. Record exactly how many transactions went into each block

## Output Data

**results.csv** - One row per test run:

| Column | Description |
|--------|-------------|
| tx_count | Number of transactions submitted |
| blocks_used | Number of blocks needed to include all transactions |
| actual_extrinsics | Confirmed extrinsic count in blocks |
| duration_s | Total duration (seconds) |
| energy_j | Total energy consumed (Joules) |
| power_w | Average power (Watts) |
| joules_per_tx | Energy per transaction |
| tx_per_second | Throughput |
| block_details | Extrinsics per block (e.g., #100:25, #101:25) |

**summary.csv** - Statistics per transaction count:

| Column | Description |
|--------|-------------|
| tx_count | Transaction count tested |
| power_mean / power_std | Average power with standard deviation |
| joules_per_tx_mean / joules_per_tx_std | Energy per transaction with standard deviation |
| tps_mean | Average throughput |

## Example Results

| TX Count | Runs | Avg Power (W) | Avg J/tx | Avg TPS |
|----------|------|---------------|----------|---------|
| 10 | 5 | 33.7 +/- 0.8 | 0.312 +/- 0.02 | 18.5 |
| 50 | 5 | 34.5 +/- 0.5 | 0.089 +/- 0.01 | 22.3 |
| 100 | 5 | 35.2 +/- 0.6 | 0.052 +/- 0.01 | 25.1 |
