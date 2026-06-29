"""Verify detailed properties of the experiment."""
import json
import sys

sys.path.insert(0, "/data/workspace/admin/happy_lake/.verify_judge_minimax/raft/raft_03")
from raft_simulator import Simulator

# Quick re-run for inspection
sim = Simulator(n=5, seed=1)
result = sim.run_experiment(num_commands=1000, max_ticks=200000, submit_per_tick=50)

print(f"N={result['n']}, all_committed={result['all_committed']}, monotonic={result['monotonic_commitIndex']}")
print(f"Latency stats: mean={result['latency_mean']}, median={result['latency_median']}, "
      f"min={result['latency_min']}, max={result['latency_max']}")
print(f"Final tick: {result['final_tick']}")
print(f"Commit history length: {result['commit_history_len']}")
print()

# Check distribution of latencies
from collections import Counter
lat_counter = Counter(result["latencies"])
print(f"Latency distribution: {sorted(lat_counter.items())}")

# Check distribution of replication counts
rep_counter = Counter(result["replication_counts"])
print(f"Replication count distribution: {sorted(rep_counter.items())}")

# Verify majority rule for committed entries
n = result["n"]
strict_majority = n // 2 + 1
violations = 0
for idx, l in enumerate(result["latencies"]):
    if l is not None:
        rc = result["replication_counts"][idx]
        if rc < strict_majority:
            violations += 1
            print(f"  violation: cmd {idx+1} latency={l} rep_count={rc}")
print(f"Majority violations: {violations} (out of {sum(1 for x in result['latencies'] if x is not None)} committed)")

# Check commitIndex history
prev = -2
monotonic = True
for tick, ci in result["commit_history"]:
    if ci < prev:
        monotonic = False
        print(f"  Non-monotonic: tick {tick}, ci={ci} < prev={prev}")
        break
    prev = ci
print(f"commitIndex monotonic: {monotonic}")

# Show commit progression (first 20 entries and last 20)
print("\nFirst 30 commit history entries:")
for tick, ci in result["commit_history"][:30]:
    print(f"  tick {tick}: commitIndex={ci} (committed up to cmd {ci+1})")

print(f"\nLast 30 commit history entries:")
for tick, ci in result["commit_history"][-30:]:
    print(f"  tick {tick}: commitIndex={ci} (committed up to cmd {ci+1})")

# Show command-by-command latency profile (first 20)
print("\nFirst 20 commands latency/replication:")
for i in range(20):
    print(f"  cmd {i+1}: append_tick={result['append_ticks'][i]}, "
          f"commit_tick={result['commit_ticks'][i]}, "
          f"latency={result['latencies'][i]}, "
          f"rep={result['replication_counts'][i]}")

print("\nLast 20 commands latency/replication:")
for i in range(980, 1000):
    print(f"  cmd {i+1}: append_tick={result['append_ticks'][i]}, "
          f"commit_tick={result['commit_ticks'][i]}, "
          f"latency={result['latencies'][i]}, "
          f"rep={result['replication_counts'][i]}")