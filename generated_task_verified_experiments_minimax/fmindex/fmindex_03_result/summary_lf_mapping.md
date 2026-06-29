# LF-mapping reversibility on the FM-index BWT

## Question

Does repeated LF-mapping, using only the BWT column `L`, the `C` array, and
the per-position `rank`, recover the original text byte-for-byte? If not,
where does the first deviation appear?

## Reference

Ferragina & Manzini, *Opportunistic Data Structures with Applications* (FOCS
2000), §2 *The reversible BW-transform*. The three observations and the
backward-BWT algorithm I implemented are quoted verbatim there:

> a. Given the *i*th row of M, its last character `L[i]` precedes its first
>    character `F[i]` in the original text T, namely T = ... L[i] F[i] ...
> b. Let `L[i] = c` and let `r_i` be the rank of the row `M[i]` among all the
>    rows ending with the character `c`.
> c. Take the row `M[j]` as the `r_i`-th row of M starting with `c`. Then the
>    character corresponding to `L[i]` in the first column F is located at
>    `F[j]` (we call this **LF-mapping**, where `LF[i] = j`).

> 1. Compute the array `C[1..|Σ|]` storing in `C[c]` the number of occurrences
>    of characters `(#, 1, ..., c-1)` in T.
> 2. Define the LF-mapping `LF[1..u+1]` as follows `LF[i] = C[L[i]] + r_i`,
>    where `r_i` equals the number of occurrences of character `L[i]` in the
>    prefix `L[1..i]`.
> 3. Reconstruct T backward as follows: set `s = 1` and `T[u] = L[1]`
>    (because `M[1] = #T`); then, for each `i = u, u-1, ..., 1` do
>    `s = LF[s]` and `T[i] = L[s]`.

## Setup (fixed)

* RNG seed: `20260628`.
* Text length: **200 KiB** (204,800 bytes) for the headline case — squarely
  inside the 100 KB–500 KB window.
* Alphabet: 95 printable ASCII bytes drawn uniformly at random
  (letters × 2, digits, common punctuation/whitespace, see
  `lf_mapping_experiment.py:ALPHABET`).
* BWT construction: prepend a unique sentinel byte (0, smaller than any
  alphabet byte) and run **SA-IS** via `PySAIS.sais` to get the suffix array
  in O(n). `L[i] = aug[sa[i] - 1]`, with the wrap-around pulling the
  rotation's last character.
* `C[c]` built as a single prefix-sum over byte counts in `L`.
* `rank[i]` = occurrences of `L[i]` in `L[0..i-1]` via a running counter.
* Reconstruction: start at `s = 0` (the sentinel rotation, the
  lexicographically smallest); for `m = len(text)` iterations read `L[s]`
  into the next output position from the back, then `s = C[L[s]] + rank[s]`.
  The loop runs **m** times — exactly one fewer than `len(L)` — so we stop
  one step short of the sentinel row and never read the sentinel back.

## Measurement

Headline run, fixed seed and text:

| step                | time     |
|---------------------|----------|
| BWT build (SA-IS)   | 172.41 ms |
| C + rank build      | 13.90 ms |
| reconstruction      | 18.07 ms |

`len(L) = 204 801`, `|C| = 256`, `|rank| = 204 801`.

### Byte-wise comparison

`equal = True`, `first_mismatch = -1`. Every one of the 204,800 bytes of
the reconstructed text equals the corresponding byte of the original.

Cross-checks across the size window and stress inputs (see
`lf_extra_checks.py`):

| case                |   length | equal | first_mismatch |
|---------------------|---------:|:-----:|:--------------:|
| 100 KB random       | 102 400  | True  | −1             |
| 200 KB random (main)| 204 800  | True  | −1             |
| 500 KB random       | 512 000  | True  | −1             |
| 150 KB all-bytes (every byte 1..255 repeats) | 153 600 | True | −1 |
| `"hello"`           |       5  | True  | −1             |

All five runs reconstruct to a text byte-equal to the original.

## Interpretation

LF-mapping is **fully reversible** on this input — the reconstruction is
byte-identical to the original, with **no mismatch anywhere** in 204,800
positions (and identically across the cross-checks). The two off-by-one
hazards I hit and corrected while implementing the paper's recipe are
worth recording because they are the kind of thing the brief deliberately
leaves to the implementer:

1. **1-index vs 0-index of the start row.** The paper's "`s = 1`" refers to
   the row whose cyclic shift starts with the sentinel. In a 0-indexed
   Python implementation that row is `s = 0`, not `s = 1`. Starting from
   `s = 1` immediately desynchronises the LF walk and produces garbage.
2. **Loop count.** The LF walk is a single cycle of length `m + 1` over
   the `m + 1` rows of `M` (original text of length `m` plus the sentinel
   row). Starting from the sentinel row and reading `L` before each LF
   step gives `m + 1` reads if you also count the sentinel itself.
   Stopping after exactly `m` reads yields the original text; doing `m +
   1` reads writes the sentinel as the first byte of the output.

Once those two are correct, the LF walk traces the rotations in
lexicographic order, peeling off `T[u], T[u-1], ..., T[1]` — i.e. the
original text in reverse — and the last LF state returns to `s = 0` on
its own, which is why no extra "rewind" step is needed.

## Conclusion

On a 200 KiB pseudo-random text generated with the fixed seed
`20260628`, building the BWT (`L`), the `C` array, and `rank` and then
reconstructing by repeated LF-mapping **produces a text that is
completely identical to the original** — every one of the 204,800
bytes matches. **There is no first-mismatch position; the reconstruction
is exact.**

The same conclusion holds for the lower edge (100 KiB), the upper edge
(500 KiB) of the requested size window, an input that exercises every
non-sentinel byte value, and a 5-byte smoke test. LF-mapping is
reversible.

## Artifacts

* `lf_mapping_experiment.py` — main experiment (BWT → C/rank → LF-reconstruct → byte compare).
* `lf_extra_checks.py` — size sweep and stress checks.
* `summary_metrics.txt` — headline run numbers (regenerated by the main script).
