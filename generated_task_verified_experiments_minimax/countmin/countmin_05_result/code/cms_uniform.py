"""Sanity check: uniform distribution - point query and F2 comparison."""
import numpy as np
import time
from cms_experiment import (
    pairwise_hash_params, _hash_columns, W, D, P,
    N_UPDATES, N_ITEMS, N_SEEDS
)


def run_uniform_one_seed(seed):
    rng_stream = np.random.default_rng(seed * 1000 + 7)
    # Uniform 1e6 updates over 1e5 items -> each item has ~10 updates
    items = rng_stream.integers(1, N_ITEMS + 1, size=N_UPDATES, dtype=np.int64)

    a = np.bincount(items, minlength=N_ITEMS + 1).astype(np.int64)
    F2_true = float((a.astype(np.float64) ** 2).sum())
    F1_true = int(a.sum())
    assert F1_true == N_UPDATES

    a_coef, b_coef = pairwise_hash_params(seed, W, D)
    sketch = np.zeros((D, W), dtype=np.int64)
    for j in range(D):
        idx = _hash_columns(items, a_coef[j], b_coef[j])
        np.add.at(sketch[j], idx, 1)

    # Point query
    ids = np.arange(0, N_ITEMS + 1, dtype=np.int64)
    per_row = np.empty((D, ids.shape[0]), dtype=np.int64)
    for j in range(D):
        col = _hash_columns(ids, a_coef[j], b_coef[j])
        per_row[j] = sketch[j, col]
    a_hat = per_row.min(axis=0)

    denom = np.maximum(a, 1)
    point_err_all = float(((a_hat - a) / denom).mean())
    mask_pos = a > 0
    point_err_pos = float(((a_hat[mask_pos] - a[mask_pos]) /
                           a[mask_pos]).mean()) if mask_pos.sum() > 0 else 0.0

    # F2
    row_sq_sums = (sketch.astype(np.float64) ** 2).sum(axis=1)
    F2_hat = float(row_sq_sums.min())
    F2_err = (F2_hat - F2_true) / F2_true

    return point_err_all, point_err_pos, F2_err, F2_true, F2_hat


# Run uniform experiment
print("Uniform distribution experiment:")
print("=" * 70)
pes_all, pes_pos, f2es = [], [], []
for s in range(N_SEEDS):
    seed = 1009 + s * 37
    pa, pp, fe, F2, F2h = run_uniform_one_seed(seed)
    pes_all.append(pa)
    pes_pos.append(pp)
    f2es.append(fe)
    print(f"  seed={seed}: point_err_all={pa:.4f}, point_err_pos={pp:.4f}, "
          f"F2_err={fe:.4e}, F2_true={F2:.4e}, F2_hat={F2h:.4e}")

print()
print(f"Uniform mean over {N_SEEDS} seeds:")
print(f"  point_err (all items):      {np.mean(pes_all):.4f}")
print(f"  point_err (a[i]>0 only):    {np.mean(pes_pos):.4f}")
print(f"  F2_err:                     {np.mean(f2es):.4e}")
