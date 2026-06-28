# Count-Min Sketch — Width `w` vs Point-Query Over-Estimate (d=5 fixed)

## 1. What was run

Independent re-implementation of Count-Min Sketch from the paper (Python/numpy, CPU only).
Sketch = `d` rows of `w` counters. Update `update(item,c)`: `C[j][h_j(item)] += c` for every row `j`.
Point query: `â[i] = min_{j∈[d]} C[j][ h_j(item) ]`. CMS never underestimates, so the
over-estimate `â[i] − a[i] ≥ 0` always.

**Hash family.** `d` pairwise-independent (2-universal) hash functions from the Dietzfelbinger
multiply-shift linear family `h_{a,b}(x) = ((a·x + b) mod 2⁶⁴) >> (64 − log₂ w)`, `a` odd.
Each row gets a distinct `(a_j, b_j)`; each seed draws a fresh independent set. This is a
standard pairwise-independent family for CMS and is fully vectorised over uint64 numpy arrays,
so the whole study (all `w`, seeds, both distributions) finishes in ~2 s.

**Fixed setup (per task, unchanged):** depth `d = 5`; `w ∈ {128,256,512,1024,2048,4096}`;
stream of `1e6` updates over a universe of `1e5` items; two frequency laws —
**Zipfian (s≈1.0)** and **Uniform**; true frequencies `a[i]` recorded directly while
generating the stream (`||a||₁ = 1e6` for both). For every `w`, the over-estimate
`â[i]−a[i]` is computed over **all** `1e5` items and its mean and 99th percentile are
reported; each `w` is repeated over **5 independent hash seeds** and averaged.

Stream facts: Zipf — top item frequency **82,664**, only **80,725/100,000** items ever appear
(heavy tail). Uniform — top frequency **25**, essentially all items appear ~10× each.

## 2. Results table

Over-estimate `â[i] − a[i]` (mean of 5 seeds). `||a||₁/w` is the classic per-row bound on the
expected bucket load — the same for both distributions because the total stream mass is identical.

| `w` | Zipf **mean** | Zipf **p99** | Zipf **max** | Uniform **mean** | Uniform **p99** | Uniform **max** | `‖a‖₁/w` (bound) |
|----:|------:|------:|------:|------:|------:|------:|------:|
| 128  | 4368  | 5984  | 12515 | 7698  | 7825  | 7921  | 7812.5 |
| 256  | 1932  | 2768  | 5630  | 3817  | 3914  | 3985  | 3906.2 |
| 512  |  842  | 1285  | 2812  | 1886  | 1955  | 2007  | 1953.1 |
| 1024 |  373  |  570  | 1388  |  925  |  976  | 1015  |  976.6 |
| 2048 |  161  |  257  |  503  |  448  |  486  |  514  |  488.3 |
| 4096 |   65  |  115  |  265  |  212  |  240  |  261  |  244.1 |

Log-log slope of `error ∝ w^slope` (least-squares over the 6 widths):

| distribution | slope of **mean** | slope of **p99** |
|---|---:|---:|
| Uniform | **−1.034** | **−1.005** |
| Zipfian | −1.208 | −1.142 |

Halving ratio `error(2w)/error(w)` (≈0.5 means exact 1/w):
Uniform p99 → `0.500, 0.500, 0.499, 0.498, 0.493` (almost perfectly ½);
Uniform mean → `0.496, 0.494, 0.490, 0.485, 0.473`;
Zipf p99 → `0.463, 0.464, 0.444, 0.451, 0.446`; Zipf mean → `0.442, 0.436, 0.443, 0.431, 0.405`.

**Figure:** `cm_02_width_vs_error.png` — log-log mean and p99 vs `w` for both distributions, with a `∝1/w` reference line.

## 3. Conclusions

**(a) Over-estimate falls ≈ `1/w` when `w` grows — CONFIRMED (primary goal).**
For both distributions, every doubling of `w` roughly **halves** the mean and the 99th-percentile
over-estimate, and the log-log slope is ≈ −1 (Uniform mean −1.03, p99 −1.005). The Uniform 99th
percentile halves almost exactly (ratio 0.493–0.500). This matches the CMS guarantee: the expected
per-row bucket load is `‖a‖₁/w`, so the point-query error budget scales as `1/w`; `d` only
tightens the tail probability, it does not change the `1/w` dependence on `w`.
(The Zipf mean decays slightly *faster* than `1/w`, slope −1.21 — a secondary effect of the min
explained below; the leading `1/w` behaviour is still clearly present.)

**(b) Is the Zipf over-estimate "significantly larger" than uniform? — Nuanced, and the common
intuition is only half-right.** Measured over all items:

- **Mean and 99th-percentile over-estimate are actually SMALLER for Zipf, not larger.**
  At `w=1024`: Zipf mean **373** vs Uniform **925** (Zipf is **0.40×**); Zipf p99 **570** vs
  Uniform **976** (0.58×). Even the p99.9 is smaller (0.75×).
- **What IS amplified by the heavy tail is the worst case and the spread.** Zipf **max**
  over-estimate (1388) exceeds Uniform (1015) — **1.37×** — and the dispersion `max/mean` is
  **3.7× for Zipf vs 1.1× for Uniform**. Zipf overtakes Uniform only in the extreme tail
  (beyond p99.9); the bulk of the distribution sits well below Uniform's near-constant value.

**Why — the mechanism (and a correction to the "`‖a‖₁` large" framing).**

1. *The per-row error budget is set by `‖a‖₁`, which is the same for both streams* (both are
   `1e6` updates). For any item, the expected load of the bucket it lands in, in a single row,
   is `‖a‖₁/w` — **independent of the frequency distribution**. So the average over-estimate is
   *not* larger for Zipf just because items are skewed; `‖a‖₁` is the total mass, not something
   the heavy items inflate. What the heavy tail inflates is the **second moment / max frequency**
   (Zipf top item 82,664 vs Uniform 25), i.e. the *variance* of bucket loads, not the mean.

2. *The `min` over `d=5` rows exploits that variance.* CMS's point estimate is the **minimum**
   across `d` rows. Under Uniform, every bucket is loaded almost identically (`≈‖a‖₁/w`), so all
   `d` rows agree and `min ≈ ‖a‖₁/w` (measured ≈0.95–0.98× the bound). Under Zipf, bucket loads
   vary wildly — a few buckets hold a giant item, most buckets are nearly empty — so the min over
   5 independent rows reliably lands on a lightly-loaded bucket, driving the *typical* (mean,
   median, p99) over-estimate **below** the uniform case (≈0.27–0.56× the bound, trending toward
   `1/d = 0.2` as `w` grows — which is exactly why the Zipf slope is a bit steeper than −1).

3. *The heavy tail then bites the unlucky few.* A small fraction of items happen to collide with
   a heavy item (frequency up to 82,664) in *their* minimum row — or across several rows — and
   inherit that huge count. These victims form the long right tail: they push up the **max** and
   the **max/mean** ratio dramatically, even though they are too few to move the mean or p99.

**Bottom line.** The headline research claim — *error ∝ 1/w, halving with each doubling of `w`* —
is confirmed cleanly for both distributions. The "skewed distribution amplifies collision
over-estimate" intuition is correct **only for the worst case / dispersion**: heavy items create
occasional very large over-estimates (higher max, ~3.7× larger spread). For the *average* and
*typical* (p99) over-estimate, Zipf is in fact **smaller** than uniform, because CMS's min operator
capitalises on the higher bucket-load variance and the per-row budget `‖a‖₁/w` is identical for
both streams.

## 4. Reproducibility

- Code: `run_experiment.py` (CMS + sweep, writes `results_cm_02.json`), `make_plot.py` (fit + figure).
- Hash: pairwise-independent multiply-shift linear family (2-universal), `d=5` distinct params
  per seed; results averaged over seeds `{11,22,33,44,55}`. Stream seed fixed at `12345`.
- Runtime ≈ 2 s, CPU only; no GPU. All outputs in this directory.
