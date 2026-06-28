#!/usr/bin/env python3
"""N-Queens scaling with z3-solver.

Encoding: one Int per row, domain 1..N (column index).
Constraints:
  - all columns distinct (Distinct over the column vars)
  - all (row - col) distinct  (anti-diagonal uniqueness)
  - all (row + col) distinct  (main-diagonal uniqueness)
Solver settings fixed across all N. We find the FIRST solution (sat).
Timeout: 120 seconds per instance.
"""

import time
import z3

TIMEOUT_MS = 120 * 1000  # 120 seconds


def build_model(N):
    cols = [z3.Int(f"c_{r}") for r in range(N)]
    s = z3.Solver()
    # fixed solver settings
    s.set("timeout", TIMEOUT_MS)
    # random_seed for reproducibility (affects restart/split heuristic)
    s.set("random_seed", 1)

    for c in cols:
        s.add(c >= 1, c <= N)

    # distinct columns
    s.add(z3.Distinct(cols))

    # distinct diagonals: (row - col) and (row + col) must all differ
    diag1 = [z3.Int(f"d1_{r}") for r in range(N)]  # row - col
    diag2 = [z3.Int(f"d2_{r}") for r in range(N)]  # row + col
    for r in range(N):
        s.add(diag1[r] == r - cols[r])
        s.add(diag2[r] == r + cols[r])
    s.add(z3.Distinct(diag1))
    s.add(z3.Distinct(diag2))

    return s, cols


def solve_one(N):
    s, cols = build_model(N)
    t0 = time.time()
    res = s.check()
    elapsed = time.time() - t0
    status = str(res)
    sol = None
    if res == z3.sat:
        m = s.model()
        sol = [m[c].as_long() for c in cols]
    return status, elapsed, sol


def main():
    Ns = [8, 10, 12, 15, 20]
    print(f"{'N':>4} | {'status':<10} | {'time_s':>10} | solution")
    print("-" * 70)
    results = []
    for N in Ns:
        status, t, sol = solve_one(N)
        soldisp = sol if (sol and N <= 12) else (sol if sol else "—")
        print(f"{N:>4} | {status:<10} | {t:>10.4f} | {soldisp}")
        results.append((N, status, t, sol))
    print()
    print("=== JSON ===")
    import json
    out = [{"N": N, "status": st, "time_s": round(t, 4),
            "sol": sol if sol is not None else None} for N, st, t, sol in results]
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
