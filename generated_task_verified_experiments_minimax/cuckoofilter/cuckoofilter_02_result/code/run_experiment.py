"""
Experiment: false-positive rate of a cuckoo filter vs. fingerprint size f.

Fixed:  b = 4
        M = 2^19 = 524288  (large enough so f=4 still inserts everything
                            at modest load; see notes in summary)
        N = 200_000         (items 0..N-1 inserted; N..2N-1 queried)
Vary:   f ∈ {4, 8, 12, 16}
        20 seeds per f

Theory (Fan et al. 2014, §5.1, Eq. 5):
    FPR(f)  ≈  1 - (1 - 1/2^f)^(2 b) ≈ 2b / 2^f        (worst case, α=1)
    With load α:  FPR(f, α) ≈ 1 - (1 - 1/2^f)^(2 b α)
"""

import time
import csv
import os
from cuckoo_filter import CuckooFilter

# ---- fixed settings ---------------------------------------------------
B = 4                  # bucket size
M = 1 << 19           # 524288 buckets  (2^19)
N = 200_000           # items inserted; same # of non-members queried
F_VALUES = [4, 8, 12, 16]
SEEDS = list(range(1, 21))           # 20 seeds
MAX_KICKS = 500
OUT_DIR = "/data/workspace/admin/happy_lake/.verify_judge_minimax/cuckoofilter/cuckoofilter_02"

# ---- pre-compute query keys (independent of seed) ---------------------
INSERT_KEYS = list(range(N))
QUERY_KEYS = list(range(N, 2 * N))


def run_one(f_bits, seed):
    """Build filter, insert INSERT_KEYS, query QUERY_KEYS, return stats."""
    cf = CuckooFilter(M=M, b=B, f_bits=f_bits, seed=seed, max_kicks=MAX_KICKS)

    t0 = time.perf_counter()
    inserted = 0
    failures = 0
    for k in INSERT_KEYS:
        if cf.insert(k):
            inserted += 1
        else:
            failures += 1
    t_insert = time.perf_counter() - t0

    load = inserted / (M * B)

    t0 = time.perf_counter()
    fp = 0
    for k in QUERY_KEYS:
        if cf.lookup(k):
            fp += 1
    t_query = time.perf_counter() - t0

    return {
        "f": f_bits,
        "seed": seed,
        "inserted": inserted,
        "failures": failures,
        "load": load,
        "false_positives": fp,
        "fpr": fp / N,
        "t_insert": t_insert,
        "t_query": t_query,
    }


def main():
    print(f"b={B}, M={M}, N={N}, max_kicks={MAX_KICKS}")
    print(f"target load (if all inserts succeed) = {N/(M*B):.6f}")
    print(f"# seeds = {len(SEEDS)}, # f values = {len(F_VALUES)}")
    print()

    rows = []
    overall_t0 = time.perf_counter()
    for f in F_VALUES:
        for s in SEEDS:
            r = run_one(f, s)
            rows.append(r)
            print(f"  f={f:2d}  seed={s:2d}  inserted={r['inserted']:6d}  "
                  f"load={r['load']:.4f}  FPR={r['fpr']:.6e}  "
                  f"FP={r['false_positives']}")
        print()

    total = time.perf_counter() - overall_t0
    print(f"\ntotal wall time: {total:.1f} s")

    # ---- save raw results ---------------------------------------------
    raw_path = os.path.join(OUT_DIR, "results_raw.csv")
    with open(raw_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"raw results written to {raw_path}")

    # ---- aggregate ---------------------------------------------------
    print("\n--- summary ---")
    print(f"{'f':>4} {'mean FPR':>14} {'theory (α)':>14} {'mean load':>11} {'mean FP':>10} {'σ(FPR)':>14}")
    agg = []
    for f in F_VALUES:
        sub = [r for r in rows if r["f"] == f]
        fprs = [r["fpr"] for r in sub]
        loads = [r["load"] for r in sub]
        fps = [r["false_positives"] for r in sub]
        mean_fpr = sum(fprs) / len(fprs)
        mean_load = sum(loads) / len(loads)
        mean_fp = sum(fps) / len(fps)
        if len(fprs) > 1:
            var = sum((x - mean_fpr) ** 2 for x in fprs) / (len(fprs) - 1)
            sd = var ** 0.5
        else:
            sd = 0.0
        theory = 1.0 - (1.0 - 1.0 / (1 << f)) ** (2 * B * mean_load)
        theory_worst = 2 * B / (1 << f)
        agg.append({
            "f": f,
            "mean_fpr": mean_fpr,
            "sd_fpr": sd,
            "mean_load": mean_load,
            "mean_fp": mean_fp,
            "theory_actual_load": theory,
            "theory_worst_case": theory_worst,
        })
        print(f"{f:>4d} {mean_fpr:14.6e} {theory:14.6e} {mean_load:11.4f} "
              f"{mean_fp:10.2f} {sd:14.6e}")

    # save aggregated
    agg_path = os.path.join(OUT_DIR, "results_summary.csv")
    with open(agg_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(agg[0].keys()))
        w.writeheader()
        w.writerows(agg)
    print(f"\naggregated summary written to {agg_path}")


if __name__ == "__main__":
    main()