"""Analysis: look at the noise mechanism in detail."""
import numpy as np
from cms_experiment import run_one_seed, N_SEEDS, N_ITEMS, W, D

# Run one seed and dig into the noise
seed = 1009
pe, fe, extras = run_one_seed(seed)
a_coef, b_coef = None, None  # rebuild

# Re-build to get sketch
import time
from cms_experiment import (
    sample_zipf_s1, pairwise_hash_params, _hash_columns, ZIPF_S, N_UPDATES
)

rng_stream = np.random.default_rng(seed * 1000 + 7)
items = sample_zipf_s1(rng_stream, N_ITEMS, N_UPDATES)
items = np.clip(items, 1, N_ITEMS).astype(np.int64)
a = np.bincount(items, minlength=N_ITEMS + 1).astype(np.int64)
a_coef, b_coef = pairwise_hash_params(seed, W, D)
sketch = np.zeros((D, W), dtype=np.int64)
for j in range(D):
    idx = _hash_columns(items, a_coef[j], b_coef[j])
    np.add.at(sketch[j], idx, 1)

# Look at the F2 collision structure
print("=" * 60)
print("F2 self-join noise analysis")
print("=" * 60)
F2_true = float((a.astype(np.float64) ** 2).sum())
print(f"F2_true = {F2_true:.4e}")
for j in range(D):
    row_sq = float((sketch[j].astype(np.float64) ** 2).sum())
    excess = row_sq - F2_true
    print(f"  row {j}: Σ C[j,l]^2 = {row_sq:.4e}, excess = {excess:.4e}, "
          f"rel = {(row_sq - F2_true)/F2_true:.4e}")

# The "true cross-term" per row: (1/w) * Σ_{i≠k} a[i]*a[k]
# Note: F̂_2 = F_2 + 2 * Σ_l Σ_{i<k: h(i)=h(k)=l} a[i]*a[k]
# Per row, expected: 2/w * Σ_{i<k} a[i]*a[k] = (F_1^2 - F_2)/w
F1 = int(a.sum())
expected_per_row = (F1**2 - F2_true) / W
print(f"\nExpected cross-term per row (uniform hash): "
      f"(F_1^2 - F_2)/w = ({F1**2:.4e} - {F2_true:.4e})/{W} = {expected_per_row:.4e}")
print(f"Actual min over rows: {min((sketch[j].astype(np.float64)**2).sum() - F2_true for j in range(D)):.4e}")

# Now look at the point query noise per item, by frequency bucket
print("\n" + "=" * 60)
print("Point query noise vs frequency bucket")
print("=" * 60)
ids = np.arange(0, N_ITEMS + 1, dtype=np.int64)
per_row = np.empty((D, ids.shape[0]), dtype=np.int64)
for j in range(D):
    col = _hash_columns(ids, a_coef[j], b_coef[j])
    per_row[j] = sketch[j, col]
a_hat = per_row.min(axis=0)
noise = a_hat - a

# Bucket items by true frequency
print(f"{'bucket':>20s}  {'count':>7s}  {'mean_a':>12s}  {'mean_hat':>12s}  {'mean_noise':>12s}  {'mean_rel':>12s}")
buckets = [
    ("a[i] == 0",        (a == 0)),
    ("1 <= a[i] < 10",   (a >= 1) & (a < 10)),
    ("10 <= a[i] < 100", (a >= 10) & (a < 100)),
    ("100 <= a[i] < 1k", (a >= 100) & (a < 1000)),
    ("1k <= a[i] < 10k", (a >= 1000) & (a < 10000)),
    ("10k <= a[i]",      (a >= 10000)),
]
for name, mask in buckets:
    if mask.sum() == 0:
        continue
    aa = a[mask]
    ah = a_hat[mask]
    n = noise[mask]
    rel = n / np.maximum(aa, 1)
    print(f"{name:>20s}  {mask.sum():>7d}  {aa.mean():>12.2f}  {ah.mean():>12.2f}  {n.mean():>12.2f}  {rel.mean():>12.4f}")
