# FM-index (count / locate) vs naive O(n·m) substring search

Speed comparison on a fixed text with a fixed pattern set.

## Setup (fixed)

- **Text**: 150000 bytes, alphabet `ACGT`, generated with `numpy.random.default_rng(12345)` (CPU, fixed seed).
- **Sentinel**: `'$'` appended (lex-smallest, unique) so all suffixes are distinct.
- **Patterns**: 40 random patterns of length 6–15 (first 30 seeded from the text so they occur at least once; last 10 fully random, rarer — some absent).
- **FM-index**: BWT via prefix-doubling suffix array; full `Occ(c,i)` rank table of shape `(5, 150002)` (~3.0 MB); SA sampled every `4` rows for LF-walk locate.
- **Naive**: pure-Python O(n·m) scan, char-by-char, early exit.
- **Correctness**: FM-index count and locate positions matched the naive search for **all 40 patterns** (0 mismatches).

Independent variable = query method (count / locate / naive); everything else fixed.

## Build cost (one-time, not per query)

| step | time |
|---|---|
| suffix array (prefix doubling) | 61.6 ms |
| BWT + C + full Occ table | 2.7 ms |
| total build | 64.3 ms |

## Per-query results

Times averaged over many reps for the fast FM-index paths (count ×500, locate ×100); naive ×1 (it is slow). All times in **microseconds (µs)**.

| # | pattern | m | occ | count µs | locate µs | naive µs | count/naive | locate/naive |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| 1 | `TTCTTGCC` | 8 | 4 | 3.06 | 6.20 | 8732.4 | 0.0004 | 0.0007 |
| 2 | `GAGCACAAAT` | 10 | 1 | 3.81 | 5.32 | 8996.6 | 0.0004 | 0.0006 |
| 3 | `CGCTGCTA` | 8 | 2 | 3.04 | 5.41 | 8867.9 | 0.0003 | 0.0006 |
| 4 | `AGTAGATGA` | 9 | 1 | 3.39 | 4.58 | 11016.7 | 0.0003 | 0.0004 |
| 5 | `ATGCGGGC` | 8 | 1 | 4.60 | 7.12 | 11948.5 | 0.0004 | 0.0006 |
| 6 | `TCGCACCGTG` | 10 | 1 | 5.87 | 6.50 | 9195.5 | 0.0006 | 0.0007 |
| 7 | `GCCACTT` | 7 | 10 | 2.76 | 8.22 | 8852.3 | 0.0003 | 0.0009 |
| 8 | `CAAGCCGC` | 8 | 1 | 3.08 | 4.53 | 8828.6 | 0.0003 | 0.0005 |
| 9 | `TTAATAAT` | 8 | 2 | 3.04 | 4.10 | 8716.4 | 0.0003 | 0.0005 |
| 10 | `CGGGAG` | 6 | 35 | 2.39 | 25.67 | 8820.8 | 0.0003 | 0.0029 |
| 11 | `GTATCGTT` | 8 | 6 | 3.10 | 7.35 | 8945.1 | 0.0003 | 0.0008 |
| 12 | `CGCGAGGG` | 8 | 4 | 3.13 | 6.42 | 10766.3 | 0.0003 | 0.0006 |
| 13 | `GTCAACGTC` | 9 | 1 | 4.99 | 6.89 | 11138.1 | 0.0004 | 0.0006 |
| 14 | `GTGCCTG` | 7 | 7 | 3.74 | 9.76 | 9980.5 | 0.0004 | 0.0010 |
| 15 | `GGCTAA` | 6 | 32 | 2.30 | 23.69 | 8810.4 | 0.0003 | 0.0027 |
| 16 | `AGTGCGGA` | 8 | 5 | 3.06 | 5.35 | 8869.6 | 0.0003 | 0.0006 |
| 17 | `AGGTACCT` | 8 | 3 | 3.11 | 4.29 | 8975.2 | 0.0003 | 0.0005 |
| 18 | `CCCATA` | 6 | 44 | 2.30 | 37.13 | 8799.4 | 0.0003 | 0.0042 |
| 19 | `ATAGGCTC` | 8 | 1 | 3.12 | 3.92 | 8996.9 | 0.0003 | 0.0004 |
| 20 | `AAGGTA` | 6 | 41 | 2.43 | 27.87 | 10980.4 | 0.0002 | 0.0025 |
| 21 | `GGGACCA` | 7 | 8 | 4.02 | 14.39 | 11046.1 | 0.0004 | 0.0013 |
| 22 | `ATACATGC` | 8 | 5 | 4.66 | 11.76 | 9787.6 | 0.0005 | 0.0012 |
| 23 | `GTGAATAG` | 8 | 7 | 3.16 | 8.69 | 8800.1 | 0.0004 | 0.0010 |
| 24 | `TCGCGAGGG` | 9 | 2 | 3.51 | 5.86 | 8846.1 | 0.0004 | 0.0007 |
| 25 | `CCTGGCCC` | 8 | 4 | 3.12 | 5.87 | 8818.5 | 0.0004 | 0.0007 |
| 26 | `ACCTATGGTT` | 10 | 1 | 3.84 | 5.02 | 8868.6 | 0.0004 | 0.0006 |
| 27 | `ATCGTT` | 6 | 54 | 2.42 | 32.90 | 9014.3 | 0.0003 | 0.0037 |
| 28 | `AACAGAC` | 7 | 7 | 2.83 | 9.70 | 11199.6 | 0.0003 | 0.0009 |
| 29 | `AGGACTCT` | 8 | 4 | 4.70 | 9.74 | 11257.5 | 0.0004 | 0.0009 |
| 30 | `TTAGGCTCT` | 9 | 1 | 5.19 | 4.91 | 13375.2 | 0.0004 | 0.0004 |
| 31 | `AAACGCCAAATTGTT` | 15 | 0 | 5.74 | 5.81 | 9621.8 | 0.0006 | 0.0006 |
| 32 | `CCCGGAAAATACTA` | 14 | 0 | 6.12 | 4.80 | 9780.6 | 0.0006 | 0.0005 |
| 33 | `CCGAACGGCATCA` | 13 | 0 | 5.95 | 6.15 | 16267.8 | 0.0004 | 0.0004 |
| 34 | `GCCAGAATACTGCC` | 14 | 0 | 3.80 | 3.88 | 9975.3 | 0.0004 | 0.0004 |
| 35 | `CCTGGGCTCAATCA` | 14 | 0 | 5.28 | 5.06 | 11422.0 | 0.0005 | 0.0004 |
| 36 | `AAGCACATTATTGAA` | 15 | 0 | 4.94 | 5.10 | 11860.2 | 0.0004 | 0.0004 |
| 37 | `ATGCGGCCGCCC` | 12 | 0 | 4.45 | 3.41 | 9022.9 | 0.0005 | 0.0004 |
| 38 | `TGTGCTATTCCACC` | 14 | 0 | 3.67 | 3.76 | 9030.2 | 0.0004 | 0.0004 |
| 39 | `CGTCTCCTCAGAA` | 13 | 0 | 4.42 | 4.45 | 9024.4 | 0.0005 | 0.0005 |
| 40 | `ACCGCATCGCGAGC` | 14 | 0 | 3.77 | 3.81 | 8978.0 | 0.0004 | 0.0004 |

## Totals across all 40 queries (single-query avg × N)

| method | total time | 
|---|---|
| FM-index count | 151.9 µs (0.152 ms) |
| FM-index locate | 365.4 µs (0.365 ms) |
| naive O(n·m) | 396234.5 µs (396.235 ms) |

## Conclusion

- **Count**: FM-index backward-search count is **2608×** faster than naive scanning in total (0.152 ms vs 396.235 ms over 40 queries). Count cost is essentially independent of text length — `O(p)` with the full Occ table, vs naive `O(n·m)`.
- **Locate**: FM-index LF-walk locate is **1084×** faster than naive in total (0.365 ms vs 396.235 ms). Locate cost grows with `occ` (`O(occ·d)` for sampling step d=4); for the low-occurrence patterns here it stays far below naive, and would only approach/beaten-by naive when a pattern occurs very frequently (occ ≈ Θ(n)).
- **Per-query pattern**: longer / rarer patterns (small `occ`) make FM-index's advantage largest, since naive always pays `O(n·m)` while count pays `O(p)` and locate pays `O(occ·d)`.
- **Trade-off**: the speedup is bought with a one-time build cost of ~64 ms and ~3.0 MB of index memory; for a *single* ad-hoc query naive wins, but for a *batch* of queries over the same text the FM-index amortises its build cost and dominates.
