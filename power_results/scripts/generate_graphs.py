#!/usr/bin/env python3
"""QXChain Power Consumption Visualization"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import sys

# Get run directory from argument or find latest
if len(sys.argv) > 1:
    run_dir = Path(sys.argv[1])
else:
    base_dir = Path('/home/teo/qxchain/power_results')
    runs_dir = base_dir / 'runs'
    if runs_dir.exists():
        run_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir()])
        if run_dirs:
            run_dir = run_dirs[-1]
        else:
            print("No run directories found!")
            sys.exit(1)
    else:
        print("No runs directory found!")
        sys.exit(1)

data_dir = run_dir / 'data'
graphs_dir = run_dir / 'graphs'
graphs_dir.mkdir(exist_ok=True)

print(f'Run directory: {run_dir}')
print(f'Data directory: {data_dir}')
print(f'Graphs directory: {graphs_dir}')

# All possible functions (order matters for display)
all_functions = [
    # Baseline
    'idle_chain_paused',
    'idle_consensus_running',
    # Consensus
    'block_production_aura',
    'finalization_grandpa',
    # Transaction Pool
    'tx_pool_pending',
    # Balance & Account
    'account_info_query',
    'balance_query',
    # State Storage
    'state_read_simple',
    'state_read_keys',
    'state_runtime_version',
    # Chain Queries
    'chain_get_block',
    'chain_get_header',
    # RPC
    'rpc_metadata_fetch',
    'rpc_system_info',
    # Runtime API
    'runtime_api_calls',
    # Mixed
    'mixed_workload',
    # Legacy names (for backwards compatibility)
    'balance_transfer',
    'state_read',
    'rpc_light_calls',
]

# Load all CSVs that exist
data = {}
for func in all_functions:
    path = data_dir / f'{func}.csv'
    if not path.exists():
        # Try with timestamp suffix
        matches = list(data_dir.glob(f'{func}*.csv'))
        if matches:
            path = matches[0]

    if path.exists():
        data[func] = pd.read_csv(path)
        print(f'  {func}: {len(data[func])} samples, avg {data[func]["pkg_mw"].mean():.0f} mW')

if not data:
    print("No CSV files found!")
    sys.exit(1)

functions = list(data.keys())
n_funcs = len(functions)

# Calculate grid size for individual graphs
n_cols = 4
n_rows = (n_funcs + n_cols - 1) // n_cols

# Individual graphs
fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, 4 * n_rows))
axes = axes.flatten() if n_funcs > 1 else [axes]
colors = plt.cm.tab20(np.linspace(0, 1, n_funcs))

for idx, func in enumerate(functions):
    df = data[func]
    ax = axes[idx]
    ax.plot(df['elapsed_ms']/1000, df['pkg_mw']/1000, color=colors[idx], linewidth=0.8)
    ax.axhline(y=df['pkg_mw'].mean()/1000, color='red', linestyle='--', alpha=0.7,
               label=f'Avg: {df["pkg_mw"].mean()/1000:.1f}W')
    ax.fill_between(df['elapsed_ms']/1000, df['pkg_mw']/1000, alpha=0.3, color=colors[idx])
    ax.set_title(func.replace('_', ' ').title(), fontsize=10, fontweight='bold')
    ax.set_xlabel('Time (s)', fontsize=8)
    ax.set_ylabel('Power (W)', fontsize=8)
    ax.legend(loc='upper right', fontsize=7)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, max(df['pkg_mw']/1000) * 1.2)

# Hide empty subplots
for idx in range(n_funcs, len(axes)):
    axes[idx].set_visible(False)

plt.tight_layout()
plt.savefig(graphs_dir / 'individual_power_graphs.png', dpi=150)
print(f'\nSaved: {graphs_dir}/individual_power_graphs.png')

# Combined timeline
combined = []
offset = 0
boundaries = []

for func in functions:
    df = data[func].copy()
    start_offset = offset
    df['global_time'] = df['elapsed_ms'] + offset
    df['function'] = func
    combined.append(df)
    offset = df['global_time'].max()
    boundaries.append((start_offset, offset, func))

combined_df = pd.concat(combined, ignore_index=True)

fig, ax = plt.subplots(figsize=(20, 8))
colors_map = dict(zip(functions, plt.cm.tab20(np.linspace(0, 1, len(functions)))))

for func in functions:
    segment = combined_df[combined_df['function'] == func]
    ax.plot(segment['global_time']/1000, segment['pkg_mw']/1000,
            color=colors_map[func], linewidth=0.8)

# Add shaded regions and labels
for start, end, func in boundaries:
    color = colors_map[func]
    ax.axvspan(start/1000, end/1000, alpha=0.1, color=color)
    mid = (start + end) / 2000
    ypos = combined_df['pkg_mw'].max()/1000 * 0.95
    ax.annotate(func.replace('_', '\n'), xy=(mid, ypos),
                ha='center', va='top', fontsize=6, fontweight='bold', rotation=90,
                bbox=dict(boxstyle='round,pad=0.2', facecolor=color, alpha=0.6))

ax.set_xlabel('Time (seconds)', fontsize=12)
ax.set_ylabel('Package Power (Watts)', fontsize=12)
ax.set_title('QXChain Power Consumption - All Functions Timeline', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3)

avg_power = combined_df['pkg_mw'].mean()/1000
ax.axhline(y=avg_power, color='black', linestyle='--', alpha=0.5)
ax.text(combined_df['global_time'].max()/1000, avg_power, f' Avg: {avg_power:.1f}W',
        va='center', fontsize=9)

plt.tight_layout()
plt.savefig(graphs_dir / 'combined_power_timeline.png', dpi=150, bbox_inches='tight')
print(f'Saved: {graphs_dir}/combined_power_timeline.png')

# Bar chart - grouped by category
summary = []
categories = {
    'Baseline': ['idle_chain_paused', 'idle_consensus_running'],
    'Consensus': ['block_production_aura', 'finalization_grandpa'],
    'Tx Pool': ['tx_pool_pending', 'balance_transfer'],
    'Account': ['account_info_query', 'balance_query'],
    'State': ['state_read_simple', 'state_read_keys', 'state_runtime_version', 'state_read'],
    'Chain': ['chain_get_block', 'chain_get_header'],
    'RPC': ['rpc_metadata_fetch', 'rpc_system_info', 'rpc_light_calls'],
    'Runtime': ['runtime_api_calls'],
    'Mixed': ['mixed_workload'],
}

for func in functions:
    df = data[func]
    cat = 'Other'
    for c, funcs in categories.items():
        if func in funcs:
            cat = c
            break
    summary.append({
        'Function': func,
        'Category': cat,
        'Mean_W': df['pkg_mw'].mean()/1000,
        'Core_W': df['core_mw'].mean()/1000,
        'Std_W': df['pkg_mw'].std()/1000,
    })

summary_df = pd.DataFrame(summary)

fig, ax = plt.subplots(figsize=(16, 7))
x = np.arange(len(summary_df))
width = 0.6

# Color by category
cat_colors = plt.cm.Set3(np.linspace(0, 1, len(categories)))
cat_color_map = dict(zip(categories.keys(), cat_colors))
bar_colors = [cat_color_map.get(row['Category'], 'gray') for _, row in summary_df.iterrows()]

bars = ax.bar(x, summary_df['Mean_W'], width, color=bar_colors, edgecolor='black', linewidth=0.5)

# Error bars
ax.errorbar(x, summary_df['Mean_W'], yerr=summary_df['Std_W'], fmt='none', color='black', capsize=2)

ax.set_ylabel('Power (Watts)', fontsize=12)
ax.set_title('Power Consumption by Blockchain Function', fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels([f.replace('_', '\n') for f in summary_df['Function']], fontsize=8, rotation=45, ha='right')
ax.grid(True, axis='y', alpha=0.3)

# Add value labels
for bar in bars:
    height = bar.get_height()
    ax.annotate(f'{height:.1f}', xy=(bar.get_x() + bar.get_width()/2, height),
                xytext=(0, 3), textcoords='offset points', ha='center', va='bottom', fontsize=7)

# Legend for categories
from matplotlib.patches import Patch
legend_elements = [Patch(facecolor=cat_color_map[cat], edgecolor='black', label=cat)
                   for cat in categories.keys() if any(f in functions for f in categories[cat])]
ax.legend(handles=legend_elements, loc='upper right', fontsize=8)

plt.tight_layout()
plt.savefig(graphs_dir / 'power_comparison_bar.png', dpi=150)
print(f'Saved: {graphs_dir}/power_comparison_bar.png')

# Save summary CSV
summary_df.to_csv(graphs_dir / 'power_summary.csv', index=False)
print(f'Saved: {graphs_dir}/power_summary.csv')

# Print summary table
print('\n' + '='*60)
print('SUMMARY')
print('='*60)
print(f"{'Function':<25} {'Avg (W)':>10} {'Std (W)':>10} {'Category':<10}")
print('-'*60)
for _, row in summary_df.iterrows():
    print(f"{row['Function']:<25} {row['Mean_W']:>10.1f} {row['Std_W']:>10.2f} {row['Category']:<10}")
print('='*60)

print('\nDone!')
