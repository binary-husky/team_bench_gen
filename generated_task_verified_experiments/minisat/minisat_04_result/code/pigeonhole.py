#!/usr/bin/env python3
"""Pigeonhole-principle CNF experiment with PySAT MiniSAT.

PHP_n: n+1 pigeons into n holes.
  - each pigeon enters at least one hole  (positive clause over its vars)
  - each hole holds at most one pigeon    (pairwise binary negative clauses)
The formula is always UNSAT.

Fixed: PHP encoding, n in {3,4,5,6,7}, solver = MiniSAT (minisat22).
Sole independent variable: n.
Record conflicts and wall time per n.
"""
import time
from pysat.formula import CNF
from pysat.solvers import Solver

SOLVER = "minisat22"
NS = [3, 4, 5, 6, 7]


def build_php(n):
    """Build CNF for PHP_n: n+1 pigeons, n holes."""
    cnf = CNF()
    npigeons = n + 1

    def var(i, j):
        # pigeon i (1-indexed), hole j (1-indexed) -> variable id (1-indexed)
        return (i - 1) * n + j

    # (1) each pigeon in at least one hole
    for i in range(1, npigeons + 1):
        cnf.append([var(i, j) for j in range(1, n + 1)])

    # (2) each hole at most one pigeon (pairwise mutual exclusion)
    for j in range(1, n + 1):
        for i1 in range(1, npigeons + 1):
            for i2 in range(i1 + 1, npigeons + 1):
                cnf.append([-var(i1, j), -var(i2, j)])
    return cnf


def run(n):
    cnf = build_php(n)
    n_vars = cnf.nv
    n_clauses = len(cnf.clauses)
    t0 = time.perf_counter()
    with Solver(name=SOLVER, bootstrap_with=cnf.clauses) as s:
        sat = s.solve()
        stats = s.accum_stats()
    elapsed = time.perf_counter() - t0
    return {
        "n": n,
        "pigeons": n + 1,
        "holes": n,
        "vars": n_vars,
        "clauses": n_clauses,
        "sat": sat,
        "conflicts": stats.get("conflicts", -1),
        "decisions": stats.get("decisions", -1),
        "propagations": stats.get("propagations", -1),
        "time": elapsed,
    }


def main():
    rows = []
    print(f"{'n':>3} {'pigeons':>7} {'holes':>5} {'vars':>6} {'clauses':>8} "
          f"{'conflicts':>10} {'decisions':>10} {'props':>12} {'time_s':>10} {'sat':>5}")
    for n in NS:
        r = run(n)
        rows.append(r)
        print(f"{r['n']:>3} {r['pigeons']:>7} {r['holes']:>5} {r['vars']:>6} "
              f"{r['clauses']:>8} {r['conflicts']:>10} {r['decisions']:>10} "
              f"{r['propagations']:>12} {r['time']:>10.4f} {str(r['sat']):>5}")
    # save machine-readable
    import json
    with open("pigeonhole_results.json", "w") as f:
        json.dump(rows, f, indent=2)
    return rows


if __name__ == "__main__":
    main()
