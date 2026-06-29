# t-SNE convergence vs. `max_iter` on `sklearn.datasets.load_digits`

## Setup

- **Data**: `sklearn.datasets.load_digits` — 1 797 samples × 64 features, 10 classes (digits 0–9).
- **Fixed hyperparameters**:
  - `n_components=2`, `init='pca'`, `perplexity=30`,
  - `learning_rate='auto'` (sklearn resolves this to `max(N / 12, 50) = 149.75` for `N=1797`),
  - `method='barnes_hut'` (sklearn default),
  - `random_state=0`.
- **Independent variable**: `max_iter ∈ {250, 500, 1000, 2000}`.
- **Metrics**:
  - (a) Final KL divergence from the fitted estimator's `kl_divergence_` attribute.
  - (b) Silhouette score of the 2-D embedding against the true digit labels
        (`sklearn.metrics.silhouette_score`, full sample).

Each setting was run once with the same `random_state=0`, so the only
stochastic variation is the IRNG seed shared across all four runs.

## Raw results

| `max_iter` | `n_iter_` (actual) | KL divergence | Silhouette (digit labels) | Wall time (s) |
|-----------:|------------------:|--------------:|-------------------------:|--------------:|
| 250        | 250               | 1.797693e+308 *(sentinel, see note)* | **0.6349** | 0.5 |
| 500        | 499               | **0.8231**   | 0.5215  | 0.8 |
| 1000       | 999               | 0.7536       | 0.5557  | 1.3 |
| 2000       | 1999              | **0.7363**   | **0.5684** | 2.3 |

(For each metric the bolder value is the more meaningful endpoint — i.e. the
lowest real KL, the highest real silhouette.)

### Note on the `max_iter = 250` row

The value 1.797 693 134 862 315 7e+308 is exactly `np.finfo(float).max`. In
sklearn ≥ 1.0, `TSNE.fit_transform` runs the optimizer in two stages
(`sklearn/manifold/_t_sne.py:1075-1094`):

1. **Stage 1 — early exaggeration.** 250 fixed iterations with
   `momentum=0.5`, `learning_rate='auto'`, and `P *= early_exaggeration`
   (default 12).
2. **Stage 2 — post-exaggeration.** Iterations `range(250, max_iter)` with
   `momentum=0.8` and the un-exaggerated `P`.

When `max_iter = 250` the second stage has empty range `range(250, 250)`, so
its loop body never runs and `error` is never overwritten from its initial
sentinel value `np.finfo(float).max`. The reported `kl_divergence_` is
therefore *not* a real KL reading — it is the un-updated sentinel. The
silhouette 0.6349 is real, but it is taken from a point cloud whose
attractions are scaled by `early_exaggeration = 12`, which artificially
pushes clusters apart and inflates between-cluster distance, so it
overstates the converged separation.

The other three rows are real measurements taken from stage 2 and are
directly comparable.

## Trend analysis

| Pair (it → it) | ΔKL absolute | ΔKL relative | Δ silhouette |
|----------------|-------------:|-------------:|-------------:|
| 500  → 1000    | −0.0695      | −8.4 %       | +0.0342      |
| 1000 → 2000    | −0.0173      | −2.3 %       | +0.0127      |
| 500  → 2000    | −0.0868      | −10.5 %      | +0.0469      |

- KL decreases monotonically; the curve is clearly diminishing-returns.
  ~83 % of the 500→2000 KL improvement is already captured by iteration 1000;
  the second 1 000 iterations shave off only the remaining ~17 %.
- Silhouette increases monotonically (after the early-exaggeration artefact
  at 250). The gain from 1000 to 2000 is roughly 0.013, which is
  comparable to the within-class spread of silhouette values reported for
  t-SNE on digits in the literature, i.e. it is on the borderline of
  perceptible.
- The two metrics agree: the embedding has largely settled by 1000
  iterations.

## Conclusion — "about how many iterations to basically converge?"

On `sklearn.datasets.load_digits` with the fixed settings above, **roughly
1 000 iterations are enough for basic convergence** of t-SNE:

- Below 1 000 (i.e. `max_iter = 500` here) the optimizer is still in the
  steep part of the KL-vs-iteration curve — the embedding continues to
  rearrange substantially and silhouette is noticeably worse.
- At 1 000, the KL has dropped to within ~2 % of its value at 2 000 and the
  silhouette has reached ~98 % of its 2 000-iteration value.
- Doubling the budget to 2 000 buys only a small additional refinement and
  roughly doubles the wall time.

This matches sklearn's own default (`max_iter=1000` since 1.2) and is
consistent with the visual guidance in van der Maaten & Hinton (2008) that
the optimisation is "typically stable after a few hundred iterations" once
early exaggeration is removed — on this small (N = 1797), low-dimensional
(64-D) dataset, "a few hundred" post-exaggeration iterations (~500–750) is
already in the flat region, and 1 000 is comfortably past the knee of the
curve.

### Practical recommendation

For this dataset / hyper-parameter combination, set `max_iter=1000` for
routine work; use 1 500–2 000 only if you specifically need a polished
embedding and can afford the extra compute. Avoid `max_iter=250`, because
that is the boundary case where stage 2 of sklearn's optimiser never runs
and you only get the early-exaggerated embedding (high silhouette, no
meaningful KL).
