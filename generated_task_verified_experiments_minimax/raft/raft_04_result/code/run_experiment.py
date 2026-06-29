"""
Run the Raft failover experiment across >= 10 seeds and persist raw results.
"""
import json
import statistics
from raft_sim import run_one


def main():
    seeds = list(range(10))
    n = 5
    pre_kill = 100
    post_kill = 100
    election_timeout_range = (20, 40)

    results = []
    for seed in seeds:
        r = run_one(
            seed=seed,
            n=n,
            election_timeout_range=election_timeout_range,
            pre_kill_entries=pre_kill,
            post_kill_entries=post_kill,
            verbose=False,
        )
        results.append(r)
        print(f"seed={seed} latency={r.get('detection_reelection_latency_ticks')} "
              f"post_rate={r.get('post_commit_rate')} survived={r.get('pre_fault_survived')}")

    # Aggregate
    latencies = [r["detection_reelection_latency_ticks"] for r in results
                 if r.get("detection_reelection_latency_ticks") is not None]
    rates = [r["post_commit_rate"] for r in results]
    survived = [bool(r["pre_fault_survived"]) for r in results]
    kill_leaders = [r["killed_leader"] for r in results]
    new_leaders = [r["new_leader"] for r in results]

    summary = {
        "n": n,
        "election_timeout_range": list(election_timeout_range),
        "pre_kill_entries": pre_kill,
        "post_kill_entries": post_kill,
        "num_seeds": len(seeds),
        "per_seed": results,
        "aggregate": {
            "latency_ticks": {
                "mean": statistics.mean(latencies),
                "median": statistics.median(latencies),
                "max": max(latencies),
                "min": min(latencies),
                "stdev": statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
                "values": latencies,
            },
            "post_commit_rate": {
                "mean": statistics.mean(rates),
                "min": min(rates),
                "max": max(rates),
                "values": rates,
            },
            "pre_fault_survived": {
                "all_survived": all(survived),
                "count_true": sum(survived),
                "count_total": len(survived),
            },
            "killed_leader_distribution": {
                str(k): kill_leaders.count(k) for k in sorted(set(kill_leaders))
            },
            "new_leader_distribution": {
                str(k): new_leaders.count(k) for k in sorted(set(new_leaders))
            },
        },
    }
    with open("results_raft_04_failover.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print("\nWrote results_raft_04_failover.json")
    print(json.dumps(summary["aggregate"], indent=2, default=str))


if __name__ == "__main__":
    main()
