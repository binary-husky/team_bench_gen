"""
Experiment: effect of bucket size b on maximum load factor and average kicks
in a partial-key cuckoo filter (Fan et al., 2014).

We fix the number of buckets M, the kick limit MaxNumKicks, and the random
seed. We vary b in {2, 4, 8}, and keep inserting random keys until one
insertion requires more than MaxNumKicks consecutive kicks (filter full).
"""

import hashlib
import json
import random
import struct
import time


class CuckooFilter:
    """Partial-key cuckoo filter (Algorithm 1 from Fan et al., 2014).

    Each item maps to two candidate buckets via:
        i1 = hash(x) mod M
        i2 = i1 XOR hash(fingerprint(x)) mod M
    """

    def __init__(self, M, b, fingerprint_bits=16, max_kicks=500):
        self.M = M
        self.b = b
        self.fingerprint_bits = fingerprint_bits
        self.max_kicks = max_kicks
        self.fp_mask = (1 << fingerprint_bits) - 1
        # Each bucket is a list of `b` slots; 0 means empty.
        self.buckets = [[0] * b for _ in range(M)]

    @staticmethod
    def _hash64(x, salt):
        """64-bit hash of (x, salt) using SHA-256."""
        data = struct.pack("<QQ", x & 0xFFFFFFFFFFFFFFFF, salt)
        h = hashlib.sha256(data).digest()
        return int.from_bytes(h[:8], "little")

    def _fingerprint(self, x):
        h = self._hash64(x, salt=0xA1)
        fp = h & self.fp_mask
        # Avoid 0 so 0 unambiguously means "empty slot".
        if fp == 0:
            fp = 1
        return fp

    def _i1(self, x):
        return self._hash64(x, salt=0xB2) % self.M

    def _offset_for_fp(self, fp):
        return self._hash64(fp, salt=0xC3) % self.M

    def _i2_from(self, i, fp):
        return (i ^ self._offset_for_fp(fp)) % self.M

    def insert(self, x, rng):
        """Insert x. Returns (success, kicks_used).

        kicks_used = 0 if x fits directly; otherwise the number of
        relocations performed before x was placed.
        """
        fp = self._fingerprint(x)
        i1 = self._i1(x)
        i2 = self._i2_from(i1, fp)

        # Try empty slots in either candidate bucket.
        for bi in (i1, i2):
            bucket = self.buckets[bi]
            for j in range(self.b):
                if bucket[j] == 0:
                    bucket[j] = fp
                    return True, 0

        # Relocation loop.
        i = i1 if rng.random() < 0.5 else i2
        for n in range(self.max_kicks):
            j = rng.randrange(self.b)
            old_fp = self.buckets[i][j]
            self.buckets[i][j] = fp
            fp = old_fp
            i = self._i2_from(i, fp)
            bucket = self.buckets[i]
            for k in range(self.b):
                if bucket[k] == 0:
                    bucket[k] = fp
                    return True, n + 1

        return False, self.max_kicks


def run_experiment(M, b, max_kicks=500, seed=42, fingerprint_bits=16):
    cf = CuckooFilter(M, b, fingerprint_bits, max_kicks)
    # A single RNG drives both key generation and the random choices inside
    # insert(). Reset per experiment so that the sequence is reproducible
    # for a given (seed, b).
    rng = random.Random(seed * 1_000_003 + b)

    num_success = 0
    total_kicks = 0
    t0 = time.time()

    while True:
        key = rng.getrandbits(64)
        success, kicks = cf.insert(key, rng)
        if success:
            num_success += 1
            total_kicks += kicks
        else:
            break

    elapsed = time.time() - t0
    load_factor = num_success / (M * b)
    avg_kicks = total_kicks / num_success if num_success > 0 else 0.0

    return {
        "M": M,
        "b": b,
        "fingerprint_bits": fingerprint_bits,
        "max_kicks": max_kicks,
        "seed": seed,
        "num_success": num_success,
        "total_slots": M * b,
        "load_factor": load_factor,
        "total_kicks": total_kicks,
        "avg_kicks": avg_kicks,
        "elapsed_s": elapsed,
    }


if __name__ == "__main__":
    # Fixed settings — only b varies.
    M = 1 << 14          # 16 384 buckets
    MAX_KICKS = 500
    SEED = 42
    FINGERPRINT_BITS = 16

    print(
        f"Fixed settings: M={M}, max_kicks={MAX_KICKS}, "
        f"seed={SEED}, fingerprint_bits={FINGERPRINT_BITS}"
    )
    print("-" * 72)

    results = []
    for b in (2, 4, 8):
        r = run_experiment(
            M=M,
            b=b,
            max_kicks=MAX_KICKS,
            seed=SEED,
            fingerprint_bits=FINGERPRINT_BITS,
        )
        results.append(r)
        print(
            f"b={b:>1}  num_success={r['num_success']:>7}  "
            f"total_slots={r['total_slots']:>6}  "
            f"load_factor={r['load_factor']:.4f}  "
            f"avg_kicks={r['avg_kicks']:.4f}  "
            f"({r['elapsed_s']:.2f}s)"
        )

    with open("experiment_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Wrote experiment_results.json")