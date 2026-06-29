# Summary: Effect of `n_estimators` on OOB / Test Error

## Setup

- **Dataset**: `sklearn.datasets.load_digits` (1,797 samples, 64 features, 10 classes)
- **Split**: 70% train / 30% test, stratified, fixed seed `0`
  - Train: 1,257 samples; Test: 540 samples
- **Model**: `RandomForestClassifier(oob_score=True, random_state=0)`, `n_jobs=-1`
- **Varying parameter**: `n_estimators ∈ {10, 50, 100, 200, 500, 1000}`
- **Fixed**: dataset, split seed, model seed, all other RandomForest defaults
- **Metric**: OOB error = `1 - oob_score_`; Test error = `1 - accuracy_score(y_test, ŷ)`

## Results

| n_estimators | OOB error | Test error | Train error | OOB − Test gap |
|-------------:|----------:|-----------:|------------:|---------------:|
|           10 |    0.1496 |     0.0519 |       0.000 |          +0.0977 |
|           50 |    0.0382 |     0.0315 |       0.000 |          +0.0067 |
|          100 |    0.0263 |     0.0296 |       0.000 |          −0.0034 |
|          200 |    0.0270 |     0.0222 |       0.000 |          +0.0048 |
|          500 |    0.0255 |     0.0241 |       0.000 |          +0.0014 |
|         1000 |    0.0255 |     0.0204 |       0.000 |          +0.0051 |

### Consecutive differences (Δerror)

| Transition     | Δ OOB error | Δ Test error |
|----------------|------------:|-------------:|
| 10 → 50        |    −0.1114  |     −0.0204  |
| 50 → 100       |    −0.0119  |     −0.0019  |
| 100 → 200      |    +0.0008  |     −0.0074  |
| 200 → 500      |    −0.0016  |     +0.0019  |
| 500 → 1000     |    +0.0000  |     −0.0037  |

### Range across the sweep

| Metric      |  min  |  max  | max − min |
|-------------|------:|------:|----------:|
| OOB error   | 0.0255 | 0.1496 | 0.1241 |
| Test error  | 0.0204 | 0.0519 | 0.0315 |

## Observations

1. **Both OOB and test error decrease and then plateau as `n_estimators` grows.** Train error stays at 0 throughout (trees can perfectly memorise the bootstrap sample) — the OOB/test curves are the ones that matter.
2. **The drop is concentrated in the small-`n` regime.** Going from 10 → 50 trees removes most of the error (OOB −0.111, Test −0.020). Beyond 50, both metrics barely move: OOB sits in [0.0255, 0.0270] and test sits in [0.0204, 0.0315] for n ∈ {50, 100, 200, 500, 1000}. By the 100 → 1000 range, the OOB error is identical to four decimal places (0.0255 at n=500 and n=1000) and consecutive Δ-test errors are all ≤ 0.008 in absolute value.
3. **No overfitting as `n_estimators` grows.** Test error never increases monotonically — the worst it does between consecutive points is +0.0019 (200 → 500), and the 1000-tree test error (0.0204) is the lowest of the sweep. This is the empirical signature of the convergence theorem from Breiman (2001): the generalization error of a random forest converges (a.s.) to a finite limit as the number of trees grows, rather than growing without bound.
4. **OOB is a noisy, pessimistic estimator at very small `n`.** At n=10 the OOB error (0.1496) is almost 3× the test error (0.0519). sklearn itself warns *"Some inputs do not have OOB scores … too few trees were used to compute any reliable OOB estimates."* The reason is that each training point's OOB estimate is averaged over only a handful of trees at n=10, so per-point vote tallies are high-variance.
5. **OOB converges to a near-unbiased estimate of test error once `n` is large enough.** From n=50 onward, the OOB / test gap is small in magnitude (≤ 0.0067) and bounces around zero (−0.0034 to +0.0051), with no systematic direction. This matches the paper's claim (Section 4) that OOB estimates the generalization error well for forests of sufficient size.
6. **Practical implication.** For this dataset, ~100–200 trees are enough to reach the converged error regime; pushing to 500 or 1000 produces no further OOB improvement and at most a 0.7-percentage-point test-error fluctuation (which is within ±1/540 ≈ 0.2 pp of just the test-set sampling noise). More trees buy stability, not accuracy.

## Conclusion

Increasing `n_estimators` drives both OOB and held-out test error **downward and then to a stable plateau** — they do **not** keep improving forever, and they do **not** start to overfit. On load_digits with this 70/30 split, the bulk of the gain happens between 10 and 50 trees; from 100 trees onward the metrics are essentially flat (OOB ≈ 0.026, test ≈ 0.02–0.03), confirming Breiman's (2001) theoretical result that random-forest generalization error converges to a limit as the number of trees increases.
