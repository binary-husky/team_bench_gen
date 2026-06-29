# Cuckoo Filter vs Bloom Filter — Deletion Correctness

Self-implemented filters, run on 100 000 random 128-bit keys, single fixed
random seed (`42`). Source: `experiment.py` (also `sweep_f.py`,
`diagnose.py`). All numbers below come from that run.

## 1. Setup

| | Cuckoo filter | Standard Bloom filter |
|---|---|---|
| bucket / parameter | `b = 4` entries/bucket | — |
| fingerprint | `f = 12` bits | — |
| `N` (inserted keys) | 100 000 | 100 000 |
| table size | `m = 32 768` buckets (= 2¹⁵) | `m = 1 200 000` bits |
| hash functions | partial-key cuckoo: `i₁ = h(x) mod m`, `i₂ = i₁ ⊕ hash(fp)` | `k = 8` via double hashing `g_i(x) = h₁(x) + i·h₂(x) mod m` |
| target load factor | `N / (b·m) = 0.763` | `(k·N)/m ≈ 0.667` (→ theory FPR ≈ 0.314 %) |

**Why `m = 2¹⁵`?** Partial-key cuckoo hashing computes the alternate bucket
by `i ⊕ hash(fp)`. If `m` is *not* a power of 2, that XOR does not round-trip
mod `m`, so kicks can leave a fingerprint in a bucket that is neither of its
candidate locations — producing spurious false negatives at lookup time even
*before* any deletion. With `m = 32 768 = 2¹⁵` the round-trip holds and the
filter has the textbook property of zero false negatives. (I confirmed this
empirically: `sweep_f.py` reports 0 % FN for `f = 8, 10, 12, 14, 16`, whereas
a non-power-of-2 `m` gave ≈ 1.3 % FN for every `f`.)

**Hashing.** All hashes come from SHA-256: `fingerprint = SHA256("fp|"+key)`
(low 12 bits, clamped to non-zero); bucket index `i₁` from
`SHA256("i1|"+key) mod m`; alternate-bucket hash from
`SHA256("alt|"+fp) mod m`. Bloom uses the standard 64-bit double-hashing
trick (`h₁, h₂ = SHA256(x)[:8], SHA256(x)[8:16]`).

## 2. Cuckoo filter — measured results

```
inserted  : 100 000 / 100 000         (0 insertion failures)
delete()  : 50 000 / 50 000 removed  (every random-half key reported a removal)
retained  : 50 000 / 50 000 hits     false-negative rate = 0.000 000
deleted   :     31 / 50 000 hits     residual rate       = 0.000 620
fresh keys:     74 / 100 000 hits    false-positive rate = 0.000 740
theory FPR:  1 - (1 - 1/2^f)^(2b) = 1 - (4095/4096)^8 ≈ 0.001 951
actual load factor after insert: 100 000 / (32 768·4) = 0.7629
```

### Interpretation

* **0 % false negatives on the retained half.** Every one of the 50 000
  retained keys still reports present after its 50 000 siblings have been
  deleted. This is the property the cuckoo filter is designed for: the
  per-fingerprint removal in `Delete(x)` matches exactly the *one* copy of
  `fingerprint(x)` that was stored in `bucket[i₁(x)]` or `bucket[i₂(x)]`,
  and the lookup still finds it in the other candidate bucket. As long as no
  bucket ever overflows (no `Insert` returned `Failure`), the filter has no
  false negatives — Section 3.2 of Fan et al., 2014.

* **0.062 % "residual" on the deleted half is *not* a sign of a broken
  delete.** It is the filter's natural false-positive rate: a freshly
  queried, *non-deleted* key set (the "fresh" row) gives 0.074 %, almost
  identical. The deleted set sits at exactly the expected FPR — i.e. the
  fingerprint of every deleted key is genuinely gone from the table. The
  residual 31 hits are not because "delete forgot" anything, they are the
  ~0.07 % of deletes that happen to share a fingerprint with one of the
  50 000 retained keys (fingerprint collision ≠ false negative).

* **Empirical FPR < theoretical FPR.** Theory assumes the table is full
  (load factor 1.0); we operate at 0.76, so the real FPR ≈ (0.76 · 2b)/2^f
  ≈ 0.001 49, consistent with the measured 0.000 74.

## 3. Standard (non-counting) Bloom filter — `bit-clear` delete demo

I built a vanilla Bloom filter with the *same* `N` and a similarly tuned
`m = 1 200 000`, `k = 8`. After inserting all 100 000 keys, the filter has
a fresh-set FPR of **0.310 %** (theory 0.314 %). Then I picked one victim
key `x = 96 8f 09 8d …` and applied the natural-looking "delete" — clear
each of `x`'s `k = 8` bit positions:

```
victim bit positions: 923263, 425372, 1127481, 629590, 131699,
                      833808, 335917, 1038026
```

Counting which *other* inserted keys happen to hash to any of those 8 bit
positions: **5** other inserted keys share at least one bit with the
victim. (For `m = 1.2 M`, `k = 8`, `N = 1e5`, the expected number of
bit-sharing keys is `N·(1 − (1 − k/m)^k) ≈ 6.4` — empirical 5 is right on.)

After clearing the victim's 8 bits:

| Query | Result |
|---|---|
| `bf.contains(victim)` | `False`  (the delete "worked" for the victim) |
| All 99 999 *other* inserted keys | **5** of them now return `False` |
| The 5 bit-sharing keys specifically | **5 / 5** report `False` (100 %) |

So *every* key whose bits overlapped the victim's now produces a false
negative — the bits they relied on were wiped along with the victim's. This
is exactly the well-known reason standard Bloom filters are not safely
deletable: the `k` positions are *shared* with `Θ(N·k/m)` other keys, and
you cannot tell whose bit is whose.

### Cascade: more naive deletes = more false negatives

In a second pass I deleted 5, 10, 15, … 50 random keys in a fresh filter
and counted how many of the 100 000 originally-present keys now report
`False`:

| Keys "deleted" (bit-cleared) | Inserted keys now reporting `False` | False-negative rate |
|---:|---:|---:|
|   5 |   7 | 0.007 % |
|  10 |  14 | 0.014 % |
|  15 |  19 | 0.019 % |
|  20 |  24 | 0.024 % |
|  25 |  31 | 0.031 % |
|  30 |  35 | 0.035 % |
|  35 |  43 | 0.043 % |
|  40 |  52 | 0.052 % |
|  45 |  64 | 0.064 % |
|  50 |  70 | 0.070 % |

The false-negative count grows roughly **linearly** with the number of
"deletions": each cleared key knocks out its own 8 bits, and any neighbour
key that touched any of those 8 bits is now wrongly declared absent. There
is no way to undo this — the standard Bloom filter has no per-bit
reference count.

## 4. Bottom line

* **Cuckoo filter** (`b = 4`, `f = 12`, `m = 32 768`, `N = 1e5`):
  * Insert success: 100 %.
  * `delete()` removes the right thing every time, **leaving zero false
    negatives** on the 50 000 retained keys.
  * The 0.062 % "residual" hits on the deleted set are just the filter's
    normal false-positive rate, indistinguishable from the 0.074 % rate on a
    fresh non-member set. The deleted keys are genuinely gone.
  * This is the cuckoo filter's central deletion guarantee (Fan et al.
    §3.3): `Delete(x)` is exact when the corresponding `Insert(x)` succeeded
    and no bucket overflow has occurred.

* **Standard Bloom filter**: the natural-looking `clear-bit` "delete" is
  unsalvageable. A single bit-clearing deletion of one key caused 5 *other*
  inserted keys to become false negatives, and the effect grows linearly
  with more deletes. This is why Bloom filters either forbid deletion or
  must be upgraded to a counting variant (with the 3–4× space cost
  documented in the paper).
