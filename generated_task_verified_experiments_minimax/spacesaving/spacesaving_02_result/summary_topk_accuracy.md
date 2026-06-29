# Space-Saving top-k accuracy measurement

## Setup (fixed)

| Parameter | Value |
|---|---|
| Stream length `N` | 1,000,000 |
| Zipfian skew parameter `α` | 1.0 (canonical Zipf) |
| Alphabet size `|A|` | 500,000 |
| Random seed | 42 |
| Number of counters `k` | 100 |
| Stream generator | `numpy.random.Generator.choice` with `p(r) ∝ 1/r^α` |
| Ground truth | Full exact `Counter` of all stream items |
| Space-Saving variant | Standard "Stream-Summary" algorithm from Metwally, Agrawal, El Abbadi 2005 |

Theoretical reference: Metwally, Agrawal, El Abbadi, *Efficient Computation of Frequent and Top-k Elements in Data Streams*, 2005 (the paper provided in `spacesaving_material/`).

## Stream shape (ground truth)

- 176,478 distinct elements observed (out of 500,000 in the alphabet).
- True frequency of the most frequent element: **72,698**.
- True frequency of the 10th most frequent element: **7,383**.
- True frequency of the 100th most frequent element: **723**.
- Ratio F₁ / F₁₀₀ ≈ 100 (consistent with α ≈ 1).

## Space-Saving monitor-set state at end of stream

| Quantity | Value |
|---|---|
| Monitor size | 100 (= k) |
| Sum of all counter values | 1,000,000 (= N, by Lemma 1 of the paper) |
| Minimum counter value in monitor | 8,713 |
| Maximum counter value in monitor | 72,698 (= true top-1, exact) |
| Average counter value | 10,000 |

The minimum counter 8,713 is consistent with Lemma 2's upper bound `min ≤ ⌊N/m⌋ = 10,000`.

## Top-k accuracy

Reported top-k = the 100 elements in the SS monitor set sorted by their counter values (descending). Truth top-k = the 100 elements with the largest exact counts.

| Metric | Value |
|---|---|
| **precision@100** | **0.31** (31 of the 100 SS-reported elements are in the true top-100) |
| **recall@100** | **0.31** (31 of the 100 true top-100 elements are in the SS-reported set) |

Since both sets have size 100, `precision@k == recall@k` here. The two metrics will differ when the monitor-set size differs from the truth-set size.

### Why precision is below 1.0 at α = 1.0

The paper's Theorem 7 explicitly notes that **the α = 1 boundary case requires O(k²·ln|A|) counters for exact top-k**:

> When α = 1, the space complexity reduces to min(|A|, O(k² ln(|A|)) and ln(|A|)).

For k = 100 and |A| = 500,000, this is ≈ 100² · ln(500,000) ≈ 1.3 × 10⁵ counters — three orders of magnitude more than the 100 we use. The observed precision = 0.31 is therefore the expected behaviour at α = 1 with limited counters, not a bug.

The mechanism: at α = 1, the long tail is "fat" — many elements have similar frequencies to the top-100 (F₁₀₀ ≈ 723 vs F₂₀₀ ≈ 364 — only a 2× gap). The 100-counter monitor set cannot discriminate this boundary sharply, so it ends up containing 69 elements with true ranks 101–67,933 that have been "promoted" via evictions.

## Frequency estimation error (f̂ vs f)

The Space-Saving algorithm over-estimates frequencies (Lemma 3: f̂ ≥ f, ε = f̂ − f ≤ min). Confirmed empirically: **0 under-estimates, 6 exact, 94 over-estimates** among the 100 reported top-k elements.

### Error statistics for the reported top-100

| Statistic | Value |
|---|---|
| Number of elements | 100 |
| Under-estimated (f̂ < f) | 0 (matches Lemma 3 guarantee) |
| Exact (f̂ = f) | 6 |
| Over-estimated (f̂ > f) | 94 |
| Mean over-estimation Δf = f̂ − f | **7,229.94** |
| Median over-estimation | 8,673 |
| Maximum over-estimation | **8,713** |
| Minimum over-estimation | 0 |
| 95th percentile over-estimation | 8,713 |
| 99th percentile over-estimation | 8,713 |
| Mean over-estimation (only over-estimated) | 7,691.43 |
| Mean absolute error | 7,229.94 |
| Mean **relative** over-estimation (f̂/f − 1) | 1,895.23× |
| Max relative over-estimation | 8,713× |

The maximum over-estimation of 8,713 exactly equals the current monitor-set minimum counter value — consistent with Lemma 3 (`ε_i ≤ min`).

### Per-rank snapshot (first 10 reported)

| SS rank | element | f (truth) | f̂ | Δf | true rank | in true top-100? |
|---|---|---|---|---|---|---|
| 1 | 1 | 72,698 | 72,698 | 0 | 1 | ✓ |
| 2 | 2 | 36,612 | 36,612 | 0 | 2 | ✓ |
| 3 | 3 | 24,467 | 24,467 | 0 | 3 | ✓ |
| 4 | 4 | 18,177 | 18,177 | 0 | 4 | ✓ |
| 5 | 5 | 14,596 | 14,596 | 0 | 5 | ✓ |
| 6 | 6 | 12,167 | 12,167 | 0 | 6 | ✓ |
| 7 | 7 | 10,414 | 10,415 | +1 | 7 | ✓ |
| 8 | 8 | 9,184 | 9,185 | +1 | 8 | ✓ |
| 9 | 10 | 7,383 | 8,719 | +1,336 | 10 | ✓ |
| 10 | 9 | 8,069 | 8,717 | +648 | 9 | ✓ |

The very top of the ranking is essentially correct: ranks 1–6 are exact, 7–8 have Δf = 1, and 9–10 are merely swapped due to a 648-hit over-estimate on element 9 (whose true count 8,069 > 7,383). The over-estimation problem dominates lower in the top-100.

## Conclusions

1. **Over-estimation, not under-estimation.** Across the 100 reported top-k elements, **0 were under-estimated, 6 were exact, and 94 were over-estimated** — exactly as Lemma 3 of the paper predicts (count ≥ true count, error ≤ min).

2. **Over-estimation magnitudes.** The mean over-estimate is **7,230** and the max is **8,713**. The max equals the current monitor-set minimum counter value 8,713, consistent with the paper's upper-bound guarantee.

3. **precision@100 = recall@100 = 0.31.** With only k = 100 counters at α = 1, Space-Saving recovers 31 of the 100 true top elements. This is expected: at α = 1 the paper's bound is O(k²·ln|A|) counters for exact top-k, ≈ 130,000 — far more than 100. The thin (2×) gap between F₁₀₀ ≈ 723 and F₂₀₀ ≈ 364 means the top-100 boundary is fuzzy, so the monitor set mixes true top-100 elements with long-tail elements that get "promoted" by evictions.

4. **Frequency-error asymmetry.** The top-1 element is recovered with zero error (Δf = 0). The over-estimation accumulates for lower-ranked elements, especially for non-top-100 elements that happen to enter the monitor set late (when the global min counter is already large). Their `f̂` reflects the count of the element they evicted, not their own true frequency — a 8713× relative over-estimation is possible for an element that appeared only once.

5. **Practical implication.** For Zipf α = 1 streams, Space-Saving with O(k) counters is **not** exact for top-k. To get exact top-k, the paper's analysis says we need O(k²·ln|A|) counters; to get high-precision top-k at α = 1 in practice one should either (a) increase k significantly, (b) increase α by choosing a more skewed distribution, or (c) accept that the monitor set is approximate and use the counter lower-bound `f̂ − min` as a guaranteed range.

## Reproducing this measurement

```
python3 run_final.py
```

The script writes full numerical metrics to `metrics.json` and per-element details to `topk_detail.json`. Stream generation: 0.13 s; exact counting: 0.09 s; Space-Saving pass: 3.57 s. Total ≈ 3.8 s on a single CPU.
