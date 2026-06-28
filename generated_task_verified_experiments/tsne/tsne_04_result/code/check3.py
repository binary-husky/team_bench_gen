import numpy as np
from sklearn.datasets import load_digits
from sklearn.manifold import TSNE
X = load_digits().data
for mi in [250, 300, 400, 500, 1000]:
    t = TSNE(n_components=2, init="pca", perplexity=30, learning_rate="auto",
             max_iter=mi, random_state=0)
    Y = t.fit_transform(X)
    print(f"max_iter={mi:5d}: kl={t.kl_divergence_:.6g} | "
          f"Y_std={np.round(Y.std(0),2)} | Y_range=[{Y.min():.1f},{Y.max():.1f}] | "
          f"n_iter_={t.n_iter_}")
