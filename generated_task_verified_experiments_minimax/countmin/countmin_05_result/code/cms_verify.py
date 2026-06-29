"""Quick test: verify hash function is uniform and pairwise independent."""
import numpy as np
from cms_experiment import pairwise_hash_params, W, D, P, _hash_columns

# Uniformity check
a_coef, b_coef = pairwise_hash_params(123, W, D)
items = np.arange(10000, dtype=np.int64)
for j in range(D):
    col = _hash_columns(items, a_coef[j], b_coef[j])
    counts = np.bincount(col, minlength=W)
    expected = len(items) / W
    chi2 = ((counts - expected)**2 / expected).sum()
    print(f"row {j}: chi-square (uniform) = {chi2:.2f} (W={W}, E={expected:.2f}, "
          f"min={counts.min()}, max={counts.max()}, mean={counts.mean():.2f})")

# Pairwise independence check: P(h(i) = h(j)) should be ~ 1/w for i != j
n = 5000
items = np.arange(n, dtype=np.int64)
for j in range(D):
    col = _hash_columns(items, a_coef[j], b_coef[j])
    same = 0
    total = 0
    for i in range(min(200, n)):
        for k in range(i+1, min(200, n)):
            if col[i] == col[k]:
                same += 1
            total += 1
    emp = same / total
    print(f"row {j}: P(h(i)=h(j)) empirical={emp:.4f}, theoretical=1/W={1/W:.4f}")
