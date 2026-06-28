#!/usr/bin/env python3
"""Re-run sims, collect per-entry commit latencies, and produce a figure."""
import statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from raft_sim import Sim, SEEDS, NUM_COMMANDS


def collect_latencies(n):
    per_seed = []
    for seed in SEEDS:
        sim = Sim(n, seed)
        sim.run()
        lats = []
        for idx in range(1, NUM_COMMANDS + 1):
            if idx in sim.commit_tick and idx in sim.append_tick:
                lats.append(sim.commit_tick[idx] - sim.append_tick[idx])
        per_seed.append(lats)
    # pool across seeds
    pooled = [x for sub in per_seed for x in sub]
    return pooled, per_seed


def main():
    lat3, _ = collect_latencies(3)
    lat5, _ = collect_latencies(5)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, lats, n in [(axes[0], lat3, 3), (axes[1], lat5, 5)]:
        ax.hist(lats, bins=range(min(lats), max(lats) + 2),
                edgecolor="black", color="#4C72B0", align="left", rwidth=0.85)
        ax.set_title(f"N={n}  (mean={statistics.mean(lats):.2f} ticks, "
                     f"median={statistics.median(lats)}, max={max(lats)})")
        ax.set_xlabel("commit latency (logical ticks)")
        ax.set_ylabel("count of entries (out of 5000 = 5 seeds x 1000)")
        ax.set_xticks(range(min(lats), max(lats) + 1))
    fig.suptitle("Raft AppendEntries commit latency distribution (1000 entries x 5 seeds)")
    fig.tight_layout()
    fig.savefig("latency_dist.png", dpi=110)
    print("wrote latency_dist.png")

    # also dump a tiny CSV of pooled stats for the summary table
    with open("latency_stats.csv", "w") as f:
        f.write("n,mean,median,max,min,stdev,count\n")
        for n, lats in [(3, lat3), (5, lat5)]:
            f.write(f"{n},{statistics.mean(lats):.3f},{statistics.median(lats)},"
                    f"{max(lats)},{min(lats)},{statistics.pstdev(lats):.3f},{len(lats)}\n")
    print("wrote latency_stats.csv")


if __name__ == "__main__":
    main()
