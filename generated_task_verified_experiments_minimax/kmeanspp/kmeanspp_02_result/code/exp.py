"""
Compare KMeans inertia for k-means++ vs random initialization.
- Dataset: make_blobs(n=5000, k=10, fixed random seed)
- 30 different random_state values for each init method
- n_init=1 (only one initialization per run)
"""
import numpy as np
from sklearn.datasets import make_blobs
from sklearn.cluster import KMeans
import json
import time

# Generate dataset with a fixed random seed
DATA_SEED = 42
N_SAMPLES = 5000
K = 10
N_TRIALS = 30

print("Generating dataset...")
X, y_true = make_blobs(n_samples=N_SAMPLES, centers=K, n_features=2, random_state=DATA_SEED)
print(f"Dataset shape: {X.shape}, true centers: {K}")

# Map key in results to (init kwarg, label)
configs = [
    ('kmeanspp', 'k-means++'),
    ('random',   'random'),
]
results = {key: [] for key, _ in configs}

random_states = list(range(N_TRIALS))

for key, init_method in configs:
    print(f"\n--- Running init={init_method} ---")
    t0 = time.time()
    for rs in random_states:
        km = KMeans(n_clusters=K, init=init_method, n_init=1, random_state=rs, max_iter=300)
        km.fit(X)
        results[key].append(float(km.inertia_))
    print(f"  done in {time.time()-t0:.2f}s")

# Compute statistics
def stats(name, vals):
    arr = np.array(vals)
    return {
        'name': name,
        'mean': float(arr.mean()),
        'std': float(arr.std(ddof=0)),     # population std
        'std_sample': float(arr.std(ddof=1)),  # sample std
        'min': float(arr.min()),
        'max': float(arr.max()),
        'median': float(np.median(arr)),
        'values': vals,
    }

s_pp = stats('k-means++', results['kmeanspp'])
s_rd = stats('random',   results['random'])

print("\n=== k-means++ ===")
print(f"  mean = {s_pp['mean']:.4f}, std = {s_pp['std']:.4f}, min = {s_pp['min']:.4f}, max = {s_pp['max']:.4f}, median = {s_pp['median']:.4f}")
print("\n=== random ===")
print(f"  mean = {s_rd['mean']:.4f}, std = {s_rd['std']:.4f}, min = {s_rd['min']:.4f}, max = {s_rd['max']:.4f}, median = {s_rd['median']:.4f}")

print(f"\nratio mean(random)/mean(kmeans++) = {s_rd['mean']/s_pp['mean']:.4f}")
print(f"ratio max(random)/min(kmeans++)   = {s_rd['max']/s_pp['min']:.4f}")
print(f"ratio std(random)/std(kmeans++)   = {s_rd['std']/s_pp['std']:.4f}")

# Persist results
with open('/data/workspace/admin/happy_lake/.verify_judge_minimax/kmeanspp/kmeanspp_02/results.json', 'w') as f:
    json.dump({
        'kmeanspp': s_pp,
        'random':   s_rd,
        'data_seed': DATA_SEED,
        'n_samples': N_SAMPLES,
        'k': K,
        'n_trials': N_TRIALS,
    }, f, indent=2)
print("\nResults saved to results.json")
