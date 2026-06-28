# HyperLogLog Mergeability Study (HLL-05)

Reproduction of HyperLogLog (FlFuGaMe07) from scratch in Python/numpy with a
64-bit hash, focused on **mergeability**: whether per-register `max` merge of
two same-precision sketches equals the sketch of the union stream.

## Setup (fixed)

| Parameter | Value |
|---|---|
| Precision `p` | 14 |
| Registers `m = 2^p` | 16384 |
| Bias constant `α_m` | `0.7213 / (1 + 1.079/m)` (m ≥ 128) |
| Hash | 64-bit, MurmurHash3 finalizer over uint64 items (good avalanche) |
| Stream A | `n_A = 5·10^4` distinct items, drawn from `[0, 2^62)` |
| Stream B | `n_B = 5·10^4` distinct items, drawn from `[2^62, 2^63)` |
| Disjointness | A and B from disjoint 62-bit halves ⇒ `A ∩ B = ∅` guaranteed |
| True union cardinality | `n_A + n_B = 10^5` |
| Independent seeds | 7 (1…7); streams regenerated per seed |
| Merge op | `S_merge[j] = max(S_A[j], S_B[j])` |

Estimator uses the standard small-range correction (`E ≤ 2.5m`) and large-range
correction (`E > 2^32/30`); neither fires here (`E ≈ 10^5`, `2.5m = 40960`,
`2^32/30 ≈ 1.4·10^8`), so the reported numbers are the raw stochastic estimate.

Implementation: `hll_merge.py`; raw per-seed numbers: `results_hll_05.json`.

## Per-seed results

| seed | n_A | n_B | true union | Ê_merge | Ê_direct | Ê_dup | merge rel.err | S_merge==S_direct (reg) | Ê_dup / n_A |
|---:|---:|---:|---:|---:|---:|---:|---:|:---:|---:|
| 1 | 50000 | 50000 | 100000 | 100515.7 | 100515.7 | 50232.4 | 0.516% | ✓ True | 1.0046 |
| 2 | 50000 | 50000 | 100000 | 100306.0 | 100306.0 | 50431.1 | 0.306% | ✓ True | 1.0086 |
| 3 | 50000 | 50000 | 100000 |  98926.3 |  98926.3 | 50476.0 | 1.074% | ✓ True | 1.0095 |
| 4 | 50000 | 50000 | 100000 | 100557.0 | 100557.0 | 50734.9 | 0.557% | ✓ True | 1.0147 |
| 5 | 50000 | 50000 | 100000 | 100377.0 | 100377.0 | 50768.3 | 0.377% | ✓ True | 1.0154 |
| 6 | 50000 | 50000 | 100000 | 101108.5 | 101108.5 | 50890.2 | 1.108% | ✓ True | 1.0178 |
| 7 | 50000 | 50000 | 100000 | 100029.7 | 100029.7 | 51077.1 | 0.030% | ✓ True | 1.0215 |

## Aggregated metrics (across 7 seeds, mean ± std)

| Metric | Value |
|---|---|
| **Merge accuracy** `\|Ê_merge − (n_A+n_B)\| / (n_A+n_B)` | **0.567% ± 0.368%** |
| Direct-stream accuracy `\|Ê_direct − (n_A+n_B)\| / (n_A+n_B)` | 0.567% ± 0.368% (identical to merge) |
| **Register-level equivalence** `S_merge == S_direct` (all 16384 regs) | **True on every seed (7/7)** |
| Estimate-level equivalence `Ê_merge == Ê_direct` | True on every seed (7/7) |
| **Idempotency** `Ê_dup / n_A` (1.0 = dedup, 2.0 = sum) | **1.013 ± 0.005** ⇒ ≈ n_A, not 2·n_A |

## Interpretation of the three required indicators

1. **Merge gives union cardinality, not the sum.** `Ê_merge` hovers around
   `10^5` (the union), with mean relative error 0.567% — the standard HLL
   error of `~1.04/√m ≈ 0.81%`. It is **not** `n_A + n_B` summed twice
   (`2·10^5`); merging does not add the two cardinalities.

2. **Register-level equivalence to the direct-union sketch.** On all 7 seeds,
   `S_merge` is **bit-for-bit identical** (all 16384 registers equal) to
   `S_direct`, the sketch built by feeding the entire `A ∪ B` to a fresh HLL.
   Consequently `Ê_merge == Ê_direct` exactly. This is the core of
   mergeability: per-register `max` recomputes the same register state the
   union stream would have produced, because a register's value is just the
   max `ρ` over all items that hashed into that bucket, and the max over the
   union of two item sets equals `max(max over A, max over B)`.

3. **Idempotency / dedup semantics.** Merging `A` with a duplicate copy of
   itself yields `Ê_dup ≈ n_A` (`Ê_dup/n_A = 1.013`, i.e. ~50k, not ~100k).
   Per-register `max(A[j], A[j]) = A[j]`, so the merged sketch equals `S_A`
   and the estimate is unchanged — duplicate items are de-duplicated, exactly
   as a set-union cardinality should behave.

## Conclusion

**Per-register `max` merge of two equal-precision HyperLogLog sketches yields
the union cardinality (not the sum of the two stream cardinalities), is
register-for-register identical to the sketch built directly on the union
stream, and is idempotent with respect to duplicate elements (deduplication
semantics).** Verified across 7 independent seeds: merge relative error
0.567% ± 0.368% against the true union of 10^5; `S_merge == S_direct` on
every register on every seed; `Ê_dup ≈ n_A` (ratio 1.013, not 2.0).
