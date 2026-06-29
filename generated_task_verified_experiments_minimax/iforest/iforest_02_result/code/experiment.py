"""
Experiment: Effect of sub-sampling size ψ (max_samples) on Isolation Forest
detection performance (AUC), as described in Liu, Ting, Zhou (2008).

Setup:
- Normal data: ~5000 points via sklearn.datasets.make_blobs (multi-cluster)
- Anomalies: ~2% uniform-outlier points (known labels), fixed random seed
- IsolationForest(n_estimators=100, random_state=0), vary max_samples ψ
- Metric: sklearn.metrics.roc_auc_score
"""
import numpy as np
from sklearn.datasets import make_blobs
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score
import time

# ---- Reproducible dataset construction ----
DATA_SEED = 0
N_NORMAL = 5000
CONTAMINATION = 0.02  # 2% anomalies
N_ANOMALY = int(N_NORMAL * CONTAMINATION / (1 - CONTAMINATION))  # ~102
# Note: paper says "约 5000 个正常点 + 约 2% 的均匀分布离群点", meaning
# anomalies are about 2% of the total. We build total so that ~2% is anomalous.

# 1) Generate normal points with a few Gaussian clusters
X_normal, _ = make_blobs(
    n_samples=N_NORMAL,
    centers=[[0, 0], [5, 5], [-4, 3], [3, -4]],  # several clusters
    cluster_std=[1.0, 1.2, 0.9, 1.1],
    n_features=2,
    random_state=DATA_SEED,
)

# 2) Generate uniform-outlier points in a bounding box larger than the data
x_min, x_max = X_normal[:, 0].min() - 3, X_normal[:, 0].max() + 3
y_min, y_max = X_normal[:, 1].min() - 3, X_normal[:, 1].max() + 3
rng_outlier = np.random.RandomState(DATA_SEED + 1)
X_outliers = rng_outlier.uniform(
    low=[x_min, y_min], high=[x_max, y_max], size=(N_ANOMALY, 2)
)

# 3) Combine, label anomalies=1, normal=0
X = np.vstack([X_normal, X_outliers])
y = np.concatenate([np.zeros(N_NORMAL, dtype=int), np.ones(N_ANOMALY, dtype=int)])

print(f"Total samples: {len(X)} (normal={N_NORMAL}, anomalies={N_ANOMALY})")
print(f"Anomaly ratio in dataset: {y.mean():.4f}")

# ---- Vary ψ and measure AUC ----
psi_values = [16, 32, 64, 128, 256, 512, "full"]  # "full" == use every sample
results = []

for psi in psi_values:
    # Map the "full" sentinel to an explicit integer >= len(X) so the new
    # sklearn API accepts it (it no longer accepts None).
    max_samples_arg = len(X) if psi == "full" else psi
    label = "full" if psi == "full" else str(psi)
    t0 = time.time()
    iso = IsolationForest(
        n_estimators=100,
        max_samples=max_samples_arg,
        random_state=0,
        n_jobs=1,
    )
    iso.fit(X)
    # decision_function: higher => more normal. We want anomaly score s.
    # The paper's s = 2 ** (-E(h)/c(n)) is monotonically decreasing in path length.
    # In sklearn, decision_function = -score_samples (path length-based, monotonic in s).
    # Use score_samples and negate so larger => more anomalous (matches s).
    raw = -iso.score_samples(X)
    auc = roc_auc_score(y, raw)
    elapsed = time.time() - t0
    results.append((psi, auc, elapsed))
    print(f"ψ={label:>5}  AUC={auc:.4f}  time={elapsed:.2f}s")

# ---- Persist a small CSV-like table for the summary ----
with open("results.csv", "w") as f:
    f.write("psi,auc,seconds\n")
    for psi, auc, t in results:
        psi_str = "None" if psi == "full" else str(psi)
        f.write(f"{psi_str},{auc:.6f},{t:.4f}\n")

print("\nResults written to results.csv")
