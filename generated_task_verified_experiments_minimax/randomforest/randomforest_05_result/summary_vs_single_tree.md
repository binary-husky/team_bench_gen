# Random Forest vs. Single Decision Tree — Variance Reduction / Overfitting Resistance

## Setup

- **Dataset:** `sklearn.datasets.load_digits` (1,797 samples, 64 features, 10 classes)
- **Models compared**
  - (a) `sklearn.ensemble.RandomForestClassifier(n_estimators=200, random_state=42)`
  - (b) `sklearn.tree.DecisionTreeClassifier(random_state=42)` — fully grown, unpruned
- **Train/test split:** stratified 70 / 30, repeated over random seeds `0,1,2,3,4,5,6,7,8,9` (10 seeds)
- **Independent variable:** model type
- **Fixed:** dataset, `n_estimators=200`, split ratio, seed set
- **Metric:** classification error = `1 − accuracy` (training error and test error per seed)

Per-seed values were also written to `results.npz` for reproducibility.

## Per-seed results (test error = 1 − accuracy)

| seed | RF train | RF test | DT train | DT test |
|---:|---:|---:|---:|---:|
| 0 | 0.0000 | 0.0222 | 0.0000 | 0.1500 |
| 1 | 0.0000 | 0.0296 | 0.0000 | 0.1574 |
| 2 | 0.0000 | 0.0296 | 0.0000 | 0.1500 |
| 3 | 0.0000 | 0.0259 | 0.0000 | 0.1556 |
| 4 | 0.0000 | 0.0296 | 0.0000 | 0.1704 |
| 5 | 0.0000 | 0.0148 | 0.0000 | 0.1556 |
| 6 | 0.0000 | 0.0204 | 0.0000 | 0.1444 |
| 7 | 0.0000 | 0.0130 | 0.0000 | 0.1574 |
| 8 | 0.0000 | 0.0167 | 0.0000 | 0.1519 |
| 9 | 0.0000 | 0.0222 | 0.0000 | 0.1630 |

## Cross-seed summary

| Model | Train error (mean ± std) | Test error (mean ± std) |
|---|---|---|
| **RandomForest (n=200)** | 0.0000 ± 0.0000 | **0.0224 ± 0.0063** |
| **DecisionTree (single)** | 0.0000 ± 0.0000 | **0.1556 ± 0.0073** |

(RandomForest accuracy ≈ 97.76 % vs. DecisionTree accuracy ≈ 84.44 % on the held-out 30 %.)

## Comparison and conclusion

1. **Generalization gap (overfitting indicator)**
   - The single decision tree attains **0.0000 training error** but **0.1556 test error** — a large generalization gap of ~15.6 percentage points, the classic fingerprint of an unpruned tree that has memorized the training set (high variance, low bias).
   - The random forest also achieves **0.0000 training error** on every seed (with enough trees the bootstrap-sampled predictors collectively memorize the training points) yet its **test error is only 0.0224** — a gap of ~2.2 percentage points. The gap is roughly **7× smaller** for the forest.

2. **Variance reduction across seeds (test-error std)**
   - RF test-error std = 0.0063 vs. DT test-error std = 0.0073. The forest is not only more accurate on average but also slightly more stable across different 70/30 partitions.
   - This matches Breiman (2001): for an ensemble, generalization error is bounded by `var(mr)/s²`, where reducing inter-tree correlation (`ρ̄`) and tree strength (`s`) lowers the margin variance. Bagging + random feature subsampling decorrelates the trees and shrinks variance.

3. **Mean test-error reduction**
   - RF − DT mean test error = 0.0224 − 0.1556 = **−0.1332**, i.e. the forest cuts error by **~13.3 absolute percentage points** (~85.6 % relative reduction) on `load_digits`.
   - Because both models already drive training error to zero, this gap is almost entirely attributable to **variance reduction**, not bias change — exactly the mechanism Random Forests are designed to exploit (Theorem 1.2 in Breiman 2001: the forest's generalization error converges to a limit that depends on the strength/correlation of the individual trees, and does not grow with more trees).

4. **Interpretation**
   - The single decision tree is a **high-variance** learner: small changes in the training sample produce noticeably different trees (a few flips in the held-out points suffice to swing test accuracy). The forest averages 200 decorrelated trees, so individual tree mistakes largely cancel out — this is the **bagging / random-subspace variance-reduction** effect described in Breiman (2001, §2.2).
   - The fact that the forest is *not* worse than the single tree on training (both zero error) yet markedly better on the test set directly demonstrates **resistance to overfitting**, the central empirical claim of the Random Forests paper.

## Headline numbers (one-liner)

> On `load_digits` (10 stratified 70/30 splits): RandomForest (n_estimators=200) test error = **0.0224 ± 0.0063**, single DecisionTree test error = **0.1556 ± 0.0073**. Both reach 0 training error, so the ~13 pp test-error gap is pure variance reduction — confirming the variance-reduction / overfitting-resistance theory of Random Forests (Breiman 2001).