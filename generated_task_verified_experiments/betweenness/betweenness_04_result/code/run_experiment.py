"""
Experiment: sampling-approximate betweenness centrality vs exact.

NetworkX betweenness_centrality(G, k=K) implements the sampling approximation of
Brandes' algorithm: it runs the single-source shortest-path dependency
accumulation for only K uniformly-sampled source nodes (distinct, w/o
replacement) instead of all n, and rescales by n/k so the result is an
*unbiased* estimator of the exact normalized BC. We verify empirically that:
  (1) the estimator is unbiased (mean over seeds ~ exact),
  (2) approximation error decays ~ 1/sqrt(K)  (K x4 -> error ~ /2),
  (3) small K gives large speedup (time ~ K BFS passes instead of n),
and pick a practical tradeoff K.

Fixed setup (do not change):
  - Graph: Barabasi-Albert(3000, 3), seed=42, largest connected component.
  - Exact:   betweenness_centrality(G, k=None, normalized=True)
  - Approx:  betweenness_centrality(G, k=K, normalized=True, seed=s)
             K in {10,50,100,500,min(n,2000)}, >=5 seeds.
Whole run << 30 min, CPU only.
"""
import json
import time

import numpy as np
import networkx as nx


def spearman(a, b):
    """Spearman rank correlation of two equal-length arrays (no scipy needed)."""
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean(); rb -= rb.mean()
    denom = np.sqrt((ra @ ra) * (rb @ rb))
    return float((ra @ rb) / denom) if denom > 0 else 0.0


def topk_overlap(a, b, k):
    """Fraction of the top-k (by value) of `a` that also appear in top-k of `b`."""
    ia = set(np.argsort(a)[::-1][:k])
    ib = set(np.argsort(b)[::-1][:k])
    return len(ia & ib) / k


# ----------------------------------------------------------------------
# 0. Fixed baseline graph
# ----------------------------------------------------------------------
N_GRAPH = 3000
G = nx.barabasi_albert_graph(N_GRAPH, 3, seed=42)
G = max((G.subgraph(c) for c in nx.connected_components(G)), key=len).copy()
n = G.number_of_nodes(); m = G.number_of_edges()
nodes = list(G.nodes())
print(f"Graph: BA(3000,3) largest CC -> n={n}, m={m}, avg_deg={2*m/n:.2f}")

K_GRID = [10, 50, 100, 500, min(n, 2000)]
SEEDS = [101, 202, 303, 404, 505, 606, 707]      # 7 seeds (>=5)
NREPS = len(SEEDS)

# ----------------------------------------------------------------------
# 1. EXACT betweenness (all n sources)
# ----------------------------------------------------------------------
t0 = time.perf_counter()
bc_exact = nx.betweenness_centrality(G, k=None, normalized=True)
t_exact = time.perf_counter() - t0
ex = np.array([bc_exact[v] for v in nodes])
print(f"\nExact BC (k=None, all {n} sources): time={t_exact:.2f}s")
print(f"  sum(BC_exact)={ex.sum():.4f}  max={ex.max():.4f}  mean={ex.mean():.4e}")

# ----------------------------------------------------------------------
# 2. APPROXIMATE betweenness over the K grid, repeated over seeds
# ----------------------------------------------------------------------
results = {}
for K in K_GRID:
    emax, el1, ermse, rt, esp, etop = [], [], [], [], [], []
    bias_mean = []                       # mean over nodes of (approx - exact)
    for s in SEEDS:
        t0 = time.perf_counter()
        bc = nx.betweenness_centrality(G, k=K, normalized=True, seed=s)
        dt = time.perf_counter() - t0
        ap = np.array([bc[v] for v in nodes])
        d = ap - ex
        emax.append(np.max(np.abs(d)))
        el1.append(np.sum(np.abs(d)))
        ermse.append(np.sqrt(np.mean(d ** 2)))
        rt.append(dt)
        esp.append(spearman(ap, ex))
        etop.append(topk_overlap(ap, ex, 20))
        bias_mean.append(np.mean(d))
    r = {
        "nrep": NREPS,
        "err_max_mean": float(np.mean(emax)),  "err_max_std": float(np.std(emax, ddof=1)),
        "err_l1_mean": float(np.mean(el1)),    "err_l1_std": float(np.std(el1, ddof=1)),
        "err_rmse_mean": float(np.mean(ermse)),"err_rmse_std": float(np.std(ermse, ddof=1)),
        "spearman_mean": float(np.mean(esp)),  "spearman_std": float(np.std(esp, ddof=1)),
        "top20_mean": float(np.mean(etop)),    "top20_std": float(np.std(etop, ddof=1)),
        "bias_mean": float(np.mean(bias_mean)),
        "time_mean": float(np.mean(rt)),       "time_std": float(np.std(rt, ddof=1)),
        "time_exact": float(t_exact),
        "speedup_mean": float(t_exact / np.mean(rt)),
    }
    results[K] = r
    print(f"K={K:5d}: max|err|={r['err_max_mean']:.3e}+/-{r['err_max_std']:.0e}  "
          f"RMSE={r['err_rmse_mean']:.3e}  spearman={r['spearman_mean']:.4f}  "
          f"top20={r['top20_mean']:.2f}  time={r['time_mean']:.2f}s  "
          f"speedup={r['speedup_mean']:.0f}x  bias={r['bias_mean']:+.1e}")

# ----------------------------------------------------------------------
# 3. Fit error ~ c / sqrt(K)  (over the small/mid-K sampling regime)
# ----------------------------------------------------------------------
ks = np.array([K for K in K_GRID if K < n], dtype=float)
emax_mean = np.array([results[K]["err_max_mean"] for K in K_GRID if K < n])
# log-log linear fit of max|err| vs K  -> slope expected ~ -0.5
slope, intercept = np.polyfit(np.log(ks), np.log(emax_mean), 1)
c = float(np.exp(intercept))
pred_at_K = c / np.sqrt(ks)
r2 = 1 - np.sum((emax_mean - pred_at_K) ** 2) / np.sum((emax_mean - emax_mean.mean()) ** 2)
print(f"\nFit err_max ~ c/sqrt(K): exponent={slope:.3f} (expect -0.5), c={c:.3f}, R^2={r2:.4f}")
print(f"  Check error*sqrt(K) const: " +
      ", ".join(f"{K}:{results[K]['err_max_mean']*K**0.5:.3f}" for K in K_GRID if K < n))

# ----------------------------------------------------------------------
# 4. Save
# ----------------------------------------------------------------------
out = {
    "graph": {"generator": "barabasi_albert_graph(3000,3,seed=42) largest CC",
              "n": int(n), "m": int(m), "avg_deg": float(2*m/n)},
    "networkx_version": nx.__version__,
    "exact_time_s": float(t_exact),
    "sum_bc_exact": float(ex.sum()), "max_bc_exact": float(ex.max()),
    "seeds": SEEDS, "k_grid": K_GRID,
    "fit_err_vs_K": {"exponent": float(slope), "c": c, "R2": float(r2)},
    "results": {str(k): v for k, v in results.items()},
}
with open("results.json", "w") as fh:
    json.dump(out, fh, indent=2)
print("\nSaved results.json")
