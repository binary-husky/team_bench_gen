#!/usr/bin/env python3
"""Graph coloring difficulty via SAT (MiniSAT) experiment.

For each random graph G(n,p) with n in {10,15,20}, p=0.5, several seeds,
encode "is G k-colorable" as CNF and scan k=1,2,3,... until first SAT,
giving the chromatic number chi(G). Record conflicts and wall time per k.
"""
import time
import json
import statistics
import networkx as nx
from pysat.formula import CNF
from pysat.solvers import Solver

NS = [10, 15, 20]
P = 0.5
SEEDS = [1, 2, 3, 4, 5]
SOLVER = "minisat22"
K_MAX = 12  # safety cap; chi for G(n,0.5) is small (<= ~n/(2 log2 n) region)


def build_cnf(graph, k):
    """k-colorability CNF.

    var x_{v,c} = 1 + v*k + c  (v in 0..n-1, c in 0..k-1)
    clauses:
      (1) each vertex >=1 color: OR_c x_{v,c}
      (2) adjacent vertices differ: for edge (u,v), for each c: -x_{u,c} v -x_{v,c}
    """
    cnf = CNF()
    n = graph.number_of_nodes()
    nodes = list(range(n))
    idx = {v: v for v in nodes}  # node label -> 0..n-1
    def var(v, c):
        return 1 + idx[v] * k + c

    for v in nodes:
        cnf.append([var(v, c) for c in range(k)])  # at least one color
    for u, w in graph.edges():
        u, w = idx[u], idx[w]
        for c in range(k):
            cnf.append([-var(u, c), -var(w, c)])  # no two adjacent same color
    return cnf


def solve_k(graph, k):
    cnf = build_cnf(graph, k)
    t0 = time.perf_counter()
    with Solver(name=SOLVER, bootstrap_with=cnf.clauses) as s:
        sat = s.solve()
        stats = s.accum_stats()
    dt = time.perf_counter() - t0
    return sat, stats.get("conflicts", 0), dt, cnf.nv, len(cnf.clauses)


def main():
    results = []
    for n in NS:
        for seed in SEEDS:
            g = nx.gnp_random_graph(n, P, seed=seed)
            g = nx.Graph(g)
            g.remove_edges_from(nx.selfloop_edges(g))
            # ensure simple graph, nodes 0..n-1
            chi = None
            per_k = []
            for k in range(1, K_MAX + 1):
                sat, conflicts, dt, nvars, nclauses = solve_k(g, k)
                per_k.append({
                    "k": k,
                    "sat": sat,
                    "conflicts": conflicts,
                    "time_s": dt,
                    "n_vars": nvars,
                    "n_clauses": nclauses,
                })
                if sat and chi is None:
                    chi = k
                    break  # first SAT -> chi; stop (per task: "until first SAT")
            results.append({
                "n": n, "p": P, "seed": seed,
                "num_edges": g.number_of_edges(),
                "chi": chi,
                "scan": per_k,
            })
            print(f"n={n} seed={seed} edges={g.number_of_edges()} chi={chi} | "
                  f"k={per_k[-1]['k']}({'SAT' if per_k[-1]['sat'] else 'UNSAT'}) "
                  f"conf={per_k[-1]['conflicts']} t={per_k[-1]['time_s']:.4f}s")

    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nWrote results.json")

    # Aggregate summary
    print("\n=== Aggregate by n ===")
    for n in NS:
        rs = [r for r in results if r["n"] == n]
        chis = [r["chi"] for r in rs]
        print(f"n={n}: chi values {chis} mean={statistics.mean(chis):.2f}")

    # Hardest k analysis: for each graph, find the UNSAT k just below chi (k=chi-1)
    # that's the hardest. Show conflicts at k=chi-1 (UNSAT) vs k=chi (SAT).
    print("\n=== Difficulty near chi (per graph) ===")
    for r in results:
        chi = r["chi"]
        scan = {p["k"]: p for p in r["scan"]}
        if chi - 1 in scan:
            uns = scan[chi - 1]
            sat = scan[chi]
            print(f"n={r['n']} seed={r['seed']} chi={chi}: "
                  f"k={chi-1}(UNSAT) conf={uns['conflicts']} t={uns['time_s']:.4f}s  |  "
                  f"k={chi}(SAT) conf={sat['conflicts']} t={sat['time_s']:.4f}s")


if __name__ == "__main__":
    main()
