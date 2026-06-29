"""
Compare 2D embedding quality of PCA and t-SNE on sklearn.load_digits.

Data: 1797 x 64, 10 classes.
Method A: PCA(n_components=2)
Method B: sklearn.manifold.TSNE(n_components=2, init='pca',
                                perplexity=30, learning_rate='auto',
                                max_iter=1000, random_state=0)

Per embedding we compute:
    - silhouette score (metric='euclidean') using the digit labels
    - trustworthiness (n_neighbors=12) with respect to the original 64-d space
"""

import time
import json
import numpy as np
from sklearn.datasets import load_digits
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_score
from sklearn.manifold import trustworthiness


def main() -> None:
    digits = load_digits()
    X, y = digits.data, digits.target  # X: (1797, 64), y: (1797,)
    print(f"digits: X={X.shape}, y={y.shape}, n_classes={len(np.unique(y))}")

    results = {"dataset": "sklearn.datasets.load_digits",
               "n_samples": int(X.shape[0]),
               "n_features": int(X.shape[1]),
               "n_classes": int(len(np.unique(y)))}

    # -------- PCA (first 2 components) --------
    t0 = time.time()
    pca = PCA(n_components=2, random_state=0)
    X_pca = pca.fit_transform(X)
    pca_time = time.time() - t0
    pca_sil = float(silhouette_score(X_pca, y, metric="euclidean"))
    pca_trust = float(trustworthiness(X, X_pca, n_neighbors=12))
    print(f"PCA  silhouette={pca_sil:.4f}  trustworthiness={pca_trust:.4f}  "
          f"time={pca_time:.2f}s  explained_var_ratio="
          f"{pca.explained_variance_ratio_}")

    results["pca"] = {
        "silhouette": pca_sil,
        "trustworthiness_k12": pca_trust,
        "fit_time_s": pca_time,
        "explained_variance_ratio": [float(v) for v in pca.explained_variance_ratio_],
        "cumulative_explained_variance": float(pca.explained_variance_ratio_.sum()),
    }

    # -------- t-SNE (fixed hyperparameters per task) --------
    t0 = time.time()
    tsne = TSNE(n_components=2,
                init="pca",
                perplexity=30,
                learning_rate="auto",
                max_iter=1000,
                random_state=0)
    X_tsne = tsne.fit_transform(X)
    tsne_time = time.time() - t0
    tsne_sil = float(silhouette_score(X_tsne, y, metric="euclidean"))
    tsne_trust = float(trustworthiness(X, X_tsne, n_neighbors=12))
    kl_div = float(tsne.kl_divergence_) if hasattr(tsne, "kl_divergence_") else None
    print(f"tSNE silhouette={tsne_sil:.4f}  trustworthiness={tsne_trust:.4f}  "
          f"time={tsne_time:.2f}s  KL={kl_div}")

    results["tsne"] = {
        "silhouette": tsne_sil,
        "trustworthiness_k12": tsne_trust,
        "fit_time_s": tsne_time,
        "kl_divergence": kl_div,
        "n_iter": int(getattr(tsne, "n_iter_", -1)),
        "hyperparams": {
            "n_components": 2,
            "init": "pca",
            "perplexity": 30,
            "learning_rate": "auto",
            "max_iter": 1000,
            "random_state": 0,
        },
    }

    # -------- Comparison --------
    print()
    print("=" * 60)
    print("Comparison (digits, 1797x64, 10 classes)")
    print("=" * 60)
    print(f"{'method':<10}{'silhouette':>14}{'trust(k=12)':>16}{'time(s)':>12}")
    print("-" * 60)
    print(f"{'PCA':<10}{pca_sil:>14.4f}{pca_trust:>16.4f}{pca_time:>12.2f}")
    print(f"{'t-SNE':<10}{tsne_sil:>14.4f}{tsne_trust:>16.4f}{tsne_time:>12.2f}")
    print("-" * 60)
    print(f"{'Δ (tSNE-PCA)':<10}{tsne_sil - pca_sil:>+14.4f}"
          f"{tsne_trust - pca_trust:>+16.4f}")

    results["delta_tsne_minus_pca"] = {
        "silhouette": tsne_sil - pca_sil,
        "trustworthiness_k12": tsne_trust - pca_trust,
    }

    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nWrote results.json")

    # also save the 2D coordinates for plotting / inspection
    np.save("X_pca.npy", X_pca)
    np.save("X_tsne.npy", X_tsne)
    np.save("y.npy", y)


if __name__ == "__main__":
    main()
