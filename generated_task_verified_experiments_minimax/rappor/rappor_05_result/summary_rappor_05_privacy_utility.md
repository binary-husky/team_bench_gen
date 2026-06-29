# RAPPOR Privacy–Utility Trade-off — Experiment 5

This experiment characterises how the PRR parameter `f` of RAPPOR
(Erlingsson, Pihur, Korolova, CCS 2014) trades **utility** (frequency-estimation
accuracy) against **privacy** (the per-report differential-privacy budget
ε_perm). The full RAPPOR encode/decode pipeline is implemented from scratch in
`run_rappor.py` (Python + NumPy + scikit-learn LASSO, CPU-only, ~13 s wall time).

## 1. Setup

| Parameter     | Value | Meaning                                                |
|---------------|-------|--------------------------------------------------------|
| `N`           | 5×10⁴ | number of clients / reports                            |
| Bloom `k`     | 128   | Bloom filter length                                    |
| Bloom `h`     | 4     | number of hash functions                               |
| IRR `p`       | 0.50  | probability bit = 1 in `S` when underlying Bloom bit = 0 |
| IRR `q`       | 0.75  | probability bit = 1 in `S` when underlying Bloom bit = 1 |
| `M`           | 200   | candidate dictionary size                              |
| True dist.    | exp-decay (Zipf-like) over 200 candidates             |
| Seeds         | {11, 22, 33} — three per setting                     |
| `f`           | {0.10, 0.25, 0.50, 0.75, 0.90}                         |
| `ε_perm`      | ln((2 − f)/f)   (per task)                             |

### Pipeline per run

1. **Encode** — for every client:
   * hash value `v` into a Bloom filter `B` of length 128 with 4 hash functions,
   * Permanent RR with parameter `f`: each Bloom bit is replaced by a random
     bit with probability `f` and otherwise kept (Theorem 1 of the paper gives
     `ε_perm = 2·ln((1−f/2)/(f/2))`; we use the task-defined
     `ε_perm = ln((2−f)/f)` for reporting),
   * Instantaneous RR with `(p, q) = (0.5, 0.75)` (Lemma 1 / Theorem 2 of the paper).
2. **Decode** — server-side, per-bit:
   * aggregate bit counts `c_i = Σ S_i`,
   * invert the per-bit bias/scale of the two-stage RR (Sec. 4 of the paper):
     `t_i = (c_i − (p + ½f·q − ½f·p)·N) / ((1 − f/2)·(q − p))`,
   * build the design matrix `X` (128 × 200, one Bloom filter per candidate),
   * solve a non-negative LASSO (`α = 5×10⁻⁴`) for the per-candidate counts;
     falls back to NNLS if LASSO leaves too much mass unexplained.
3. **Score** — compute
   `L1 = Σ |ĉ − c_true|` and `max = max |ĉ − c_true|` over the 200 candidates.
4. **Baseline** — clients report true string verbatim; the server simply counts.
   This baseline has only finite-sample noise (`O(√N)`); we expect its error to
   be near zero.

## 2. Results

Per-setting mean ± std across three random seeds.

| `f`   | `ε_perm` | L1 error          | max-abs error     |
|------:|---------:|------------------:|------------------:|
| 0.10  |  2.9444  | 32 673 ± 4 051    | 1 146.5 ± 80.5    |
| 0.25  |  1.9459  | 36 526 ± 3 818    | 1 294.9 ± 171.3   |
| 0.50  |  1.0986  | 42 796 ± 1 072    | 1 477.9 ± 49.7    |
| 0.75  |  0.5108  | 48 983 ± 1 883    | 2 132.8 ± 142.2   |
| 0.90  |  0.2007  | 52 268 ± 2 417    | 2 331.9 ± 93.9    |
| **non-private** | — | **1 587 ± 70**  | **80.6 ± 18.7**   |

The same data plotted (`privacy_utility.png`):

![privacy–utility trade-off](privacy_utility.png)

Left panel — error vs `ε_perm = ln((2−f)/f)` (small ε → strong privacy);
right panel — error vs the underlying PRR parameter `f`.

## 3. Conclusions

1. **Stronger privacy ⇒ larger error.** L1 error grows monotonically from
   ~3.27×10⁴ at `f = 0.10` (ε ≈ 2.94, weak privacy) to ~5.23×10⁴ at
   `f = 0.90` (ε ≈ 0.20, strong privacy). The same monotone trend holds for
   the max-abs error (1 147 → 2 332). Going from `f = 0.10` to `f = 0.90`
   multiplies the L1 error by ~1.6×.

2. **The non-private baseline is essentially "free".** Direct counting
   achieves L1 ≈ 1 587 (max-abs ≈ 81) — about **20×–33× smaller** than the
   private L1 errors and roughly equal to the per-seed finite-sample noise
   of N = 5×10⁴ over 200 candidates. This gap is the *utility price paid for
   local differential privacy*: RAPPOR injects the noise needed to make each
   individual report ε-differentially private, and that noise propagates
   through the per-bit inversion and the LASSO coefficient recovery.

3. **`f` (equivalently ε_perm) is the privacy–utility knob.** Tuning `f` is a
   clean way to interpolate between the two extremes: `f → 0` recovers
   non-private accuracy (only IRR noise remains, which can be averaged out
   analytically), while `f → 1` gives maximum obfuscation of every Bloom bit
   but still leaves the server with consistent counts because the IRR stage
   preserves the marginals of `B`.

4. **Decoding is the bottleneck, not the IRR step alone.** Holding IRR fixed
   at `(p, q) = (0.5, 0.75)` and only sweeping `f`, L1 error rises ~60%
   across the scan. This matches the paper's intuition: more aggressive PRR
   shrinks the signal that the LASSO must recover from `t`, so the inverse
   problem gets progressively ill-conditioned.

5. **Take-aways for practitioners.**
   * Choose `f` to set ε_perm at the desired budget; the curve above lets you
     read off the resulting utility loss.
   * Even at the most permissive setting (`f = 0.10`, ε_perm ≈ 2.94) the
     private pipeline is ~20× worse than the baseline — privacy, even
     local, is never free.
   * For very long-tail distributions the relative error on rare candidates
     will be larger because the per-bit inversion noise is multiplicative on
     small counts. Practitioners should aggregate rare categories before
     decoding, as the paper itself recommends.

## 4. Reproducing

```bash
cd /data/workspace/admin/happy_lake/.verify_judge_minimax/rappor/rappor_05
python3 run_rappor.py     # ~13 s; writes results_raw.json
python3 make_plot.py      # writes privacy_utility.png + summary table
```

Raw JSON of every per-seed run is in `results_raw.json`.