# Summary: Effect of `max_features` (mtry) on Random Forest Performance

## Setup

- **Dataset:** `sklearn.datasets.load_digits` (p = 64 features, 10 classes, n = 1797)
- **Split:** stratified 70 / 30 (`random_state = 0`)
  - Train: 1257 samples, Test: 540 samples
- **Model:** `RandomForestClassifier(n_estimators=200, oob_score=True, random_state=0, n_jobs=-1)`
- **Sole independent variable:** `max_features` ∈ {1, `"sqrt"` (=8), `p/3` (=21), `None` (=64, all features)}

The number of trees, the bootstrap samples, every random draw, the train/test split,
and the data set are all held constant — only `max_features` changes between runs.

## Results

| `max_features` | # features / split | OOB error | OOB accuracy | Test accuracy | Avg. single-tree acc. | Mean pairwise tree corr. ρ̄ | ρ̄ / s²  |
|---:|---:|---:|---:|---:|---:|---:|---:|
| **1**            |  1 | 0.0366 | 0.9634 | 0.9611 | 0.6323 | 0.1492 | 0.526 |
| **`sqrt` (≈8)**  |  8 | **0.0270** | **0.9730** | **0.9778** | 0.7565 | 0.1964 | 0.456 |
| **`p/3` (≈21)**  | 21 | 0.0286 | 0.9714 | 0.9759 | 0.7916 | 0.2317 | 0.484 |
| **`None` (=64)** | 64 | 0.0565 | 0.9435 | 0.9593 | 0.8238 | 0.3070 | 0.586 |

- `s` (the "strength" proxy in Breiman's bound) is taken as `avg_tree_acc − 1/10 = avg_tree_acc − 0.1`.
- Between-tree correlation ρ̄ is the average off-diagonal Pearson correlation of the
  per-tree correct/incorrect indicator vectors on the held-out test set
  (1 if the tree classifies the sample correctly, 0 otherwise).

## How accuracy / OOB error change with `max_features`

Both metrics follow a **non-monotonic, U-shaped curve**:

```
max_features:    1     ─►  sqrt(8)  ─►  p/3(21) ─►  None(64)
OOB error:    0.0366   ─►  0.0270    ─►  0.0286  ─►  0.0565
Test acc.:    0.9611   ─►  0.9778    ─►  0.9759  ─►  0.9593
```

- **Best** accuracy / lowest OOB error is achieved at `max_features = "sqrt"` (≈8),
  closely followed by `p/3` (≈21). The two are essentially tied (difference < 0.002).
- **Worst** performance is at `max_features = None` (all 64 features per split).
  OOB error jumps from 0.027 → 0.056, and test accuracy drops from 0.978 → 0.959.
- `max_features = 1` is surprisingly strong (test acc. 0.961): even with only one
  random feature per split, the ensemble compensates because the 200 trees see
  very different splits.

## How between-tree correlation changes with `max_features`

ρ̄ rises monotonically with `max_features`:

```
max_features:    1     ─►  sqrt(8)  ─►  p/3(21) ─►  None(64)
ρ̄:           0.1492   ─►  0.1964    ─►  0.2317  ─►  0.3070
```

At the same time, the **average single-tree accuracy** rises from 0.63 → 0.82 —
individual trees get stronger (better "strength" `s`) but also more alike
(higher "correlation" ρ̄), exactly the trade-off Breiman's Theorem 2.3 predicts.

The composite ratio ρ̄ / s² (Breiman's `c/s²`, "smaller is better") is:

- `sqrt` (8): **0.456 — best**
- `p/3` (21): 0.484
- `1`:       0.526
- `None` (64): 0.586 — worst

The ordering of ρ̄/s² matches the ordering of OOB / test error, in agreement with
Breiman's upper bound `PE* ≤ ρ̄ (1 − s²) / s²`.

## Interpretation (Breiman 2001, Sections 6 & 9)

1. **Strength vs. correlation trade-off.** As `max_features` grows, each tree
   sees more candidate splits at every node → splits are nearly optimal → trees
   are individually stronger but also look more like one another. The diversity
   injected by random feature sub-sampling shrinks.
2. **Why `sqrt` wins on load_digits.** With p = 64, `sqrt(p) = 8` gives roughly
   enough signal at each node to maintain strength while still forcing the trees
   to disagree. This is the textbook default and it pays off here.
3. **Why `None` is worst.** With all 64 features considered at every split, the
   trees become highly correlated (ρ̄ = 0.31), and the ensemble loses much of its
   variance-reduction benefit — even though each tree is the strongest possible.
4. **Why `max_features = 1` is decent.** The correlation is at its lowest (0.15),
   so 200 maximally-decorrelated trees still vote well. Strength is poor (0.63),
   but the ensemble margin compensates — consistent with Breiman's observation
   that "selecting one or two features gives near-optimum results".
5. **Practical default confirmed.** For classification with hundreds–thousands of
   features, `max_features = "sqrt"` is a robust, near-optimal choice; the
   experiment reproduces this rule of thumb on load_digits.

## Conclusion

On load_digits with n_estimators = 200:

- OOB error is **lowest** at `max_features = "sqrt"` (0.027), and **highest** at
  `None` (0.057).
- Test accuracy is **highest** at `"sqrt"` (0.978) and **lowest** at `None` (0.959).
- Between-tree correlation ρ̄ grows monotonically with `max_features` (0.15 → 0.31),
  while individual-tree strength grows in the same direction (0.63 → 0.82).
- The trade-off is best resolved at `"sqrt"` (or `p/3`), exactly where the
  ratio ρ̄/s² is minimized, matching Breiman's strength/correlation theory.

Raw numbers (JSON): `./results_max_features.json`
Source code: `./experiment_full.py`