"""
Experiment: investigate the interaction between perplexity and learning_rate in t-SNE.

Run sklearn.manifold.TSNE on {perplexity in {5, 30, 100}} x {learning_rate in {50, 200, 1000}}
with fixed n_components=2, init='pca', max_iter=1000, random_state=0 on sklearn.datasets.load_digits.

For each of the 9 combinations, compute the silhouette score of the 2D embedding
according to digit labels, and write the table to ./summary_perplexity_lr.md.
"""

import time
import numpy as np
from sklearn.datasets import load_digits
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_score


def main() -> None:
    digits = load_digits()
    X = digits.data
    y = digits.target

    perplexities = [5, 30, 100]
    learning_rates = [50, 200, 1000]

    # silhouette_score[i, j] corresponds to (perplexity[i], learning_rate[j])
    silhouette = np.zeros((len(perplexities), len(learning_rates)))
    kl_div = np.zeros((len(perplexities), len(learning_rates)))
    elapsed = np.zeros((len(perplexities), len(learning_rates)))

    for i, perp in enumerate(perplexities):
        for j, lr in enumerate(learning_rates):
            t0 = time.time()
            tsne = TSNE(
                n_components=2,
                perplexity=perp,
                learning_rate=lr,
                init="pca",
                max_iter=1000,
                random_state=0,
            )
            emb = tsne.fit_transform(X)
            t1 = time.time()

            sil = silhouette_score(emb, y, metric="euclidean")
            silhouette[i, j] = sil
            kl_div[i, j] = float(tsne.kl_divergence_)
            elapsed[i, j] = t1 - t0

            print(
                f"perplexity={perp:>4d}, learning_rate={lr:>5d} -> "
                f"silhouette={sil:.4f}, KL={float(tsne.kl_divergence_):.4f}, "
                f"time={t1 - t0:.1f}s"
            )

    # Print 3x3 silhouette table
    print("\nSilhouette table (rows=perplexity, cols=learning_rate):")
    header = "perp \\ lr   | " + " | ".join(f"lr={lr:>5d}" for lr in learning_rates)
    print(header)
    print("-" * len(header))
    for i, perp in enumerate(perplexities):
        row = f"perp={perp:>4d}  | " + " | ".join(f"{silhouette[i, j]:.4f}" for j in range(len(learning_rates)))
        print(row)

    # Identify best combination
    best_i, best_j = np.unravel_index(np.argmax(silhouette), silhouette.shape)
    print(
        f"\nBest: perplexity={perplexities[best_i]}, "
        f"learning_rate={learning_rates[best_j]} "
        f"-> silhouette={silhouette[best_i, best_j]:.4f}"
    )

    # Marginal means to assess main effects vs. interaction
    perp_means = silhouette.mean(axis=1)
    lr_means = silhouette.mean(axis=0)
    overall = silhouette.mean()
    print("\nMean silhouette by perplexity:", dict(zip(perplexities, perp_means)))
    print("Mean silhouette by learning_rate:", dict(zip(learning_rates, lr_means)))
    print(f"Overall mean: {overall:.4f}")

    # Two-way ANOVA decomposition (Type I, no replication, just to assess interaction)
    # SS_total = sum((x - mean)^2)
    # SS_perp  = n_lr * sum((perp_mean - overall)^2)
    # SS_lr    = n_perp * sum((lr_mean - overall)^2)
    # SS_int   = SS_total - SS_perp - SS_lr (residual)
    n_perp = len(perplexities)
    n_lr = len(learning_rates)
    ss_total = float(((silhouette - overall) ** 2).sum())
    ss_perp = n_lr * float(((perp_means - overall) ** 2).sum())
    ss_lr = n_perp * float(((lr_means - overall) ** 2).sum())
    ss_int = ss_total - ss_perp - ss_lr
    print(f"\nSS_total = {ss_total:.6f}")
    print(f"SS_perp  = {ss_perp:.6f} ({100 * ss_perp / ss_total:.1f}%)")
    print(f"SS_lr    = {ss_lr:.6f} ({100 * ss_lr / ss_total:.1f}%)")
    print(f"SS_int   = {ss_int:.6f} ({100 * ss_int / ss_total:.1f}%)")

    # Save the arrays to disk for the write-up
    np.savez(
        "experiment_results.npz",
        silhouette=silhouette,
        kl_div=kl_div,
        elapsed=elapsed,
        perplexities=np.array(perplexities),
        learning_rates=np.array(learning_rates),
    )


if __name__ == "__main__":
    main()