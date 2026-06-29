"""
Experiment: compare Lloyd-iteration counts for init='k-means++' vs init='random'
on the same fixed dataset (n=5000, k=10), sweeping ~30 random_states with n_init=1.
"""
import numpy as np
from sklearn.cluster import KMeans
from sklearn.datasets import make_blobs

# ---------- Fixed settings ----------
N_SAMPLES = 5000
N_FEATURES = 2
N_CLUSTERS = 10
DATA_SEED = 42                # fixed dataset seed
RANDOM_STATES = list(range(30))  # ~30 random_states
N_INIT = 1
TOL = 1e-4
MAX_ITER = 300

# ---------- Generate the fixed dataset once ----------
X, y_true = make_blobs(
    n_samples=N_SAMPLES,
    n_features=N_FEATURES,
    centers=N_CLUSTERS,
    cluster_std=1.0,
    random_state=DATA_SEED,
    shuffle=True,
)

print(f"dataset: n={X.shape[0]}, d={X.shape[1]}, true_k={len(np.unique(y_true))}")


def run_one(init_name: str, rs: int) -> int:
    km = KMeans(
        n_clusters=N_CLUSTERS,
        init=init_name,
        n_init=N_INIT,
        max_iter=MAX_ITER,
        tol=TOL,
        random_state=rs,
    )
    km.fit(X)
    return int(km.n_iter_)


def collect(init_name: str) -> list[int]:
    return [run_one(init_name, rs) for rs in RANDOM_STATES]


kpp_iters = collect("k-means++")
rnd_iters = collect("random")


def stats(name: str, arr: list[int]) -> dict:
    a = np.asarray(arr, dtype=int)
    return {
        "name": name,
        "mean": float(a.mean()),
        "std": float(a.std(ddof=1)),       # sample std (ddof=1)
        "min": int(a.min()),
        "median": float(np.median(a)),
        "max": int(a.max()),
        "values": arr,
    }


s_kpp = stats("k-means++", kpp_iters)
s_rnd = stats("random", rnd_iters)

# ---------- Pretty print ----------
print()
print(f"{'init':<12s}  mean    std     min  median  max")
for s in (s_kpp, s_rnd):
    print(
        f"{s['name']:<12s}  "
        f"{s['mean']:5.2f}  {s['std']:5.2f}  "
        f"{s['min']:3d}  {s['median']:5.1f}  {s['max']:3d}"
    )

# Save raw numbers for the summary
import json
out = {
    "dataset": {
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "k": N_CLUSTERS,
        "data_seed": DATA_SEED,
    },
    "kmeans_settings": {
        "n_init": N_INIT,
        "tol": TOL,
        "max_iter": MAX_ITER,
        "random_states": RANDOM_STATES,
    },
    "kmeanspp": s_kpp,
    "random": s_rnd,
}
with open("lloyd_iters_raw.json", "w") as f:
    json.dump(out, f, indent=2)

print("\nWrote lloyd_iters_raw.json")
