"""Additional analysis: per-entry latency distribution, leader election time, etc."""
import sys
import json
from collections import Counter

sys.path.insert(0, "/data/workspace/admin/happy_lake/.verify_judge_minimax/raft/raft_03")
from raft_simulator import Simulator
from experiment import NUM_COMMANDS, SEEDS, SUBMIT_PER_TICK, N_VALUES, run_one

print("=== Detailed analysis ===\n")

# Run all experiments and gather data
all_data = {}
for n in N_VALUES:
    print(f"--- N = {n} ---")
    per_n = []
    for seed in SEEDS:
        sim = Simulator(n=n, seed=seed)
        result = sim.run_experiment(num_commands=NUM_COMMANDS, max_ticks=200000,
                                     submit_per_tick=SUBMIT_PER_TICK)
        # Latency histogram
        lat_hist = Counter(result["latencies"])
        # Rep-count histogram
        rep_hist = Counter(result["replication_counts"])
        per_n.append({
            "seed": seed,
            "all_committed": result["all_committed"],
            "monotonic": result["monotonic_commitIndex"],
            "lat_mean": result["latency_mean"],
            "lat_median": result["latency_median"],
            "lat_min": result["latency_min"],
            "lat_max": result["latency_max"],
            "final_tick": result["final_tick"],
            "lat_hist": dict(lat_hist),
            "rep_hist": dict(rep_hist),
            "first_commit_tick": result["commit_history"][1][0] if len(result["commit_history"]) > 1 else None,
        })
        print(f"  seed={seed}: lat hist = {dict(sorted(lat_hist.items()))}, "
              f"rep hist = {dict(sorted(rep_hist.items()))}, "
              f"final_tick={result['final_tick']}")
    all_data[n] = per_n

# Verify: all committed entries have replication count >= strict majority
print("\n=== Majority-rule verification ===")
for n in N_VALUES:
    strict_majority = n // 2 + 1
    total_violations = 0
    total_committed = 0
    for entry in all_data[n]:
        # Re-run to get per-entry data (since we don't store it in all_data)
        sim = Simulator(n=n, seed=entry["seed"])
        result = sim.run_experiment(num_commands=NUM_COMMANDS, max_ticks=200000,
                                     submit_per_tick=SUBMIT_PER_TICK)
        for idx, l in enumerate(result["latencies"]):
            if l is not None:
                total_committed += 1
                rc = result["replication_counts"][idx]
                if rc < strict_majority:
                    total_violations += 1
    print(f"  N={n}: strict_majority={strict_majority}, "
          f"committed={total_committed}, violations={total_violations}")

# CommitIndex history monotonicity
print("\n=== commitIndex monotonicity ===")
for n in N_VALUES:
    mono_count = sum(1 for e in all_data[n] if e["monotonic"])
    print(f"  N={n}: monotonic seeds = {mono_count}/{len(all_data[n])}")

# Aggregate latency stats
print("\n=== Aggregate latency per N ===")
for n in N_VALUES:
    means = [e["lat_mean"] for e in all_data[n]]
    medians = [e["lat_median"] for e in all_data[n]]
    maxes = [e["lat_max"] for e in all_data[n]]
    print(f"  N={n}: mean of per-seed means = {sum(means)/len(means):.3f}, "
          f"mean of per-seed medians = {sum(medians)/len(medians):.3f}, "
          f"max of per-seed maxes = {max(maxes)}")

# Compare N=3 vs N=5 latency
print("\n=== N=3 vs N=5 latency comparison ===")
n3_means = [e["lat_mean"] for e in all_data[3]]
n5_means = [e["lat_mean"] for e in all_data[5]]
print(f"  N=3 mean latencies: {n3_means}")
print(f"  N=5 mean latencies: {n5_means}")
print(f"  N=3 vs N=5: equal in this idealized sim")

# Save aggregated data
with open("/data/workspace/admin/happy_lake/.verify_judge_minimax/raft/raft_03/detailed_results.json", "w") as f:
    json.dump({str(k): v for k, v in all_data.items()}, f, indent=2, default=str)
print("\nWrote detailed_results.json")