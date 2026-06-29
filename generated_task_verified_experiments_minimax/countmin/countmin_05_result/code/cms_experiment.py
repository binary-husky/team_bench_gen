"""
Count-Min Sketch experiment: comparing point-query error vs self-join F2 error.

Implements Count-Min from Cormode-Muthukrishnan 2003 ("An Improved Data
Stream Summary: The Count-Min Sketch and its Applications").

For each of >=10 hash seeds we:
  1. Build a sketch with w=2048, d=8 by ingesting 1e6 Zipfian(s=1.0) updates
     drawn from 1e5 distinct items.
  2. Run POINT QUERY: â[i] = min_j C[j, h_j(i)]
     -> Mean of (â[i] - a[i]) / max(a[i], 1) over all items.
  3. Run SELF-JOIN / F2 QUERY: F̂_2 = min_j Σ_l C[j,l]^2
     -> (F̂_2 - F_2) / F_2 where F_2 = Σ_i a[i]^2.

We average both metrics across seeds.
"""

import time
import numpy as np

# -------- Fixed experimental settings (do not change) --------
W = 2048          # width per row
D = 8             # number of rows (hashes)
N_UPDATES = 1_000_000
N_ITEMS = 100_000
ZIPF_S = 1.0
N_SEEDS = 12      # >= 10

# Large prime for pairwise-independent hashing
# h_j(i) = ((a_j * i + b_j) mod P) mod W
P = (1 << 61) - 1  # Mersenne prime 2^61 - 1


def pairwise_hash_params(seed, w, d):
    """Return (a[d], b[d]) pairwise-independent hash coefficients mod P."""
    rng = np.random.default_rng(seed)
    # a in [1, P-1], b in [0, P-1]
    a = rng.integers(1, P, size=d, dtype=np.int64)
    b = rng.integers(0, P, size=d, dtype=np.int64)
    return a, b


def zipf_s1_pmf(n):
    """Zipf(s=1.0) PMF over k = 1..n: p(k) = 1 / (k * H_n)."""
    H_n_exact = float(np.sum(1.0 / np.arange(1, n + 1, dtype=np.float64)))
    pk = 1.0 / (np.arange(1, n + 1, dtype=np.float64) * H_n_exact)
    return pk, H_n_exact


def sample_zipf_s1(rng, n, size):
    """Inverse-CDF sampling for Zipf(s=1.0) on 1..n."""
    pk, _ = zipf_s1_pmf(n)
    cdf = np.cumsum(pk)
    u = rng.random(size)
    return np.searchsorted(cdf, u).astype(np.int64) + 1  # 1..n


def _hash_columns(items, a_j, b_j):
    """Return column indices for items in row j using Python-int arithmetic
    (to avoid int64 overflow on a_j * items)."""
    a_j = int(a_j)
    b_j = int(b_j)
    items_py = items.astype(object)  # promote to Python int
    col = (a_j * items_py + b_j) % P
    col = col % W
    return col.astype(np.int64)


def run_one_seed(seed, return_arrays=False):
    """Run full experiment for one hash seed. Returns (point_err, F2_err, ...)."""
    rng_stream = np.random.default_rng(seed * 1000 + 7)
    items = sample_zipf_s1(rng_stream, N_ITEMS, N_UPDATES)
    items = np.clip(items, 1, N_ITEMS).astype(np.int64)

    # True frequencies
    a = np.bincount(items, minlength=N_ITEMS + 1).astype(np.int64)
    F2_true = float((a.astype(np.float64) ** 2).sum())
    F1_true = int(a.sum())
    assert F1_true == N_UPDATES, (F1_true, N_UPDATES)

    # Build sketch
    a_coef, b_coef = pairwise_hash_params(seed, W, D)
    sketch = np.zeros((D, W), dtype=np.int64)

    print(f"  seed={seed}: building sketch ...")
    t0 = time.time()
    for j in range(D):
        idx = _hash_columns(items, a_coef[j], b_coef[j])
        np.add.at(sketch[j], idx, 1)
    t_build = time.time() - t0
    print(f"    build time = {t_build:.2f}s, ||a||_1 = {F1_true}, F2 = {F2_true:.4e}, "
          f"distinct_items = {(a > 0).sum()}")

    # ------- Point query: â[i] = min_j C[j, h_j(i)] -------
    ids = np.arange(0, N_ITEMS + 1, dtype=np.int64)
    per_row_estimates = np.empty((D, ids.shape[0]), dtype=np.int64)
    for j in range(D):
        col = _hash_columns(ids, a_coef[j], b_coef[j])
        per_row_estimates[j] = sketch[j, col]
    a_hat = per_row_estimates.min(axis=0)

    # Reported metric: mean of (â[i] - a[i]) / max(a[i], 1) over all items.
    denom = np.maximum(a, 1)
    point_err_all = float(((a_hat - a) / denom).mean())
    # Also: only over items that appear (a[i] > 0)
    mask_pos = a > 0
    point_err_pos = float(((a_hat[mask_pos] - a[mask_pos]) /
                           a[mask_pos]).mean()) if mask_pos.sum() > 0 else 0.0

    # ------- Self-join F2 query: F̂_2 = min_j Σ_l C[j,l]^2 -------
    row_sq_sums = (sketch.astype(np.float64) ** 2).sum(axis=1)
    F2_hat = float(row_sq_sums.min())
    F2_err = (F2_hat - F2_true) / F2_true

    # Also per-row F̂_2 errors (without the min)
    per_row_F2 = row_sq_sums
    per_row_errs = (per_row_F2 - F2_true) / F2_true

    extras = {
        "F1": F1_true, "F2_true": F2_true, "F2_hat": F2_hat,
        "F2_err_per_row": per_row_errs.tolist(),
        "point_err_all": point_err_all, "point_err_pos": point_err_pos,
        "distinct": int(mask_pos.sum()),
    }
    return point_err_all, F2_err, extras


def main():
    point_errs = []
    F2_errs = []
    rows_data = []
    for s in range(N_SEEDS):
        seed = 1009 + s * 37
        pe, fe, extras = run_one_seed(seed)
        print(f"  seed={seed}: point_err={pe:.6e}, F2_err={fe:.6e}, "
              f"F2_true={extras['F2_true']:.3e}, F2_hat={extras['F2_hat']:.3e}")
        point_errs.append(pe)
        F2_errs.append(fe)
        rows_data.append(extras["F2_err_per_row"])

    pe_arr = np.array(point_errs)
    fe_arr = np.array(F2_errs)
    print()
    print("=" * 70)
    print(f"Number of seeds: {N_SEEDS}")
    print(f"Point-query mean relative overestimate (over ALL items): "
          f"{pe_arr.mean():.6e} (std {pe_arr.std(ddof=1):.3e})")
    print(f"F2 self-join mean relative error:        {fe_arr.mean():.6e} "
          f"(std {fe_arr.std(ddof=1):.3e})")
    print(f"Ratio point_err / F2_err = {pe_arr.mean() / fe_arr.mean():.3f}")
    # Save rows for analysis
    np.savez("/data/workspace/admin/happy_lake/.verify_judge_minimax/countmin/countmin_05/cms_results.npz",
             point_errs=pe_arr, F2_errs=fe_arr, rows_data=np.array(rows_data))


if __name__ == "__main__":
    main()
