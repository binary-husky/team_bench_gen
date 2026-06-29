#!/usr/bin/env python3
"""Compare cuckoo filter and Bloom filter under equal memory budget.

Configuration:
- N = 2 * 10^5 keys
- Memory budget B = 3,145,728 bits (384 KiB)
- Cuckoo filter: f=12, b=4, M=65,536 buckets  -> memory = 65,536 * 4 * 12 = 3,145,728 bits
  (M is a power of 2 so that partial-key cuckoo hashing's XOR alternate is reversible)
- Bloom filter: m = B = 3,145,728 bits, k = round((m/N) * ln2) = 11
"""

import json
import time
import numpy as np


# ====== Configuration ======
SEED = 42
N = 200_000
B_BUDGET_BITS = 3_145_728  # bits

# Cuckoo filter parameters (f, b=4, M chosen so memory ≈ B bits; M must be power of 2)
F_BITS = 12
B = 4
M_BUCKETS = 65_536  # memory = 65,536 * 4 * 12 = 3,145,728 bits

# Bloom filter parameters (m = B bits, k = optimal)
M_BITS = B_BUDGET_BITS
K_HASHES = round((M_BITS / N) * np.log(2))  # ~10.9 -> 11


def splitmix64(x):
    """A fast 64-bit hash function (Vigna 2014). Uses 64-bit overflow intentionally."""
    x = np.uint64(x) + np.uint64(0x9e3779b97f4a7c15)
    z = x
    z = (z ^ (z >> np.uint64(30))) * np.uint64(0xbf58476d1ce4e5b9)
    z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94d049bb133111eb)
    z = z ^ (z >> np.uint64(31))
    return z


# ====== Cuckoo Filter ======
class CuckooFilter:
    """Partial-key cuckoo filter with bucket size b=4.

    Note: requires M to be a power of 2 so that the XOR-based alternate-bucket
    computation is reversible modulo M. (a XOR b) XOR b = a only when the
    intermediate results stay in [0, M).
    """

    def __init__(self, M, b, f_bits, max_kicks=500):
        assert M & (M - 1) == 0, "M must be a power of 2"
        self.M = M
        self.b = b
        self.f_bits = f_bits
        self.max_kicks = max_kicks
        self.f_mask = (1 << f_bits) - 1
        # Each slot holds a fingerprint in [1, 2^f - 1]; 0 means empty.
        self.table = np.zeros((M, b), dtype=np.uint16)
        self.n_inserts = 0
        self.n_failures = 0

    def _fp(self, x):
        # 12-bit fingerprint (must be non-zero; 0 is reserved for "empty")
        fp = int(splitmix64(np.uint64(x) ^ np.uint64(0x123456789abcdef0))) & self.f_mask
        return fp if fp != 0 else 1

    def _hash1(self, x):
        # i1 = hash(x) mod M
        return int(splitmix64(np.uint64(x)) & np.uint64(self.M - 1))

    def _hash_fp(self, fp):
        # hash(fp), restricted to [0, M)
        return int(splitmix64(np.uint64(fp) ^ np.uint64(0xfedcba9876543210))
                   & np.uint64(self.M - 1))

    def insert(self, x):
        fp = self._fp(x)
        i1 = self._hash1(x)
        i2 = i1 ^ self._hash_fp(fp)  # i2 in [0, M) since M is power of 2

        # Try i1
        for j in range(self.b):
            if self.table[i1, j] == 0:
                self.table[i1, j] = fp
                self.n_inserts += 1
                return True
        # Try i2
        for j in range(self.b):
            if self.table[i2, j] == 0:
                self.table[i2, j] = fp
                self.n_inserts += 1
                return True

        # Must evict. Use a deterministic xorshift64* seeded by the key.
        state = (np.uint64(x) ^ np.uint64(0x9e3779b97f4a7c15)).astype(np.uint64)
        state = (state ^ (state >> np.uint64(30))) * np.uint64(0xbf58476d1ce4e5b9)
        state = (state ^ (state >> np.uint64(27))) * np.uint64(0x94d049bb133111eb)
        state = state ^ (state >> np.uint64(31))
        i = i1 if (int(state) & 1) else i2

        for _ in range(self.max_kicks):
            # xorshift64* step
            state ^= state << np.uint64(13)
            state ^= state >> np.uint64(7)
            state ^= state << np.uint64(17)
            j = int(state) & (self.b - 1)
            old_fp = int(self.table[i, j])
            self.table[i, j] = fp
            fp = old_fp
            i1 = i
            i2 = i1 ^ self._hash_fp(fp)  # alternate of new carried fp
            i = i1 if (int(state) & 1) else i2
            for jj in range(self.b):
                if self.table[i, jj] == 0:
                    self.table[i, jj] = fp
                    self.n_inserts += 1
                    return True

        self.n_failures += 1
        return False

    def lookup(self, x):
        fp = self._fp(x)
        i1 = self._hash1(x)
        i2 = i1 ^ self._hash_fp(fp)
        bucket1 = self.table[i1]
        for j in range(self.b):
            if bucket1[j] == fp:
                return True
        bucket2 = self.table[i2]
        for j in range(self.b):
            if bucket2[j] == fp:
                return True
        return False

    def delete(self, x):
        fp = self._fp(x)
        i1 = self._hash1(x)
        i2 = i1 ^ self._hash_fp(fp)
        for j in range(self.b):
            if self.table[i1, j] == fp:
                self.table[i1, j] = 0
                return True
        for j in range(self.b):
            if self.table[i2, j] == fp:
                self.table[i2, j] = 0
                return True
        return False


# ====== Bloom Filter ======
class BloomFilter:
    """Standard Bloom filter using bit-packed uint64 storage and double hashing."""

    def __init__(self, m_bits, k):
        self.m = m_bits
        self.k = k
        self.n_uint64 = (m_bits + 63) // 64
        self.bits = np.zeros(self.n_uint64, dtype=np.uint64)

    def _hash_positions_batch(self, keys):
        """Compute k hash positions per key using double hashing (vectorized)."""
        # Use mod m for h1, and mod (m-1)+1 for h2 so that all i*h2 give distinct positions
        h1 = splitmix64(keys) % np.uint64(self.m)
        h2 = (splitmix64(keys ^ np.uint64(0x5555555555555555))
              % np.uint64(self.m - 1)) + np.uint64(1)
        positions = np.empty((len(keys), self.k), dtype=np.uint64)
        for i in range(self.k):
            positions[:, i] = (h1 + np.uint64(i) * h2) % np.uint64(self.m)
        return positions

    def insert_batch(self, keys):
        positions = self._hash_positions_batch(keys)
        for i in range(self.k):
            pos = positions[:, i]
            word_idx = (pos // 64).astype(np.int64)
            bit_idx = (pos % 64).astype(np.uint64)
            masks = np.uint64(1) << bit_idx
            np.bitwise_or.at(self.bits, word_idx, masks)

    def lookup_batch(self, keys):
        positions = self._hash_positions_batch(keys)
        results = np.ones(len(keys), dtype=bool)
        for i in range(self.k):
            pos = positions[:, i]
            word_idx = (pos // 64).astype(np.int64)
            bit_idx = (pos % 64).astype(np.uint64)
            bits_at_pos = (self.bits[word_idx] >> bit_idx) & np.uint64(1)
            results &= (bits_at_pos != np.uint64(0))
        return results


# ====== Print configuration ======
print("=" * 60)
print("Cuckoo Filter vs Bloom Filter Comparison")
print("=" * 60)
print(f"Random seed: {SEED}")
print(f"N (key set size): {N}")
print(f"B (memory budget): {B_BUDGET_BITS} bits "
      f"= {B_BUDGET_BITS / 8 / 1024:.2f} KiB")
print()
print(f"Cuckoo filter: f={F_BITS}, b={B}, M={M_BUCKETS} (power of 2)")
print(f"  Memory = {M_BUCKETS * B * F_BITS} bits "
      f"= {M_BUCKETS * B * F_BITS / 8 / 1024:.2f} KiB")
print(f"  Total slots = {M_BUCKETS * B}, "
      f"load factor = {N / (M_BUCKETS * B):.4f}")
fpr_th_cuckoo = 2 * B / (2 ** F_BITS)
print(f"  Theoretical FPR ≈ 2b/2^f = {fpr_th_cuckoo:.6f}")
print()
print(f"Bloom filter: m={M_BITS} bits, k={K_HASHES}")
fpr_th_bf = (1 - np.exp(-K_HASHES / (M_BITS / N))) ** K_HASHES
print(f"  Theoretical FPR = {fpr_th_bf:.6f}")
print("=" * 60)


# ====== Generate keys ======
print("\nGenerating keys...")
rng = np.random.default_rng(SEED)
# Split the key space into two halves to guarantee no overlap
member_keys = rng.integers(0, 2**62, size=N, dtype=np.int64)
nonmember_keys = rng.integers(2**62, 2**63, size=N, dtype=np.int64)
assert not np.any(np.isin(nonmember_keys, member_keys)), "Overlap detected!"
print(f"  Generated {N} member keys and {N} non-member keys (no overlap)")

# Convert member/nonmember keys to plain int lists for the cuckoo filter
member_list = member_keys.tolist()
nonmember_list = nonmember_keys.tolist()


# ====== Run experiments ======
results = {}

# --- Cuckoo Filter ---
print("\n[1] Cuckoo Filter")
cf = CuckooFilter(M_BUCKETS, B, F_BITS)

# Time insertion
print("  Inserting members...")
t0 = time.perf_counter()
for x in member_list:
    cf.insert(x)
t_insert_cf = time.perf_counter() - t0
print(f"    Time: {t_insert_cf:.3f}s, throughput = {N/t_insert_cf:.0f} ops/s")
print(f"    Insertion failures: {cf.n_failures}/{N}")

# Time lookup on non-members (FPR measurement)
print("  Querying non-members (FPR)...")
t0 = time.perf_counter()
fp_count = 0
for x in nonmember_list:
    if cf.lookup(x):
        fp_count += 1
t_query_cf = time.perf_counter() - t0
fpr_cf = fp_count / N
print(f"    Time: {t_query_cf:.3f}s, throughput = {N/t_query_cf:.0f} ops/s")
print(f"    FPR = {fp_count}/{N} = {fpr_cf:.6f}")

# Time lookup on members (sanity check for false negatives)
print("  Querying members (sanity check, no false negatives expected)...")
t0 = time.perf_counter()
tp_count = 0
for x in member_list:
    if cf.lookup(x):
        tp_count += 1
t_query_cf_pos = time.perf_counter() - t0
fn_count = N - tp_count
print(f"    Time: {t_query_cf_pos:.3f}s, throughput = {N/t_query_cf_pos:.0f} ops/s")
print(f"    True positives = {tp_count}/{N}, false negatives = {fn_count}")

# Test deletion support
print("  Testing deletion support (deleting 1000 inserted items)...")
n_del_ok = 0
for x in member_list[:1000]:
    if cf.delete(x):
        n_del_ok += 1
print(f"    Deleted {n_del_ok}/1000 members successfully")

results['cuckoo'] = {
    'f': F_BITS,
    'b': B,
    'M': M_BUCKETS,
    'memory_bits': M_BUCKETS * B * F_BITS,
    'load_factor': N / (M_BUCKETS * B),
    'insert_failures': cf.n_failures,
    'fpr_measured': fpr_cf,
    'fpr_count': fp_count,
    'fpr_n': N,
    'insert_throughput_ops': N / t_insert_cf,
    'query_neg_throughput_ops': N / t_query_cf,
    'query_pos_throughput_ops': N / t_query_cf_pos,
    'insert_time_s': t_insert_cf,
    'query_neg_time_s': t_query_cf,
    'query_pos_time_s': t_query_cf_pos,
    'true_positive_count': tp_count,
    'false_negative_count': fn_count,
    'supports_deletion': True,
    'deletion_successful': n_del_ok,
    'fpr_theoretical': float(fpr_th_cuckoo),
}


# --- Bloom Filter ---
print("\n[2] Bloom Filter")
bf = BloomFilter(M_BITS, K_HASHES)

# Time insertion (batch)
print("  Inserting members (batched)...")
t0 = time.perf_counter()
bf.insert_batch(member_keys)
t_insert_bf = time.perf_counter() - t0
print(f"    Time: {t_insert_bf:.3f}s, throughput = {N/t_insert_bf:.0f} ops/s")

# Time lookup on non-members (FPR)
print("  Querying non-members (FPR, batched)...")
t0 = time.perf_counter()
results_neg = bf.lookup_batch(nonmember_keys)
t_query_bf = time.perf_counter() - t0
fp_count_bf = int(np.sum(results_neg))
fpr_bf = fp_count_bf / N
print(f"    Time: {t_query_bf:.3f}s, throughput = {N/t_query_bf:.0f} ops/s")
print(f"    FPR = {fp_count_bf}/{N} = {fpr_bf:.6f}")

# Time lookup on members (sanity check)
print("  Querying members (sanity check, batched)...")
t0 = time.perf_counter()
results_pos = bf.lookup_batch(member_keys)
t_query_bf_pos = time.perf_counter() - t0
tp_count_bf = int(np.sum(results_pos))
fn_count_bf = N - tp_count_bf
print(f"    Time: {t_query_bf_pos:.3f}s, throughput = {N/t_query_bf_pos:.0f} ops/s")
print(f"    True positives = {tp_count_bf}/{N}, false negatives = {fn_count_bf}")

results['bloom'] = {
    'm_bits': M_BITS,
    'k': K_HASHES,
    'memory_bits': M_BITS,
    'fpr_theoretical': float(fpr_th_bf),
    'fpr_measured': fpr_bf,
    'fpr_count': fp_count_bf,
    'fpr_n': N,
    'insert_throughput_ops': N / t_insert_bf,
    'query_neg_throughput_ops': N / t_query_bf,
    'query_pos_throughput_ops': N / t_query_bf_pos,
    'insert_time_s': t_insert_bf,
    'query_neg_time_s': t_query_bf,
    'query_pos_time_s': t_query_bf_pos,
    'true_positive_count': tp_count_bf,
    'false_negative_count': fn_count_bf,
    'supports_deletion': False,
}


# ====== Print summary table ======
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"{'Filter':<15} {'FPR':<12} {'Inserts/s':<15} "
      f"{'Queries/s':<15} {'Delete?':<8}")
print("-" * 60)
print(f"{'Cuckoo':<15} {results['cuckoo']['fpr_measured']:<12.6f} "
      f"{results['cuckoo']['insert_throughput_ops']:<15.0f} "
      f"{results['cuckoo']['query_neg_throughput_ops']:<15.0f} "
      f"{'Yes':<8}")
print(f"{'Bloom':<15} {results['bloom']['fpr_measured']:<12.6f} "
      f"{results['bloom']['insert_throughput_ops']:<15.0f} "
      f"{results['bloom']['query_neg_throughput_ops']:<15.0f} "
      f"{'No':<8}")

# Save results
with open('experiment_results.json', 'w') as fp:
    json.dump(results, fp, indent=2)
print("\nResults saved to experiment_results.json")