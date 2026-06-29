#!/usr/bin/env python3
"""Generate plots for the summary."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Load main experiment
with open('experiment_results.json') as f:
    main_results = json.load(f)

with open('fine_sweep_results.json') as f:
    fine_results = json.load(f)

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

# Plot 1: main grid - split-vote rate vs spread
ax = axes[0]
spreads = [r['spread'] for r in main_results]
sv_rates = [r['split_vote_rate'] for r in main_results]
ax.bar([str(s) for s in spreads], sv_rates, color='steelblue', edgecolor='black')
ax.set_xlabel('Spread (in ticks)')
ax.set_ylabel('Split-vote rate')
ax.set_title(f'Split-vote rate vs spread (N={main_results[0]["n_nodes"]}, H={main_results[0]["heartbeat_interval"]})')
ax.set_ylim([0, 1.05])
for i, v in enumerate(sv_rates):
    ax.text(i, v + 0.02, f'{v:.0%}', ha='center')
ax.grid(axis='y', alpha=0.3)

# Plot 2: fine sweep
ax = axes[1]
fspreads = [r['spread'] for r in fine_results]
fsv_rates = [r['split_vote_rate'] for r in fine_results]
ax.plot(fspreads, fsv_rates, 'o-', color='crimson', linewidth=2, markersize=8)
ax.set_xlabel('Spread (in ticks)')
ax.set_ylabel('Split-vote rate')
ax.set_title('Fine sweep: split-vote transition (T_min=30, H=10)')
ax.set_ylim([-0.05, 1.05])
ax.axhline(y=0, color='gray', linestyle=':', alpha=0.5)
ax.grid(alpha=0.3)
ax.set_xticks(fspreads)

plt.tight_layout()
plt.savefig('election_spread_plot.png', dpi=120)
print('Plot saved to election_spread_plot.png')

# Additional figure: time-to-elect vs spread
fig, ax = plt.subplots(figsize=(6, 4.5))
medians = [r['median_time_to_elect'] if r['median_time_to_elect'] else 0 for r in main_results]
t_maxs = [r['t_max'] for r in main_results]
means = [r['mean_time_to_elect'] if r['mean_time_to_elect'] else 0 for r in main_results]
mins = [r['min_time_to_elect'] if r['min_time_to_elect'] else 0 for r in main_results]
maxs = [r['max_time_to_elect'] if r['max_time_to_elect'] else 0 for r in main_results]

x = range(len(spreads))
ax.plot(x, medians, 'o-', label='median', linewidth=2, markersize=8)
ax.plot(x, means, 's--', label='mean', alpha=0.7)
ax.fill_between(x, mins, maxs, alpha=0.15, label='min–max range')
ax.set_xticks(x)
ax.set_xticklabels([f'{s}\n(T_max={t})' for s, t in zip(spreads, t_maxs)])
ax.set_xlabel('Spread (in ticks)')
ax.set_ylabel('Time-to-elect (ticks)')
ax.set_title('Time-to-elect vs spread (N=5, 100 seeds)')
ax.legend()
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig('time_to_elect_plot.png', dpi=120)
print('Plot saved to time_to_elect_plot.png')