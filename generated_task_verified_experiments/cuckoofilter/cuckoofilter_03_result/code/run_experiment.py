#!/usr/bin/env python3
"""
Experiment: effect of bucket size b on max load factor and kick behavior
in a self-implemented cuckoo filter using partial-key cuckoo hashing
(Fan et al. 2014, Algorithm 1).

Fixed:  number of buckets M, MaxNumKicks (=500), random seed.
Variable: b in {2, 4, 8}.

For each b: keep inserting random keys until an insert fails because its
consecutive kick count exceeds MaxNumKicks (filter considered full).
Record:
  - max load factor = occupied slots / total slots  (at the failing insert)
  - average kicks per successful insertion
"""

import random
import sys
from array import array

# ---------- fixed settings ----------
SEED = 1234567
M = 1 << 14            # number of buckets = 16384 (power of two -> xor stays in range)
MASK = M - 1
MAX_KICKS = 500        # as in the paper's implementation
FP_BITS = 16           # fingerprint length (bits); nonzero values only
FP_MAX = 1 << FP_BITS  # 65536; valid fps in [1, 65535], 0 == empty

# ---------- hashing (deterministic, well-mixed) ----------
MASK64 = 0xffffffffffffffff
def mix64(x):
    """splitmix64-style finalizer on a 64-bit integer."""
    x &= MASK64
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9 & MASK64
    x = (x ^ (x >> 27)) * 0x94d049bb133111eb & MASK64
    x = x ^ (x >> 31)
    return x

# A second independent mixer for fingerprint hashing (used in partial-key xor).
def mix64_fp(x):
    x &= MASK64
    x = (x ^ (x >> 28)) * 0x9e3779b97f4a7c15 & MASK64
    x = (x ^ (x >> 29)) * 0xc2b2ae3d27d4eb4f & MASK64
    x = x ^ (x >> 32)
    return x

def item_index_and_fp(x):
    """Return (i1, fingerprint) for item x."""
    h = mix64(x)
    i1 = h & MASK
    fp = (h >> 32) & (FP_MAX - 1)
    if fp == 0:
        fp = 1                 # 0 reserved as empty marker
    return i1, fp

def fp_alt_offset(fp):
    """mask-sized xor offset to reach the alternate bucket."""
    return mix64_fp(fp) & MASK


class CuckooFilter:
    __slots__ = ("b", "table", "count")

    def __init__(self, b):
        self.b = b
        # flat array of M*b 16-bit slots, 0 == empty
        self.table = array('H', bytes(2 * M * b))
        self.count = 0          # number of occupied slots

    def _bucket_has_space(self, i):
        b = self.b
        base = i * b
        t = self.table
        for k in range(b):
            if t[base + k] == 0:
                return base + k
        return -1

    def insert(self, x, rng):
        """Return (ok, kicks) where kicks = #displacements performed."""
        b = self.b
        t = self.table
        i1, fp = item_index_and_fp(x)
        off = fp_alt_offset(fp)
        i2 = i1 ^ off

        slot = self._bucket_has_space(i1)
        if slot < 0:
            slot = self._bucket_has_space(i2)
        if slot >= 0:
            t[slot] = fp
            self.count += 1
            return True, 0

        # must relocate
        i = i1 if rng.random() < 0.5 else i2
        kicks = 0
        for _ in range(MAX_KICKS):
            base = i * b
            e = rng.randrange(b)
            # swap f with the fingerprint in entry e
            fp, t[base + e] = t[base + e], fp
            i = i ^ fp_alt_offset(fp)      # fp is now the kicked-out fingerprint
            kicks += 1
            slot = self._bucket_has_space(i)
            if slot >= 0:
                t[slot] = fp
                self.count += 1
                return True, kicks
        # table considered full
        return False, kicks


def run_for_b(b, seed=SEED):
    rng = random.Random(seed)
    cf = CuckooFilter(b)
    total_slots = M * b
    total_kicks_success = 0
    n_success = 0
    # generate random keys: 64-bit integers
    while True:
        x = rng.getrandbits(64)
        ok, kicks = cf.insert(x, rng)
        if not ok:
            # filter full at this insert
            break
        n_success += 1
        total_kicks_success += kicks

    load_factor = cf.count / total_slots
    avg_kicks = (total_kicks_success / n_success) if n_success else 0.0
    return {
        "b": b,
        "M": M,
        "total_slots": total_slots,
        "n_success": n_success,
        "occupied": cf.count,
        "load_factor": load_factor,
        "avg_kicks": avg_kicks,
    }


def main():
    results = []
    for b in (2, 4, 8):
        print(f"running b={b} ...", flush=True)
        r = run_for_b(b)
        results.append(r)
        print(
            f"  b={b}: load_factor={r['load_factor']:.4f} "
            f"avg_kicks={r['avg_kicks']:.4f} "
            f"n_success={r['n_success']} occupied={r['occupied']} "
            f"total_slots={r['total_slots']}",
            flush=True,
        )

    # stash for the summary writer
    with open("_results.txt", "w") as f:
        for r in results:
            f.write(repr(r) + "\n")
    print("done", flush=True)


if __name__ == "__main__":
    main()
