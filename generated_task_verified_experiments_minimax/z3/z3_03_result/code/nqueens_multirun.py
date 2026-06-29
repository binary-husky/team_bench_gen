"""
Repeated runs of N-Queens to characterize the timing distribution.
Same encoding as nqueens_experiment.py, but we run each N several times
under different random seeds so we can see whether "first solution"
timing is seed-dependent (i.e. how much variance there is in finding
"the first" solution vs. finding *a* solution).

The primary experiment (one fixed seed) is in nqueens_experiment.py;
this script provides complementary statistics.
"""

import time
import json
import z3

TIMEOUT_MS = 120_000


def build_nqueens(N: int):
    Q = [z3.Int(f"Q_{i}") for i in range(N)]
    s = z3.Solver()
    for q in Q:
        s.add(q >= 0, q <= N - 1)
    s.add(z3.Distinct(Q))
    for i in range(N):
        for j in range(i + 1, N):
            d = j - i
            s.add(Q[i] - Q[j] != d)
            s.add(Q[i] - Q[j] != -d)
    return s, Q


def run_once(N: int, seed: int):
    z3.set_param("smt.random_seed", seed)
    z3.set_param("timeout", TIMEOUT_MS)
    solver, Q = build_nqueens(N)
    t0 = time.perf_counter()
    result = solver.check()
    elapsed = time.perf_counter() - t0
    return result, elapsed


def main():
    sizes = [8, 10, 12, 15, 20]
    n_repeats = 10
    seeds = [11, 23, 37, 53, 71, 97, 123, 257, 509, 1024]

    aggregated = []
    for N in sizes:
        runs = []
        for s in seeds:
            res, t = run_once(N, s)
            assert res == z3.sat, f"unexpected result for N={N} seed={s}: {res}"
            runs.append(t)
        aggregated.append(
            {
                "N": N,
                "repeats": n_repeats,
                "times_s": runs,
                "min_s": min(runs),
                "median_s": sorted(runs)[n_repeats // 2],
                "mean_s": sum(runs) / len(runs),
                "max_s": max(runs),
            }
        )
        a = aggregated[-1]
        print(
            f"N={N:>2}  min={a['min_s']:7.4f}s  median={a['median_s']:7.4f}s  "
            f"mean={a['mean_s']:7.4f}s  max={a['max_s']:7.4f}s"
        )

    with open("nqueens_multirun.json", "w") as f:
        json.dump(aggregated, f, indent=2)


if __name__ == "__main__":
    main()
