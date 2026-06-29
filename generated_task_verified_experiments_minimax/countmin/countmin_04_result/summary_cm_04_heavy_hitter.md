# Count-Min Sketch heavy-hitter experiment
## Setup
- Stream: 1,000,000 updates over 100,000 distinct items, Zipfian(s=1.0).
- Real top-K (ground truth): k=100 items ranked by true frequency `a[i]`.
- Sketch grid: [(512, 3), (1024, 5), (2048, 5), (4096, 8), (8192, 10)]
- Seeds per config: 5 (seeds 0..4).
- Query rule: estimate `â[i] = min_j count[j, h_j(i)]` for every seen item,
  then take the top-100 estimated items and compare to real top-100.
- precision@100 = (#items in both real top-100 and estimated top-100) / 100.
- recall@100 = (#items in both real top-100 and estimated top-100) / 100
  (since both sets have size 100, precision == recall).

## Per-seed results

| (w, d) | seed | precision@100 | recall@100 |
|---|---|---:|---:|
| (512, 3) | 0 | 0.4400 | 0.4400 |
| (512, 3) | 1 | 0.4300 | 0.4300 |
| (512, 3) | 2 | 0.4000 | 0.4000 |
| (512, 3) | 3 | 0.4400 | 0.4400 |
| (512, 3) | 4 | 0.4200 | 0.4200 |
| (1024, 5) | 0 | 0.9900 | 0.9900 |
| (1024, 5) | 1 | 0.9600 | 0.9600 |
| (1024, 5) | 2 | 0.9800 | 0.9800 |
| (1024, 5) | 3 | 0.9700 | 0.9700 |
| (1024, 5) | 4 | 0.9600 | 0.9600 |
| (2048, 5) | 0 | 1.0000 | 1.0000 |
| (2048, 5) | 1 | 1.0000 | 1.0000 |
| (2048, 5) | 2 | 0.9900 | 0.9900 |
| (2048, 5) | 3 | 0.9900 | 0.9900 |
| (2048, 5) | 4 | 0.9800 | 0.9800 |
| (4096, 8) | 0 | 0.9900 | 0.9900 |
| (4096, 8) | 1 | 1.0000 | 1.0000 |
| (4096, 8) | 2 | 1.0000 | 1.0000 |
| (4096, 8) | 3 | 0.9900 | 0.9900 |
| (4096, 8) | 4 | 1.0000 | 1.0000 |
| (8192, 10) | 0 | 0.9900 | 0.9900 |
| (8192, 10) | 1 | 1.0000 | 1.0000 |
| (8192, 10) | 2 | 0.9900 | 0.9900 |
| (8192, 10) | 3 | 0.9900 | 0.9900 |
| (8192, 10) | 4 | 0.9900 | 0.9900 |

## Mean ± std (over 5 seeds)

| (w, d) | precision@100 (mean±std) | recall@100 (mean±std) |
|---|---|---|
| (512, 3) | 0.4260 ± 0.0150 | 0.4260 ± 0.0150 |
| (1024, 5) | 0.9720 ± 0.0117 | 0.9720 ± 0.0117 |
| (2048, 5) | 0.9920 ± 0.0075 | 0.9920 ± 0.0075 |
| (4096, 8) | 0.9960 ± 0.0049 | 0.9960 ± 0.0049 |
| (8192, 10) | 0.9920 ± 0.0040 | 0.9920 ± 0.0040 |

## Conclusion

- As sketch size (w, d) grows, both precision@100 and recall@100 increase
  and converge toward 1.0, as expected from the CM Sketch error bound
  `â_i ≤ a_i + ε‖a‖₁` (so the relative error on heavy hitters shrinks
  with growing w because ε = e/w).
- Small sketches (e.g. w=512, d=3) suffer from **false positives**:
  long-tail items collide on the same row cell as a heavy hitter and
  their estimated count is inflated enough to leak into the top-100,
  pushing real heavy hitters out. This shows up as precision
  dropping below 1.
- Each top-100 has exactly 100 items, so precision@100 and recall@100
  are numerically equal (the |intersection| / 100 cancels) and the
  two metrics reveal the same symmetric error: false positives in the
  estimated top-100 correspond one-for-one to false negatives w.r.t.
  the real top-100.
- The smallest sketch configuration achieving **both** precision and
  recall ≥ 0.95 in this experiment is **(w=1024, d=5)** (P=0.9720, R=0.9720).

## Notes on the implementation
- Hash family: pairwise-independent `h_{a,b}(x) = ((a*x + b) mod p) mod w`
  with prime p > number of items and per-row independent (a, b) drawn
  from a seeded numpy RNG.
- Updates and point queries are batched via numpy vectorization
  (`np.add.at` and fancy indexing).
- Estimates use the **min** across rows, the standard CM point-query
  estimator for the non-negative / cash-register case.
