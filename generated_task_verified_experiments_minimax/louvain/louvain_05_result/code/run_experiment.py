"""
Experiment: study how the Louvain resolution parameter γ affects the
granularity of community detection on an LFR benchmark graph.

Graph parameters (fixed):
    n = 1000, tau1 = 3, tau2 = 1.5, mu = 0.4,
    average_degree = 6, min_community = 20, seed = 0

Independent variable: resolution γ ∈ {0.5, 1.0, 1.5, 2.0}

For each γ we record:
    - number of communities (#C)
    - average community size (mean |c|, computed as n / #C)
    - standard modularity Q (computed with γ = 1.0 formula, so partitions are
      comparable on the same modularity scale).
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

import community as community_louvain   # python-louvain
import networkx as nx


HERE = Path(__file__).resolve().parent
RESULTS_PATH = HERE / "results.json"


# ---------------------------------------------------------------------------
# Modularity helpers
# ---------------------------------------------------------------------------
def standard_modularity(G: nx.Graph, partition: dict[int, int]) -> float:
    """Standard Newman-Girvan modularity (γ = 1).

    Q = (1/(2m)) Σ_ij [ A_ij - (k_i k_j)/(2m) ] δ(c_i, c_j)

    Computed directly so the resolution used during optimisation does not bias
    the reported Q value.
    """
    if G.is_multigraph():
        A_ij = {(u, v): d for u, v, d in G.edges(data=True)}
        # for multigraph we need to weight by multiplicity
        # use sum of weights if 'weight' present, otherwise count edges
        weight = None
        if any("weight" in d for _, _, d in G.edges(data=True)):
            weight = {(u, v): d.get("weight", 1) for u, v, d in G.edges(data=True)}
    else:
        A_ij = {(u, v): 1 for u, v in G.edges()}
        weight = None

    # multigraph handling
    if G.is_multigraph():
        # each parallel edge counts once toward adjacency (use weight sum)
        if weight is None:
            weight = {(u, v): 1 for u, v in G.edges()}
        # convert multigraph adjacency to a single weight sum per unordered pair
        deg = {}
        weighted_adj: dict[tuple, float] = {}
        for (u, v), w in weight.items():
            a, b = (u, v) if u <= v else (v, u)
            weighted_adj[(a, b)] = weighted_adj.get((a, b), 0.0) + w
            deg[u] = deg.get(u, 0) + w
            deg[v] = deg.get(v, 0) + w
        two_m = 2.0 * sum(weighted_adj.values())
        if two_m == 0:
            return 0.0
        Q = 0.0
        # group nodes by community
        comm: dict[int, list] = {}
        for n, c in partition.items():
            comm.setdefault(c, []).append(n)
        for nodes in comm.values():
            # L_c = sum of weights of edges with both ends in nodes
            # R_c = sum of degrees of nodes in nodes
            L_c = 0.0
            for i in nodes:
                for j in nodes:
                    if i <= j:
                        w = weighted_adj.get((i, j), 0.0)
                        if i == j:
                            L_c += w
                        else:
                            L_c += 2 * w  # (i,j) and (j,i) both contribute
            R_c = sum(deg[i] for i in nodes)
            Q += L_c / two_m - (R_c / two_m) ** 2
        return Q

    # simple graph
    deg = dict(G.degree())
    m = G.number_of_edges()
    if m == 0:
        return 0.0
    two_m = 2.0 * m

    # group nodes by community
    comm: dict[int, list] = {}
    for n, c in partition.items():
        comm.setdefault(c, []).append(n)

    Q = 0.0
    for nodes in comm.values():
        # L_c: number of edges inside the community (counted twice for Q formula)
        L_c = 0.0
        for i in nodes:
            for j in G.neighbors(i):
                if partition.get(j) == partition[i] and j >= i:
                    # only count each edge once when i<=j
                    pass
            # easier: just count edges inside the community once
        # simpler implementation: iterate edge list once
        L_c = 0.0
        node_set = set(nodes)
        for u, v in G.edges():
            if u in node_set and v in node_set:
                L_c += 1
        R_c = sum(deg[i] for i in nodes)
        Q += L_c / m - (R_c / two_m) ** 2
    return Q


# ---------------------------------------------------------------------------
# Experiment
# ---------------------------------------------------------------------------
def build_lfr_graph() -> nx.Graph:
    return nx.LFR_benchmark_graph(
        n=1000,
        tau1=3.0,
        tau2=1.5,
        mu=0.4,
        average_degree=6,
        min_community=20,
        seed=0,
    )


def run():
    # Make sure both random number generators are reproducible.
    random.seed(0)
    G = build_lfr_graph()
    # python-louvain expects a simple Graph; LFR returns a simple Graph here.

    print(f"Graph: |V|={G.number_of_nodes()}, |E|={G.number_of_edges()}")
    print(f"Is multigraph: {G.is_multigraph()}")

    gammas = [0.5, 1.0, 1.5, 2.0]
    results = []
    for gamma in gammas:
        # Same seed for every run so the only varying factor is γ.
        partition = community_louvain.best_partition(
            G, random_state=0, resolution=gamma
        )
        counts = Counter(partition.values())
        n_comms = len(counts)
        sizes = list(counts.values())
        avg_size = sum(sizes) / n_comms
        Q = standard_modularity(G, partition)
        Q_lib = community_louvain.modularity(partition, G)  # sanity check
        results.append(
            {
                "gamma": gamma,
                "n_communities": n_comms,
                "avg_community_size": avg_size,
                "modularity_Q_standard": Q,
                "modularity_Q_python_louvain": Q_lib,
                "min_size": min(sizes),
                "max_size": max(sizes),
                "median_size": sorted(sizes)[len(sizes) // 2],
            }
        )
        print(
            f"γ={gamma:.2f} | #C={n_comms:3d} | "
            f"avg|C|={avg_size:7.2f} | "
            f"min={min(sizes):3d} | max={max(sizes):3d} | "
            f"Q_std={Q:.4f} | Q_lib={Q_lib:.4f}"
        )

    RESULTS_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {RESULTS_PATH}")
    return results


if __name__ == "__main__":
    run()
