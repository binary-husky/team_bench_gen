"""
Run t-SNE on sklearn's load_digits with varying perplexity values and report
silhouette score (using digit labels) and trustworthiness (n_neighbors=12).
"""

import time

import numpy as np
from sklearn.datasets import load_digits
from sklearn.manifold import TSNE, trustworthiness
from sklearn.metrics import silhouette_score


def main() -> None:
    digits = load_digits()
    X = digits.data
    y = digits.target
    print(f"Dataset shape: {X.shape}, classes: {len(np.unique(y))}, samples: {X.shape[0]}")

    perplexities = [5, 15, 30, 50, 100, 200]
    results = []

    for perp in perplexities:
        t0 = time.time()
        tsne = TSNE(
            n_components=2,
            perplexity=perp,
            init="pca",
            learning_rate="auto",
            max_iter=1000,
            random_state=0,
        )
        X_embedded = tsne.fit_transform(X)
        elapsed = time.time() - t0

        sil = silhouette_score(X_embedded, y, metric="euclidean")
        trust = trustworthiness(X, X_embedded, n_neighbors=12)

        results.append((perp, sil, trust, elapsed))
        print(
            f"perplexity={perp:>3} | silhouette={sil:.6f} | "
            f"trustworthiness={trust:.6f} | time={elapsed:.2f}s"
        )

    # Print a Markdown-friendly table.
    print("\nMarkdown table:")
    print("| perplexity | silhouette_score | trustworthiness (n_neighbors=12) | runtime (s) |")
    print("|------------|------------------|--------------------------------|-------------|")
    for perp, sil, trust, elapsed in results:
        print(f"| {perp} | {sil:.6f} | {trust:.6f} | {elapsed:.2f} |")

    # Identify the best perplexity by each metric.
    best_sil = max(results, key=lambda r: r[1])
    best_trust = max(results, key=lambda r: r[2])
    print(f"\nBest silhouette at perplexity={best_sil[0]} (score={best_sil[1]:.6f})")
    print(f"Best trustworthiness at perplexity={best_trust[0]} (score={best_trust[2]:.6f})")

    # Write a small JSON for downstream summarisation.
    import json

    with open("results.json", "w") as f:
        json.dump(
            [
                {
                    "perplexity": perp,
                    "silhouette": sil,
                    "trustworthiness": trust,
                    "runtime_seconds": elapsed,
                }
                for perp, sil, trust, elapsed in results
            ],
            f,
            indent=2,
        )


if __name__ == "__main__":
    main()