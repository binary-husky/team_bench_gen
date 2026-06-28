import numpy as np
from sklearn.datasets import make_blobs
from sklearn.cluster import KMeans

# Fixed dataset: n=5000 points, k=10 gaussian clusters, fixed seed.
N = 5000
K = 10
DATA_SEED = 0

X, _ = make_blobs(
    n_samples=N,
    centers=K,
    n_features=2,
    cluster_std=1.0,
    random_state=DATA_SEED,
)

# Fixed set of random_states for the KMeans runs.
random_states = list(range(30))

results = {"k-means++": [], "random": []}
for init in ["k-means++", "random"]:
    for rs in random_states:
        km = KMeans(
            n_clusters=K,
            init=init,
            n_init=1,
            random_state=rs,
            algorithm="lloyd",
        )
        km.fit(X)
        results[init].append(float(km.inertia_))

for init in ["k-means++", "random"]:
    arr = np.array(results[init])
    print(f"=== init={init} ===")
    print(f"  mean   = {arr.mean():.4f}")
    print(f"  std    = {arr.std(ddof=1):.4f}")
    print(f"  min    = {arr.min():.4f}")
    print(f"  max    = {arr.max():.4f}")
    print(f"  median = {np.median(arr):.4f}")
    print()

kmpp = np.array(results["k-means++"])
rand = np.array(results["random"])
print(f"k-means++ mean advantage over random mean: "
      f"{(rand.mean() - kmpp.mean()) / rand.mean() * 100:.2f}%")
print(f"k-means++ worst (max) vs random worst (max): "
      f"{kmpp.max():.4f} vs {rand.max():.4f}")
print(f"ratio random_best/kmpp_best: {rand.min()/kmpp.min():.4f}")

# Save raw numbers for the summary.
np.savez("results.npz",
         kmpp=kmpp, rand=rand,
         random_states=np.array(random_states),
         data_seed=DATA_SEED, n=N, k=K)
print("saved results.npz")
