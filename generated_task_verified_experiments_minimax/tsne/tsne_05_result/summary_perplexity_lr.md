# t-SNE on `sklearn.datasets.load_digits`: perplexity × learning_rate interaction

## Setup

- Data: `sklearn.datasets.load_digits()` (1,797 samples × 64 features; 10 digit classes).
- Model: `sklearn.manifold.TSNE(n_components=2, init='pca', max_iter=1000, random_state=0)`.
- Grid: perplexity ∈ {5, 30, 100} × learning_rate ∈ {50, 200, 1000} — 9 runs total.
- Metric: silhouette score (Euclidean) of the 2-D embedding, using the digit label.
- Auxiliary metrics: final KL divergence (`tsne.kl_divergence_`) and wall-clock.

The two hyperparameters `perplexity` and `learning_rate` were varied; all other TSNE
settings were fixed at the values listed above. The task ran end-to-end in ~13 s on CPU.

## 3 × 3 silhouette score table

Rows = perplexity, columns = learning_rate. Higher is better.

| perp \ lr   | lr = 50  | lr = 200  | lr = 1000 |
|-------------|----------|-----------|-----------|
| perp = 5    | 0.4283   | 0.4433    | 0.3991    |
| perp = 30   | 0.5557   | **0.5626**| 0.5597    |
| perp = 100  | 0.5198   | 0.5231    | 0.5277    |

Best combination: **perplexity = 30, learning_rate = 200**, silhouette = **0.5626**
(KL divergence = 0.7397). Second-best is (30, 1000) at 0.5597, third is (30, 50)
at 0.5557 — all three are essentially tied within ~0.007.

For reference, the KL-divergence and run-time per cell:

| perp \ lr   | KL (lr=50) | KL (lr=200) | KL (lr=1000) |
|-------------|------------|-------------|--------------|
| perp = 5    | 0.9430     | 0.9269      | 0.9399       |
| perp = 30   | 0.7536     | 0.7397      | 0.7469       |
| perp = 100  | 0.5940     | 0.5962      | 0.5971       |

KL divergence is monotonically driven by perplexity (larger perp ⇒ smaller KL on
this dataset), confirming that perplexity controls the *quality of the optimum
reached*, not just the surface that learning_rate explores.

## Marginal means and decomposition of variance

Marginal mean silhouette (averaged across the other factor):

- By perplexity: perp=5 → **0.4236**, perp=30 → **0.5593**, perp=100 → **0.5235**
- By learning_rate: lr=50 → **0.5013**, lr=200 → **0.5097**, lr=1000 → **0.4955**

Two-way decomposition (additive model, SS attributed to each effect):

| Source            | Sum of squares | Share of SS_total |
|-------------------|----------------|-------------------|
| perplexity        | 0.029709       | **96.5 %**        |
| learning_rate     | 0.000304       | 1.0 %             |
| interaction (residual) | 0.000761  | 2.5 %             |
| **Total**         | 0.030775       | 100 %             |

Perplexity accounts for ~97 % of the variation across the grid, learning rate
alone for ~1 %, and the (perplexity × learning_rate) interaction for ~2.5 %.

## Where the small interaction lives

The interaction is small in magnitude but visible in the *direction* of the
learning-rate effect, which flips between rows:

| perplexity | effect of lr along {50 → 200 → 1000}         |
|------------|-----------------------------------------------|
| 5          | 0.4283 → 0.4433 → 0.3991 (peak at lr=200)    |
| 30         | 0.5557 → 0.5626 → 0.5597 (peak at lr=200)    |
| 100        | 0.5198 → 0.5231 → 0.5277 (monotonically up)  |

At small perplexity (5) the optimum is at lr=200, and a very large lr=1000
actively hurts (0.4433 → 0.3991, a drop of ~0.044). At large perplexity (100)
the relationship reverses — the embedding keeps improving slightly as lr grows
to 1000. So a "best learning rate" exists but it shifts by only ~0.05 silhouette
units, while the choice of perplexity swings the score by ~0.14.

## Conclusion: interaction or main effects?

**The two factors act almost entirely through independent main effects; the
interaction is weak.** On the load_digits grid:

- Perplexity is the dominant hyperparameter: silhouette varies from ~0.42
  (perp=5) to ~0.56 (perp=30), a swing of ~0.14 that is consistent across all
  three learning rates. Roughly **96.5 %** of the variance across the 9 cells
  is explained by the perplexity main effect alone.
- Learning rate contributes only **~1 %** of the variance as a main effect;
  its optimal value is approximately 200 but the silhouette score is nearly
  flat across {50, 200, 1000} at the best perplexity (0.5557 vs 0.5626 vs 0.5597).
- The **interaction accounts for only ~2.5 %** of the variance. It is
  qualitatively detectable — at perp=5 a high learning rate (1000) degrades the
  embedding, whereas at perp=100 the same high learning rate slightly improves
  it — but quantitatively it is an order of magnitude smaller than the
  perplexity main effect and is dominated by it.

So this is **not** a case of strong perplexity–learning_rate synergy: tuning
perplexity alone captures essentially all the available signal, and the
recommended operating point (perp=30, lr=200) is robust because the
learning-rate optimum is essentially flat at the best perplexity. The mild
interaction can be read as "use a moderate learning rate when perplexity is
small, and feel free to push it higher when perplexity is large," but it
should not change the choice of perplexity.

This picture matches the original van der Maaten & Hinton (2008) report that
t-SNE is "fairly robust to changes in the perplexity" in the typical 5–50 range
and that the algorithm's optimization behaviour is governed mainly by the
neighborhood bandwidth (perplexity), with the learning rate acting as a much
weaker knob that mostly affects convergence speed rather than the final
embedding quality.