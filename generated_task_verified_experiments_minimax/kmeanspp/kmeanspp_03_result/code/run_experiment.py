"""
Empirical evaluation of k-means++ approximation ratio (cost/OPT*)
on well-separated Gaussian clusters.

Theoretical reference: Arthur & Vassilvitskii (2007):
    E[phi] <= 8 (ln k + 2) * phi_OPT
    lower bound: D^2 seeding is no better than 2 ln(k)-competitive
"""

import json
import time
import numpy as np
from sklearn.datasets import make_blobs
from sklearn.cluster import KMeans

# ----------------- Fixed experimental settings -----------------
N_SAMPLES = 5000
DATA_SEED = 42  # for make_blobs
KS = [5, 10, 20, 50]
N_TRIALS_OPT = 200        # number of trials to find best-inertia proxy OPT*
N_TRIALS_RATIO = 50       # number of single k-means++ runs for ratio distribution
N_INIT = 1                # single k-means++ initialization per KMeans() call
MAX_ITER = 300

# Make_centers well-separated; small within-cluster std to ease clustering
N_CENTERS_MAX = max(KS)
CENTERS = (np.arange(N_CENTERS_MAX) * 10.0).reshape(-1, 1)  # 1D centers spaced 10 apart
CENTERS = np.hstack([CENTERS, np.zeros((N_CENTERS_MAX, 1))])  # make 2D for visualization
CLUSTER_STD = 1.0
RANDOM_DIM = 2

# Set seeds for the k-means++ trial runs
TRIAL_SEEDS = [1000 + i for i in range(N_TRIALS_RATIO)]
OPT_SEEDS = [2000 + i for i in range(N_TRIALS_OPT)]


def build_dataset():
    X, y_true = make_blobs(
        n_samples=N_SAMPLES,
        centers=CENTERS[:N_CENTERS_MAX],
        cluster_std=CLUSTER_STD,
        n_features=RANDOM_DIM,
        random_state=DATA_SEED,
    )
    return X, y_true


def find_opt_star(X, k):
    """Best inertia over many k-means++ restarts (proxy for OPT*)."""
    best = np.inf
    for s in OPT_SEEDS:
        km = KMeans(
            n_clusters=k,
            init="k-means++",
            n_init=N_INIT,
            max_iter=MAX_ITER,
            random_state=s,
        )
        km.fit(X)
        if km.inertia_ < best:
            best = km.inertia_
    return best


def run_trials(X, k):
    """Return list of inertias for N_TRIALS_RATIO single k-means++ runs."""
    inertias = []
    for s in TRIAL_SEEDS:
        km = KMeans(
            n_clusters=k,
            init="k-means++",
            n_init=N_INIT,
            max_iter=MAX_ITER,
            random_state=s,
        )
        km.fit(X)
        inertias.append(km.inertia_)
    return inertias


def main():
    t0 = time.time()
    X, _ = build_dataset()
    print(f"Dataset: n={N_SAMPLES}, d={X.shape[1]}, k<=center count: {N_CENTERS_MAX}")
    print(f"Data shape: {X.shape}")
    print(f"k values: {KS}")
    print(f"OPT* trials: {N_TRIALS_OPT}, Ratio trials: {N_TRIALS_RATIO}")
    print()

    results = {}
    for k in KS:
        print(f"=== k = {k} ===")
        # Step 1: estimate OPT* via many k-means++ restarts
        t_opt = time.time()
        opt_star = find_opt_star(X, k)
        dt_opt = time.time() - t_opt
        print(f"  OPT* (best over {N_TRIALS_OPT} runs) = {opt_star:.6f}   [{dt_opt:.1f}s]")

        # Step 2: run single k-means++ trials and compute ratios
        t_rat = time.time()
        inertias = run_trials(X, k)
        ratios = [i / opt_star for i in inertias]
        dt_rat = time.time() - t_rat
        print(f"  Single-run trials: {N_TRIALS_RATIO}, time: {dt_rat:.1f}s")

        mean_r = float(np.mean(ratios))
        max_r = float(np.max(ratios))
        med_r = float(np.median(ratios))
        std_r = float(np.std(ratios))
        min_r = float(np.min(ratios))
        p95_r = float(np.percentile(ratios, 95))
        # Theoretical bounds (Arthur & Vassilvitskii 2007)
        bound_8lnk2 = 8.0 * (np.log(k) + 2.0)
        bound_2lnk = 2.0 * np.log(k)

        results[k] = {
            "opt_star": opt_star,
            "n_trials_opt": N_TRIALS_OPT,
            "n_trials_ratio": N_TRIALS_RATIO,
            "ratios": ratios,
            "inertias": inertias,
            "mean_ratio": mean_r,
            "max_ratio": max_r,
            "min_ratio": min_r,
            "median_ratio": med_r,
            "std_ratio": std_r,
            "p95_ratio": p95_r,
            "theoretical_bound_8_lnk_plus_2": float(bound_8lnk2),
            "theoretical_bound_2_lnk": float(bound_2lnk),
        }
        print(f"  Ratio: mean={mean_r:.4f}, max={max_r:.4f}, "
              f"min={min_r:.4f}, p95={p95_r:.4f}, std={std_r:.4f}")
        print(f"  Theoretical upper bound 8(ln k + 2) = {bound_8lnk2:.4f}, "
              f"lower bound 2 ln k = {bound_2lnk:.4f}")
        print()

    # Save raw data
    out = {
        "settings": {
            "n_samples": N_SAMPLES,
            "data_seed": DATA_SEED,
            "ks": KS,
            "n_trials_opt": N_TRIALS_OPT,
            "n_trials_ratio": N_TRIALS_RATIO,
            "cluster_std": CLUSTER_STD,
            "n_features": RANDOM_DIM,
            "max_iter": MAX_ITER,
            "n_init_per_call": N_INIT,
        },
        "results": {str(k): results[k] for k in KS},
    }
    with open("raw_results.json", "w") as f:
        json.dump(out, f, indent=2)

    print(f"Total time: {time.time()-t0:.1f}s")
    print("Saved raw_results.json")


if __name__ == "__main__":
    main()
