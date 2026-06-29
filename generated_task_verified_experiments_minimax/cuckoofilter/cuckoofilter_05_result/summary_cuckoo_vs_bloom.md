# Cuckoo Filter vs Bloom Filter — Equal-Memory Comparison

## Experimental Setup (fixed parameters)

| Parameter | Value |
|-----------|-------|
| `N` (key set size) | 200,000 |
| `B` (memory budget) | 3,145,728 bits (384 KiB) |
| Random seed | 42 |
| Independent variable | filter type |

**Cuckoo filter configuration** — `f, b=4, M` chosen so memory ≈ B:
- fingerprint bits `f = 12`
- entries per bucket `b = 4`
- bucket count `M = 65,536` (must be a power of 2 so the partial-key XOR alternate is reversible mod M)
- memory = `M × b × f = 65,536 × 4 × 12 = 3,145,728` bits  ✅
- slot count = 262,144; load factor `α = N / (M·b) = 200,000 / 262,144 ≈ 0.763`

**Bloom filter configuration** — `m = B, k = round((m/N)·ln2)`:
- `m = 3,145,728` bits
- `k = round((3,145,728 / 200,000) · ln 2) = round(10.90) = 11` hash functions (double-hashed from two 64-bit hashes)

The same 200,000 random 64-bit member keys (drawn from `[0, 2^62)`) are inserted into both filters; 200,000 disjoint random 64-bit non-member keys (drawn from `[2^62, 2^63)`) are used for the FPR query set. Insertion and query throughputs are wall-clock `ops/sec` over the full N-item batch in a fresh filter.

## Results

| Filter | FPR (measured) | FPR (theory) | Insert (ops/s) | Query-neg (ops/s) | Query-pos (ops/s) | Deletion? |
|--------|----------------:|-------------:|---------------:|------------------:|------------------:|:---------:|
| **Cuckoo** (f=12, b=4, M=65,536) | **297/200,000 = 0.001485** (0.149%) | 2b/2^f = 8/4096 = **0.001953** (0.195%) | **73,000** | **57,062** | 79,699 | **Yes** (1000/1000 deleted) |
| **Bloom** (m=3,145,728, k=11) | **113/200,000 = 0.000565** (0.057%) | (1−e^(−kN/m))^k = **0.000523** (0.052%) | **4,366,599** | **6,625,264** | 8,585,622 | **No** |

Sanity: both filters have **0 false negatives** on the member set (200,000 / 200,000 true positives).

## Discussion

### 1. False Positive Rate (FPR)

At this memory budget (≈ 15.73 bits/item), the Bloom filter with optimal `k = 11` achieves a lower FPR than the cuckoo filter:
- Bloom FPR ≈ 0.057% (measured, 113/200,000) — matches the closed-form (1−e^(−kN/m))^k ≈ 0.052%.
- Cuckoo FPR ≈ 0.149% (measured, 297/200,000), close to the theoretical 2b/2^f = 8/4096 = 0.195% (the small gap comes from the table not being 100% full, α ≈ 0.76).

Why is cuckoo's FPR higher here? Cuckoo's FPR is **not** set by the memory budget but by `f` and `b`: with `f=12` and `b=4` it is fixed at ≈ 2b/2^f ≈ 0.2%. To drive cuckoo's FPR down, one must increase `f` (which costs more memory per item). The original Fan et al. paper notes that cuckoo filters beat Bloom filters on space only when targeting very low FPR (ϵ < 3%); at ϵ ≈ 0.05% here, both filters occupy similar memory but Bloom wins on FPR.

If we instead targeted FPR ≈ 0.001% with `f=16, b=4, M=65,536` (memory 4.19 Mbit), cuckoo would use ≈ 21 bits/item and Bloom with that budget would have k≈14 and FPR ≈ 2×10⁻⁵ — the two converge at this regime, with cuckoo edging ahead only at the very low end. The Fan et al. paper's Table 3 shows the same picture: at 192 MB / ~128 M items (≈12.6 bits/item), the semi-sorting cuckoo filter wins on FPR over standard Bloom.

### 2. Throughput (ops/sec)

The raw numbers favor Bloom by ≈ 60× (inserts) and ≈ 115× (queries). **However, this gap is largely an artifact of the implementation, not the data structure:**

- The Bloom filter's `insert_batch` / `lookup_batch` are fully vectorised: positions are computed in one `numpy` call and bits are flipped / read with `np.bitwise_or.at` / fancy indexing.
- The cuckoo filter's insert path contains an inherently sequential eviction chain (kick an entry, recompute its alternate, retry — up to `MaxNumKicks = 500` times). This cannot be vectorised, so it falls back to a Python `for` loop with two `numpy` slot reads per iteration.

In a fair C/C++ implementation with cache-resident tables, both structures are memory-bound and reach comparable throughputs (cf. Fan et al. §7.2 — the paper's optimized `ss-CF` and `BF` land within a factor of 2 on lookup throughput, with cuckoo slightly ahead on cache misses). The python+numpy numbers here demonstrate that **cuckoo's sequential eviction is hard to vectorise**, while **Bloom's k-independent bit-twiddling is a natural fit for SIMD / batch kernels** — a real-world advantage for Bloom on modern hardware.

### 3. Deletion Support

- **Cuckoo filter: supports deletion natively.** The 1000-item deletion probe removed all 1000 fingerprints (`1000/1000 = 100%`). Cuckoo's partial-key hashing lets us remove one fingerprint copy from one of the two candidate buckets in O(b) time, without affecting other items that happen to share a bucket (each entry stores only its fingerprint, not the original key). Duplicate insertion is bounded: the same fingerprint may be stored up to `2b = 8` times, so the same key can be inserted up to 8 times before insertion fails.
- **Bloom filter: does not support deletion in its standard form.** Removing a single element would require clearing k bits, but those bits may be shared by other members, leading to false negatives. Counting Bloom filters, d-left counting Bloom filters, and quotient filters exist for this, but each pays extra space (typically 3-4× for counting Bloom, 1.5-2× for d-left CBF). The standard Bloom filter is therefore a **build-once, query-many** structure.

This is the most important practical difference between the two: if the workload needs deletions (e.g. cache invalidation, key revocation, sliding-window deduplication), cuckoo is the natural choice at this budget. If deletions are not needed and only FPR + throughput matter, Bloom wins on both — except at very low FPR targets where the two structures trade places.

## Conclusion

Under the equal-memory setup above (N=200,000, B=3,145,728 bits):
- **FPR**: Bloom wins (0.057% vs 0.149%) because cuckoo's FPR is locked to 2b/2^f for a given `(f, b)`.
- **Throughput (Python+numpy benchmark)**: Bloom wins by ~60-115× thanks to vectorisable batch bit operations vs. cuckoo's sequential eviction chain. The gap would shrink dramatically in a C/C++ implementation.
- **Deletion**: only cuckoo supports deletion. This is the cuckoo filter's signature advantage over the standard Bloom filter.