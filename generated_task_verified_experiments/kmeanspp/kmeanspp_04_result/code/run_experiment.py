"""
Experiment: Lloyd iterations to convergence for k-means++ vs random init.

Fixed setup:
  - Dataset: make_blobs, n_samples=5000, centers=k=10, fixed seed (dataset_seed=42)
  - k=10
  - n_init=1
  - tol=1e-4 (sklearn default)
  - algorithm='lloyd'
  - ~30 random_states for the KMeans run (0..29)
Independent variable: init method ('k-means++' vs 'random').
Measured: km.n_iter_ per run.
"""
import numpy as np
from sklearn.datasets import make_blobs
from sklearn.cluster import KMeans

# ---- fixed dataset ----
DATASET_SEED = 42
N = 5000
K = 10
X, _ = make_blobs(n_samples=N, centers=K, n_features=10,
                  random_state=DATASET_SEED, cluster_std=1.5)

TOL = 1e-4
MAX_ITER = 300
N_TRIALS = 30
random_states = list(range(N_TRIALS))

def run(init):
    iters = []
    inerts = []
    for rs in random_states:
        km = KMeans(n_clusters=K, init=init, n_init=1,
                    max_iter=MAX_ITER, tol=TOL,
                    algorithm='lloyd', random_state=rs)
        km.fit(X)
        iters.append(int(km.n_iter_))
        inerts.append(float(km.inertia_))
    return np.array(iters), np.array(inerts)

results = {}
for init in ['k-means++', 'random']:
    iters, inerts = run(init)
    results[init] = (iters, inerts)
    print(f"=== init='{init}' ===")
    print("n_iter_:", iters.tolist())
    print(f"mean={iters.mean():.3f}  std={iters.std(ddof=1):.3f}  "
          f"min={iters.min()}  max={iters.max()}")
    print(f"inertia mean={inerts.mean():.3f}  std={inerts.std(ddof=1):.3f}  "
          f"min={inerts.min():.3f}  max={inerts.max():.3f}")
    print()

# Save raw data for the summary
np.savez('results.npz',
         random_states=np.array(random_states),
         pp_iters=results['k-means++'][0],
         pp_inerts=results['k-means++'][1],
         rnd_iters=results['random'][0],
         rnd_inerts=results['random'][1])
print("saved results.npz")
