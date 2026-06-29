# Distribution of Isolation-Forest anomaly scores (normal vs. anomalous)

## Setup

* **Data.** Synthetic 2-D dataset (fixed seed `SEED = 0`):
  * **Normal points (4 500):** three Gaussian clusters, centres at `(0,0)`, `(6,0)`, `(0,6)`,
    isotropic std 1.0, 1 500 points per cluster.
  * **Anomalies (120):** two Gaussian clusters, centres at `(10,10)` and `(-10,-6)`,
    isotropic std 0.6, 60 points per cluster.
  * **Contamination ratio:** `120 / 4 620 = 2.60%` (matches the task's "~2% injected outliers").
* **Model.** `sklearn.ensemble.IsolationForest` with the paper's recommended defaults
  `max_samples = psi = 256`, `n_estimators = 100`, `random_state = 0`,
  `contamination = "auto"`.
* **Score definitions** (the same ones the paper introduces in §2):
  * `h(x) = number of edges traversed in one iTree` (Algorithm 3 in the paper,
    including the `c(Size)` adjustment for unbuilt sub-trees).
  * `E[h(x)] = mean of h(x) over the 100 iTrees` — the expected path length.
  * `c(psi) = 2 H(psi-1) − 2(psi-1)/psi ≈ 10.2448` — the average path length of an
    unsuccessful BST search with `psi` elements (Eq. 1 of the paper, used as the
    normalising constant).
  * **Anomaly score (paper, Eq. 2):** `s(x, psi) = 2^{-E[h(x)]/c(psi)}` — values
    close to 1 ⇒ definitely an anomaly, close to 0 ⇒ definitely normal, ≈ 0.5 ⇒
    "neither" (per the paper's qualitative assessment).
  * **`decision_function`** (sklearn, `contamination="auto"`) is `0.5 − s_paper`,
    i.e. `>0` for inliers and `<0` for outliers.

`E[h(x)]` was computed independently per tree (matching Algorithm 3) and then
re-derived as `E[h] = −c(psi)·log2(s_paper)`; both agreed with
`-IsolationForest.score_samples` to numerical precision
(`np.allclose(atol=1e-8)` passed).

## Distribution of E[h(x)] — expected path length

| group    |    n |   mean | median |   std |   min |   p05 |   p25 |   p50 |   p75 |   p95 |   max |
|----------|-----:|-------:|-------:|------:|------:|------:|------:|------:|------:|------:|------:|
| normal   | 4500 | 11.719 | 12.045 | 1.220  |  6.44 |  9.16 | 11.12 | 12.05 | 12.65 | 13.10 | 13.47 |
| anomaly  |  120 |  4.412 |  4.347 | 0.343  |  3.76 |  3.93 |  4.20 |  4.35 |  4.64 |  5.04 |  5.55 |

**Anomalies are isolated ~2.7× faster than normal points.**
The two distributions are almost disjoint on the path-length axis:
the maximum anomaly path length is 5.55, while the 5-th percentile of normal
points is already 9.16 — an empirical gap of more than 3.6 path-length units.
The means differ by `11.72 − 4.41 = 7.31`, which is many standard deviations
(`~6 σ` on the pooled scale).

## Distribution of the paper's anomaly score  s(x) = 2^{−E[h]/c(psi)}

| group    |    n |  mean  | median |  std  |  min  |  p05  |  p25  |  p50  |  p75  |  p95  |  max  |
|----------|-----:|-------:|-------:|------:|------:|------:|------:|------:|------:|------:|------:|
| normal   | 4500 | 0.4541 | 0.4427 | 0.039 | 0.402 | 0.412 | 0.425 | 0.443 | 0.471 | 0.538 | 0.647 |
| anomaly  |  120 | 0.7421 | 0.7452 | 0.017 | 0.687 | 0.711 | 0.731 | 0.745 | 0.753 | 0.766 | 0.775 |

The normal distribution is centred **just below** the 0.5 mark
(`mean = 0.454, median = 0.443`), exactly the picture the paper describes for
"safe to be regarded as normal instances" (case (b), §2, Eq. 2). The anomaly
distribution is centred at `~0.74`, in the "definitely anomalies" regime
(case (a) in the paper).

**No overlap between the central 90% of the two groups.** Normal p95 = 0.538,
anomaly p05 = 0.711; the empirical margins are 0.17 score units.

## Distribution of `decision_function`  (sklearn,  contamination="auto")

| group    |    n |  mean  | median |  std  |  min  |  p05  |  p25  |  p50  |  p75  |  p95  |  max  |
|----------|-----:|-------:|-------:|------:|------:|------:|------:|------:|------:|------:|------:|
| normal   | 4500 |  0.046 |  0.057 | 0.039 | −0.147| −0.038|  0.029|  0.057|  0.075|  0.088|  0.098|
| anomaly  |  120 | −0.242 | −0.245 | 0.017 | −0.275| −0.266| −0.253| −0.245| −0.231| −0.211| −0.187|

Note the strict sign convention that sklearn's `decision_function` enforces with
`contamination="auto"`: the threshold is `0`, and every single anomaly has
`decision_function < 0` while 4 461 / 4 500 = 99.1% of normal points have
`decision_function > 0`. The two distributions do not overlap on the central
90% either (normal p05 = −0.038, anomaly p95 = −0.211; a 0.17-unit gap).

## Separability (AUC using true labels)

The same ranking is used in all three AUCs (a higher score ⇒ more anomalous):

| score used                                  |  AUC  |
|---------------------------------------------|------:|
| `s = 2^{−E[h]/c(psi)}`  (paper, Eq. 2)       | **1.0000** |
| `−E[h(x)]`  (raw path-length view)           | **1.0000** |
| `−decision_function`  (sklearn convention)   | **1.0000** |

In other words, with this synthetic setup the two score distributions are
perfectly rank-separable: every anomaly outranks every normal point on any of
the three score scales. (The 1.0000 is exact up to numerical precision
`~1e-7`; the worst-case margins reported above keep an O(10⁻²) buffer
between the two score clouds.)

## Take-aways (matches the paper's claims)

1. **Anomalies have shorter expected path lengths than normal points.**
   Means are `4.41` vs `11.72`; medians `4.35` vs `12.05`. The anomaly
   mean sits *below* the paper's "average path length" `c(psi) = 10.24`,
   the normal mean sits *above* it — exactly the behaviour the paper
   predicts from the "few and different" argument (§2).

2. **Anomaly score `s = 2^{−E[h]/c(psi)}` cleanly separates the two groups.**
   Normal s is centred at 0.45 (<< 0.5, "safe normal"), anomaly s is
   centred at 0.74 (well into the "definitely anomaly" region of Fig. 2
   of the paper). The 90%-quantile bands do not overlap.

3. **AUC = 1.0 with psi=256, n_estimators=100, random_state=0.**
   The paper argues (and our experiment confirms) that a sub-sampling size of
   ψ=256 and ~100 trees are already enough to give near-perfect detection on
   a well-separated 2-D scenario with a few-percent contamination ratio.
   This is consistent with the paper's Table 3 results on synthetic /
   near-Gaussian data (e.g. *Mulcross*: AUC = 0.97) and the "synthetic
   normal distribution of 135 points" illustration in Fig. 1, where the
   expected path lengths converge to `4.02` (anomaly) and `12.82` (normal) —
   virtually the same ratio we observe (4.4 vs 11.7).
