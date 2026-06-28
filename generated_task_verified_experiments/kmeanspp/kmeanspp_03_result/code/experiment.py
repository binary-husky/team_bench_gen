"""
Empirical approximation ratio of k-means++ in practice.

Task (kmeanspp_03):
  - Generate well-separated Gaussian blobs with make_blobs (n=5000, fixed seed).
  - For k in {5, 10, 20, 50}:
        OPT*  = best inertia across many k-means++ runs (proxy for OPT)
        ratio = inertia_i / OPT*   for each single k-means++ run
        report mean / max of the ratio distribution
  - Compare the practical ratio (vs k) against the worst-case O(log k) bound.
Independent variable: k.  Fixed: dataset, k set, random_state set.
"""

import numpy as np
from sklearn.datasets import make_blobs
from sklearn.cluster import KMeans
import math
import json

# ----------------------------------------------------------------------
# Fixed settings (held constant across all k)
# ----------------------------------------------------------------------
N_SAMPLES   = 5000
N_FEATURES  = 10
N_TRUE_CENT = 60          # >= max k (50) so every k is meaningful; well separated
CLUSTER_STD = 0.8
DATA_SEED   = 1234        # fixed dataset

K_VALUES    = [5, 10, 20, 50]
RUN_STATES  = list(range(1, 121))   # 120 independent single-run random_states
N_RUNS      = len(RUN_STATES)

# k-means++ is sklearn's default init; n_init=1 -> a single k-means++ run.
def run_kmeanspp(X, k, seed):
    km = KMeans(
        n_clusters=k,
        init="k-means++",
        n_init=1,
        max_iter=300,
        tol=1e-4,
        random_state=seed,
    )
    km.fit(X)
    return km.inertia_

# ----------------------------------------------------------------------
# Build the fixed dataset
# ----------------------------------------------------------------------
X, _ = make_blobs(
    n_samples=N_SAMPLES,
    n_features=N_FEATURES,
    centers=N_TRUE_CENT,
    cluster_std=CLUSTER_STD,
    random_state=DATA_SEED,
    shuffle=True,
)
print(f"dataset: n={N_SAMPLES}  dim={N_FEATURES}  true_centers={N_TRUE_CENT} "
      f"std={CLUSTER_STD}  seed={DATA_SEED}")
print(f"runs per k: {N_RUNS}\n")

# ----------------------------------------------------------------------
# For each k: collect inertias, OPT* = min, ratios
# ----------------------------------------------------------------------
rows = {}
for k in K_VALUES:
    inertias = np.array([run_kmeanspp(X, k, s) for s in RUN_STATES])
    opt_star = inertias.min()
    ratios   = inertias / opt_star
    rows[k] = {
        "opt_star":   float(opt_star),
        "ratio_mean": float(ratios.mean()),
        "ratio_std":  float(ratios.std()),
        "ratio_max":  float(ratios.max()),
        "ratio_p50":  float(np.percentile(ratios, 50)),
        "ratio_p95":  float(np.percentile(ratios, 95)),
        "ratio_min":  float(ratios.min()),
        "ratios":     ratios.tolist(),
    }
    # Theoretical worst-case (Arthur & Vassilvitskii 2007):
    #   E[cost] <= 8 (ln k + 2) * OPT
    theory = 8.0 * (math.log(k) + 2.0)
    print(f"k={k:3d} | OPT*={opt_star:.2f} | ratio mean={ratios.mean():.4f} "
          f"max={ratios.max():.4f} p95={np.percentile(ratios,95):.4f} | "
          f"theory 8(ln k+2)={theory:.3f}  ln k={math.log(k):.3f}")

with open("results.json", "w") as f:
    json.dump({"config": {
        "n_samples": N_SAMPLES, "n_features": N_FEATURES,
        "true_centers": N_TRUE_CENT, "cluster_std": CLUSTER_STD,
        "data_seed": DATA_SEED, "k_values": K_VALUES,
        "n_runs": N_RUNS, "run_states": RUN_STATES,
    }, "rows": {k: {kk: vv for kk, vv in v.items() if kk != "ratios"} for k, v in rows.items()}}, f, indent=2)

print("\nsaved results.json")
