"""
Count-Min Sketch: heavy-hitter / top-k precision-recall vs sketch size.

Reproduction of the Cormode-Muthukrishnan Count-Min Sketch (paper in
countmin_material/cm-full.pdf):
  - d pairwise-independent hash functions  h_j : {1..n} -> {1..w}
        h_j(x) = ((a_j * x + b_j) mod p) mod w        (Carter-Wegman, p prime)
  - update:  count[j, h_j(i_t)] += c_t                 (cash register, c_t = +1)
  - point:   a_hat[i] = min_j count[j, h_j(i)]
  - heavy hitter / top-k: after the stream, estimate a_hat[i] for every item
        that appeared, take top-k by a_hat[i], compare to the true top-k.

Experiment (fixed, see task.md):
  - 1e6 updates, 1e5 distinct items, Zipfian s~1.0 (heavy head + long tail).
  - ground-truth top-k = 100 by true a[i].
  - grid: {(w=512,d=3),(1024,5),(2048,5),(4096,8),(8192,10)}.
  - metrics: precision@100, recall@100  vs true top-100.
  - 5 distinct hash seeds per config; the data stream is FIXED across seeds so
    the only randomness being averaged is the choice of hash functions (which is
    exactly what the CM probabilistic guarantee is over). Means are reported.
"""

import numpy as np
import math
import json
import time

# ----------------------------- fixed config -------------------------------
N_STREAM = 1_000_000          # number of stream updates
N_ITEMS  = 100_000            # distinct item universe
S_ZIPF   = 1.0                # Zipf exponent
K        = 100                # top-k
SEEDS    = [11, 22, 33, 44, 55]   # 5 independent hash-function seeds
CONFIGS  = [(512, 3), (1024, 5), (2048, 5), (4096, 8), (8192, 10)]
P        = 2147483647         # 2^31 - 1, Mersenne prime (pairwise-indep family)
DATA_SEED = 20240601          # fixes the Zipf stream / true frequencies

# ----------------------------- data stream --------------------------------
def make_stream():
    rng = np.random.default_rng(DATA_SEED)
    # truncated Zipf pmf over n items: p_i proportional to i^{-s}
    ranks = np.arange(1, N_ITEMS + 1, dtype=np.float64)
    pmf = ranks ** (-S_ZIPF)
    pmf /= pmf.sum()
    cdf = np.cumsum(pmf)
    u = rng.random(N_STREAM)
    item_ids = np.searchsorted(cdf, u).astype(np.int64)   # in [0, N_ITEMS)
    a = np.bincount(item_ids, minlength=N_ITEMS).astype(np.int64)  # true freq
    return item_ids, a

item_ids, a = make_stream()
distinct = np.nonzero(a)[0]            # items that actually appeared
L1 = int(a.sum())
true_order = np.argsort(-a, kind="stable")          # descending by true freq
true_top = set(true_order[:K].tolist())             # ground-truth top-k set

print(f"stream: {N_STREAM} updates, {len(distinct)} distinct items appeared, "
      f"||a||_1={L1}")
print(f"top-1 true freq={a[true_order[0]]}  ({a[true_order[0]]/L1:.4f} of L1)")
print(f"100th true freq={a[true_order[99]]}  "
      f"({a[true_order[99]]/L1:.6f} of L1)")
# how many true heavy hitters at phi threshold for context
for phi in (0.01, 0.005, 0.001):
    print(f"  #items with a[i] >= {phi}*||a||_1 : {(a >= phi*L1).sum()}")

# ----------------------------- CM sketch ----------------------------------
def build_sketch(w, d, seed):
    """Build the (d,w) CM sketch from the fixed stream, return counts + coeffs."""
    rng = np.random.default_rng(seed)
    a_coef = rng.integers(1, P, size=d, dtype=np.int64)   # a_j != 0
    b_coef = rng.integers(0, P, size=d, dtype=np.int64)
    counts = np.zeros((d, w), dtype=np.int64)
    for j in range(d):
        buckets = ((a_coef[j] * item_ids + b_coef[j]) % P) % w
        # bincount over h_j(whole stream) == row j of the sketch (c_t = +1)
        counts[j] = np.bincount(buckets, minlength=w).astype(np.int64)
    return counts, a_coef, b_coef

def estimate_all(counts, a_coef, b_coef):
    """a_hat[i] = min_j count[j, h_j(i)] for every distinct item."""
    d, w = counts.shape
    est = np.full(distinct.shape[0], np.iinfo(np.int64).max, dtype=np.int64)
    for j in range(d):
        buckets_i = ((a_coef[j] * distinct + b_coef[j]) % P) % w
        est = np.minimum(est, counts[j][buckets_i])
    return est

# ----------------------------- run grid -----------------------------------
def run_config(w, d):
    precs, recs = [], []
    fp_ranks_all = []     # true ranks of false positives (long-tail intruders)
    mae_all = []          # mean(a_hat - a) over distinct items (one-sided err)
    max_over_all = []
    for seed in SEEDS:
        counts, ac, bc = build_sketch(w, d, seed)
        est = estimate_all(counts, ac, bc)
        # top-k by estimate
        order = np.argsort(-est, kind="stable")
        top_est = distinct[order[:K]]
        top_est_set = set(top_est.tolist())
        inter = len(top_est_set & true_top)
        prec = inter / K
        rec  = inter / K            # fixed-size lists -> precision==recall
        precs.append(prec); recs.append(rec)
        # false positives: in sketch top-k but not in true top-k -> their true ranks
        fp = [i for i in top_est if i not in true_top]
        fp_ranks_all.append([int(np.where(true_order == i)[0][0]) for i in fp])
        # point-query error diagnostics
        err = est - a[distinct]                # >= 0 by construction
        mae_all.append(float(err.mean()))
        max_over_all.append(int(err.max()))
    return {
        "w": w, "d": d,
        "eps_theory": math.e / w,              # epsilon = e / w
        "delta_theory": math.exp(-d),          # delta   = e^{-d}
        "precision_mean": float(np.mean(precs)),
        "recall_mean": float(np.mean(recs)),
        "precision_min": float(np.min(precs)),
        "precision_max": float(np.max(precs)),
        "precision_std": float(np.std(precs)),
        "mae_mean": float(np.mean(mae_all)),
        "max_overest_mean": float(np.mean(max_over_all)),
        "fp_true_ranks_flat": [r for sub in fp_ranks_all for r in sub],
    }

t0 = time.time()
results = []
for (w, d) in CONFIGS:
    r = run_config(w, d)
    results.append(r)
    print(f"(w={w:>5},d={d:>2}) eps={r['eps_theory']:.2e} delta={r['delta_theory']:.2e}"
          f"  P@100={r['precision_mean']:.3f}  R@100={r['recall_mean']:.3f}"
          f"  mae={r['mae_mean']:.1f}  max_over={r['max_overest_mean']}")
print(f"elapsed: {time.time()-t0:.1f}s")

# smallest config where both precision & recall >= 0.95
min95 = None
for r in results:
    if r["precision_mean"] >= 0.95 and r["recall_mean"] >= 0.95:
        min95 = (r["w"], r["d"]); break
print("min config with P,R >= 0.95:", min95)

with open("cm_results.json", "w") as f:
    json.dump({
        "config": {"N_STREAM": N_STREAM, "N_ITEMS": N_ITEMS, "S_ZIPF": S_ZIPF,
                   "K": K, "seeds": SEEDS, "L1": L1,
                   "n_distinct_seen": int(len(distinct))},
        "results": results,
        "min_config_ge_0.95": min95,
    }, f, indent=2)
print("wrote cm_results.json")
