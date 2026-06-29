"""Full experiment for raft_03: log replication & commit across N=3 and N=5.

For each (N, seed), runs:
1. Bootstrap: elect a leader with reasonable timeout parameters.
2. Submit 1000 client commands to the leader.
3. Record per-entry: replication count, commit status, commit latency, and
   verify commitIndex monotonicity.

Reports aggregated stats across seeds.
"""

import sys
import time
import json
from statistics import mean, median

sys.path.insert(0, "/data/workspace/admin/happy_lake/.verify_judge_minimax/raft/raft_03")
from raft_simulator import Simulator

NUM_COMMANDS = 1000
SEEDS = [1, 2, 3, 4, 5, 6, 7, 8]  # 8 seeds (>5 required)
SUBMIT_PER_TICK = 50  # submit many per tick to drive traffic; not too high to avoid mailbox overflow
N_VALUES = [3, 5]


def run_one(n, seed):
    """Run one (n, seed) experiment and return result dict."""
    sim = Simulator(n=n, seed=seed)
    result = sim.run_experiment(
        num_commands=NUM_COMMANDS,
        max_ticks=200000,
        submit_per_tick=SUBMIT_PER_TICK,
    )
    return result


def aggregate(results):
    """Aggregate per-seed results into summary stats."""
    n_seeds = len(results)
    all_committed_count = sum(1 for r in results if r["all_committed"])
    monotonic_count = sum(1 for r in results if r["monotonic_commitIndex"])

    # Per-seed mean/median/max latency (over committed entries)
    means = []
    medians = []
    maxes = []
    mins = []
    for r in results:
        if r["latency_mean"] is not None:
            means.append(r["latency_mean"])
            medians.append(r["latency_median"])
            maxes.append(r["latency_max"])
            mins.append(r["latency_min"])

    # Strict-majority check: for every committed entry, was the replication count >= strict majority?
    violation_count = 0
    for r in results:
        n = r["n"]
        strict_majority = n // 2 + 1
        for idx, l in enumerate(r["latencies"]):
            if l is not None:
                rc = r["replication_counts"][idx]
                if rc < strict_majority:
                    violation_count += 1
    return {
        "n_seeds": n_seeds,
        "all_committed_seeds": all_committed_count,
        "monotonic_seeds": monotonic_count,
        "latency_mean_of_means": mean(means) if means else None,
        "latency_mean_of_medians": mean(medians) if medians else None,
        "latency_median_of_means": median(means) if means else None,
        "latency_median_of_medians": median(medians) if medians else None,
        "latency_mean_of_maxes": mean(maxes) if maxes else None,
        "latency_max_of_maxes": max(maxes) if maxes else None,
        "latency_min_of_mins": min(mins) if mins else None,
        "majority_violations": violation_count,
        "per_seed_means": means,
        "per_seed_medians": medians,
        "per_seed_maxes": maxes,
    }


def main():
    overall_start = time.time()
    print(f"=== raft_03 experiment ===")
    print(f"NUM_COMMANDS={NUM_COMMANDS}, SEEDS={SEEDS}, N_VALUES={N_VALUES}")
    print(f"SUBMIT_PER_TICK={SUBMIT_PER_TICK}")
    print()

    summary = {}
    for n in N_VALUES:
        print(f"--- N = {n} ---")
        results = []
        for seed in SEEDS:
            t0 = time.time()
            result = run_one(n, seed)
            elapsed = time.time() - t0
            ok = "OK" if result["all_committed"] else "FAIL"
            mono = "MONO" if result["monotonic_commitIndex"] else "NON-MONO"
            print(f"  N={n} seed={seed} [{ok}/{mono}] "
                  f"lat mean/med/max = "
                  f"{result['latency_mean']:.2f}/{result['latency_median']}/{result['latency_max']} "
                  f"final_tick={result['final_tick']} elapsed={elapsed:.2f}s")
            results.append(result)
        agg = aggregate(results)
        summary[n] = {"per_seed": results, "aggregate": agg}
        print(f"  AGG n={n}: all_committed={agg['all_committed_seeds']}/{agg['n_seeds']} "
              f"monotonic={agg['monotonic_seeds']}/{agg['n_seeds']} "
              f"mean_lat_of_means={agg['latency_mean_of_means']:.2f} "
              f"mean_lat_of_medians={agg['latency_mean_of_medians']:.2f} "
              f"max_of_maxes={agg['latency_max_of_maxes']} "
              f"violations={agg['majority_violations']}")

    overall_elapsed = time.time() - overall_start
    print(f"\nTotal elapsed: {overall_elapsed:.2f}s")

    # Save raw results for the report
    raw_out = {
        "num_commands": NUM_COMMANDS,
        "seeds": SEEDS,
        "submit_per_tick": SUBMIT_PER_TICK,
        "summary": {
            str(n): {
                "aggregate": summary[n]["aggregate"],
                "per_seed": [
                    {
                        "seed": SEEDS[i],
                        "all_committed": summary[n]["per_seed"][i]["all_committed"],
                        "monotonic_commitIndex": summary[n]["per_seed"][i]["monotonic_commitIndex"],
                        "latency_mean": summary[n]["per_seed"][i]["latency_mean"],
                        "latency_median": summary[n]["per_seed"][i]["latency_median"],
                        "latency_max": summary[n]["per_seed"][i]["latency_max"],
                        "latency_min": summary[n]["per_seed"][i]["latency_min"],
                        "committed_count": summary[n]["per_seed"][i]["committed_count"],
                        "final_tick": summary[n]["per_seed"][i]["final_tick"],
                        "commit_history_len": summary[n]["per_seed"][i]["commit_history_len"],
                    }
                    for i in range(len(SEEDS))
                ],
            }
            for n in N_VALUES
        },
    }
    with open("/data/workspace/admin/happy_lake/.verify_judge_minimax/raft/raft_03/raw_results.json", "w") as f:
        json.dump(raw_out, f, indent=2)
    print("Wrote raw_results.json")

    return summary


if __name__ == "__main__":
    main()