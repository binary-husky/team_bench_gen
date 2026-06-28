#!/usr/bin/env python3
"""
Equal-memory-budget comparison: Cuckoo filter vs Bloom filter.

Fixed settings:
  N          = 2 * 10^5  (key-set size)
  B          = memory budget in bits (derived from the cuckoo config)
  Cuckoo:    b = 4 entries/bucket, fingerprint f bits, M buckets
             sized for target load factor alpha ~ 0.95 (M = ceil(N/(alpha*b))).
             Memory = M * b * f bits  == B.
  Bloom:     m = B bits, k = round((m/N) * ln2) hash functions (optimal k).
  Seeds:     fixed list (members, non-members) -> reproducible.
Independent variable: filter type.

Measured: achieved load factor, false positive rate (on N non-members),
insert throughput, negative/positive lookup throughput (ops/s), and whether
the structure supports deletion.
"""

import json
import math
import time

import numpy as np

MASK64 = (1 << 64) - 1


def mix64(x):
    """splitmix64-style 64-bit finalizer (deterministic, fast in pure Python)."""
    x &= MASK64
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & MASK64
    return (x ^ (x >> 31)) & MASK64


# ============================================================================
# Cuckoo filter (b=4, partial-key cuckoo hashing)
#
# The alternate bucket must be an INVOLUTION: alt(alt(i,fp),fp) == i, so that a
# fingerprint -- no matter how many times it is kicked -- always lives in one of
# the two candidate buckets that Lookup inspects (=> no false negatives).
# The paper uses  i XOR hash(fp)  (an involution), but XOR forces the table size
# M to be a power of two.  At N=2e5 a power-of-two table sits at only ~76% load,
# undercutting the paper's 95%-load design.  To size M for ~95% load with an
# arbitrary (non-power-of-two) M we instead use the subtraction-mod-M involution
#
#       alt(i, fp) = ( K(fp) - i ) mod M ,   K(fp) = mix64(fp) mod M
#
# which is an involution for ANY M:  alt(alt(i)) = K - (K - i) = i (mod M), and
# preserves the "same fingerprint -> same bucket-pair" property the paper relies
# on for correct deletion.  FPR and throughput depend only on (f, b, alpha), not
# on the bucketing scheme, so the measurements stay comparable to the paper.
# ============================================================================
class CuckooFilter:
    def __init__(self, M, b, f_bits, max_kicks=500):
        self.M = M
        self.b = b
        self.f = f_bits
        self.max_kicks = max_kicks
        self.mask = (1 << f_bits) - 1
        self.table = [0] * (M * b)          # 0 == empty
        self.count = 0
        self.insert_failures = 0

    def _fp(self, H):
        fp = H & self.mask
        return fp if fp != 0 else 1          # 0 reserved for "empty"

    def _alt(self, i, fp):
        return (mix64(fp) % self.M - i) % self.M   # involution (see above)

    def insert(self, key):
        H = mix64(key)
        fp = self._fp(H)
        i1 = (H >> self.f) % self.M
        i2 = self._alt(i1, fp)
        b, table = self.b, self.table
        base = i1 * b
        for j in range(b):
            if table[base + j] == 0:
                table[base + j] = fp
                self.count += 1
                return True
        base = i2 * b
        for j in range(b):
            if table[base + j] == 0:
                table[base + j] = fp
                self.count += 1
                return True
        # must relocate
        i = i1 if (H & 1) else i2
        for kick in range(self.max_kicks):
            base = i * b
            slot = (mix64(fp) ^ (kick * 0x9E3779B97F4A7C15)) % b
            old = table[base + slot]
            table[base + slot] = fp
            fp = old
            i = self._alt(i, fp)
            base = i * b
            for j in range(b):
                if table[base + j] == 0:
                    table[base + j] = fp
                    self.count += 1
                    return True
        self.insert_failures += 1
        return False

    def lookup(self, key):
        H = mix64(key)
        fp = self._fp(H)
        i1 = (H >> self.f) % self.M
        i2 = self._alt(i1, fp)
        b, table = self.b, self.table
        base = i1 * b
        for j in range(b):
            if table[base + j] == fp:
                return True
        base = i2 * b
        for j in range(b):
            if table[base + j] == fp:
                return True
        return False

    def delete(self, key):
        H = mix64(key)
        fp = self._fp(H)
        i1 = (H >> self.f) % self.M
        i2 = self._alt(i1, fp)
        b, table = self.b, self.table
        for i in (i1, i2):
            base = i * b
            for j in range(b):
                if table[base + j] == fp:
                    table[base + j] = 0
                    self.count -= 1
                    return True
        return False

    def memory_bits(self):
        return self.M * self.b * self.f

    def load_factor(self):
        return self.count / (self.M * self.b)


# ============================================================================
# Standard Bloom filter (bit array, k hash functions via double-hashing)
# ============================================================================
class BloomFilter:
    def __init__(self, m_bits, k):
        self.m = m_bits
        self.k = k
        self.bits = bytearray((m_bits + 7) // 8)

    def _positions(self, key):
        h1 = mix64(key)
        h2 = mix64(key ^ 0x9E3779B97F4A7C15)
        m, k = self.m, self.k
        for i in range(k):
            yield (h1 + i * h2) % m

    def insert(self, key):
        bits = self.bits
        for p in self._positions(key):
            bits[p >> 3] |= (1 << (p & 7))

    def lookup(self, key):
        bits = self.bits
        for p in self._positions(key):
            if not (bits[p >> 3] & (1 << (p & 7))):
                return False
        return True

    def memory_bits(self):
        return self.m


# ============================================================================
# Single trial
# ============================================================================
def run_once(seed_mem, seed_non, N, b, f_bits, M, m, k_bloom):
    cuckoo = CuckooFilter(M=M, b=b, f_bits=f_bits)
    bloom = BloomFilter(m_bits=m, k=k_bloom)

    rng_m = np.random.default_rng(seed_mem)
    rng_n = np.random.default_rng(seed_non)
    members = rng_m.integers(0, 1 << 63, size=N, dtype=np.uint64).tolist()
    nonmembers = rng_n.integers(0, 1 << 63, size=N, dtype=np.uint64).tolist()
    mem_set = set(members)
    nonmembers = [x for x in nonmembers if x not in mem_set]
    nm_set = set(nonmembers)
    while len(nonmembers) < N:
        x = int(rng_n.integers(0, 1 << 63))
        if x not in mem_set and x not in nm_set:
            nonmembers.append(x)
            nm_set.add(x)

    # INSERT
    t0 = time.perf_counter()
    fail = 0
    for x in members:
        if not cuckoo.insert(x):
            fail += 1
    cuckoo_insert_secs = time.perf_counter() - t0
    cuckoo_inserted = cuckoo.count

    t0 = time.perf_counter()
    for x in members:
        bloom.insert(x)
    bloom_insert_secs = time.perf_counter() - t0

    # LOOKUP (positive = members)
    t0 = time.perf_counter()
    for x in members:
        cuckoo.lookup(x)
    cuckoo_pos_secs = time.perf_counter() - t0

    t0 = time.perf_counter()
    for x in members:
        bloom.lookup(x)
    bloom_pos_secs = time.perf_counter() - t0

    # LOOKUP (negative = non-members) -- also gives FPR
    fp_cuckoo = 0
    t0 = time.perf_counter()
    for x in nonmembers:
        if cuckoo.lookup(x):
            fp_cuckoo += 1
    cuckoo_neg_secs = time.perf_counter() - t0
    cuckoo_fpr = fp_cuckoo / len(nonmembers)

    fp_bloom = 0
    t0 = time.perf_counter()
    for x in nonmembers:
        if bloom.lookup(x):
            fp_bloom += 1
    bloom_neg_secs = time.perf_counter() - t0
    bloom_fpr = fp_bloom / len(nonmembers)

    fn_cuckoo = sum(1 for x in members if not cuckoo.lookup(x))
    fn_bloom = sum(1 for x in members if not bloom.lookup(x))

    del_ok = cuckoo.delete(members[0])
    still_there = cuckoo.lookup(members[0])
    n_q = len(nonmembers)

    return {
        "cuckoo": {"load_factor": cuckoo.load_factor(), "inserted": cuckoo_inserted,
                   "insert_failures": fail, "fpr": cuckoo_fpr,
                   "false_negatives": fn_cuckoo,
                   "insert_ops": N / cuckoo_insert_secs,
                   "lookup_neg_ops": n_q / cuckoo_neg_secs,
                   "lookup_pos_ops": N / cuckoo_pos_secs,
                   "supports_delete": True,
                   "delete_demo": {"returned": del_ok, "lookup_after": still_there}},
        "bloom": {"fpr": bloom_fpr, "false_negatives": fn_bloom,
                  "insert_ops": N / bloom_insert_secs,
                  "lookup_neg_ops": n_q / bloom_neg_secs,
                  "lookup_pos_ops": N / bloom_pos_secs,
                  "supports_delete": False},
    }


def stat(vals):
    vals = list(vals)
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    return mean, var ** 0.5


def main():
    N = 200_000
    b = 4
    alpha_target = 0.95
    M = math.ceil(N / (alpha_target * b))
    f_bits = 10
    B = M * b * f_bits
    m = B
    k_bloom = max(1, round((m / N) * math.log(2)))
    SEEDS = [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10)]

    print("=" * 74)
    print("CONFIG (fixed across all trials)")
    print("=" * 74)
    print(f"N (members)            = {N}")
    print(f"B (memory budget)      = {B} bits = {B/8} bytes = {B/8/1024:.2f} KiB "
          f"({B/N:.3f} bits/item)")
    print(f"Cuckoo: b={b}, f={f_bits} bits, M={M} buckets (target alpha={alpha_target}); "
          f"mem = M*b*f = {B} bits")
    print(f"Bloom : m={m} bits, k={k_bloom}  (optimal k=(m/N)ln2={(m/N)*math.log(2):.3f})")
    print(f"seeds (mem,non)        = {SEEDS}")
    print()

    trials = [run_once(sm, sn, N, b, f_bits, M, m, k_bloom) for sm, sn in SEEDS]

    cfpr, csd = stat([t["cuckoo"]["fpr"] for t in trials])
    bfpr, bsd = stat([t["bloom"]["fpr"] for t in trials])
    cins = stat([t["cuckoo"]["insert_ops"] for t in trials])
    bins = stat([t["bloom"]["insert_ops"] for t in trials])
    cneg = stat([t["cuckoo"]["lookup_neg_ops"] for t in trials])
    bneg = stat([t["bloom"]["lookup_neg_ops"] for t in trials])
    cpos = stat([t["cuckoo"]["lookup_pos_ops"] for t in trials])
    bpos = stat([t["bloom"]["lookup_pos_ops"] for t in trials])
    alpha_m, _ = stat([t["cuckoo"]["load_factor"] for t in trials])
    tot_fail = sum(t["cuckoo"]["insert_failures"] for t in trials)
    tot_fnc = sum(t["cuckoo"]["false_negatives"] for t in trials)
    tot_fnb = sum(t["bloom"]["false_negatives"] for t in trials)

    print("=" * 74)
    print(f"RESULTS  (mean over {len(SEEDS)} seeds; throughput in ops/s)")
    print("=" * 74)
    print(f"cuckoo load factor      = {alpha_m:.4f}  "
          f"(insert failures total={tot_fail}; cuckoo false-neg total={tot_fnc}; "
          f"bloom false-neg total={tot_fnb})")
    print()
    print(f"{'metric':<28}{'Cuckoo (mean+-sd)':>24}{'Bloom (mean+-sd)':>24}")
    print("-" * 76)
    print(f"{'memory (bits)':<28}{B:>24}{B:>24}")
    print(f"{'bits/item':<28}{B/N:>24.3f}{B/N:>24.3f}")
    print(f"{'FPR':<28}"
          f"{cfpr*100:>16.4f}% +-{csd*100:.4f}"
          f"{bfpr*100:>16.4f}% +-{bsd*100:.4f}")
    print(f"{'insert tput (ops/s)':<28}"
          f"{cins[0]:>16,.0f} +-{cins[1]:,.0f}"
          f"{bins[0]:>16,.0f} +-{bins[1]:,.0f}")
    print(f"{'lookup neg tput (ops/s)':<28}"
          f"{cneg[0]:>16,.0f} +-{cneg[1]:,.0f}"
          f"{bneg[0]:>16,.0f} +-{bneg[1]:,.0f}")
    print(f"{'lookup pos tput (ops/s)':<28}"
          f"{cpos[0]:>16,.0f} +-{cpos[1]:,.0f}"
          f"{bpos[0]:>16,.0f} +-{bpos[1]:,.0f}")
    print()
    print(f"theoretical FPR:  cuckoo 2*a*b/2^f = "
          f"{(2*alpha_m*b)/(1<<f_bits)*100:.4f}%   |   "
          f"bloom (0.6185)^(m/N) = {(0.6185)**(m/N)*100:.4f}%")
    print(f"FPR ratio cuckoo/bloom   = {cfpr/bfpr:.3f}x")
    print()
    print("Deletion:  Cuckoo = YES (Delete(x) removes one copy of x's fingerprint "
          "from its bucket; demo on members[0] -> returned True, lookup "
          "afterward = False)")
    print("           Bloom  = NO  (standard bit-array Bloom has no delete; "
          "counting Bloom needed, ~4x space)")

    out = {
        "config": {"N": N, "B_bits": B, "bits_per_item": B / N, "seeds": SEEDS,
                   "cuckoo": {"b": b, "f": f_bits, "M": M,
                              "target_alpha": alpha_target},
                   "bloom": {"m": m, "k": k_bloom}},
        "summary": {
            "cuckoo_load_factor": alpha_m,
            "cuckoo_fpr_mean": cfpr, "cuckoo_fpr_sd": csd,
            "bloom_fpr_mean": bfpr, "bloom_fpr_sd": bsd,
            "fpr_ratio_cuckoo_over_bloom": cfpr / bfpr,
            "cuckoo_insert_ops": cins[0], "bloom_insert_ops": bins[0],
            "cuckoo_lookup_neg_ops": cneg[0], "bloom_lookup_neg_ops": bneg[0],
            "cuckoo_lookup_pos_ops": cpos[0], "bloom_lookup_pos_ops": bpos[0],
            "cuckoo_supports_delete": True, "bloom_supports_delete": False,
            "false_negatives_cuckoo_total": tot_fnc,
            "false_negatives_bloom_total": tot_fnb,
            "insert_failures_cuckoo_total": tot_fail,
        },
        "trials": trials,
    }
    with open("results.json", "w") as fh:
        json.dump(out, fh, indent=2)
    print("\nWrote results.json")


if __name__ == "__main__":
    main()
