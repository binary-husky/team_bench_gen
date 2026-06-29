"""Diagnostic: explore the distribution to understand point query vs F2."""
import numpy as np
from cms_experiment import (
    sample_zipf_s1, pairwise_hash_params, ZIPF_S, N_UPDATES, N_ITEMS, W, D, P
)

seed = 42
rng = np.random.default_rng(seed * 1000 + 7)
items = sample_zipf_s1(rng, ZIPF_S, N_UPDATES, N_ITEMS)
items = np.clip(items, 1, N_ITEMS).astype(np.int64)

a = np.bincount(items, minlength=N_ITEMS + 1).astype(np.int64)
print(f"F1 = {a.sum()}")
print(f"F2 = {float((a.astype(np.float64)**2).sum()):.3e}")
print(f"Number of distinct items (a[i] > 0): {(a > 0).sum()}")
print(f"a[i] distribution: min={a.min()}, max={a.max()}, mean={a.mean():.2f}")
nz = a[a > 0]
print(f"  conditional on a[i]>0: min={nz.min()}, max={nz.max()}, mean={nz.mean():.2f}, median={np.median(nz):.1f}")

# Top 10 items
order = np.argsort(-a)[:10]
print("Top 10:", [(int(i), int(a[i])) for i in order])

# Build sketch
a_coef, b_coef = pairwise_hash_params(seed, W, D)
sketch = np.zeros((D, W), dtype=np.int64)
for j in range(D):
    a_j = int(a_coef[j]); b_j = int(b_coef[j])
    items_obj = items.astype(object)
    idx = ((a_j * items_obj + b_j) % P) % W
    np.add.at(sketch[j], idx.astype(np.int64), 1)

# Point query for all items
ids = np.arange(0, N_ITEMS + 1, dtype=np.int64)
per_row = np.empty((D, ids.shape[0]), dtype=np.int64)
for j in range(D):
    a_j = int(a_coef[j]); b_j = int(b_coef[j])
    ids_obj = ids.astype(object)
    col = ((a_j * ids_obj + b_j) % P) % W
    per_row[j] = sketch[j, col.astype(np.int64)]
a_hat = per_row.min(axis=0)

# Different metrics
denom = np.maximum(a, 1)

# All items (the task's literal definition)
rel_over_all = (a_hat - a) / denom
print(f"\nMetric 1 (ALL items, a[i]=0..N_ITEMS): mean rel-over = {rel_over_all.mean():.3e}")

# Only items that appear in stream
mask_appear = a > 0
rel_over_appear = (a_hat[mask_appear] - a[mask_appear]) / np.maximum(a[mask_appear], 1)
print(f"Metric 2 (only items with a[i]>0): mean rel-over = {rel_over_appear.mean():.3e}, "
      f"count={mask_appear.sum()}")

# Items with a[i] >= some threshold
for thresh in [1, 10, 100, 1000]:
    mask = a >= thresh
    if mask.sum() > 0:
        r = (a_hat[mask] - a[mask]) / np.maximum(a[mask], 1)
        print(f"  items with a[i] >= {thresh}: n={mask.sum()}, mean rel-over = {r.mean():.3e}")

# F2 self-join
row_sq = (sketch.astype(np.float64) ** 2).sum(axis=1)
F2_hat = float(row_sq.min())
F2_true = float((a.astype(np.float64) ** 2).sum())
print(f"\nF2 self-join: F2_true={F2_true:.4e}, F2_hat={F2_hat:.4e}, "
      f"F2_err = {(F2_hat - F2_true)/F2_true:.4e}")
