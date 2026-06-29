"""Sanity check: increase N_TRIALS_OPT to 800 for k=50 to see if OPT* estimate moves."""
import json
import numpy as np
from sklearn.datasets import make_blobs
from sklearn.cluster import KMeans

# Same dataset as run_experiment.py
N_SAMPLES = 5000
DATA_SEED = 42
CLUSTER_STD = 1.0
RANDOM_DIM = 2
N_CENTERS_MAX = 50
CENTERS = np.hstack([(np.arange(N_CENTERS_MAX) * 10.0).reshape(-1, 1),
                     np.zeros((N_CENTERS_MAX, 1))])

X, _ = make_blobs(n_samples=N_SAMPLES, centers=CENTERS, cluster_std=CLUSTER_STD,
                  n_features=RANDOM_DIM, random_state=DATA_SEED)

# Run k=50 with 800 seeds; record running min every 200
k = 50
results = []
best = np.inf
for i in range(800):
    s = 2000 + i
    km = KMeans(n_clusters=k, init="k-means++", n_init=1, max_iter=300, random_state=s)
    km.fit(X)
    if km.inertia_ < best:
        best = km.inertia_
    if (i + 1) % 200 == 0:
        results.append((i + 1, best))
        print(f"  after {i+1} trials: best inertia = {best:.6f}")

print("Running min over time:")
for n, b in results:
    print(f"  n={n}: {b:.6f}")
