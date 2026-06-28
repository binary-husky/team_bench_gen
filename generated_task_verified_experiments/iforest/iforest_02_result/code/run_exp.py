import numpy as np
from sklearn.datasets import make_blobs
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score

# --- Build dataset: ~5000 normal points in clusters, +2% uniform outliers ---
rng_seed = 42
n_normal = 5000
n_centers = 5
# normal points clustered
X_normal, _ = make_blobs(
    n_samples=n_normal,
    n_features=2,
    centers=n_centers,
    cluster_std=1.0,
    center_box=(-10.0, 10.0),
    random_state=rng_seed,
)

# ~2% outliers as uniform distribution
n_outliers = int(round(0.02 * n_normal))  # 100
rng = np.random.RandomState(rng_seed)
# uniform over a region larger than the clusters so outliers are clearly anomalous
X_outliers = rng.uniform(low=-15, high=15, size=(n_outliers, 2))

X = np.vstack([X_normal, X_outliers])
# labels: 1 = normal, -1 = anomaly (isolation forest convention for anomaly)
y = np.concatenate([np.ones(n_normal, dtype=int), -np.ones(n_outliers, dtype=int)])
# For AUC we need a "anomaly score": higher = more anomalous.
# IsolationForest decision_function: higher = more normal (anomaly = lower score).
# So anomaly_score = -decision_function (or score_samples). Use -decision_function.

print(f"Dataset: {X.shape[0]} points, {n_outliers} outliers ({n_outliers/X.shape[0]*100:.2f}%)")
print(f"Features: {X.shape[1]}, clusters (normal): {n_centers}")

psis = [16, 32, 64, 128, 256, 512, None]

results = []
for psi in psis:
    # max_samples = psi; None means use whole dataset
    max_samples = psi if psi is not None else X.shape[0]
    clf = IsolationForest(
        n_estimators=100,
        max_samples=max_samples,
        random_state=0,
        n_jobs=-1,
    )
    clf.fit(X)
    # anomaly score: higher = more anomalous
    score = -clf.decision_function(X)
    auc = roc_auc_score(
        # convert: anomaly (-1) should be the positive class for AUC of "detection"
        (y == -1).astype(int),
        score,
    )
    label = "None (full)" if psi is None else str(psi)
    print(f"psi={label:>12}: max_samples={max_samples:<6}  AUC={auc:.4f}")
    results.append((label, max_samples, auc))

print("\n--- summary table ---")
print(f"{'psi':>12} {'max_samples':>12} {'AUC':>8}")
for label, ms, auc in results:
    print(f"{label:>12} {ms:>12} {auc:>8.4f}")

# Save results to a small json for reference
import json
with open("results.json", "w") as f:
    json.dump([{"psi": l, "max_samples": ms, "auc": a} for l, ms, a in results], f, indent=2)
