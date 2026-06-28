# Cuckoo Filter Deletion Correctness vs. Standard Bloom Filter

This report summarizes a self-run experiment (see `experiment.py`, results in
`results.json`) examining **deletion correctness** of a self-implemented
Cuckoo Filter and contrasting it with a standard (non-counting) Bloom filter.
Reference material: *Cuckoo Filter: Practically Better Than Bloom* (Fan et al.,
2014) in `cuckoofilter_material/`.

## Fixed settings

| Parameter | Value |
|---|---|
| Cuckoo bucket size `b` | 4 slots/bucket |
| Cuckoo fingerprint `f` | 12 bits |
| Number of keys `N` | 100,000 |
| Cuckoo table | 2^17 = 131,072 buckets (capacity 524,288; load 0.191) |
| Max kicks | 500 |
| Bloom `m` | 1,000,000 bits |
| Bloom `k` | 7 hash functions (≈0.8% FPR at n=1e5) |
| Random seed | 1234 (fixed; governs key set, delete split, kick RNG) |

Independent variable: **whether deletion occurred / which query set is probed.**
Everything else is fixed.

The Cuckoo filter uses partial-key cuckoo hashing: fingerprint `fp = hash_f(x)`,
primary index `i1 = hash_i(x) mod 2^power`, alternate index
`i2 = i1 XOR hash(fp)`. Insert tries `i1` then `i2`, else cuckoo-kicks.
Lookup checks both candidate buckets for `fp`. Delete removes one occurrence
of `fp` from a candidate bucket.

---

## 1. Cuckoo filter: insert N, delete half, query three sets

Inserted all 100,000 keys (0 insert failures). Then randomly selected exactly
half (50,000) and deleted them; the other 50,000 were retained.

| Query set | Size | Result | Metric |
|---|---|---|---|
| **Retained** (must all hit) | 50,000 | 50,000 hit, **0 missed** | **FNR = 0.000000** |
| **Deleted** (must be absent) | 50,000 | 29 reported present | FP = 29; **correct-removal = 99.942%** |
| **Fresh non-members** | 100,000 | 50 reported present | **FPR = 0.0500%** |

### 1a. False-negative rate on retained keys: **0 / 50,000 = 0.0%**

After deleting half the keys, **every one of the 50,000 retained keys was
still found**. The cuckoo filter produces **zero false negatives** when
deleting only keys that were genuinely inserted. This is the central result:

> Cuckoo-filter deletion is *safe*: removing an inserted key never destroys
> the fingerprint of a *different, retained* key.

Why it holds: each key stores its **own** fingerprint copy in one of its two
candidate buckets. Deleting key `x` only removes one occurrence of `fp(x)` from
`{i1(x), i2(x)}`. A retained key `y` is missed only if `y`'s fingerprint were
removed — but `y`'s copy is distinct from `x`'s copy (each insertion writes a
separate slot). Even in the collision case `fp(x) == fp(y)` with the same
bucket-pair, *both* keys deposit a copy, so deleting `x` leaves `y`'s copy
intact. The only way to create a cuckoo false negative is to **delete a key
that was never inserted** (removing a stranger's fingerprint) — which this
experiment does not do. Hence FNR = 0.

### 1b. Correct removal of deleted keys

All 50,000 `delete()` calls succeeded (50000/50000 fingerprints removed).
After deletion, 29 of the 50,000 deleted keys were nonetheless reported
"present" on query. These 29 are **false positives, not failed deletions**:
the deleted key's own fingerprint was removed, but a *different* key sharing
the same 12-bit fingerprint and an overlapping candidate bucket still holds a
matching fingerprint, so lookup returns true. This matches the filter's
measured FPR on fresh non-members (0.0500% → ~50 expected per 100k; here 29
per 50k ≈ 0.058%, consistent). The deletion mechanism itself is 100%
successful; the residual "present" reports are the inherent FPR.

### 1c. Fresh non-members (FPR sanity check)

50 / 100,000 = **0.050%** false positives. This agrees with the deleted-key
FP rate, confirming the 29 "present" results in §1b are ordinary FPR noise
rather than deletion failures.

---

## 2. Standard (non-counting) Bloom filter: deletion is unsafe

A standard Bloom filter stores only set bits. "Deleting" a key by clearing its
`k` bits is the obvious (and broken) approach: those bits are **shared** with
other keys, so clearing them removes evidence belonging to innocent members.

### 2a. Single bit-clearing deletion

After inserting all 100,000 keys (baseline: 0 false negatives), the key
`bloom-0` was "deleted" by clearing its 7 bits.

- The victim itself correctly reads absent: `bloom-0` ✓ removed.
- **Collateral damage:** 8 of the remaining 99,999 keys became false negatives
  (0.0080%).
- Concrete example: `bloom-7590` is now a false negative — it **shared 1 of its
  7 bits** with `bloom-0`; clearing that single shared bit was enough to make
  `bloom-7590`'s lookup fail, even though it was never deleted.

### 2b. Scaling: bit-clearing 1% of keys

Deleting 1,000 keys (1%) by bit-clearing produced **4,563 collateral false
negatives among 99,000 survivors (4.61%)** — i.e., deleting 1% of members
silently broke ~4.6% of the *unrelated* survivors. The damage grows
super-linearly with deletions because every cleared bit can invalidate every
key that uses it.

### Why Bloom cannot delete safely

A bit in a standard Bloom filter is the OR of many keys' membership. The
filter cannot tell whether a set bit is "owned" by one key or by thousands, so
it cannot subtract a single key. Correct deletion requires a **counting
Bloom filter** (4–8 bits/counter to avoid overflow) or a structure that stores
per-key evidence — exactly the gap Cuckoo filters fill by storing the
fingerprint itself.

---

## 3. Conclusion

| Property | Cuckoo filter (b=4, f=12) | Standard Bloom filter |
|---|---|---|
| Delete a genuinely-inserted key | Safe; 100% of deletions succeed | N/A (no deletion primitive) |
| False negatives on **retained** keys after deleting half | **0 / 50,000 = 0.0%** | — |
| Correct removal of deleted keys | 99.94% (residual 0.058% is FPR, not failure) | — |
| Naive bit-clear deletion | (not applicable — stores fingerprints) | **Breaks unrelated keys**: 1 delete → 8 collateral FN; deleting 1% → 4.6% collateral FN |
| FPR (fresh non-members) | 0.050% | ~0.8% by design |

The experiment directly demonstrates the headline claim of Fan et al. (2014):
**because the Cuckoo filter stores the key's fingerprint, it supports deletion
without harming other keys**, attaining a **0% false-negative rate** on
retained members after deleting half the set. A standard Bloom filter has no
safe deletion: the bit-clearing illusion of deletion silently destroys shared
bits and produces false negatives in keys that were never touched — making
deletion in a non-counting Bloom filter fundamentally unsound.
