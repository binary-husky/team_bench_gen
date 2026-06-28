"""
Experiment: effect of n_estimators on score stability and detection AUC.

Per task.md:
- Fixed dataset (fixed seed), psi (max_samples) = 256.
- n_estimators in {10, 50, 100, 200, 500}.
- For each n_estimators, run multiple random_states (replicates).
- Stability metric: for each point, variance of its anomaly score across
  replicates; average that over all points -> "mean score variance".
- Detection metric: AUC (vs ground-truth labels).
- Only n_estimators is the independent variable.
"""
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

# ----------------------------------------------------------------------
# 1. Fixed dataset (fixed seed). Synthetic anomaly-detection benchmark:
#    inliers drawn from Gaussian blobs; anomalies from a broad uniform.
#    Seed is fixed so the dataset is identical across all runs.
# ----------------------------------------------------------------------
DS_SEED = 42
N_SAMPLES = 3000
N_FEATURES = 8
CONTAMINATION = 0.10

rng = np.random.RandomState(DS_SEED)
n_inliers = int(N_SAMPLES * (1 - CONTAMINATION))
n_outliers = N_SAMPLES - n_inliers

# inliers: two Gaussian blobs
from sklearn.datasets import make_blobs
X_in, _ = make_blobs(n_samples=n_inliers, n_features=N_FEATURES,
                     centers=3, cluster_std=0.8, random_state=DS_SEED)
# anomalies: uniform over a wide box covering [-8, 8]
X_out = rng.uniform(low=-8.0, high=8.0,
                    size=(n_outliers, N_FEATURES))
X = np.vstack([X_in, X_out])
y = np.array([0] * n_inliers + [1] * n_outliers)   # 1 = anomaly

# standardize (fit only once, fixed)
X = StandardScaler().fit_transform(X)
# shuffle order (so labels not contiguous) with fixed seed
perm = np.random.RandomState(DS_SEED).permutation(len(X))
X, y = X[perm], y[perm]

print(f"Dataset: N={len(X)}  d={N_FEATURES}  anomalies={int(y.sum())} "
      f"({y.mean()*100:.1f}%)")

# ----------------------------------------------------------------------
# 2. Experiment
# ----------------------------------------------------------------------
PSI = 256                      # max_samples (sub-sampling size)
N_EST = [10, 50, 100, 200, 500]
# replicate seeds (independent of dataset seed)
REPLICA_SEEDS = list(range(0, 20))

# anomaly score: higher = more anomalous. We use -decision_function.
def scores_of(model, X):
    return -model.decision_function(X)   # higher -> more anomalous

rows = []
for n in N_EST:
    score_matrix = []   # shape (n_replicas, N) : per-point scores across replicas
    aucs = []
    for s in REPLICA_SEEDS:
        clf = IsolationForest(n_estimators=n, max_samples=PSI,
                              contamination='auto', random_state=s,
                              n_jobs=-1)
        clf.fit(X)
        sc = scores_of(clf, X)
        score_matrix.append(sc)
        aucs.append(roc_auc_score(y, sc))
    score_matrix = np.vstack(score_matrix)            # (R, N)
    # per-point variance across replicas, averaged over points
    per_point_var = score_matrix.var(axis=0, ddof=1)  # (N,)
    mean_var = per_point_var.mean()
    auc_mean = float(np.mean(aucs))
    auc_std = float(np.std(aucs, ddof=1))
    # also: AUC of the score averaged across replicas (ensemble-averaged score)
    avg_score = score_matrix.mean(axis=0)
    auc_avg = roc_auc_score(y, avg_score)
    rows.append(dict(n_estimators=n, mean_score_var=mean_var,
                     auc_mean=auc_mean, auc_std=auc_std,
                     auc_ensemble_avg=auc_avg,
                     n_replicas=len(REPLICA_SEEDS)))
    print(f"n_est={n:4d}  mean_var={mean_var:.6e}  "
          f"AUC(mean over replicas)={auc_mean:.4f} +/- {auc_std:.4f}  "
          f"AUC(ensemble-avg score)={auc_avg:.4f}")

# save raw table
import json
with open("results.json", "w") as f:
    json.dump(rows, f, indent=2)

# also dump a markdown-friendly summary
print("\nDone. rows:")
for r in rows:
    print(r)
