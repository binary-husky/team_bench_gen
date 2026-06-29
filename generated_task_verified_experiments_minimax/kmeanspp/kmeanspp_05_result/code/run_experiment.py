"""
Experiment: Effect of cluster separation (cluster_std) on k-means++ advantage.

- Generate n=5000, k=10 blobs with make_blobs.
- Vary cluster_std in {0.5, 1.0, 1.5, 2.5, 4.0} (well-separated to highly overlapping).
- For each cluster_std, run both k-means++ and random init (n_init=1) over a fixed
  set of ~20 random_states, and record the inertia.
- Compute mean inertia for each initialization, and the ratio inertia_random / inertia_kmeanspp.
"""

import json
import os

import numpy as np
from sklearn.datasets import make_blobs
from sklearn.cluster import KMeans

# Fixed experimental settings
N_SAMPLES = 5000
K = 10
N_TRIALS = 20
CLUSTER_STDS = [0.5, 1.0, 1.5, 2.5, 4.0]

# Fixed seed for the dataset itself
DATA_RANDOM_STATE = 42

# Fixed set of random_state values for the kmeans initializations
RANDOM_STATES = list(range(N_TRIALS))

# n_init=1 -> single initialization per call (per task requirement)
N_INIT = 1
MAX_ITER = 300
TOL = 1e-6


def run_experiment():
    results = {}
    for std in CLUSTER_STDS:
        # Same data for each cluster_std so the only varying parameter is the std
        X, _ = make_blobs(
            n_samples=N_SAMPLES,
            centers=K,
            cluster_std=std,
            random_state=DATA_RANDOM_STATE,
        )

        inerts_pp = []
        inerts_random = []
        for rs in RANDOM_STATES:
            km_pp = KMeans(
                n_clusters=K,
                init="k-means++",
                n_init=N_INIT,
                max_iter=MAX_ITER,
                tol=TOL,
                random_state=rs,
            )
            km_pp.fit(X)
            inerts_pp.append(km_pp.inertia_)

            km_rand = KMeans(
                n_clusters=K,
                init="random",
                n_init=N_INIT,
                max_iter=MAX_ITER,
                tol=TOL,
                random_state=rs,
            )
            km_rand.fit(X)
            inerts_random.append(km_rand.inertia_)

        mean_pp = float(np.mean(inerts_pp))
        mean_rand = float(np.mean(inerts_random))
        ratio = mean_rand / mean_pp if mean_pp > 0 else float("nan")

        results[str(std)] = {
            "cluster_std": std,
            "inertia_kmeanspp": inerts_pp,
            "inertia_random": inerts_random,
            "mean_inertia_kmeanspp": mean_pp,
            "mean_inertia_random": mean_rand,
            "std_inertia_kmeanspp": float(np.std(inerts_pp)),
            "std_inertia_random": float(np.std(inerts_random)),
            "min_inertia_kmeanspp": float(np.min(inerts_pp)),
            "min_inertia_random": float(np.min(inerts_random)),
            "ratio_random_over_kmeanspp": ratio,
        }

    return results


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_json = os.path.join(out_dir, "results.json")
    results = run_experiment()
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)

    # Print a compact table for easy reading
    print(f"{'std':>6}  {'mean_pp':>14}  {'mean_rand':>14}  {'ratio':>8}  "
          f"{'min_pp':>14}  {'min_rand':>14}")
    for std in CLUSTER_STDS:
        r = results[str(std)]
        print(f"{std:>6.2f}  {r['mean_inertia_kmeanspp']:>14.2f}  "
              f"{r['mean_inertia_random']:>14.2f}  {r['ratio_random_over_kmeanspp']:>8.4f}  "
              f"{r['min_inertia_kmeanspp']:>14.2f}  {r['min_inertia_random']:>14.2f}")


if __name__ == "__main__":
    main()
