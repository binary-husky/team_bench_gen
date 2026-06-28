"""
Reproduce Count-Min Sketch and study how width w (depth d fixed) affects
point-query over-estimation error.

Theory (from the CMS paper): the point-query estimate a_hat[i] = min_j C[j][h_j(i)]
never underestimates, and its over-estimate a_hat[i]-a[i] scales as ~ ||a||_1 / w
(independent of the item), with d only tightening the tail probability.

Goal: verify that over-estimate ~ 1/w (doubling w halves the error), for both a
heavy-tailed Zipfian(s~=1.0) stream and a uniform stream, each over a finite
universe of 1e5 items with 1e6 updates.

Hash family: 2-wise independent (pairwise-independent) Dietzfelbinger
multiply-shift linear family
    h_{a,b}(x) = ((a*x + b) mod 2^64) >> (64 - k),   w = 2^k, a odd
which maps the universe into {0,...,w-1} and is 2-universal.  Different rows j
get different (a_j, b_j); different seeds give independent param sets.  This is
vectorised over numpy uint64 arrays so the whole study runs in seconds on CPU.
"""

import numpy as np
import json
import time

# ----------------------------------------------------------------------
# Fixed experimental setup (per task.md) -- DO NOT CHANGE
# ----------------------------------------------------------------------
D = 5                                    # sketch depth (number of hash rows)
WIDTHS = [128, 256, 512, 1024, 2048, 4096]
N_UNIVERSE = 100_000                     # distinct items
N_STREAM = 1_000_000                     # updates
ZIPF_S = 1.0                             # Zipfian exponent s ~= 1.0
HASH_SEEDS = [11, 22, 33, 44, 55]        # >=3 independent repetitions
STREAM_SEED = 12345                      # fixed so the stream is reproducible


# ----------------------------------------------------------------------
# 2-wise independent multiply-shift hash to w=2^k buckets (vectorised)
# ----------------------------------------------------------------------
def hash_mask(x_uint64, a, b, k):
    shift = 64 - k
    raw = ((x_uint64 * np.uint64(a)) + np.uint64(b))  # mod 2^64 (uint64 wraps)
    return (raw >> np.uint64(shift)).astype(np.intp)  # top k bits -> [0, 2^k)


# ----------------------------------------------------------------------
# Stream generation
# ----------------------------------------------------------------------
def make_stream(distribution, rng):
    """Return uint64 array of N_STREAM item ids + true-frequency array a (len N)."""
    if distribution == "uniform":
        items = rng.integers(0, N_UNIVERSE, size=N_STREAM)
    elif distribution == "zipf":
        # exact Zipf(s) over a finite universe of N items: p_i ∝ i^{-s}
        ranks = np.arange(1, N_UNIVERSE + 1, dtype=np.float64)
        p = ranks ** (-ZIPF_S)
        p /= p.sum()
        items = rng.choice(N_UNIVERSE, size=N_STREAM, p=p)
    else:
        raise ValueError(distribution)
    items = items.astype(np.uint64)
    a_true = np.bincount(items.astype(np.intp), minlength=N_UNIVERSE)
    return items, a_true


# ----------------------------------------------------------------------
# CMS run for one (w, seed): build sketch from stream, query ALL universe items
# ----------------------------------------------------------------------
def run_one_w(items, a_true, w, seed):
    k = int(round(np.log2(w)))
    x_all = np.arange(N_UNIVERSE, dtype=np.uint64)  # all universe items to query
    rng = np.random.default_rng(seed)
    # d pairwise-independent hash params (a odd)
    a_par = (rng.integers(1, 2**63, size=D) | 1)
    b_par = rng.integers(0, 2**63, size=D)

    est = np.full(N_UNIVERSE, np.iinfo(np.int64).max, dtype=np.int64)
    for j in range(D):
        aj = int(a_par[j]); bj = int(b_par[j])
        # ---- UPDATE (vectorised): C[j] = bincount of h_j(stream) ----
        b_stream = hash_mask(items, aj, bj, k)
        C = np.bincount(b_stream, minlength=w).astype(np.int64)
        # ---- POINT QUERY: C[j][ h_j(item) ] for all items ----
        b_item = hash_mask(x_all, aj, bj, k)
        est_row = C[b_item]
        est = np.minimum(est, est_row)
    over = est - a_true  # >= 0 always (CMS never underestimates)
    assert (over >= 0).all(), "CMS must not underestimate"
    pcts = {q: float(np.percentile(over, q))
            for q in [50, 90, 95, 99, 99.9]}
    return float(over.mean()), pcts, float(over.max())


def main():
    t0 = time.time()
    results = {}
    for dist in ["zipf", "uniform"]:
        rng = np.random.default_rng(STREAM_SEED)
        items, a_true = make_stream(dist, rng)
        l1 = int(a_true.sum())
        # diagnostics on the true frequency distribution
        nz = int((a_true > 0).sum())
        top1 = int(a_true.max())
        print(f"[{dist}] ||a||_1={l1}  distinct_appearing={nz}/{N_UNIVERSE}  "
              f"max_freq={top1}  mean_freq(nonzero)={l1/max(nz,1):.3f}")
        results[dist] = {"L1": l1, "distinct": nz, "max": top1, "rows": []}
        for w in WIDTHS:
            agg = {q: [] for q in [50, 90, 95, 99, 99.9]}
            means, maxs = [], []
            for seed in HASH_SEEDS:
                m, pcts, mx = run_one_w(items, a_true, w, seed)
                means.append(m); maxs.append(mx)
                for q in agg:
                    agg[q].append(pcts[q])
            row = {
                "w": w,
                "mean": float(np.mean(means)),
                "mean_std": float(np.std(means)),
                "p50": float(np.mean(agg[50])),
                "p90": float(np.mean(agg[90])),
                "p95": float(np.mean(agg[95])),
                "p99": float(np.mean(agg[99])),
                "p99_std": float(np.std(agg[99])),
                "p999": float(np.mean(agg[99.9])),
                "max": float(np.mean(maxs)),
                "theory_mean": l1 / w,          # classic per-row bound
            }
            results[dist]["rows"].append(row)
            print(f"  w={w:5d}  mean={row['mean']:9.1f}(thr {row['theory_mean']:9.1f}) "
                  f"p50={row['p50']:9.1f} p95={row['p95']:9.1f} p99={row['p99']:9.1f} "
                  f"p99.9={row['p999']:9.1f} max={row['max']:9.1f}")
    print(f"elapsed {time.time()-t0:.1f}s")
    with open("results_cm_02.json", "w") as f:
        json.dump(results, f, indent=2)
    print("wrote results_cm_02.json")


if __name__ == "__main__":
    main()
