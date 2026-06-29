"""
Cuckoo filter vs Bloom filter deletion experiment.

Implements:
  * A standard (non-counting) Bloom filter
  * A cuckoo filter with bucket size b=4 and fingerprint size f=12

The experiment:
  1. Insert N = 1e5 random 128-bit keys into a cuckoo filter.
  2. Pick a random half and delete them.
  3. Query the retained half (must all hit; report false-negative rate).
  4. Query the deleted half (must be gone; report residual false-positive rate).
  5. Query a fresh set of N non-members (false-positive rate).
  6. With a standard Bloom filter, demonstrate that naive bit-clearing "delete"
     also clears bits shared with other keys, producing false negatives.
"""

import hashlib
import random
import struct
import json
from math import log, log2, exp

# -------- Fixed experiment parameters --------
SEED = 42                 # random seed (single, fixed source of variation)
N      = 100_000          # number of inserted keys
B      = 4                # cuckoo bucket size
F      = 12               # cuckoo fingerprint size, in bits
KEY_BYTES = 16            # 128-bit random keys (simulates UUIDs / 64-bit hashes)
MAX_KICKS = 500           # cuckoo insertion kick budget
HALF = N // 2

# Cuckoo table sizing. With b=4, f=12 the paper (Fig. 2a) reports ~95% load factor
# is achievable for large enough tables. Partial-key cuckoo hashing requires
# m to be a power of 2 for the XOR-based alternate index to round-trip
# correctly, so we use m = 2^15 = 32768 (load factor ~0.763).
NUM_BUCKETS_CF = 32_768   # = 2^15; target load factor = N/(b*m) ~= 0.763

# Bloom filter parameters. Chosen for a target FPR close to the cuckoo filter's
# FPR (which for f=12, b=4 is roughly 1-(1-1/2^f)^(2b) = ~0.00195).
# With m = 1,200,000 bits, k = 8: theoretical FPR ~ (1-exp(-kN/m))^k ~ 0.0029
M_BLOOM = 1_200_000
K_BLOOM = 8


# =============================================================================
#                            CUCKOO FILTER
# =============================================================================
class CuckooFilter:
    """A simple cuckoo filter with b entries per bucket, f-bit fingerprints.

    Uses partial-key cuckoo hashing:
        i1 = h(x) mod m
        i2 = i1 xor hash(fingerprint)
    """

    EMPTY = 0  # empty slot marker

    def __init__(self, num_buckets, b=B, f=F, max_kicks=MAX_KICKS):
        self.m = num_buckets
        self.b = b
        self.f = f
        self.max_kicks = max_kicks
        # Flatten buckets for cache friendliness
        self.table = [0] * (num_buckets * b)

    # ---- low-level hashing helpers ----
    @staticmethod
    def _u64(data):
        return int.from_bytes(hashlib.sha256(data).digest()[:8], "big")

    def _fingerprint_of(self, key):
        """Compute the f-bit fingerprint of a key. Must be non-zero."""
        fp = self._u64(b"fp|" + key) & ((1 << self.f) - 1)
        if fp == 0:
            fp = 1
        return fp

    def _alt_index(self, i, fp):
        return (i ^ (self._u64(b"alt|" + struct.pack(">I", fp)) % self.m)) % self.m

    def _indices(self, key, fp):
        i1 = self._u64(b"i1|" + key) % self.m
        return i1, self._alt_index(i1, fp)

    # ---- bucket-level helpers (operate directly on self.table) ----
    def _bucket_start(self, idx):
        return idx * self.b

    def _bucket_contains(self, idx, fp):
        s = self._bucket_start(idx)
        for j in range(self.b):
            if self.table[s + j] == fp:
                return True
        return False

    def _bucket_insert(self, idx, fp):
        s = self._bucket_start(idx)
        for j in range(self.b):
            if self.table[s + j] == self.EMPTY:
                self.table[s + j] = fp
                return True
        return False

    def _bucket_delete(self, idx, fp):
        s = self._bucket_start(idx)
        for j in range(self.b):
            if self.table[s + j] == fp:
                self.table[s + j] = self.EMPTY
                return True
        return False

    # ---- public API ----
    def insert(self, key):
        fp = self._fingerprint_of(key)
        i1, i2 = self._indices(key, fp)
        if self._bucket_insert(i1, fp) or self._bucket_insert(i2, fp):
            return True
        # must kick
        i = random.choice((i1, i2))
        for _ in range(self.max_kicks):
            j = random.randrange(self.b)
            evicted_fp = self.table[i * self.b + j]
            self.table[i * self.b + j] = fp
            fp = evicted_fp
            i = self._alt_index(i, fp)
            if self._bucket_insert(i, fp):
                return True
        return False

    def lookup(self, key):
        fp = self._fingerprint_of(key)
        i1, i2 = self._indices(key, fp)
        return self._bucket_contains(i1, fp) or self._bucket_contains(i2, fp)

    def delete(self, key):
        fp = self._fingerprint_of(key)
        i1, i2 = self._indices(key, fp)
        return self._bucket_delete(i1, fp) or self._bucket_delete(i2, fp)

    def occupancy(self):
        return sum(1 for v in self.table if v != self.EMPTY)


# =============================================================================
#                            BLOOM FILTER
# =============================================================================
class BloomFilter:
    """Standard (non-counting) Bloom filter."""

    def __init__(self, m, k):
        self.m = m
        self.k = k
        self.bits = bytearray((m + 7) // 8)  # bit-packed array

    @staticmethod
    def _two_hashes(key):
        h = hashlib.sha256(key).digest()
        h1 = int.from_bytes(h[:8], "big")
        h2 = int.from_bytes(h[8:16], "big")
        return h1, h2

    def _positions(self, key):
        h1, h2 = self._two_hashes(key)
        return [(h1 + i * h2) % self.m for i in range(self.k)]

    @staticmethod
    def _get(bit_arr, pos):
        return (bit_arr[pos >> 3] >> (pos & 7)) & 1

    @staticmethod
    def _set(bit_arr, pos, val):
        if val:
            bit_arr[pos >> 3] |= 1 << (pos & 7)
        else:
            bit_arr[pos >> 3] &= ~(1 << (pos & 7))

    def add(self, key):
        for p in self._positions(key):
            self._set(self.bits, p, 1)

    def contains(self, key):
        for p in self._positions(key):
            if not self._get(self.bits, p):
                return False
        return True

    def clear_bit(self, key):
        """Naive 'delete' for a standard Bloom filter: clear the bits the key
        was inserted with. This is the broken operation the cuckoo filter
        avoids by storing fingerprints (with per-fingerprint reference counts
        via multi-set tables)."""
        for p in self._positions(key):
            self._set(self.bits, p, 0)


# =============================================================================
#                            EXPERIMENT
# =============================================================================
def make_keys(n, seed=SEED):
    """Deterministically generate n random 128-bit keys."""
    rng = random.Random(seed)
    return [rng.getrandbits(KEY_BYTES * 8).to_bytes(KEY_BYTES, "big") for _ in range(n)]


def main():
    rng = random.Random(SEED)

    # ---- 1. Build the cuckoo filter ----
    print("=" * 60)
    print(f"Cuckoo filter: b={B}, f={F}, m={NUM_BUCKETS_CF}, N={N}")
    print(f"  target load factor = {N / (B * NUM_BUCKETS_CF):.3f}")
    cf = CuckooFilter(NUM_BUCKETS_CF)
    keys = make_keys(N, SEED)

    insert_failures = 0
    for k in keys:
        if not cf.insert(k):
            insert_failures += 1
    occ = cf.occupancy()
    capacity = NUM_BUCKETS_CF * B
    actual_load = occ / capacity
    print(f"  inserted: {N - insert_failures} / {N} (failures={insert_failures})")
    print(f"  actual load factor = {actual_load:.4f}  ({occ}/{capacity} slots)")

    # ---- 2. Randomly delete half ----
    keys_copy = list(keys)
    rng.shuffle(keys_copy)
    keys_retained = keys_copy[:HALF]
    keys_deleted = keys_copy[HALF:]

    delete_hits = sum(cf.delete(k) for k in keys_deleted)
    print(f"  delete(): {delete_hits}/{len(keys_deleted)} reported a removal")
    post_occ = cf.occupancy()
    print(f"  occupancy after delete = {post_occ}/{capacity} "
          f"(load {post_occ / capacity:.4f})")

    # ---- 3. Query retained half (should all hit) ----
    retained_hits = sum(1 for k in keys_retained if cf.lookup(k))
    fn_retained = (HALF - retained_hits) / HALF
    print(f"  retained half lookup: {retained_hits}/{HALF} hits, "
          f"false-negative rate = {fn_retained:.6f}")

    # ---- 4. Query deleted half (should be gone) ----
    deleted_hits = sum(1 for k in keys_deleted if cf.lookup(k))
    fp_deleted = deleted_hits / HALF
    print(f"  deleted half lookup : {deleted_hits}/{HALF} hits, "
          f"residual 'false positive' on deleted set = {fp_deleted:.6f}")

    # ---- 5. Query fresh non-members ----
    keys_new = make_keys(N, SEED + 1)  # disjoint random set
    new_hits = sum(1 for k in keys_new if cf.lookup(k))
    fpr_new = new_hits / N
    print(f"  fresh non-member    : {new_hits}/{N} hits, "
          f"false-positive rate = {fpr_new:.6f}")

    # Theoretical FPR for cuckoo filter: 1 - (1 - 1/2^f)^(2b) ~ 2b/2^f
    theory_cf_fpr = 1 - (1 - 1 / (1 << F)) ** (2 * B)
    print(f"  theoretical cuckoo FPR = {theory_cf_fpr:.6f}")

    cf_results = dict(
        b=B, f=F, num_buckets=NUM_BUCKETS_CF,
        target_load=N / (B * NUM_BUCKETS_CF),
        actual_load=actual_load,
        insert_failures=insert_failures,
        retained_hits=retained_hits,
        retained_total=HALF,
        false_negative_rate=fn_retained,
        deleted_residual_hits=deleted_hits,
        deleted_residual_rate=fp_deleted,
        fresh_fpr=fpr_new,
        theoretical_cuckoo_fpr=theory_cf_fpr,
    )

    # =====================================================================
    #                    BLOOM FILTER NAIVE DELETE DEMO
    # =====================================================================
    print()
    print("=" * 60)
    print(f"Bloom filter: m={M_BLOOM}, k={K_BLOOM}, N={N}")
    bf = BloomFilter(M_BLOOM, K_BLOOM)
    for k in keys:
        bf.add(k)

    # Sanity: all N keys present
    sanity_present = sum(1 for k in keys if bf.contains(k))
    print(f"  Bloom contains(x) on inserted set: {sanity_present}/{N}")

    # Fresh non-members
    fresh_present = sum(1 for k in keys_new if bf.contains(k))
    bloom_fpr = fresh_present / N
    theory_bloom_fpr = (1 - exp(-K_BLOOM * N / M_BLOOM)) ** K_BLOOM
    print(f"  Bloom FPR on fresh set: {fresh_present}/{N} = {bloom_fpr:.6f} "
          f"(theory {theory_bloom_fpr:.6f})")

    # Now pick ONE inserted key x and do the broken "delete" on it.
    # Then re-query the entire set of other inserted keys and see how many
    # of them went from True -> False (false negatives).
    victim = keys[0]  # the key we will "delete"
    h1, h2 = BloomFilter._two_hashes(victim)
    victim_positions = [(h1 + i * h2) % M_BLOOM for i in range(K_BLOOM)]

    # Count how many OTHER keys share each bit position with the victim.
    # This explains the false-negative mechanism.
    shared_other_keys = set()
    for k in keys[1:]:
        positions = bf._positions(k)
        if set(positions) & set(victim_positions):
            shared_other_keys.add(k)
    n_shared_other = len(shared_other_keys)
    print(f"  victim = {victim.hex()[:24]}…")
    print(f"  victim touches {K_BLOOM} bit positions; "
          f"{n_shared_other} other inserted keys share at least one bit with it")

    # Naive bit-clearing "delete"
    bf.clear_bit(victim)

    # Measure cascade over the *entire* insert set: how many inserted keys
    # other than the victim now report "absent" (false negatives)?
    fn_after_one_delete = sum(
        1 for k in keys[1:] if not bf.contains(k)
    )
    fn_rate_overall = fn_after_one_delete / (N - 1)
    print(f"  AFTER naive 'clear-bit' delete of victim:")
    print(f"    victim itself present?    {bf.contains(victim)}")
    print(f"    other inserted keys now False: {fn_after_one_delete} / {N-1}  "
          f"({100*fn_rate_overall:.2f}% false-negative rate on the full insert set)")

    # Also report on the shared set specifically
    now_false = sum(1 for k in shared_other_keys if not bf.contains(k))
    fn_rate_shared = now_false / max(1, len(shared_other_keys))
    print(f"    of the {len(shared_other_keys)} bit-sharing keys: {now_false} "
          f"now False ({100*fn_rate_shared:.2f}%)")

    # Cascade: keep deleting more keys, watch the false-negative count grow
    print()
    print("  Cascade: delete more random inserted keys, watch FN grow")
    bf_cascade = BloomFilter(M_BLOOM, K_BLOOM)
    for k in keys:
        bf_cascade.add(k)
    rng_b = random.Random(SEED + 99)
    victims = list(keys)
    rng_b.shuffle(victims)
    for c, victim in enumerate(victims[1:50:5], start=1):
        bf_cascade.clear_bit(victim)
        fns = sum(1 for k in keys if not bf_cascade.contains(k))
        # Note: fns also counts already-deleted victims as FN (intentional)
        print(f"    after deleting {c*5:3d} random keys: "
              f"{fns:5d} inserted keys now report False  "
              f"({100*fns/N:.2f}%)")

    bloom_results = dict(
        m=M_BLOOM, k=K_BLOOM,
        bloom_fpr_fresh=bloom_fpr,
        theoretical_bloom_fpr=theory_bloom_fpr,
        n_other_keys_sharing_bits_with_victim=n_shared_other,
        false_negatives_after_naive_delete=now_false,
        false_negative_rate_on_shared=fn_rate_shared,
        example_victim=victim.hex(),
        example_victim_bit_positions=victim_positions,
    )

    # Persist results
    with open("results.json", "w") as f:
        json.dump({"cuckoo": cf_results, "bloom": bloom_results,
                   "params": dict(N=N, B=B, F=F, seed=SEED,
                                  m_bloom=M_BLOOM, k_bloom=K_BLOOM)},
                  f, indent=2)
    print("\nResults written to results.json")

    return cf_results, bloom_results


if __name__ == "__main__":
    main()
