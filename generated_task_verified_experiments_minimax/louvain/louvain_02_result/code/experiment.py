"""
Convergence experiment for the Louvain method.

For each pass (dendrogram level) of `generate_dendrogram`, we project the
hierarchical partition back to the original nodes with `partition_at_level`,
compute modularity on the original graph, count communities, and record
the per-level Q and #communities to study how the algorithm converges.
"""
import json
import sys

import networkx as nx
import community.community_louvain as community_louvain


def main():
    # --- Build the LFR benchmark graph (fixed parameters, seed=0) -----------
    G = nx.LFR_benchmark_graph(
        n=1000,
        tau1=3,
        tau2=1.5,
        mu=0.4,
        average_degree=6,
        min_community=20,
        seed=0,
    )
    G = nx.convert_node_labels_to_integers(G)  # plain int ids, easier later
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    print(f"Graph: nodes={n_nodes} edges={n_edges}", flush=True)

    # --- Run the full dendrogram (one run -> entire pass sequence) ----------
    dendrogram = community_louvain.generate_dendrogram(
        G,
        random_state=0,
    )
    n_levels = len(dendrogram)
    print(f"Number of passes (dendrogram levels): {n_levels}", flush=True)

    # --- Per-level modularity and #communities ------------------------------
    per_pass = []
    for level in range(n_levels):
        partition = community_louvain.partition_at_level(dendrogram, level)
        n_communities = len(set(partition.values()))
        # The Louvain hierarchy can have ties: Q is not strictly monotonic
        # across passes, so we record the true value at each level.
        Q = community_louvain.modularity(partition, G)
        per_pass.append(
            {
                "pass_index": level,  # 0 == after the first pass
                "n_communities": n_communities,
                "Q": Q,
            }
        )
        print(
            f"  pass {level}: #communities={n_communities:4d}  Q={Q:.6f}",
            flush=True,
        )

    # --- Convergence diagnostics --------------------------------------------
    # By construction each pass decreases the number of meta-communities.
    # Q is generally non-decreasing in the first few passes and then plateaus
    # (sometimes with a tiny dip caused by ordering of local moves).
    Qs = [p["Q"] for p in per_pass]
    Cs = [p["n_communities"] for p in per_pass]
    deltas_Q = [Qs[i + 1] - Qs[i] for i in range(len(Qs) - 1)]
    deltas_C = [Cs[i + 1] - Cs[i] for i in range(len(Cs) - 1)]

    # Find the pass at which Q peaks.  Ties: take the first.
    best_pass = max(range(len(Qs)), key=lambda i: Qs[i])
    best_Q = Qs[best_pass]

    # Converged when neither Q nor #communities change any more.
    final_pass = n_levels - 1
    for i in range(n_levels - 1, -1, -1):
        if any(c != Cs[i] for c in Cs[i:]) or any(
            abs(q - Qs[i]) > 1e-12 for q in Qs[i:]
        ):
            converged_at = i
            break
    else:
        converged_at = 0

    summary = {
        "graph": {
            "n": n_nodes,
            "m": n_edges,
            "params": {
                "n": 1000,
                "tau1": 3,
                "tau2": 1.5,
                "mu": 0.4,
                "average_degree": 6,
                "min_community": 20,
                "seed": 0,
            },
        },
        "total_passes": n_levels,
        "best_pass_index": best_pass,
        "best_Q": best_Q,
        "final_Q": Qs[-1],
        "final_n_communities": Cs[-1],
        "per_pass": per_pass,
        "delta_Q_between_passes": deltas_Q,
        "delta_n_communities_between_passes": deltas_C,
    }

    with open("results.json", "w") as f:
        json.dump(summary, f, indent=2, default=float)
    print("\nWrote results.json", flush=True)
    print(f"Best Q={best_Q:.6f} at pass {best_pass}; final Q={Qs[-1]:.6f}", flush=True)


if __name__ == "__main__":
    main()
