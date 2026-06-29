"""
Cuckoo filter implementation with partial-key cuckoo hashing,
following Fan et al. (CoNEXT 2014).

Configuration:
- M buckets, each holding b fingerprints of f bits.
- For item x:
    i1   = hash_key(x) mod M
    f_x  = fingerprint(x)               # f bits, never zero
    i2   = i1 XOR hash_fp(f_x)          # alternate bucket
- Insert: place f_x into bucket[i1] or bucket[i2], kick existing
  fingerprints if necessary, up to MaxNumKicks.
- Lookup: return True if f_x is found in bucket[i1] or bucket[i2].
"""

import numpy as np
import hashlib
import struct
import random


class CuckooFilter:
    def __init__(self, M, b, f_bits, seed, max_kicks=500):
        # M must be a power of 2 (so i1 ^ hash_fp stays in range).
        assert M & (M - 1) == 0, "M must be a power of 2"
        self.M = M
        self.b = b
        self.f_bits = f_bits
        self.max_kicks = max_kicks
        self.seed = seed
        # Bucket storage: flat array of M*b fingerprints.
        # 0 represents "empty" (fingerprints are always > 0).
        self.buckets = np.zeros(M * b, dtype=np.uint32)
        # Independent RNG for kick decisions (separate from the hash seeds).
        self.rng = random.Random(seed ^ 0xC0FFEE)

    # ------------------------------------------------------------------ #
    # Hashing helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _sha256_u64(data):
        d = hashlib.sha256(data).digest()
        return int.from_bytes(d[:8], "little")

    def fingerprint(self, key):
        """f-bit fingerprint derived from key; never zero."""
        h = self._sha256_u64(struct.pack("<qQI", int(key) & 0xFFFFFFFFFFFFFFFF,
                                         self.f_bits, self.seed))
        fp = h & ((1 << self.f_bits) - 1)
        return fp if fp != 0 else 1

    def _hash_key(self, key):
        """Primary bucket index for a key."""
        h = self._sha256_u64(struct.pack("<qQ", int(key) & 0xFFFFFFFFFFFFFFFF,
                                         self.seed))
        return h & (self.M - 1)

    def _hash_fp(self, fp):
        """Hash a fingerprint to a value in [0, M-1] (used as the XOR mask)."""
        h = self._sha256_u64(struct.pack("<II", int(fp) & 0xFFFFFFFF, self.seed))
        return h & (self.M - 1)

    # ------------------------------------------------------------------ #
    # Lookup
    # ------------------------------------------------------------------ #
    def lookup(self, key):
        fp = self.fingerprint(key)
        i1 = self._hash_key(key)
        i2 = i1 ^ self._hash_fp(fp)
        b1 = i1 * self.b
        b2 = i2 * self.b
        # Compare against each entry in both candidate buckets.
        for j in range(self.b):
            if self.buckets[b1 + j] == fp:
                return True
        for j in range(self.b):
            if self.buckets[b2 + j] == fp:
                return True
        return False

    # ------------------------------------------------------------------ #
    # Insert
    # ------------------------------------------------------------------ #
    def insert(self, key):
        fp = self.fingerprint(key)
        i1 = self._hash_key(key)
        i2 = i1 ^ self._hash_fp(fp)
        b1 = i1 * self.b
        b2 = i2 * self.b
        # Try empty slot in i1
        for j in range(self.b):
            if self.buckets[b1 + j] == 0:
                self.buckets[b1 + j] = fp
                return True
        # Try empty slot in i2
        for j in range(self.b):
            if self.buckets[b2 + j] == 0:
                self.buckets[b2 + j] = fp
                return True
        # Otherwise kick.
        i = i1 if self.rng.random() < 0.5 else i2
        for _ in range(self.max_kicks):
            bi = i * self.b
            j = self.rng.randrange(self.b)
            old_fp = self.buckets[bi + j]
            self.buckets[bi + j] = fp
            fp = old_fp
            i = i ^ self._hash_fp(fp)
            ba = i * self.b
            for k in range(self.b):
                if self.buckets[ba + k] == 0:
                    self.buckets[ba + k] = fp
                    return True
        return False  # filter is "full"

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #
    @property
    def num_items(self):
        return int(np.count_nonzero(self.buckets))

    @property
    def load_factor(self):
        return self.num_items / (self.M * self.b)