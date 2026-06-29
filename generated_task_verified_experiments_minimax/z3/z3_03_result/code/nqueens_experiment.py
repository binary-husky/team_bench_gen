"""
N-Queens scaling experiment using z3-solver.

Encoding (fixed across all N):
  - One Int per row: Q[i], with domain [0, N-1] (column index, 0-based).
  - Column uniqueness: Distinct(Q[0], Q[1], ..., Q[N-1]).
  - Diagonal uniqueness: for all i < j, Q[i] - Q[j] != i - j
                          and Q[i] - Q[j] != j - i
    (equivalently |Q[i] - Q[j]| != |i - j|).

Solver settings (fixed):
  - Solver(): default tactics/configuration of z3 4.16.
  - timeout = 120_000 ms.
  - Fixed random seed for any randomness (z3.set_param('smt.random_seed', ...)).

Variable under study: N.
"""

import time
import json
import sys
import statistics

import z3

# Fixed solver settings ----------------------------------------------------
TIMEOUT_MS = 120_000          # 120 s, as instructed
RANDOM_SEED = 1234

# Apply global parameters once
z3.set_param("smt.random_seed", RANDOM_SEED)
z3.set_param("timeout", TIMEOUT_MS)


def build_nqueens(N: int):
    """Build the z3 formula encoding the N-Queens problem."""
    Q = [z3.Int(f"Q_{i}") for i in range(N)]
    s = z3.Solver()

    # Domain: each Q[i] in [0, N-1]
    for q in Q:
        s.add(q >= 0, q <= N - 1)

    # Columns: all distinct
    s.add(z3.Distinct(Q))

    # Diagonals: no two queens share a diagonal
    for i in range(N):
        for j in range(i + 1, N):
            d = j - i  # |i - j| (constant, i < j)
            s.add(Q[i] - Q[j] != d)
            s.add(Q[i] - Q[j] != -d)

    return s, Q


def solve_first(N: int):
    """Solve N-Queens and return (elapsed_seconds, result_kind, solution_or_None)."""
    solver, Q = build_nqueens(N)
    t0 = time.perf_counter()
    result = solver.check()
    elapsed = time.perf_counter() - t0

    if result == z3.sat:
        model = solver.model()
        sol = [model.eval(q).as_long() for q in Q]
        return elapsed, "sat", sol
    elif result == z3.unsat:
        return elapsed, "unsat", None
    else:  # unknown (timeout)
        return elapsed, "unknown", None


def verify_solution(N: int, sol) -> bool:
    """Independently sanity-check a reported solution."""
    if sol is None or len(sol) != N:
        return False
    if any(c < 0 or c >= N for c in sol):
        return False
    if len(set(sol)) != N:
        return False
    for i in range(N):
        for j in range(i + 1, N):
            if abs(sol[i] - sol[j]) == abs(i - j):
                return False
    return True


def main():
    sizes = [8, 10, 12, 15, 20]
    raw = []
    for N in sizes:
        elapsed, kind, sol = solve_first(N)
        ok = verify_solution(N, sol) if kind == "sat" else (kind == "unsat")
        raw.append(
            {
                "N": N,
                "result": kind,
                "time_s": elapsed,
                "solution_valid": ok,
                "solution": sol,
            }
        )
        # Print progress line as we go
        print(
            f"N={N:>2}  result={kind:<7}  time={elapsed:8.4f} s  valid={ok}",
            flush=True,
        )

    # JSON dump for downstream use
    with open("nqueens_results.json", "w") as f:
        json.dump(raw, f, indent=2)

    return raw


if __name__ == "__main__":
    main()
