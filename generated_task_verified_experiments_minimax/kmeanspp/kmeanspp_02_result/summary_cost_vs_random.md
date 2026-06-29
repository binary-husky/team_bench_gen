# k-means++ vs Random Initialization: Inertia (Cost) Comparison

## 1. Setup

All experiments below fix the dataset and vary **only** the seeding rule.

- **Dataset**: `sklearn.datasets.make_blobs` with `n_samples=5000`, `centers=10`, `n_features=2`, `random_state=42`.
  - Resulting shape: `X.shape = (5000, 2)`, `y_true` drawn from 10 Gaussian clusters.
- **Algorithm**: `sklearn.cluster.KMeans` with `n_clusters=10`, `n_init=1` (so the *seeding* is the only stochastic part being varied — Lloyd's loop is run from that one seed and converges).
- **Independent variable**: `init` ∈ {`"k-means++"`, `"random"`}.
- **Replications per setting**: 30 different `random_state` values (0…29), giving a sample of 30 final inertias per seeding rule.
- **Hardware**: CPU only (sklearn 1.9.0, numpy 1.26.4, scipy 1.10.1).
- **Metric**: final `KMeans.inertia_` after Lloyd convergence (sum of squared distances to assigned centers). Lower is better.

## 2. Headline Numbers

| Metric | k-means++ (init=`"k-means++"`) | random (init=`"random"`) | Ratio random / kmeans++ |
|---|---:|---:|---:|
| mean inertia | **9 352.17** | **12 133.90** | 1.297 |
| std (population) | 514.87 | 3 598.70 | 6.99 |
| std (sample, ddof=1) | 523.67 | 3 660.22 | 6.99 |
| median | 9 356.82 | 11 541.61 | 1.233 |
| min (best run) | 8 964.13 | 8 965.29 | 1.0001 |
| max (worst run) | 11 599.59 | 27 826.44 | 2.399 |
| range (max − min) | 2 635.45 | 18 861.15 | 7.16 |

All 30 raw values are in `results.json`.

### Quantiles (0%, 25%, 50%, 75%, 90%, 100%)

- k-means++: `8964.13, 8979.64, 9356.82, 9372.25, 9485.13, 11599.59`
- random:   `8965.29, 10214.53, 11541.61, 12952.79, 16176.60, 27826.44`

The k-means++ distribution is sharply bimodal-leaning: 27/30 trials cluster tightly between ~8970 and ~9385, with two outliers (10 228 and 11 599) and one near-10k case (10 141) — the seeding can still fail to spread centers, but the failures are modest. The random distribution is much broader and right-skewed, with a long upper tail and a single very bad run at 27 826.

## 3. What the Comparison Shows

**(a) Lower mean cost.** k-means++ gives a ~30 % lower mean final inertia than uniform random seeding on this dataset (9 352 vs 12 134). This is the headline "careful seeding pays off" claim of Arthur & Vassilvitskii (2007), Section 1: the D²-weighted seeding samples each new center with probability proportional to its squared distance to the nearest already-chosen center, which spreads seeds out and avoids picking several near-duplicate centers.

**(b) Much lower variance.** The standard deviation of final inertia is ~7× smaller for k-means++ (515 vs 3 599). Because `n_init=1`, every spread of the inertia distribution comes from the seeding step. Random seeding can produce a good seed (rare) or a catastrophically bad one (a "center-free" zone where two of the 10 seeds land in the same Gaussian blob and another blob is missed). k-means++'s D² weighting makes that almost impossible, so the seed quality is bounded.

**(c) Far better worst case.** The worst k-means++ run (11 599) is **2.4× better** than the worst random run (27 826). 14/30 (~47 %) of the random runs are *worse than the worst k-means++ run*, while **0/30** random runs beat the best k-means++ run. So the *best* random and the *best* k-means++ are nearly identical (8 965 vs 8 964, essentially the global optimum to within Lloyd's local-min tolerance), but the *typical* and *worst-case* k-means++ are dramatically better.

**(d) Statistical significance.** Mann–Whitney U on the 30 vs 30 samples: U=159, p ≈ 1.7 × 10⁻⁵. The two distributions are different at any reasonable significance level. Even pairing the 30 trials by index, random − k-means++ has mean +2 782 and ranges from −2 625 (one random seed slightly outperformed its k-means++ peer) to +18 414 (one random seed was catastrophic). Random lost in 26/30 paired comparisons and won in 4/30.

## 4. Interpretation in Light of the Paper

The k-means++ paper (Theorem 1.1) proves that **the expected final potential φ of k-means++ satisfies E[φ] ≤ 8(ln k + 2)·φ_OPT**, with k=10 that bound is 8·(ln 10 + 2) ≈ 38.4·φ_OPT. In practice we observe a much tighter empirical ratio:

- φ_OPT (the optimum we can reach on this dataset) is essentially the best k-means++ value, 8 964.13.
- Mean(k-means++) / min = 9 352 / 8 964 ≈ **1.043**, i.e. about 4 % above optimum on average.
- Mean(random) / min = 12 134 / 8 964 ≈ **1.354**, about 35 % above optimum.
- Worst(random) / min ≈ **3.10**, i.e. the worst random seed is 3× the optimum — the famous "arbitrarily bad" clusterings that vanilla k-means can produce.

So the paper's worst-case logarithmic bound is borne out qualitatively (random can be arbitrarily bad; k-means++ cannot), and the *empirical* advantage on this well-clustered blob is even larger than the conservative theoretical bound.

## 5. Conclusion

On the fixed `make_blobs(n=5000, centers=10, random_state=42)` dataset, with `n_init=1` and 30 different seeding random seeds:

- **k-means++ dominates uniform random seeding on every summary statistic that matters in practice** — mean, median, std, max, and range are all better.
- **k-means++ is not just slightly better; it is dramatically more reliable**: its std is ~7× smaller, and its worst case is ~2.4× better than the worst random case.
- **Random can occasionally be lucky** (best random run ≈ best k-means++ run to four digits), but that luck is rare: half the random runs are worse than *every* k-means++ run.

The empirical result matches the qualitative claim of Arthur & Vassilvitskii (2007) that "D² seeding" — sampling each new center with probability proportional to its squared distance to the closest already-chosen center — is a cheap, principled way to make k-means both faster-to-converge and resistant to the catastrophic local optima that pure random seeding can fall into.

## 6. Reproducibility

- `exp.py` — generates the dataset and runs all 60 KMeans fits.
- `postproc.py` — computes summary statistics and saves `results.json`.
- `results.json` — raw and aggregated inertia values.
- All files live in this directory; rerunning `python3 exp.py && python3 postproc.py` reproduces the numbers above bit-exactly.
