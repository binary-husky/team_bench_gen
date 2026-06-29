"""
Graph Coloring SAT Experiment
==============================
For random G(n, p) graphs, encode "k-colorable" as CNF and use PySAT's
MiniSAT to determine the chromatic number χ(G) by scanning k = 1, 2, 3, ...
until first SAT. Record conflicts and time for each (n, k).

Encoding (for a graph G=(V,E) and k colors 1..k):
  Variable x_{v,c}  for v in V, c in 1..k   (1-indexed for the SAT solver)
  - At-least-one color per vertex:        (x_{v,1} ∨ x_{v,2} ∨ ... ∨ x_{v,k})
  - At-most-one color per vertex:         (¬x_{v,c1} ∨ ¬x_{v,c2})  for c1 < c2
  - Adjacent-vertices differ:             (¬x_{u,c} ∨ ¬x_{v,c})    for (u,v) in E, c in 1..k

The at-most-one per vertex is technically redundant (the edge-inequality
plus at-least-one is enough), but in practice it dramatically prunes the
search space and makes the solver much faster.
"""

import random
import time
import csv
from itertools import combinations

import networkx as nx
from pysat.solvers import Minisat22


# ---------------------------------------------------------------------------
# CNF encoding
# ---------------------------------------------------------------------------
def var_index(v, c, n):
    """Variable x_{v,c} in 1..n*k.  v and c are 0-indexed here."""
    return v * k_of(n) + c + 1


# We use a small wrapper so var_index has access to k.  Cleaner: rebuild per k.
def build_cnf(G, k):
    """Return (cnf_clauses, n_vars) encoding 'G is k-colorable'."""
    n = G.number_of_nodes()
    nodes = sorted(G.nodes())
    # variable id:  x_{v,c}  =  v*k + c + 1   (v,c 0-indexed)
    def vid(v, c):
        return v * k + c + 1

    clauses = []

    # (1) At-least-one color per vertex
    for v in nodes:
        clauses.append([vid(v, c) for c in range(k)])

    # (2) At-most-one color per vertex (pairwise)
    if k >= 2:
        for v in nodes:
            for c1, c2 in combinations(range(k), 2):
                clauses.append([-vid(v, c1), -vid(v, c2)])

    # (3) Adjacent vertices differ on every color
    for u, v in G.edges():
        for c in range(k):
            clauses.append([-vid(u, c), -vid(v, c)])

    return clauses, n * k


# ---------------------------------------------------------------------------
# Single solve with conflict/time measurement
# ---------------------------------------------------------------------------
def solve_k(G, k, timeout_s=60.0):
    clauses, nvars = build_cnf(G, k)
    solver = Minisat22(bootstrap_with=clauses)

    t0 = time.perf_counter()
    sat = solver.solve()
    elapsed = time.perf_counter() - t0

    conflicts = solver.accum_stats()['conflicts'] if hasattr(solver, 'accum_stats') else None
    # newer pysat: use solver.statistics or solver.conflicts
    if conflicts is None:
        try:
            conflicts = solver.conflicts
        except Exception:
            conflicts = None

    solver.delete()
    return sat, elapsed, conflicts, nvars, len(clauses)


# ---------------------------------------------------------------------------
# Scan k = 1, 2, ... until first SAT -> recover χ(G)
# ---------------------------------------------------------------------------
def chromatic_number(G, kmax=20, timeout_s=30.0):
    rows = []
    chi = None
    for k in range(1, kmax + 1):
        sat, elapsed, conflicts, nvars, nclauses = solve_k(G, k, timeout_s=timeout_s)
        rows.append({
            'k': k,
            'sat': bool(sat),
            'time_s': elapsed,
            'conflicts': conflicts,
            'n_vars': nvars,
            'n_clauses': nclauses,
        })
        if sat:
            chi = k
            break
        if elapsed > timeout_s:
            # give up on this graph to keep the experiment bounded
            rows[-1]['timeout'] = True
            break
    return chi, rows


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------
def main():
    ns = [10, 15, 20]
    p = 0.5
    seeds = [1, 2, 3, 4, 5, 6, 7, 8]            # 8 seeds per n
    per_call_timeout = 20.0

    all_rows = []
    chi_summary = []

    for n in ns:
        for seed in seeds:
            rng = random.Random(seed * 1000 + n)
            G = nx.gnp_random_graph(n, p, seed=seed)
            # Force relabel to 0..n-1 in case
            G = nx.convert_node_labels_to_integers(G)
            chi, rows = chromatic_number(G, kmax=n + 2, timeout_s=per_call_timeout)
            for r in rows:
                r['n'] = n
                r['p'] = p
                r['seed'] = seed
            all_rows.extend(rows)
            chi_summary.append({'n': n, 'p': p, 'seed': seed, 'chi': chi,
                                'rows_collected': len(rows)})
            print(f"n={n:2d} seed={seed:2d}  χ={chi}  rows={len(rows)}")

    # Persist
    with open('raw_results.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['n', 'p', 'seed', 'k', 'sat',
                                          'time_s', 'conflicts',
                                          'n_vars', 'n_clauses'])
        w.writeheader()
        for r in all_rows:
            w.writerow(r)
    with open('chi_summary.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['n', 'p', 'seed', 'chi', 'rows_collected'])
        w.writeheader()
        for r in chi_summary:
            w.writerow(r)
    print('Wrote raw_results.csv and chi_summary.csv')


if __name__ == '__main__':
    main()
