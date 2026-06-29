# HyperLogLog: relative error vs true cardinality n (p = 14)

## Setup

- **Algorithm**: from-scratch re-implementation of the Flajolet–Fusy–Gandouet–Meunier 2007 HyperLogLog algorithm (paper `FlFuGaMe07.pdf`, §1 and §4 / Figure 3).
- **Hash**: 64-bit murmurhash3 (`mmh3.hash64(..., signed=False)`), fixed salt
  `0xC0FFEE`. Each input item is the 8-byte little-endian representation of a
  random 63-bit unsigned integer (so the unsigned 64-bit hash output has 50
  bits left for the rank, since the top 14 bits index the register).
- **Precision**: `p = 14`, hence `m = 2^14 = 16384` registers, bias-correction
  constant `α_m = 0.7213 / (1 + 1.079 / m) ≈ 0.72125`.
- **Estimation pipeline** (full §4 program):
  1. **Raw estimate** `E = α_m · m² · (Σ 2^(-M[j]))^{-1}` (harmonic mean).
  2. **Small-range linear-counting correction**: if `E ≤ (5/2)m` and any
     register is still 0, return `E* = m · log(m / V)` where `V` is the number
     of zero registers.
  3. **Intermediate range**: `E* = E`.
  4. **Large-range correction**: if `E > 2^64 / 30`, return
     `E* = -2^64 · log(1 - E / 2^64)`. (Not triggered for any n in this grid;
     the largest `E` is ~1.01 × 10⁶.)
- **Synthetic data**: for each trial, generate `n` distinct random 64-bit
  integers with `numpy.random.default_rng(seed)`. With `n ≤ 10⁶` drawn from a
  `2⁶³` space, birthday-collision probability is `~ n² / 2⁶⁴ < 5 × 10⁻⁷`, so
  the empirical cardinality equals `n`.
- **Random seeds**: 5 per `n` — `{11, 22, 33, 44, 55}`.
- **Grid of n**: `{1e3, 5e3, 1e4, 5e4, 1e5, 5e5, 1e6}`.
- **Metric**: relative error `|Ê − n| / n`, reported as mean ± std across the
  5 seeds.

## Theoretical reference

Paper Theorem 1: relative standard error `SE = (1/n)·√V_n(E) → β_∞ / √m`,
with `β_∞ = √(3 ln 2 − 1) ≈ 1.03896`. The §4 program adds corrections for
small/large `n`, but in the asymptotic regime the relative SE is roughly

`SE_theory ≈ 1.04 / √16384 ≈ 0.00813 ≈ 0.813%`.

## Results

| n        | mean rel err | std rel err | min rel err | max rel err | raw E (seed 11) |
|---------:|-------------:|------------:|------------:|------------:|----------------:|
|     1 000 |       0.6996 % |     0.6847 % |     0.0963 % |     1.5852 % |       1 002.0 |
|     5 000 |       0.3367 % |     0.3052 % |     0.0517 % |     0.8427 % |       4 986.3 |
|    10 000 |       0.4423 % |     0.3040 % |     0.1080 % |     0.8240 % |       9 930.4 |
|    50 000 |       0.4522 % |     0.3322 % |     0.1164 % |     0.8607 % |      50 430.4 |
|   100 000 |       0.3005 % |     0.1363 % |     0.0782 % |     0.4470 % |      99 921.8 |
|   500 000 |       0.5912 % |     0.5136 % |     0.0318 % |     1.3676 % |     501 655.6 |
| 1 000 000 |       0.5016 % |     0.2684 % |     0.1449 % |     0.8867 % |   1 008 866.6 |

Theoretical SE = `1.04/√16384` ≈ **0.8125 %**.

![relative error vs n](rel_err_vs_n.png)

## Per-seed raw estimates (sanity check)

| n       | s=11     | s=22     | s=33     | s=44     | s=55     |
|--------:|---------:|---------:|---------:|---------:|---------:|
|   1 000 |   1 002.0 |     987.1 |     996.7 |   1 001.0 |   1 015.9 |
|   5 000 |   4 986.3 |   4 982.2 |   5 008.0 |   4 957.9 |   5 002.6 |
|  10 000 |   9 930.4 |   9 967.1 |   9 989.2 |   9 974.5 |   9 917.6 |
|  50 000 |  50 430.4 |  50 086.1 |  50 365.9 |  50 189.9 |  50 058.2 |
| 100 000 |  99 921.8 |  99 664.7 |  99 553.0 |  99 705.2 |  99 653.0 |
| 500 000 | 501 655.6 | 497 877.1 | 495 995.3 | 506 838.0 | 499 841.1 |
| 1 000 000 | 1 008 866.6 | 995 767.3 | 995 244.7 | 1 001 448.8 | 1 005 774.4 |

For `n = 1 000` the raw harmonic-mean estimate (before §4 corrections) is
~12 300, ~12× too high; the linear-counting correction brings it down to the
correct ~1 000, confirming the small-range correction is doing real work at
the bottom of the grid.

## Conclusion

1. **Relative error is essentially independent of n in the mid-range.**
   Across `n ∈ {5 000 … 1 000 000}` the empirical mean relative error sits in
   a tight band of **0.30 %–0.59 %**, with no monotonic trend as `n` grows by
   three orders of magnitude. This is exactly what HLL promises: the standard
   error of the *relative* error is `Θ(1/√m)`, a function of memory
   (`m = 16 384`), not of `n`.

2. **Empirical SE is the same order of magnitude as the theoretical SE.**
   The measured mean relative errors (0.30 %–0.70 %) are all at or below the
   paper's predicted `1.04/√m ≈ 0.81 %`; the per-seed std lies in
   0.14 %–0.68 %, again at or below the prediction. Across all 35 trials the
   largest single relative error was 1.59 % (`n = 1 000`, where the small-range
   linear-counting correction, not the harmonic-mean estimator, dominates the
   error budget).

3. **Small-n regime (n = 1 000).** Here the empirical std (0.68 %) is slightly
   higher than at mid-range — the linear-counting correction has its own
   variance and we are in the very-low-`V` (≈ 15 000 zero registers) tail of
   its regime — but the estimate is still unbiased and accurate to within
   ~1.5 %.

4. **Constant relative precision verified.** Holding `p` (and therefore `m`)
   fixed yields roughly constant relative accuracy across the entire grid, as
   the theory predicts. Doubling `n` does **not** double the absolute error;
   it leaves the *relative* error unchanged. The full run (35 trials,
   `Σ n ≈ 5 × 10⁶` items) completed in **~10 s** on a single CPU.

### Files

- `hll.py` — implementation of HyperLogLog (raw estimate + small-range linear
  counting + large-range correction, 64-bit mmh3 hash).
- `experiment.py` — driver that runs the `n × seed` grid.
- `make_plot.py` — plots `rel_err_vs_n.png` from `experiment_results.json`.
- `experiment_results.json` — raw per-trial estimates and per-`n` summary.
- `rel_err_vs_n.png` — plot of mean ± std relative error vs `n`.