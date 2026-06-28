import numpy as np
from sklearn.datasets import make_blobs
from sklearn.cluster import KMeans

# Fixed settings
N = 5000
K = 10
N_INIT = 1
SEEDS = list(range(20))
STDS = [0.5, 1.0, 1.5, 2.5, 4.0]
DATA_SEED = 42  # fixed dataset seed per cluster_std

results = []
for std in STDS:
    # Fixed dataset for this std
    X, _ = make_blobs(n_samples=N, centers=K, cluster_std=std,
                      random_state=DATA_SEED)
    iner_pp = []
    iner_rand = []
    for rs in SEEDS:
        km_pp = KMeans(n_clusters=K, init='k-means++', n_init=N_INIT,
                       random_state=rs, max_iter=300).fit(X)
        km_rand = KMeans(n_clusters=K, init='random', n_init=N_INIT,
                         random_state=rs, max_iter=300).fit(X)
        iner_pp.append(km_pp.inertia_)
        iner_rand.append(km_rand.inertia_)
    m_pp = np.mean(iner_pp)
    m_rand = np.mean(iner_rand)
    ratio = m_rand / m_pp
    results.append((std, m_pp, m_rand, ratio))
    print(f"std={std:>4}  inertia_pp={m_pp:.2f}  inertia_rand={m_rand:.2f}  ratio={ratio:.4f}")

print("\nDone.")
