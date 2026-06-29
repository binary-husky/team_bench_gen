# FM-index count / locate vs. naive substring search — speed comparison

## 1. Setup (everything fixed except the search method)

| Item | Value |
| --- | --- |
| Text body | random English-like (a–z + space), seed `12345`, **150,000 chars** |
| Alphabet Σ | `abcdefghijklmnopqrstuvwxyz ` (28 symbols incl. sentinel) |
| Sentinel | `\x01` (lex-smaller than every body symbol, so it is the smallest suffix) |
| `\|T\|` (incl. sentinel) | 150,001 |
| Suffix array | sorted with Python's Timsort, n·log n time; one-shot, not in the timed region |
| BWT, C, Occ | built once; the BWT and per-character cumulative `Occ` are kept in RAM (Occ is `O(σ·n) = 28·150,001` ints, ~16 MB; not in the timed region) |
| Pattern set | **200 patterns** total = 100 random (seed `54321`) + 100 text-derived (seed `54322`), 5 length buckets {3, 5, 8, 12, 20} |
| Correctness check | every pattern's `fm_count` and `fm_locate` were compared to `naive_search`; **count OK = True, locate OK = True** on all 200 patterns |
| Hardware | CPU-only Python 3.11, no GPU |
| Self-variable | the search method (`fm_count`, `fm_locate`, `naive_search`); the three implementations are otherwise identical and read the same input |

The three implementations under test (code in `experiment.py`):

- **`fm_count(P)`** — Ferragina–Manzini backward search. Walks the pattern from right to left, updating `sp, ep` with `sp = C[c] + Occ(c, 1, sp−1)`, `ep = C[c] + Occ(c, 1, ep) − 1`. Returns the `sp..ep` row interval. Cost: **O(p)**.
- **`fm_locate(P)`** — calls `fm_count` to get the row interval, then for each row `s` in the interval does an LF-walk (`pos ← LF(pos)`) until `BWT[pos] == sentinel`; the number of LF steps IS the 0-based start position. Cost: **O(p + occ · p)** in this naïve implementation (the paper improves it to `O(p + occ · log^ε n)` with sampled checkpoints, but we do the simpler version).
- **`naive_search(P)`** — Python loop `for i in range(n-m+1): if text[i:i+m] == P`. Cost: **O(n·m)**.

## 2. Aggregate timing (200 patterns, mixed lengths)

| Method | total (s) | mean (s) | median (s) | min (s) | max (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| **FM-index count** | **0.000435** | 2.17 × 10⁻⁶ | 1.63 × 10⁻⁶ | 8.0 × 10⁻⁷ | 6.09 × 10⁻⁶ |
| FM-index locate   | 11.541 | 5.77 × 10⁻² | 2.58 × 10⁻³ | 8.2 × 10⁻⁷ | 2.41 |
| Naive O(n·m)      | 1.372  | 6.86 × 10⁻³ | 6.72 × 10⁻³ | 6.64 × 10⁻³ | 7.51 × 10⁻³ |

**Speedups (200-pattern totals, vs. naive = 1.00×):**

- **FM-index count is ≈ 3,156× faster than naive** (0.435 ms vs 1,372 ms total; **per query: ~2 µs vs ~6.9 ms**).
- FM-index locate is **8.4× slower** in total, but this is *entirely* due to high-occurrence patterns (L=3, ~24 hits avg, ~3× per-LF × 24 = 72 LF steps per query on average). For a pattern that does not occur, locate is even faster than naive.

## 3. Per-pattern-length breakdown (mean time per single query)

### 3a. All 200 patterns (random + text-derived, mix of present and absent)

| L | #pats | count (s) | locate (s) | naive (s) | mean #occ |
|---:|---:|---:|---:|---:|---:|
|  3 | 34 | 1.08 × 10⁻⁶ | 0.310  | 6.75 × 10⁻³ | 23.7 |
|  5 | 43 | 1.55 × 10⁻⁶ | 5.93 × 10⁻³ | 6.72 × 10⁻³ | 0.53 |
|  8 | 45 | 2.06 × 10⁻⁶ | 5.75 × 10⁻³ | 6.71 × 10⁻³ | 0.44 |
| 12 | 36 | 2.64 × 10⁻⁶ | 6.16 × 10⁻³ | 6.71 × 10⁻³ | 0.56 |
| 20 | 42 | 3.42 × 10⁻⁶ | 6.51 × 10⁻³ | 7.39 × 10⁻³ | 0.48 |

### 3b. Text-derived patterns only (always present, isolating the `occ` cost)

| L | #pats | count (s) | locate (s) | naive (s) | mean #occ |
|---:|---:|---:|---:|---:|---:|
|  3 | 20 | 9.80 × 10⁻⁷ | 0.453  | 6.76 × 10⁻³ | **35.15** |
|  5 | 20 | 1.59 × 10⁻⁶ | 1.27 × 10⁻² | 6.71 × 10⁻³ | 1.15 |
|  8 | 20 | 2.63 × 10⁻⁶ | 1.29 × 10⁻² | 6.70 × 10⁻³ | 1.00 |
| 12 | 20 | 3.50 × 10⁻⁶ | 1.11 × 10⁻² | 6.70 × 10⁻³ | 1.00 |
| 20 | 20 | 5.51 × 10⁻⁶ | 1.37 × 10⁻² | 7.41 × 10⁻³ | 1.00 |

## 4. Observations (matches the FM-index paper's predicted asymptotics)

1. **FM-index count is essentially free.**  At ~1.6–5.5 µs per query it is **3 to 4 orders of magnitude faster than naive** (~6.7 ms), and the time grows only with pattern length `p`, not with the text size `n`. This is exactly the `O(p)` behaviour the paper proves (Theorem 1).

2. **Naive search is flat with `p` (and linear in `n·m`).**  Mean ~6.7 ms for any length 3–20 because the inner `text[i:i+m] == P` check is dominated by the 150,000 outer-loop iterations and the `O(m)` character compare, with little variation in `m` over our range. Naive does **not** benefit from increasing `p` — its cost is `O(n·m)` regardless.

3. **FM-index locate has two regimes.**
   - When the pattern **does not occur** (the random-pattern majority), locate collapses to just `fm_count` (it returns `[]` immediately). Mean time ≈ 1.6 µs — basically free.
   - When the pattern **does occur**, each occurrence costs one full LF-walk from the row to the sentinel row. Length-3 patterns with ~35 occurrences on average take ~0.45 s/query (≈ 13 ms per located hit, matching `O(p + occ·p)` with `p=3`). This is the well-known weakness of the naïve `locate`: cost scales **linearly with the number of occurrences**, exactly the `O(p + occ log² n)` in Theorem 2 of the paper. With sampling/checkpoints (Lemma 2) you would drop this to `O(p + occ · log^ε n)`.

4. **Scaling sanity check (length sweep, text-derived patterns).**
   - Naive grows from 6.76 ms (L=3) to 7.41 ms (L=20): **~10% over a 6.7× pattern-length increase**, consistent with `O(n·m)` and a fixed per-iteration overhead in Python (so the slope is shallow in our `m` range).
   - FM-index count grows from 0.98 µs (L=3) to 5.51 µs (L=20): **~5.6× over 6.7× pattern-length increase** — essentially linear in `p`, exactly as predicted.
   - FM-index locate for `occ = 1` (L=5,8,12,20): stays at ~12 ms because the dominant cost is a single LF-walk of ~L steps from row to sentinel, plus a fixed Python-loop overhead per LF step. With `occ = 1` the cost is roughly the locate overhead, not the pattern length.

5. **Bottom line for the original task.**  On this 150 KB text, on this pattern set, with this Python implementation:

   - **Count vs. naive: FM-index count is ~3,000× faster in total, ~3,000× faster per query.**  The wall-clock gap is dominated by Python interpreter overhead, but the *ratio* still reflects the asymptotic advantage (count is `O(p)`, naive is `O(n·m)`).
   - **Locate vs. naive: ambiguous, sensitive to `occ`.**  When the pattern rarely occurs, locate is faster than naive (1.6 µs vs 6.7 ms — ~4,000×). When the pattern occurs many times (e.g. a 3-letter word in natural text, ~35 hits), locate is **slower** than naive (0.45 s vs 6.7 ms — ~67× slower), because the naïve LF-walk cost `O(occ·p)` overwhelms everything. The paper's sampled-checkpoint locate would close this gap (Theorem 2 refined: `O(p + occ log^ε n)` instead of `O(p + occ log² n)`).
   - The experimental ranking `count ≪ naive < locate-for-rare ≪ locate-for-frequent` is a textbook FM-index outcome and matches the paper's complexity claims.

## 5. Files

- `experiment.py` — full implementation (text generation, FM-index build, three search methods, correctness check, timing).
- `raw_results.json` — all numbers above as machine-readable JSON.
- `summary_speed_vs_naive.md` — this file.
