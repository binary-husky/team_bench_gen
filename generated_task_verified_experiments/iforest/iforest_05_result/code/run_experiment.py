"""
iForest vs LOF baseline comparison.

Reproducible anomaly-detection benchmark comparing
sklearn.ensemble.IsolationForest (psi=256, n_estimators=100, random_state=0)
against sklearn.neighbors.LocalOutlierFactor (baseline, k=10 as in the paper).

Dataset: since no external data is provided in this directory, we generate a
fixed-seed synthetic benchmark in the spirit of the paper's Mulcross generator
(multivariate-Gaussian normal cluster + distant anomaly clusters, contamination=10%).
The seed is fixed so the data is identical for both methods.
"""
import time
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.metrics import roc_auc_score

SEED = 0
rng = np.random.RandomState(SEED)

# ------------------------------------------------------------------
# Build a fixed, reproducible anomaly-detection benchmark dataset.
# Normal points: one multivariate Gaussian cluster.
# Anomalies: two distant Gaussian clusters (distance factor = 2 in units of std).
# Contamination = 10%.
# ------------------------------------------------------------------
N = 20000
D = 10
CONTAMINATION = 0.10
n_anom = int(N * CONTAMINATION)
n_norm = N - n_anom

mean_normal = np.zeros(D)
cov_normal = np.eye(D)
X_normal = rng.multivariate_normal(mean_normal, cov_normal, size=n_norm)

# Anomalies: scattered (sparse) outliers drawn uniformly from a wide ring
# outside the normal cluster, so they are genuinely isolated points that BOTH
# a distance/density method (LOF) and an isolation method (iForest) can detect.
# This is the classic Gaussian + uniform-outlier anomaly benchmark and gives a
# fair, non-degenerate baseline comparison.
radius = np.linalg.norm(X_normal, axis=1)
r_lo, r_hi = np.quantile(radius, 0.99), np.quantile(radius, 0.99) + 6.0
dir_uniform = rng.standard_normal((n_anom, D))
dir_uniform /= np.linalg.norm(dir_uniform, axis=1, keepdims=True)
radii = rng.uniform(r_lo, r_hi, size=n_anom)
X_anom = dir_uniform * radii[:, None]

X = np.vstack([X_normal, X_anom])
y = np.concatenate([np.zeros(n_norm), np.ones(n_anom)]).astype(int)  # 1 = anomaly

# shuffle
perm = rng.permutation(N)
X = X[perm]
y = y[perm]

print(f"Dataset: N={N}, D={D}, anomalies={y.sum()} ({y.mean()*100:.1f}%)")
print("-" * 60)


def bench_iforest():
    clf = IsolationForest(
        n_estimators=100,
        max_samples=256,   # psi = 256
        contamination="auto",
        random_state=SEED,
        n_jobs=1,
    )
    t0 = time.perf_counter()
    clf.fit(X)
    t_fit = time.perf_counter() - t0

    t0 = time.perf_counter()
    scores = -clf.score_samples(X)   # higher = more anomalous
    t_pred = time.perf_counter() - t0

    auc = roc_auc_score(y, scores)
    return auc, t_fit, t_pred


def bench_lof():
    # k=10 as commonly used in the iForest paper for LOF.
    clf = LocalOutlierFactor(n_neighbors=10, contamination="auto", n_jobs=1)
    t0 = time.perf_counter()
    clf.fit(X)
    t_fit = time.perf_counter() - t0

    t0 = time.perf_counter()
    # negative_outlier_factor_: lower = more anomalous -> negate for AUC
    scores = -clf.negative_outlier_factor_
    t_pred = time.perf_counter() - t0

    auc = roc_auc_score(y, scores)
    return auc, t_fit, t_pred


# run a few repetitions to stabilise timings; AUC is deterministic given seed
N_REPS = 5
if_results = [bench_iforest() for _ in range(N_REPS)]
lof_results = [bench_lof() for _ in range(N_REPS)]


def summarize(results):
    aucs = [r[0] for r in results]
    fits = [r[1] for r in results]
    preds = [r[2] for r in results]
    return (
        aucs[0],                       # AUC deterministic
        float(np.mean(fits)), float(np.max(fits)),
        float(np.mean(preds)), float(np.max(preds)),
        float(np.mean(fits) + np.mean(preds)),
    )


if_auc, if_fit_mean, if_fit_max, if_pred_mean, if_pred_max, if_total = summarize(if_results)
lof_auc, lof_fit_mean, lof_fit_max, lof_pred_mean, lof_pred_max, lof_total = summarize(lof_results)

print("IsolationForest (psi=256, t=100, random_state=0):")
print(f"  AUC          = {if_auc:.4f}")
print(f"  fit time     = {if_fit_mean*1000:.1f} ms (max {if_fit_max*1000:.1f} ms)")
print(f"  predict time = {if_pred_mean*1000:.1f} ms (max {if_pred_max*1000:.1f} ms)")
print(f"  total        = {if_total*1000:.1f} ms")
print()
print("LocalOutlierFactor (k=10, baseline):")
print(f"  AUC          = {lof_auc:.4f}")
print(f"  fit time     = {lof_fit_mean*1000:.1f} ms (max {lof_fit_max*1000:.1f} ms)")
print(f"  predict time = {lof_pred_mean*1000:.1f} ms (max {lof_pred_max*1000:.1f} ms)")
print(f"  total        = {lof_total*1000:.1f} ms")
print()
print(f"AUC delta (iForest - LOF)     = {if_auc - lof_auc:+.4f}")
print(f"Speedup (LOF total / iForest) = {lof_total / if_total:.2f}x")

# persist raw numbers for the summary writer
import json
with open("results.json", "w") as f:
    json.dump({
        "dataset": {"N": N, "D": D, "contamination": CONTAMINATION,
                    "n_anomalies": int(y.sum()), "seed": SEED},
        "iforest": {"auc": if_auc, "fit_ms_mean": if_fit_mean*1000,
                    "pred_ms_mean": if_pred_mean*1000, "total_ms": if_total*1000},
        "lof": {"auc": lof_auc, "fit_ms_mean": lof_fit_mean*1000,
                "pred_ms_mean": lof_pred_mean*1000, "total_ms": lof_total*1000},
        "auc_delta": if_auc - lof_auc,
        "speedup": lof_total / if_total,
        "n_reps": N_REPS,
    }, f, indent=2)
