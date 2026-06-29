#!/usr/bin/env python3
"""Fine sweep around the spread=0 transition to characterize split-vote drop-off."""
import json
import sys
sys.path.insert(0, '.')
from raft_simulator import run_experiment

n_seeds = 200  # higher N for fine sweep
t_min = 30
heartbeat_interval = t_min // 3
# Finer grid: 0, 1, 2, 3, 5, 10, 20, 30 (in ticks)
spreads = [0, 1, 2, 3, 5, 10, 20, 30]

results = []
for spread in spreads:
    r = run_experiment(spread, n_seeds, t_min=t_min)
    results.append(r)
    med = r['median_time_to_elect']
    med_s = "n/a" if med is None else f"{med}"
    print(
        f"spread={r['spread']:>3} (T_max={r['t_max']:>3}): "
        f"median={med_s:>10} | "
        f"split-vote={r['split_vote_rate']:.2%} | "
        f"no-leader={r['no_leader_rate']:.2%}"
    )

with open('fine_sweep_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print("\nFine-sweep results saved to fine_sweep_results.json")