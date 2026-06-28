#!/usr/bin/env python3
"""N-Queens scaling with z3-solver: repeated runs for stable timing."""
import time
import statistics
import z3

TIMEOUT_MS = 120 * 1000
REPEATS = 5


def build_and_solve(N):
    cols = [z3.Int(f"c_{r}") for r in range(N)]
    s = z3.Solver()
    s.set("timeout", TIMEOUT_MS)
    s.set("random_seed", 1)
    for c in cols:
        s.add(c >= 1, c <= N)
    s.add(z3.Distinct(cols))
    diag1 = [r - cols[r] for r in range(N)]
    diag2 = [r + cols[r] for r in range(N)]
    s.add(z3.Distinct(diag1))
    s.add(z3.Distinct(diag2))
    t0 = time.time()
    res = s.check()
    elapsed = time.time() - t0
    sol = None
    if res == z3.sat:
        m = s.model()
        sol = [m[c].as_long() for c in cols]
    return str(res), elapsed, sol


def main():
    Ns = [8, 10, 12, 15, 20]
    print(f"{'N':>4} | {'status':<6} | {'median_s':>10} | {'min_s':>10} | {'max_s':>10} | runs")
    print("-" * 80)
    rows = []
    for N in Ns:
        times = []
        status = None
        sol = None
        for _ in range(REPEATS):
            st, t, s_ = build_and_solve(N)
            status = st
            sol = s_
            times.append(t)
        med = statistics.median(times)
        print(f"{N:>4} | {status:<6} | {med:>10.4f} | {min(times):>10.4f} | "
              f"{max(times):>10.4f} | {[round(x,4) for x in times]}")
        rows.append((N, status, round(med, 4), round(min(times), 4),
                     round(max(times), 4), sol))
    print()
    print("Median timings (seconds) used for the report:")
    for N, st, med, mn, mx, _ in rows:
        print(f"  N={N:>2}: {med} s  (min {mn}, max {mx}, {st})")
    print()
    print("Solutions (first run, fixed seed=1):")
    for N, st, med, mn, mx, sol in rows:
        print(f"  N={N:>2}: {sol}")


if __name__ == "__main__":
    main()
