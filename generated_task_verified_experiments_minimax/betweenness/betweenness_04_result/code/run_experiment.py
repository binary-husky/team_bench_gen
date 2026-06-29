"""
Sampling-based betweenness centrality experiment.

Compares approximate betweenness (using Brandes sampling via
nx.betweenness_centrality(G, k=K)) against exact betweenness
(nx.betweenness_centrality(G, k=None)) on a fixed medium-sized
random graph.

For each K in {10, 50, 100, 500, min(n,2000)}:
  * repeat with >= 5 different random seeds (sampling pivot endpoints)
  * record wall-clock runtime, max abs error and L1 error vs exact
"""

import json
import time
from statistics import mean, stdev

import numpy as np
import networkx as nx


GRAPH_N = 1000           # ~1e3 nodes (medium size, fast exact)
GRAPH_P = 0.05           # density (sparse but comfortably connected for n=1000)
GRAPH_SEED = 42          # graph-generation seed (fixed)

N_SEEDS = 7              # >= 5 different sampling seeds per K
SAMPLE_SEEDS = list(range(1, N_SEEDS + 1))

OUT_JSON = "results.json"


def build_graph() -> nx.Graph:
    """Build a single fixed random connected undirected graph."""
    g = nx.erdos_renyi_graph(GRAPH_N, GRAPH_P, seed=GRAPH_SEED)
    if not nx.is_connected(g):
        # Fall back to giant component if the random draw is disconnected.
        cc = max(nx.connected_components(g), key=len)
        g = g.subgraph(cc).copy()
        g = nx.convert_node_labels_to_integers(g)
    return g


def main() -> None:
    G = build_graph()
    n = G.number_of_nodes()
    m = G.number_of_edges()
    print(f"Graph: n={n}, m={m}, avg_deg={2*m/n:.2f}, "
          f"connected={nx.is_connected(G)}", flush=True)

    # ----- exact ground truth -----
    t0 = time.perf_counter()
    bc_exact = nx.betweenness_centrality(G, k=None, normalized=True)
    t_exact = time.perf_counter() - t0
    exact_vec = np.array([bc_exact[v] for v in G.nodes()], dtype=float)
    print(f"Exact (k=None) finished in {t_exact:.3f}s", flush=True)

    K_grid = [10, 50, 100, 500, min(n, 2000)]
    print(f"K grid: {K_grid}", flush=True)

    results = []
    for K in K_grid:
        per_seed = []
        for s in SAMPLE_SEEDS:
            t0 = time.perf_counter()
            bc_appr = nx.betweenness_centrality(
                G, k=K, normalized=True, seed=s
            )
            elapsed = time.perf_counter() - t0
            appr_vec = np.array(
                [bc_appr[v] for v in G.nodes()], dtype=float
            )
            err_max = float(np.max(np.abs(exact_vec - appr_vec)))
            err_l1 = float(np.sum(np.abs(exact_vec - appr_vec)))
            err_l1_mean = float(np.mean(np.abs(exact_vec - appr_vec)))
            per_seed.append(dict(
                seed=s,
                runtime=elapsed,
                err_max=err_max,
                err_l1=err_l1,
                err_l1_mean=err_l1_mean,
            ))
            print(f"  K={K:<5} seed={s} runtime={elapsed:.4f}s "
                  f"max|err|={err_max:.5f} L1={err_l1:.5f}", flush=True)

        max_errs = [r["err_max"] for r in per_seed]
        l1_errs = [r["err_l1"] for r in per_seed]
        l1m_errs = [r["err_l1_mean"] for r in per_seed]
        runtimes = [r["runtime"] for r in per_seed]
        agg = dict(
            K=K,
            n_seeds=len(per_seed),
            err_max_mean=mean(max_errs),
            err_max_std=stdev(max_errs),
            err_l1_mean=mean(l1_errs),
            err_l1_std=stdev(l1_errs),
            err_l1mean_mean=mean(l1m_errs),
            err_l1mean_std=stdev(l1m_errs),
            runtime_mean=mean(runtimes),
            runtime_std=stdev(runtimes),
            runtime_median=median(runtimes),
            speedup_vs_exact=t_exact / mean(runtimes),
            per_seed=per_seed,
        )
        results.append(agg)

    summary = dict(
        graph=dict(n=n, m=m, p=GRAPH_P, seed=GRAPH_SEED),
        exact_runtime=t_exact,
        n_seeds=N_SEEDS,
        K_grid=K_grid,
        results=results,
    )
    with open(OUT_JSON, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote {OUT_JSON}", flush=True)


def median(xs):
    s = sorted(xs)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return 0.5 * (s[n // 2 - 1] + s[n // 2])


if __name__ == "__main__":
    main()