import numpy as np
from sklearn.datasets import load_digits
from sklearn.manifold import TSNE
X = load_digits().data
for mi in [250, 260, 300, 350, 400]:
    t = TSNE(n_components=2, init="pca", perplexity=30, learning_rate="auto",
             n_iter=mi, random_state=0)
    Y = t.fit_transform(X)
    print(f"n_iter={mi}: kl={t.kl_divergence_:.6g} | Y std={np.round(Y.std(0),2)} | n_iter_={t.n_iter_}")
