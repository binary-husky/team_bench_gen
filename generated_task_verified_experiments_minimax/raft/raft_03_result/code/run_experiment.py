"""Quick sanity test for the simulator."""
import sys
sys.path.insert(0, "/data/workspace/admin/happy_lake/.verify_judge_minimax/raft/raft_03")
from raft_simulator import Simulator

sim = Simulator(n=3, seed=42)
result = sim.run_experiment(num_commands=10, max_ticks=2000, submit_per_tick=2)
print("all_committed:", result["all_committed"])
print("latency stats:", result["latency_mean"], result["latency_median"], result["latency_max"])
print("monotonic:", result["monotonic_commitIndex"])
print("commit_history (first 20):", result["commit_history"][:20])
print("commit_history (last 20):", result["commit_history"][-20:])
print("replication_counts:", result["replication_counts"])
print("latencies:", result["latencies"])
print("committed_flags:", result["committed_flags"])
print("final_tick:", result["final_tick"])
print()
# Verify committed entries had strict majority replication
maj_violations = 0
for idx, l in enumerate(result["latencies"]):
    if l is not None:
        rc = result["replication_counts"][idx]
        if rc <= sim.n // 2:
            maj_violations += 1
            print(f"!! entry {idx+1} committed but only replicated on {rc} nodes (<= N/2)")
print(f"majority_violations: {maj_violations}")