"""
Experiment: t-SNE convergence vs. max_iter on sklearn digits.
For each max_iter in {250, 500, 1000, 2000}, fit TSNE with the given fixed
hyperparameters and record (a) final KL divergence and (b) silhouette score
of the 2-D embedding against the digit labels.
"""

import time
import numpy as np
from sklearn.datasets import load_digits
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_score

FIXED_KW = dict(
    n_components=2,
    init="pca",
    perplexity=30,
    learning_rate="auto",
    random_state=0,
    method="barnes_hut",  # default; explicit for clarity
)
MAX_ITERS = [250, 500, 1000, 2000]


def main():
    digits = load_digits()
    X, y = digits.data, digits.target
    print(f"digits: X={X.shape}, y={y.shape}, classes={len(np.unique(y))}")

    rows = []
    for mi in MAX_ITERS:
        kw = dict(FIXED_KW)
        kw["max_iter"] = mi
        t0 = time.time()
        tsne = TSNE(**kw)
        emb = tsne.fit_transform(X)
        elapsed = time.time() - t0

        kl = float(tsne.kl_divergence_)
        sil = float(silhouette_score(emb, y, sample_size=None))
        n_iter_actual = int(tsne.n_iter_)
        print(
            f"max_iter={mi:>4d}  n_iter_={n_iter_actual:>4d}  "
            f"KL={kl:.6f}  silhouette={sil:.6f}  time={elapsed:.1f}s"
        )
        rows.append(
            dict(
                max_iter=mi,
                n_iter_actual=n_iter_actual,
                kl_divergence=kl,
                silhouette=sil,
                elapsed_s=elapsed,
            )
        )

    # Persist a CSV-like table for later inspection.
    with open("results.csv", "w") as f:
        f.write("max_iter,n_iter_actual,kl_divergence,silhouette,elapsed_s\n")
        for r in rows:
            f.write(
                f"{r['max_iter']},{r['n_iter_actual']},"
                f"{r['kl_divergence']:.6f},{r['silhouette']:.6f},"
                f"{r['elapsed_s']:.2f}\n"
            )
    print("\nResults written to results.csv")


if __name__ == "__main__":
    main()
