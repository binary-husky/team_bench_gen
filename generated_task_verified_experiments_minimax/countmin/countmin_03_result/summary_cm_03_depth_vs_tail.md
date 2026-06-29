# Count-Min Sketch: depth `d` vs tail-failure probability

**Task.** Implement Count-Min Sketch from the Cormode–Muthukrishnan paper
using `d` pairwise-independent hash functions (with update + point query),
then verify that, at fixed width `w`, the point-query tail-failure probability
decays roughly like `e^{-d}` as depth `d` grows.

## 1. Setup

| parameter              | value                              |
|------------------------|------------------------------------|
| width `w`              | **1024**                           |
| `ε = e / w`            | 0.002655                           |
| depth grid `d`         | 1, 2, 3, 4, 5, 8                   |
| distinct items         | 100 000                            |
| stream length          | 1 000 000 updates                  |
| distribution           | Zipfian, `s = 1.0`                 |
| unique items seen      | 80 556 / 100 000                   |
| `‖a‖₁` (= #updates)    | 1 000 000                          |
| threshold `T = ε·‖a‖₁` | 2 654.57                           |
| hash function          | `h_j(i) = ((a_j·i + b_j) mod p) mod w`, `p = 100 003` (prime) |
| hash seeds per `d`     | 25 (≥ 20, as required)             |
| stream seed            | 2024 (fixed across all `(d, seed)`) |

The data stream is sampled once from a Zipfian(1.0) distribution over
`{1,…,100 000}` using inverse-CDF sampling (numpy.random.zipf does not
support `s ≤ 1`). The same stream is fed into every `(d, seed)`
configuration so the only varying factor is the hash family.

## 2. Implementation

```python
# Update:   count[j, h_j(i)] += 1
# Query:    a_hat[i] = min_j count[j, h_j(i)]
# Failure:  a_hat[i] > a[i] + T
```

For each `(d, seed)` we:

1. Draw `(a_j, b_j)` for `j = 1..d` independently (pairwise-independent family).
2. Compute `h[i, j] = ((a_j · i + b_j) mod p) mod w` for every item `i`.
3. Build the `d × w` counter matrix as `count[j, k] = Σ_i a[i] · [h[i, j] = k]`
   (via `np.add.at`).
4. Run point queries `â[i] = min_j count[j, h[i, j]]` for **all** `100 000`
   items.
5. Record the empirical tail-failure rate, i.e. the fraction of items for
   which `â[i] > a[i] + T`.

The reported rate per `d` is the mean across the 25 seeds (± one std).

The full implementation is `experiment.py`; the per-`(d, seed)` numbers
are in `raw_rates.csv`.

## 3. Empirical results

| `d` | empirical tail-failure rate (mean ± std, 25 seeds) | theory upper bound `(1/e)^d = e^{-d}` | ratio (theory / empirical) |
|-----|----------------------------------------------------|---------------------------------------|----------------------------|
| 1   | 3.73 × 10⁻²  ± 2.9 × 10⁻³                          | 3.68 × 10⁻¹                           | 9.9 ×                      |
| 2   | 1.20 × 10⁻³  ± 2.8 × 10⁻⁴                          | 1.35 × 10⁻¹                           | 1.13 × 10²                 |
| 3   | 5.68 × 10⁻⁵  ± 7.6 × 10⁻⁵                          | 4.98 × 10⁻²                           | 8.77 × 10²                 |
| 4   | 5.60 × 10⁻⁶  ± 1.9 × 10⁻⁵                          | 1.83 × 10⁻²                           | 3.27 × 10³                 |
| 5   | 0               (≤ detection floor 4 × 10⁻⁷)        | 6.74 × 10⁻³                           | ≥ 1.7 × 10⁴                |
| 8   | 0               (≤ detection floor 4 × 10⁻⁷)        | 3.35 × 10⁻⁴                           | ≥ 8.4 × 10²                |

The detection floor is `1 / (seeds · items) = 1 / (25 · 100 000) ≈ 4 × 10⁻⁷`:
any rate smaller than this would produce zero failures in our experiment.

### Figure

![Tail-failure rate vs depth](tail_vs_depth.png)

The figure plots the empirical curve (blue) and the theoretical upper
bound `(1/e)^d` (orange) on a log scale. The empirical curve sits one to
several orders of magnitude **below** the theoretical bound at every `d`,
and steepens (on the log scale) at least as fast as the bound.

## 4. Conclusion

1. **Tail-failure probability decays roughly like `e^{-d}`** as `d` grows.
   Each additional row reduces the failure rate, and from `d = 1` to
   `d = 4` the empirical rate falls from 3.7 % to 5.6 × 10⁻⁶ — a factor
   of ≈ 6 600 over just three extra rows, i.e. an average per-step
   reduction of ≈ **1/19**, much steeper than the conservative 1/e ≈
   0.368 predicted by the worst-case bound.
   `d = 5` and `d = 8` already push the failure rate below the
   detection floor of ≈ 4 × 10⁻⁷.

2. **Empirical rates are at or below the theoretical bound `(1/e)^d`** at
   every tested depth (the inequality holds strictly in our setting:
   ratios range from ≈ 10× for `d = 1` to ≥ 10³–10⁴ for `d ≥ 4`).
   This is exactly the relationship the paper's Theorem 1 establishes:
   the bound is a **safe upper bound**, not a tight prediction. With
   `d` rows the failure probability is bounded by `(1/e)^d`; in practice
   it is much smaller because the noise `X_{i,j}` on each row is
   concentrated well below its mean (the Markov step in the proof is
   not tight), and the items share common heavy-hitter structure that
   the union bound across rows over-counts.

3. **The depth dimension is exactly the right knob for the tail**: at
   fixed `w = 1024` the per-row mean-field collision cost is fixed at
   `ε · ‖a‖₁`, and only the number of rows determines how often all
   rows simultaneously suffer an unusually large collision. The
   observed geometric decay with `d` confirms the paper's central
   claim that depth controls failure probability **exponentially**
   while width controls the **scale** of the error.

**Verdict.** The empirical tail-failure probability decreases
approximately exponentially in `d` and stays comfortably under the
`e^{-d}` upper bound predicted by Cormode–Muthukrishnan (Theorem 1),
exactly as the task hypothesis predicts.