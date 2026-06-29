"""
Experiment: Effect of n_estimators on Isolation Forest score stability and AUC.

Based on Liu, Ting, Zhou (2008) "Isolation Forest".

Setup:
- Fixed dataset (same for all n_estimators values) - synthetic 10D Mulcross-like
  (modeled after Section 5 of the paper)
- Fixed sub-sampling size psi = 256
- Variable: n_estimators in {10, 50, 100, 200, 500}
- For each n_estimators: multiple re-runs with different random_state
- Measure per-point anomaly score variance (averaged) and mean AUC

The dataset is a Mulcross-style synthetic: one dense normal Gaussian plus two
denser Gaussian anomaly clusters placed at distance_factor standard units away
from the normal center. The 2D "Mulcross" in the paper (distance_factor=2) is
not directly portable to 10D; in 10D the typical point lies at sqrt(d) ~ 3.16
units from the mean, so the anomalies need to be placed further out to be
detectable. We use distance_factor=4 which gives a moderate-difficulty problem
(single-IF AUC ~ 0.75), so we can see the effect of n_estimators on both
score stability and detection quality.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score
import time
import json

# ---------------------------------------------------------------------------
# Configuration (fixed across the sweep - the only variable is n_estimators)
# ---------------------------------------------------------------------------

# Reproducibility: fixed seed for the dataset
DATA_SEED = 42

# Mulcross-like synthetic data setup (per the paper, Section 5)
N_SAMPLES = 5000  # total
N_NORMAL = 4500
N_ANOMALY = 500  # 10% of 5000
D = 10
DISTANCE_FACTOR = 4.0  # anomaly centers at this many std-units from origin
N_ANOMALY_CLUSTERS = 2
ANOM_STD = 0.5  # tighter than normal (std 1) => denser

# Re-runs to assess stability
N_REPEATS = 30

# n_estimators values to test
N_ESTIMATORS_LIST = [10, 50, 100, 200, 500]

# Fixed sub-sampling size (psi from the paper)
PSI = 256


def make_mulcross_like(seed=DATA_SEED, n_normal=N_NORMAL, n_anomaly=N_ANOMALY,
                       d=D, distance_factor=DISTANCE_FACTOR,
                       n_anomaly_clusters=N_ANOMALY_CLUSTERS,
                       anom_std=ANOM_STD):
    """Generate a synthetic dataset similar to Mulcross (Rocke & Woodruff 1996)
    as described in the iForest paper (Section 5).
    """
    rng = np.random.default_rng(seed)
    # Main normal cluster: standard normal
    X_normal = rng.standard_normal(size=(n_normal, d))
    y_normal = np.zeros(n_normal, dtype=int)

    # Anomaly clusters: centers at distance `distance_factor` from origin
    # Each anomaly cluster is a tight Gaussian (denser than normal).
    n_per_anomaly = n_anomaly // n_anomaly_clusters
    X_anom = []
    for i in range(n_anomaly_clusters):
        direction = rng.standard_normal(size=d)
        direction /= np.linalg.norm(direction) + 1e-12
        center = direction * distance_factor
        n_here = n_per_anomaly
        if i == n_anomaly_clusters - 1:
            n_here = n_anomaly - n_per_anomaly * (n_anomaly_clusters - 1)
        X_anom.append(rng.normal(loc=center, scale=anom_std, size=(n_here, d)))
    X_anom = np.vstack(X_anom)
    y_anom = np.ones(X_anom.shape[0], dtype=int)

    X = np.vstack([X_normal, X_anom])
    y = np.concatenate([y_normal, y_anom])
    return X, y


def run_experiment():
    # 1) Build the dataset ONCE (fixed)
    print("Building fixed dataset...")
    X, y = make_mulcross_like(seed=DATA_SEED)
    n_pos = int((y == 1).sum())
    n_neg = int((y == 0).sum())
    print(f"  shape={X.shape}, anomalies={n_pos} ({100.0*n_pos/X.shape[0]:.1f}%), "
          f"normal={n_neg} ({100.0*n_neg/X.shape[0]:.1f}%)")
    print()

    results = []

    for n_est in N_ESTIMATORS_LIST:
        print(f"=== n_estimators = {n_est} ===")
        # Per-point scores across re-runs
        scores_matrix = np.zeros((N_REPEATS, X.shape[0]))
        aucs = np.zeros(N_REPEATS)
        times = np.zeros(N_REPEATS)

        for i in range(N_REPEATS):
            seed_i = 1000 + i  # distinct seeds for re-runs
            t0 = time.time()
            model = IsolationForest(
                n_estimators=n_est,
                max_samples=PSI,
                random_state=seed_i,
                n_jobs=1,
            )
            model.fit(X)
            # Anomaly score: -score_samples (paper's s, higher = more anomalous)
            scores = -model.score_samples(X)
            scores_matrix[i] = scores
            aucs[i] = roc_auc_score(y, scores)
            times[i] = time.time() - t0

        # Score stability: per-point variance across re-runs, then average
        per_point_var = scores_matrix.var(axis=0, ddof=1)  # unbiased variance
        mean_var = float(per_point_var.mean())
        std_var = float(per_point_var.std())
        max_var = float(per_point_var.max())
        # Per-point std (averaged)
        per_point_std = scores_matrix.std(axis=0, ddof=1)
        mean_std = float(per_point_std.mean())
        max_std = float(per_point_std.max())
        # Mean score (for normalization)
        mean_score = float(scores_matrix.mean())
        # CV proxy: std/mean ratio (mean across re-runs and points)
        cv_proxy = mean_std / (np.abs(mean_score) + 1e-12)

        # AUC stats
        mean_auc = float(aucs.mean())
        std_auc = float(aucs.std(ddof=1))
        min_auc = float(aucs.min())
        max_auc = float(aucs.max())
        mean_time = float(times.mean())

        # Per-class score variance (anomalies vs normal)
        per_class_var = {}
        for cls, name in [(0, "normal"), (1, "anomaly")]:
            mask = (y == cls)
            per_class_var[name] = float(per_point_var[mask].mean())

        # Average score stability: how much does the top-1% most-anomalous set
        # overlap across re-runs (Jaccard between two re-runs' top-K labels)?
        K = int(0.01 * X.shape[0])  # top 1%
        # Just measure the average score std for the top-scoring points in
        # the first re-run (a rough stability indicator for the high-score end)
        first_top_mask = np.argsort(scores_matrix[0])[-K:]
        top_score_var = float(per_point_var[first_top_mask].mean())
        top_score_std = float(per_point_std[first_top_mask].mean())

        result = {
            "n_estimators": n_est,
            "psi": PSI,
            "n_repeats": N_REPEATS,
            "mean_auc": mean_auc,
            "std_auc": std_auc,
            "min_auc": min_auc,
            "max_auc": max_auc,
            "mean_score_var": mean_var,
            "std_score_var": std_var,
            "max_score_var": max_var,
            "mean_score_std": mean_std,
            "max_score_std": max_std,
            "cv_proxy": cv_proxy,
            "mean_score": mean_score,
            "mean_time_sec": mean_time,
            "score_var_normal": per_class_var["normal"],
            "score_var_anomaly": per_class_var["anomaly"],
            "top1pct_score_var": top_score_var,
            "top1pct_score_std": top_score_std,
            "all_aucs": aucs.tolist(),
            "all_score_vars_per_point": per_point_var.tolist(),
        }
        results.append(result)
        print(f"  AUC:        mean={mean_auc:.4f} std={std_auc:.4f} "
              f"min={min_auc:.4f} max={max_auc:.4f}")
        print(f"  Score var:  mean={mean_var:.4e} (normal={per_class_var['normal']:.4e}, "
              f"anom={per_class_var['anomaly']:.4e})")
        print(f"  Score std:  mean={mean_std:.4e} max={max_std:.4e}")
        print(f"  Top-1% std: {top_score_std:.4e}")
        print(f"  Time/fit:   {mean_time*1000:.2f} ms")
        print()

    # Save raw results
    with open("results_n_estimators.json", "w") as f:
        json.dump(results, f, indent=2)

    # Also save a tidy CSV
    rows = []
    for r in results:
        rows.append({
            "n_estimators": r["n_estimators"],
            "psi": r["psi"],
            "n_repeats": r["n_repeats"],
            "mean_auc": r["mean_auc"],
            "std_auc": r["std_auc"],
            "min_auc": r["min_auc"],
            "max_auc": r["max_auc"],
            "mean_score_var": r["mean_score_var"],
            "std_score_var": r["std_score_var"],
            "max_score_var": r["max_score_var"],
            "mean_score_std": r["mean_score_std"],
            "mean_score": r["mean_score"],
            "score_var_normal": r["score_var_normal"],
            "score_var_anomaly": r["score_var_anomaly"],
            "top1pct_score_std": r["top1pct_score_std"],
            "mean_time_sec": r["mean_time_sec"],
        })
    df = pd.DataFrame(rows)
    df.to_csv("results_n_estimators.csv", index=False)
    print("\nSaved: results_n_estimators.json, results_n_estimators.csv")
    return results, X, y


if __name__ == "__main__":
    results, X, y = run_experiment()
    print("\n=== Summary table ===")
    print(f"{'n_est':>6} | {'AUC mean':>9} {'AUC std':>9} | "
          f"{'score_var':>11} {'score_std':>11} | {'time(ms)':>8}")
    for r in results:
        print(f"{r['n_estimators']:>6d} | "
              f"{r['mean_auc']:>9.4f} {r['std_auc']:>9.4f} | "
              f"{r['mean_score_var']:>11.4e} {r['mean_score_std']:>11.4e} | "
              f"{r['mean_time_sec']*1000:>8.2f}")
