"""
Louvain community detection on LFR benchmark graphs of varying size.

Investigates how community count, modularity, size distribution, and
Gini coefficient of community sizes change as the network grows.

LFR parameters (fixed):
  tau1=3, tau2=1.5, mu=0.4, average_degree=6, min_community=20, seed=0
Variable: n in {500, 1000, 2000, 4000}
"""
import json
import time

import community.community_louvain as community_louvain
import networkx as nx


def gini(values):
    """Compute the Gini coefficient of a non-negative list of values."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    s = sum(sorted_vals)
    if s == 0:
        return 0.0
    cumulative = 0.0
    for i, v in enumerate(sorted_vals, start=1):
        cumulative += i * v
    return (2.0 * cumulative) / (n * s) - (n + 1) / n


def main():
    results = {}
    sizes_record = {}
    for n in (500, 1000, 2000, 4000):
        print(f"\n=== n = {n} ===")
        t0 = time.perf_counter()
        G = nx.LFR_benchmark_graph(
            n=n,
            tau1=3,
            tau2=1.5,
            mu=0.4,
            average_degree=6,
            min_community=20,
            seed=0,
        )
        gen_time = time.perf_counter() - t0
        print(f"  LFR generated in {gen_time:.2f}s: "
              f"{G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

        # Drop any ground-truth community attribute that may leak from LFR.
        for _, d in G.nodes(data=True):
            d.pop("community", None)

        # Run Louvain
        t0 = time.perf_counter()
        partition = community_louvain.best_partition(G, random_state=0)
        louvain_time = time.perf_counter() - t0
        Q = community_louvain.modularity(partition, G)
        communities = set(partition.values())
        num_comms = len(communities)

        # Community sizes sorted descending
        size_counts = {}
        for c in communities:
            size_counts[c] = sum(1 for v in partition.values() if v == c)
        sizes_sorted = sorted(size_counts.values(), reverse=True)
        g = gini(sizes_sorted)
        gini_normalized = g * n / (n - 1) if n > 1 else 0.0

        results[n] = {
            "num_communities": num_comms,
            "modularity": Q,
            "gini": g,
            "gini_normalized": gini_normalized,
            "louvain_time_s": louvain_time,
            "gen_time_s": gen_time,
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "max_community_size": sizes_sorted[0],
            "min_community_size": sizes_sorted[-1],
            "median_community_size": sizes_sorted[len(sizes_sorted) // 2],
            "size_top5": sizes_sorted[:5],
            "size_bottom5": sizes_sorted[-5:],
            "n_communities_ge_20": sum(1 for s in sizes_sorted if s >= 20),
            "n_communities_lt_20": sum(1 for s in sizes_sorted if s < 20),
        }
        sizes_record[n] = sizes_sorted

        print(f"  Louvain in {louvain_time:.2f}s -> "
              f"k={num_comms}, Q={Q:.4f}, "
              f"max={sizes_sorted[0]}, min={sizes_sorted[-1]}, "
              f"Gini={g:.4f}")

    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)
    with open("community_sizes.json", "w") as f:
        json.dump(sizes_record, f)

    print("\nDone. Wrote results.json and community_sizes.json.")


if __name__ == "__main__":
    main()