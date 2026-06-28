#!/usr/bin/env python3
"""
Experiment: deletion correctness of a self-implemented Cuckoo Filter (b=4, f=12)
vs. a standard (non-counting) Bloom filter.

Task (cuckoofilter_04/task.md):
  - Cuckoo filter b=4, f=12, insert N=1e5 keys.
  - Randomly delete half of them.
  - Query retained half  -> should all hit (measure false-negative rate).
  - Query deleted half    -> should be absent, only FPR applies.
  - Query a fresh set of non-members.
  - Standard Bloom filter: demonstrate that "bit-clearing" deletion of one key
    wipes shared bits and creates false negatives for other keys.

Fixed settings: b=4, f=12, N, Bloom m/k, random seed.
Independent variable: whether deletion happened / which query set.
"""

import os
import random
import sys
import mmh3

SEED = 1234
random.seed(SEED)

# ----------------------------------------------------------------------
# Cuckoo filter (b=4 slots/bucket, f=12-bit fingerprint)
# ----------------------------------------------------------------------
B = 4          # slots per bucket
F = 12         # fingerprint bits
F_MASK = (1 << F) - 1
MAX_KICKS = 500


def fp_hash(x_bytes):
    """12-bit fingerprint of key."""
    return mmh3.hash(x_bytes, 1, signed=False) & F_MASK


def index_hash(x_bytes, power):
    """Primary bucket index (mod table size, table size = 2^power)."""
    return mmh3.hash(x_bytes, 2, signed=False) & ((1 << power) - 1)


def alt_index(index, fp, power):
    """Partial-key cuckoo hashing: alternate bucket = index XOR hash(fp)."""
    fp_h = mmh3.hash(str(fp).encode(), 3, signed=False) & ((1 << power) - 1)
    return index ^ fp_h


class CuckooFilter:
    def __init__(self, power):
        self.power = power
        self.size = 1 << power
        self.mask = self.size - 1
        # each bucket: list of F-bit fingerprints (0 means empty slot)
        self.buckets = [[0] * B for _ in range(self.size)]
        self.count = 0

    def _indices(self, x_bytes, fp):
        i1 = index_hash(x_bytes, self.power)
        i2 = alt_index(i1, fp, self.power)
        return i1, i2

    def insert(self, x_bytes):
        fp = fp_hash(x_bytes)
        i1, i2 = self._indices(x_bytes, fp)
        # try i1
        for j in range(B):
            if self.buckets[i1][j] == 0:
                self.buckets[i1][j] = fp
                self.count += 1
                return True
        # try i2
        for j in range(B):
            if self.buckets[i2][j] == 0:
                self.buckets[i2][j] = fp
                self.count += 1
                return True
        # cuckoo: kick
        import random as _r
        rng = _r.Random(SEED)
        idx = i1 if rng.random() < 0.5 else i2
        for _ in range(MAX_KICKS):
            slot = rng.randrange(B)
            evicted = self.buckets[idx][slot]
            self.buckets[idx][slot] = fp
            fp = evicted
            idx = alt_index(idx, fp, self.power)
            for j in range(B):
                if self.buckets[idx][j] == 0:
                    self.buckets[idx][j] = fp
                    self.count += 1
                    return True
        return False  # table full / loop

    def contains(self, x_bytes):
        fp = fp_hash(x_bytes)
        i1, i2 = self._indices(x_bytes, fp)
        if fp in self.buckets[i1]:
            return True
        if fp in self.buckets[i2]:
            return True
        return False

    def delete(self, x_bytes):
        fp = fp_hash(x_bytes)
        i1, i2 = self._indices(x_bytes, fp)
        for j in range(B):
            if self.buckets[i1][j] == fp:
                self.buckets[i1][j] = 0
                self.count -= 1
                return True
        for j in range(B):
            if self.buckets[i2][j] == fp:
                self.buckets[i2][j] = 0
                self.count -= 1
                return True
        return False


# ----------------------------------------------------------------------
# Standard (non-counting) Bloom filter
# ----------------------------------------------------------------------
class BloomFilter:
    def __init__(self, m, k, seed=SEED):
        self.m = m
        self.k = k
        self.bits = bytearray((m + 7) // 8)
        self.seed = seed

    def _positions(self, x_bytes):
        h1 = mmh3.hash(x_bytes, self.seed, signed=False)
        h2 = mmh3.hash(x_bytes, self.seed + 7919, signed=False)
        for i in range(self.k):
            yield (h1 + i * h2 + i * i) % self.m

    def add(self, x_bytes):
        for p in self._positions(x_bytes):
            self.bits[p >> 3] |= (1 << (p & 7))

    def __contains__(self, x_bytes):
        for p in self._positions(x_bytes):
            if not (self.bits[p >> 3] & (1 << (p & 7))):
                return False
        return True

    def clear_bits(self, x_bytes):
        """Naive 'bit-clearing' deletion: zero all k bits of this key."""
        for p in self._positions(x_bytes):
            self.bits[p >> 3] &= ~(1 << (p & 7))


# ----------------------------------------------------------------------
# Key generation
# ----------------------------------------------------------------------
def gen_keys(n, prefix):
    return [f"{prefix}-{i}".encode() for i in range(n)]


def main():
    N = 100_000
    # Table: 2^17 buckets * 4 slots = 524288 capacity, load 0.191 -> safe inserts
    power = 17
    cf = CuckooFilter(power)

    keys = gen_keys(N, "key")
    rng = random.Random(SEED)

    # Insert
    failed = 0
    for x in keys:
        if not cf.insert(x):
            failed += 1
    print(f"[cuckoo] inserted {N} keys, insert-failures={failed}, "
          f"load={cf.count/(cf.size*B):.4f}")

    # Split: delete half at random
    perm = keys[:]
    rng.shuffle(perm)
    half = N // 2
    deleted_set = perm[:half]
    retained_set = perm[half:]

    # Delete half
    del_ok = 0
    for x in deleted_set:
        if cf.delete(x):
            del_ok += 1
    print(f"[cuckoo] asked to delete {len(deleted_set)}, "
          f"successfully removed {del_ok}")

    # Query retained half -> expect all present (false negatives = bad)
    retained_fn = sum(1 for x in retained_set if not cf.contains(x))
    retained_total = len(retained_set)
    fnr = retained_fn / retained_total

    # Query deleted half -> expect absent; "present" = false positive
    deleted_present = sum(1 for x in deleted_set if cf.contains(x))
    deleted_total = len(deleted_set)
    # Correct removal rate = fraction of deleted keys now reported absent
    removal_rate = (deleted_total - deleted_present) / deleted_total

    # Fresh non-members
    fresh = gen_keys(N, "fresh")
    fresh_fp = sum(1 for x in fresh if cf.contains(x))
    fresh_total = len(fresh)

    print(f"[cuckoo] retained-queried={retained_total} "
          f"false-negatives={retained_fn} FNR={fnr:.6f}")
    print(f"[cuckoo] deleted-queried={deleted_total} "
          f"still-present(FP)={deleted_present} "
          f"correct-removal-rate={removal_rate:.6f}")
    print(f"[cuckoo] fresh-nonmembers={fresh_total} "
          f"false-positives={fresh_fp} FPR={fresh_fp/fresh_total:.6f}")

    # ---------------- Bloom filter demonstration ----------------
    # m = 1,000,000 bits, k = 7  (=> ~0.8% FPR for n=1e5)
    m = 1_000_000
    k = 7
    bf = BloomFilter(m, k)
    bf_keys = gen_keys(N, "bloom")
    for x in bf_keys:
        bf.add(x)

    # baseline: all should be present
    base_fn = sum(1 for x in bf_keys if x not in bf)
    print(f"[bloom] baseline FN before deletion: {base_fn}/{N}")

    # "delete" one key by bit-clearing
    victim = bf_keys[0]
    assert victim in bf
    bf.clear_bits(victim)
    victim_gone = victim not in bf
    print(f"[bloom] victim '{victim.decode()}' now absent after bit-clear: "
          f"{victim_gone}")

    # Now count how many OTHER keys became false negatives
    other = bf_keys[1:]
    collateral_fn = sum(1 for x in other if x not in bf)
    print(f"[bloom] collateral false-negatives among remaining "
          f"{len(other)} keys: {collateral_fn} "
          f"({collateral_fn/len(other):.6f})")

    # Show a concrete example of a collateral victim
    example = None
    for x in other:
        if x not in bf:
            example = x
            break
    # how many bits did victim share with the example?
    if example is not None:
        vpos = set(bf._positions(victim))
        epos = set(bf._positions(example))
        shared = vpos & epos
        print(f"[bloom] example collateral victim: '{example.decode()}', "
              f"shares {len(shared)}/{k} bits with the deleted key")

    # Also demonstrate at scale: bit-clear deletion of 1% of keys
    bf2 = BloomFilter(m, k)
    for x in bf_keys:
        bf2.add(x)
    n_del = N // 100  # 1%
    rng2 = random.Random(SEED)
    victims = rng2.sample(bf_keys, n_del)
    for v in victims:
        bf2.clear_bits(v)
    survivor_set = [x for x in bf_keys if x not in set(victims)]
    coll2 = sum(1 for x in survivor_set if x not in bf2)
    print(f"[bloom] after bit-clear deleting {n_del} keys (1%), "
          f"collateral FN among {len(survivor_set)} survivors: {coll2} "
          f"({coll2/len(survivor_set):.6f})")

    # write results to a json for summary building
    import json
    results = {
        "cuckoo": {
            "N": N, "b": B, "f": F, "table_buckets": cf.size, "capacity": cf.size*B,
            "insert_failures": failed,
            "deleted_count": deleted_total, "deleted_removed": del_ok,
            "retained_queried": retained_total,
            "retained_false_negatives": retained_fn,
            "retained_FNR": fnr,
            "deleted_queried": deleted_total,
            "deleted_still_present_FP": deleted_present,
            "correct_removal_rate": removal_rate,
            "fresh_nonmembers": fresh_total,
            "fresh_false_positives": fresh_fp,
            "fresh_FPR": fresh_fp / fresh_total,
        },
        "bloom": {
            "m": m, "k": k,
            "baseline_FN": base_fn,
            "victim_absent_after_clear": victim_gone,
            "collateral_FN_single_delete": collateral_fn,
            "collateral_FN_single_frac": collateral_fn / len(other),
            "example_victim": example.decode() if example else None,
            "shared_bits_example": len(shared) if example else None,
            "pct1_deleted": n_del,
            "pct1_collateral_FN": coll2,
            "pct1_collateral_frac": coll2 / len(survivor_set),
        },
        "seed": SEED,
    }
    with open("results.json", "w") as fh:
        json.dump(results, fh, indent=2)
    print("[done] wrote results.json")


if __name__ == "__main__":
    main()
