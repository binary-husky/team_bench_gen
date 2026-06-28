import time
import numpy as np
from sklearn.datasets import load_digits
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_score

digits = load_digits()
X = digits.data
y = digits.target
print(f"data: X={X.shape}, classes={len(np.unique(y))}")

rows = []
for max_iter in [250, 500, 1000, 2000]:
    t0 = time.time()
    tsne = TSNE(
        n_components=2,
        init="pca",
        perplexity=30,
        learning_rate="auto",
        max_iter=max_iter,
        random_state=0,
    )
    Y = tsne.fit_transform(X)
    elapsed = time.time() - t0
    kl = float(tsne.kl_divergence_)
    sil = float(silhouette_score(Y, y))
    n_iter_run = int(tsne.n_iter_)
    print(f"max_iter={max_iter:5d} | kl={kl:.4f} | silhouette={sil:.4f} | "
          f"n_iter_={n_iter_run} | time={elapsed:.1f}s")
    rows.append((max_iter, kl, sil, n_iter_run, elapsed))

# Save raw results for the summary
np.save("results.npy", np.array(rows, dtype=float))
print("DONE")
