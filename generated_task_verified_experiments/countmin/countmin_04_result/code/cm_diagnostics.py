"""Diagnostics: per-seed precision + false-positive true-rank distribution,
for the smallest config (512,3) and the dipped largest config (8192,10)."""
import numpy as np, math
from cm_experiment import (item_ids, a, distinct, true_order, true_top,
                           build_sketch, estimate_all, K, SEEDS, L1)

def diag(w, d):
    print(f"\n=== (w={w}, d={d}) ===")
    print(f"{'seed':>5} {'P@100':>7} {'#FP':>4} {'FP true-ranks (sorted)':>40}")
    for seed in SEEDS:
        counts, ac, bc = build_sketch(w, d, seed)
        est = estimate_all(counts, ac, bc)
        order = np.argsort(-est, kind="stable")
        top_est = distinct[order[:K]]
        inter = len(set(top_est.tolist()) & true_top)
        fp = [i for i in top_est if i not in true_top]
        fp_ranks = sorted(int(np.where(true_order == i)[0][0]) for i in fp)
        print(f"{seed:>5} {inter/K:>7.3f} {len(fp):>4}   {fp_ranks}")

diag(512, 3)
diag(8192, 10)

# Also show, for (512,3) seed 11, the smallest true freq inside sketch-top100
# vs the largest true freq that the sketch MISSED (boundary confusion).
counts, ac, bc = build_sketch(512, 3, 11)
est = estimate_all(counts, ac, bc)
order = np.argsort(-est, kind="stable")
top_est = distinct[order[:K]]
fp = [i for i in top_est if i not in true_top]           # wrongly admitted
missed = [i for i in true_order[:K] if i not in set(top_est.tolist())]  # wrongly dropped
print(f"\n(512,3) seed11: #FP={len(fp)} #missed={len(missed)}")
if fp:
    print(f"  FP true freqs: min={min(a[i] for i in fp)} max={max(a[i] for i in fp)} "
          f"(true top-100 boundary freq = {a[true_order[99]]})")
if missed:
    print(f"  Missed true heavy-hitter freqs: {[int(a[i]) for i in missed]}")
