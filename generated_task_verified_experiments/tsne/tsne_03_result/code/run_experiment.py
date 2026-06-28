"""
Compare t-SNE vs PCA 2D embeddings on sklearn digits (1797x64, 10 classes).

Fixed hyperparameters per task:
  TSNE: n_components=2, init='pca', perplexity=30, learning_rate='auto',
        max_iter=1000, random_state=0
  PCA:  first 2 principal components

Independent variable: reduction method (PCA vs t-SNE).
Metrics: silhouette score (by digit label), trustworthiness (n_neighbors=12).
"""

import numpy as np
from sklearn.datasets import load_digits
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE, trustworthiness
from sklearn.metrics import silhouette_score

RNG = 0
N_NEIGHBORS = 12

# ---------------------------------------------------------------- data
digits = load_digits()
X = digits.data.astype(np.float64)   # (1797, 64)
y = digits.target                     # (1797,) labels 0..9
print(f"Data: X={X.shape}  y={y.shape}  n_classes={len(np.unique(y))}")
print(f"feature range: [{X.min():.1f}, {X.max():.1f}]  mean={X.mean():.2f}")

# ---------------------------------------------------------------- PCA
pca = PCA(n_components=2, random_state=RNG)
X_pca = pca.fit_transform(X)
print(f"\nPCA explained var (2 comps): {pca.explained_variance_ratio_.sum():.4f}"
      f"  per-comp={pca.explained_variance_ratio_}")

# ---------------------------------------------------------------- t-SNE
tsne = TSNE(
    n_components=2,
    init="pca",
    perplexity=30,
    learning_rate="auto",
    max_iter=1000,
    random_state=RNG,
)
X_tsne = tsne.fit_transform(X)
print(f"t-SNE KL divergence (final): {tsne.kl_divergence_:.4f}  "
      f"n_iter={tsne.n_iter_}")

# ---------------------------------------------------------------- metrics
sil_pca = silhouette_score(X_pca, y)
sil_tsne = silhouette_score(X_tsne, y)

trust_pca = trustworthiness(X, X_pca, n_neighbors=N_NEIGHBORS)
trust_tsne = trustworthiness(X, X_tsne, n_neighbors=N_NEIGHBORS)

print("\n================ RESULTS ================")
print(f"{'metric':<28}{'PCA':>12}{'t-SNE':>12}")
print(f"{'silhouette (by label)':<28}{sil_pca:>12.4f}{sil_tsne:>12.4f}")
print(f"{'trustworthiness (k=12)':<28}{trust_pca:>12.4f}{trust_tsne:>12.4f}")
print(f"{'higher-is-better':<28}{'':>12}{'':>12}")
print("=========================================")
print(f"\nInterpretation hints:")
print(f"  silhouette:  PCA={sil_pca:.4f}  t-SNE={sil_tsne:.4f}  "
      f"(t-SNE better by {sil_tsne-sil_pca:+.4f})")
print(f"  trustworthiness: PCA={trust_pca:.4f}  t-SNE={trust_tsne:.4f}  "
      f"(t-SNE better by {trust_tsne-trust_pca:+.4f})")

# Save numeric results for the summary write-up
import json, pathlib
pathlib.Path("results.json").write_text(json.dumps({
    "n_samples": int(X.shape[0]),
    "n_features": int(X.shape[1]),
    "n_classes": int(len(np.unique(y))),
    "pca_explained_var_2comp": float(pca.explained_variance_ratio_.sum()),
    "pca_explained_var_per_comp": [float(v) for v in pca.explained_variance_ratio_],
    "tsne_kl_divergence": float(tsne.kl_divergence_),
    "tsne_n_iter": int(tsne.n_iter_),
    "silhouette_pca": float(sil_pca),
    "silhouette_tsne": float(sil_tsne),
    "trustworthiness_pca": float(trust_pca),
    "trustworthiness_tsne": float(trust_tsne),
    "n_neighbors_trust": N_NEIGHBORS,
    "random_state": RNG,
}, indent=2))
print("\nSaved results.json")
