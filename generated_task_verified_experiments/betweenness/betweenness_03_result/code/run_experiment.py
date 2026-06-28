"""
Betweenness centrality runtime study: Brandes O(nm) vs naive O(n^2(n+m)).

- Brandes: NetworkX `betweenness_centrality` (normalized=False, unweighted).
- Naive:   all-pairs BFS (dist + sigma path-counts), then for every unordered
           pair (s,t) and every node v accumulate sigma_st(v)/sigma_st using the
           identity sigma_st(v) = sigma_s[v]*sigma_t[v]  (valid when
           d(s,v)+d(v,t)=d(s,t)).  This is the per-pair, per-node accumulation
           that Brandes replaces with its single backward delta sweep; it has no
           Brandes trick and is Theta(n^2(n+m)) = Theta(n^3) for m=Theta(n).
"""
import json
import math
import time
from collections import deque

import networkx as nx
import numpy as np

C = 8                 # target average degree  -> m ~ 4n  (m = Theta(n))
SEEDS = [1, 2, 3]
NAIVE_CAP = 120.0     # ~2 min per naive point (task guideline)
BRANDES_GRID = [200, 500, 1000, 2000]
NAIVE_GRID = [100, 200, 300, 500]   # small sizes: clean power-law fit
NAIVE_TRY_LARGE = [1000]            # attempt with cap; else extrapolate


# --------------------------------------------------------------------------- #
# graph generation
# --------------------------------------------------------------------------- #
def make_graph(n, seed, c=C):
    """Connected G(n,p) with avg degree ~ c. Relabel to 0..n-1."""
    p = c / (n - 1)
    s = seed
    while True:
        G = nx.fast_gnp_random_graph(n, p, seed=s)
        if nx.is_connected(G):
            return G
        s += 7919


def adj_list(G, n):
    adj = [[] for _ in range(n)]
    for u, v in G.edges():
        adj[u].append(v)
        adj[v].append(u)
    return adj


# --------------------------------------------------------------------------- #
# naive betweenness
# --------------------------------------------------------------------------- #
def bfs_sigma(adj, src, n):
    """BFS from src -> (dist[], sigma[]) where sigma[w]=#shortest src->w paths."""
    dist = [-1] * n
    sigma = [0] * n
    dist[src] = 0
    sigma[src] = 1
    dq = deque([src])
    while dq:
        u = dq.popleft()
        du = dist[u]
        su = sigma[u]
        for w in adj[u]:
            if dist[w] < 0:
                dist[w] = du + 1
                sigma[w] = su
                dq.append(w)
            elif dist[w] == du + 1:
                sigma[w] += su
    return dist, sigma


def naive_betweenness(adj, n, cap=None):
    """Theta(n^2(n+m)). Returns (bc_list, elapsed) or (None, elapsed) on timeout."""
    t0 = time.perf_counter()
    DIST = [None] * n
    SIG = [None] * n
    for s in range(n):
        d, sg = bfs_sigma(adj, s, n)
        DIST[s] = d
        SIG[s] = sg
    bc = [0.0] * n
    for s in range(n):
        ds = DIST[s]
        ss = SIG[s]
        for t in range(s + 1, n):
            ds_t = ds[t]
            if ds_t < 0:
                continue
            sig_st = ss[t]
            dt = DIST[t]
            st = SIG[t]
            # inner v-loop: the expensive O(n) per pair
            for v in range(n):
                if v == s or v == t:
                    continue
                if ds[v] + dt[v] == ds_t:
                    bc[v] += ss[v] * st[v] / sig_st
        if cap is not None and (time.perf_counter() - t0) > cap:
            return None, time.perf_counter() - t0
    return bc, time.perf_counter() - t0


# --------------------------------------------------------------------------- #
# correctness check
# --------------------------------------------------------------------------- #
def correctness_check():
    max_err = 0.0
    for n in [10, 20, 40]:
        for seed in [1, 2, 3]:
            G = make_graph(n, seed)
            adj = adj_list(G, n)
            bc_naive, _ = naive_betweenness(adj, n)
            bc_nx = nx.betweenness_centrality(G, normalized=False)
            for v in range(n):
                max_err = max(max_err, abs(bc_naive[v] - bc_nx[v]))
    print(f"[correctness] max |naive - NetworkX| over small graphs = {max_err:.3e}")
    assert max_err < 1e-6, "naive does not match NetworkX!"
    return max_err


# --------------------------------------------------------------------------- #
# timing
# --------------------------------------------------------------------------- #
def time_brandes(G):
    t0 = time.perf_counter()
    nx.betweenness_centrality(G, normalized=False)
    return time.perf_counter() - t0


def run():
    correctness_check()

    results = {"brandes": {}, "naive": {}, "meta": {
        "C": C, "seeds": SEEDS, "naive_cap": NAIVE_CAP,
        "brandes_grid": BRANDES_GRID, "naive_grid": NAIVE_GRID,
        "naive_try_large": NAIVE_TRY_LARGE,
    }}

    # ---- Brandes over main grid ----
    for n in BRANDES_GRID:
        ts, ms = [], []
        for seed in SEEDS:
            G = make_graph(n, seed)
            ts.append(time_brandes(G))
            ms.append(G.number_of_edges())
        med_t = float(np.median(ts))
        med_m = int(np.median(ms))
        results["brandes"][n] = {"times": ts, "median": med_t,
                                 "m_median": med_m, "n": n}
        print(f"[brandes] n={n:5d}  m={med_m:6d}  nm={n*med_m:9d}  "
              f"t_med={med_t:8.3f}s")

    # ---- Naive over small grid (full, 3 seeds) ----
    for n in NAIVE_GRID:
        ts, ms = [], []
        for seed in SEEDS:
            G = make_graph(n, seed)
            adj = adj_list(G, n)
            bc, dt = naive_betweenness(adj, n, cap=NAIVE_CAP)
            ts.append(dt)
            ms.append(G.number_of_edges())
        med_t = float(np.median(ts))
        med_m = int(np.median(ms))
        results["naive"][n] = {"times": ts, "median": med_t,
                               "m_median": med_m, "n": n, "timed_out": False}
        print(f"[naive]   n={n:5d}  m={med_m:6d}  nm={n*med_m:9d}  "
              f"t_med={med_t:8.3f}s")

    # ---- Naive attempt at larger n with cap (1 seed: just probing feasibility) ----
    for n in NAIVE_TRY_LARGE:
        ts, ms = [], []
        timed_out = False
        for seed in SEEDS[:1]:           # single probe to bound wall-clock
            G = make_graph(n, seed)
            adj = adj_list(G, n)
            bc, dt = naive_betweenness(adj, n, cap=NAIVE_CAP)
            ts.append(dt)
            ms.append(G.number_of_edges())
            if bc is None:
                timed_out = True
        med_t = float(np.median(ts))
        med_m = int(np.median(ms))
        results["naive"][n] = {"times": ts, "median": med_t,
                               "m_median": med_m, "n": n, "timed_out": timed_out}
        tag = "TIMEOUT" if timed_out else "ok"
        print(f"[naive]   n={n:5d}  m={med_m:6d}  nm={n*med_m:9d}  "
              f"t_med={med_t:8.3f}s  [{tag}]")

    # ---- extrapolate naive to remaining main-grid sizes if missing ----
    ns = sorted(results["naive"].keys())
    log_ns = np.log(np.array(ns, float))
    log_ts = np.log(np.array([results["naive"][n]["median"] for n in ns]))
    slope, intercept = np.polyfit(log_ns, log_ts, 1)
    results["naive_fit"] = {"slope_vs_n": float(slope),
                            "intercept": float(intercept),
                            "fitted_on": ns}
    print(f"[naive fit] log t vs log n  slope={slope:.3f}  "
          f"(=> t ~ n^{slope:.2f})")

    for n in BRANDES_GRID:
        if n not in results["naive"]:
            extrap = float(math.exp(intercept) * n ** slope)
            results["naive"][n] = {"median": extrap, "n": n,
                                   "timed_out": True, "extrapolated": True,
                                   "m_median": results["brandes"][n]["m_median"]}
            print(f"[naive extrap] n={n:5d}  t~{extrap:9.1f}s (infeasible)")

    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n[saved] results.json")
    return results


if __name__ == "__main__":
    run()
