"""
Experiment: Compare symbolic execution vs. random fuzzing on a target function
with a deep / rare branch.

Target function g(x) has an accumulated guard chain:
    if x > 100 and x % 7 == 3 and x % 11 == 4 and x % 13 == 5 and x * 2 < 1000:
        return "TARGET"
The probability mass of inputs that reach TARGET in [0, 10^9] is ~1e-6.
"""

import random
import time
from z3 import *


# ------------------------------------------------------------
# 1.  Target function with deep "needle" branch.
# ------------------------------------------------------------
def g(x: int) -> str:
    """Return 'TARGET' iff the deep branch is hit, else 'no'."""
    if x > 100:
        if x % 7 == 3:
            if x % 11 == 4:
                if x % 13 == 5:
                    if x * 2 < 1000:
                        return "TARGET"
    return "no"


# ------------------------------------------------------------
# 2.  Symbolic execution with z3.
#     We accumulate the path constraints along the deep
#     "true" path and ask z3 for one satisfying model.
# ------------------------------------------------------------
def symbolic_execute():
    x = Int("x")
    s = Solver()

    # Walk the path constraints that lead to TARGET
    s.add(x > 100)         # guard 1
    s.add(x % 7 == 3)      # guard 2
    s.add(x % 11 == 4)      # guard 3
    s.add(x % 13 == 5)      # guard 4
    s.add(x * 2 < 1000)     # guard 5 (i.e. x < 500)

    queries = 1
    t0 = time.time()
    res = s.check()        # a single z3 query
    t1 = time.time()
    if res == sat:
        m = s.model()
        return True, queries, m[x].as_long(), (t1 - t0)
    else:
        return False, queries, None, (t1 - t0)


# ------------------------------------------------------------
# 3.  Random fuzzing.
# ------------------------------------------------------------
def random_fuzz(N: int, seed: int, lo: int = 0, hi: int = 10 ** 9):
    rng = random.Random(seed)
    hits = 0
    t0 = time.time()
    for _ in range(N):
        x = rng.randint(lo, hi)
        if g(x) == "TARGET":
            hits += 1
    t1 = time.time()
    return hits, N, (t1 - t0)


# ------------------------------------------------------------
# 4.  Run experiments.
# ------------------------------------------------------------
if __name__ == "__main__":
    SEEDS = [1, 2, 3, 4, 5]
    NS = [10 ** 3, 10 ** 4, 10 ** 5]

    print("=" * 60)
    print("Symbolic execution (z3) -- one PC, one query per run")
    print("=" * 60)
    sym_rows = []
    for seed in SEEDS:
        found, queries, val, dt = symbolic_execute()
        sym_rows.append((seed, found, queries, val, dt))
        print(f"  seed={seed}  found={found}  z3_queries={queries}  "
              f"x={val}  t={dt*1000:.2f} ms")

    print()
    print("=" * 60)
    print("Random fuzzing -- try N uniformly-random ints in [0, 10^9]")
    print("=" * 60)
    fuzz_rows = []
    for N in NS:
        print(f"\n--- N = {N:,} ---")
        for seed in SEEDS:
            hits, total, dt = random_fuzz(N, seed)
            rate = hits / total
            fuzz_rows.append((N, seed, hits, total, rate, dt))
            print(f"  seed={seed}  hits={hits}/{total}  "
                  f"hit_rate={rate:.6f}  t={dt:.3f} s")
