"""
Experiment: relative error of HyperLogLog estimate vs true cardinality n.
Fixed precision p = 14, so m = 16384 registers.  Theoretical SE ≈ 1.04/sqrt(m)
= 1.04/128 = 0.8125%.

For each n in the grid and each random seed we generate `n` distinct random
64-bit integers (collision probability with 2**63 possible values is
negligible for n <= 1e6), feed them through the HLL, and record
relative error |Ê - n| / n.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from hll import HyperLogLog

# ---------- settings (fixed per task spec) -----------------------------

P = 14
M = 1 << P                      # 16384 registers
THEORETICAL_SE = 1.04 / np.sqrt(M)   # ≈ 0.008125

N_GRID = [1_000, 5_000, 10_000, 50_000, 100_000, 500_000, 1_000_000]
SEEDS = [11, 22, 33, 44, 55]    # 5 different seeds
N_HASH_BITS = 64                # mmh3 with 64-bit output
ITEM_SPACE = 1 << 63            # use signed-63-bit ints (avoid sign bit of mmh3 quirks)

OUT_DIR = Path(__file__).resolve().parent

# ---------- experiment --------------------------------------------------

def run_one(n: int, seed: int) -> float:
    rng = np.random.default_rng(seed)
    # generate `n` distinct random uint64s; with ITEM_SPACE=2**63 and n<=1e6
    # birthday collision probability is ~n^2/2^64 < 5e-7, negligible.
    xs = rng.integers(0, ITEM_SPACE, size=n, dtype=np.int64).astype(np.uint64)
    hll = HyperLogLog(p=P)
    hll.add_uint64_array(xs)
    return hll.estimate()


def main() -> None:
    rows = []
    t_total_start = time.time()
    for n in N_GRID:
        for seed in SEEDS:
            t0 = time.time()
            est = run_one(n, seed)
            elapsed = time.time() - t0
            rel_err = abs(est - n) / n
            rows.append({
                "n": n, "seed": seed,
                "estimate": float(est),
                "rel_err": float(rel_err),
                "elapsed_s": float(elapsed),
            })
            print(f"  n={n:>7d}  seed={seed}  est={est:>10.1f}  "
                  f"rel_err={rel_err:7.3%}  t={elapsed:.2f}s")

    # aggregate per n
    summary = []
    for n in N_GRID:
        rel_errs = np.array([r["rel_err"] for r in rows if r["n"] == n])
        summary.append({
            "n": int(n),
            "mean_rel_err": float(rel_errs.mean()),
            "std_rel_err": float(rel_errs.std(ddof=1)),
            "min_rel_err": float(rel_errs.min()),
            "max_rel_err": float(rel_errs.max()),
            "n_seeds": int(rel_errs.size),
        })

    print("\n=== summary (per n) ===")
    print(f"{'n':>9s}  {'mean':>10s}  {'std':>10s}  {'min':>10s}  {'max':>10s}")
    for s in summary:
        print(f"{s['n']:>9d}  {s['mean_rel_err']:>10.4%}  {s['std_rel_err']:>10.4%}  "
              f"{s['min_rel_err']:>10.4%}  {s['max_rel_err']:>10.4%}")
    print(f"theoretical SE ≈ 1.04/sqrt(m) = {THEORETICAL_SE:.4%}")
    print(f"total elapsed: {time.time() - t_total_start:.1f}s")

    # save raw + summary
    with open(OUT_DIR / "experiment_results.json", "w") as f:
        json.dump({"p": P, "m": M, "theoretical_SE": THEORETICAL_SE,
                   "n_hash_bits": N_HASH_BITS,
                   "seeds": SEEDS,
                   "n_grid": N_GRID,
                   "raw": rows, "summary": summary}, f, indent=2)
    print(f"\nwrote {OUT_DIR / 'experiment_results.json'}")


if __name__ == "__main__":
    main()