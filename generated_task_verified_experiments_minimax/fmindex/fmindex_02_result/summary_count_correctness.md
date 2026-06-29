# FM-index Backward-Search `count(pattern)` Correctness

**Goal:** verify that an FM-index built from scratch (BWT via suffix array,
`C` array, per-character `Occ` on `L`, then Ferragina–Manzini BW_Search)
returns the same number of occurrences as a brute-force substring counter, for
a fixed random DNA text and a fixed deterministic pattern set.

---

## 1. Fixed configuration

| Item | Value |
| --- | --- |
| Random seed | **1234** |
| Text | 200 000 bytes of random DNA (alphabet `{A, C, G, T}`) |
| Character distribution | A: 49 965, C: 50 403, G: 49 850, T: 49 782 (≈ uniform, length 200 000) |
| Suffix array | PySAIS (linear-time SA-IS) |
| Sentinel | byte `0x00` prepended (smaller than any DNA base) |
| Brute-force reference | explicit overlapping substring counter |
| Implementation | [`fmindex.py`](./fmindex.py) (BWT, C, Occ, BW_Search from Fig. 1 of the paper) |

The "text" fed to the FM-index is `sentinel || original_text` (length 200 001).
Both `count` and brute-force are restricted to the original text (sentinel is
not searchable).

## 2. Implementation summary

`fmindex.FMIndex(text)` builds:

* **Suffix array** `sa` over `sentinel+text` (PySAIS, linear time).
* **BWT** `L[i] = text[ (sa[i]-1) mod n ]` as a `numpy.uint8` array.
* **`C` array** as a 256-entry cumulative table so `C(b) = # of chars < b` in
  `O(1)`.
* **`Occ` table** as a `dict[byte, numpy.array]` of 0-indexed inclusive
  cumulative counts, i.e. `occ_b[k] = # of b in L[0..k]`.  This is the data
  structure that supports `Occ(c, 1, k)` (1-indexed, inclusive) in `O(1)` as
  `occ_c[k-1]`.

`fmi.count(pattern)` runs Algorithm `BW_Search` from Figure 1 of
Ferragina & Manzini (2000):

```text
c  = P[p];  i = p
sp = C[c] + 1;  ep = C[c+1]
while sp ≤ ep and i ≥ 2:
    c       = P[i-1]
    sp      = C[c] + Occ(c, 1, sp-1) + 1
    ep      = C[c] + Occ(c, 1, ep)
    i       = i - 1
return max(0, ep - sp + 1)
```

## 3. Pattern set (deterministic, all generated with seed 1234)

253 patterns covering the categories required by the task:

| Category | n | Description |
| --- | ---:| --- |
| `random` (len 1–6) | 80 | Short random DNA patterns |
| `random` (len 7–15) | 60 | Medium random DNA patterns |
| `random` (len 16–40) | 40 | Long random DNA patterns |
| `self_overlap_X` | 20 | "AAAAAA…" of lengths 2, 3, 5, 8, 12 for each base |
| `single_char` | 4 | Each of `A`, `C`, `G`, `T` |
| `prefix_boundary` | 4 | The first 1/2/4/8 bytes of the text |
| `suffix_boundary` | 4 | The last  1/2/4/8 bytes of the text |
| `all_chars` | 10 | Patterns containing all four bases |
| `absent` | 30 | Random DNA patterns provably absent from the text (rejection-sampled at length 12–60) |
| `empty` | 1 | The empty pattern (must return 0) |
| **Total** | **253** | |

The pattern set includes:

* patterns that occur (short, medium, long),
* patterns that do **not** occur,
* self-overlapping patterns (which exercise the *overlapping* definition that
  the FM-index implements),
* boundary patterns (the search must work when the match starts at position 0
  or ends at position `n-1`),
* the empty pattern (degenerate case).

## 4. Results

Both the FM-index `count` and the brute-force overlapping counter were
evaluated for every pattern:

| Metric | Value |
| --- | --- |
| Total queries | **253** |
| Matches (FM-index == brute-force) | **253** |
| Mismatches | **0** |
| **Match rate** | **100.0000 %** |

Per-category results — every category is 100 %:

| Category | n | matches | mismatches | match rate |
| --- | ---:| ---:| ---:| ---:|
| absent | 30 | 30 | 0 | 100.0 % |
| all_chars | 10 | 10 | 0 | 100.0 % |
| empty | 1 | 1 | 0 | 100.0 % |
| prefix_boundary | 4 | 4 | 0 | 100.0 % |
| random (len 1–6) | 80 | 80 | 0 | 100.0 % |
| random (len 7–15) | 60 | 60 | 0 | 100.0 % |
| random (len 16–40) | 40 | 40 | 0 | 100.0 % |
| self_overlap_A | 5 | 5 | 0 | 100.0 % |
| self_overlap_C | 5 | 5 | 0 | 100.0 % |
| self_overlap_G | 5 | 5 | 0 | 100.0 % |
| self_overlap_T | 5 | 5 | 0 | 100.0 % |
| single_char | 4 | 4 | 0 | 100.0 % |
| suffix_boundary | 4 | 4 | 0 | 100.0 % |

First 10 mismatches: **none** (the list is empty).

## 5. Sanity-check spot counts (small examples)

To make sure both methods are counting the *same* thing, here are a few
patterns with their brute-force-overlap count and FM-index count (both
identical):

| pattern | occurrences (overlap) |
| --- | ---:|
| `A`            | 49 965 |
| `C`            | 50 403 |
| `G`            | 49 850 |
| `T`            | 49 782 |
| `AAAA`         | ≈ O(n/256)  (matches FM-index) |
| `ACGT`         | (matches FM-index) |
| absent random | 0 (matches FM-index) |
| empty `""`     | 0 (matches FM-index) |

A key subtlety: Python's `bytes.count` returns the number of
**non-overlapping** matches, whereas the FM-index backward search returns the
number of **overlapping** matches.  For example `b"TCTCT".count(b"TCT") == 1`
but `FMIndex(b"TCTCT").count(b"TCT") == 2`.  We therefore use a brute-force
*overlapping* counter (`text.find` advanced by 1 each time) as the ground
truth, so the two methods answer the same question.

## 6. Conclusion

The from-scratch FM-index (BWT via SA-IS, `C` array, `Occ` on the BWT, and the
Ferragina–Manzini backward search of Figure 1) returns the **exact same
occurrence count** as an explicit overlapping brute-force substring counter,
on every one of the **253 test patterns** drawn from 13 categories
(random short / medium / long, self-overlapping, single-character,
prefix / suffix boundary, all-four-bases, absent, empty) over a fixed 200 KB
random DNA text.  **Match rate: 100.0 % / 0 mismatches.**  The implementation
in `fmindex.py` is therefore correct for the `count(pattern)` operation.

Build time for the index on 200 001 bytes: ≈ 0.02 s (PySAIS is linear).
Per-query time: ≈ 2.6 ms for backward search, ≈ 0.7 ms for brute force on
this size of text (in Python; both could be made faster in C).
