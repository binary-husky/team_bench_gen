#!/usr/bin/env python3
"""
FM-index from scratch: verify backward-search count(pattern) == brute-force count.

Components implemented from scratch:
  - Suffix array via prefix-doubling (O(n log n), vectorized with numpy) for fast BWT construction.
  - BWT (last column L) from the suffix array.
  - C array: C[c] = #chars in text lexicographically smaller than c.
  - Occ/rank on L: Occ(c, i) = #occurrences of c in L[0:i]  (prefix-count structure).
  - Backward search counting occurrences of a pattern (half-open range [l, r)).
Brute-force reference: overlapping substring count via str.find loop.

Texts (fixed seeds): random DNA (~200KB) and pseudo-English (~200KB).
Sentinel '\x00' (smaller than any printable byte) appended to make the text uniquely
cyclic / suffix-sorted; it never participates in a query pattern.
"""
import numpy as np
import random
import sys

SENT = 0  # '\x00' sentinel byte value; smaller than any printable char


# --------------------------------------------------------------------------- #
# Suffix array (prefix doubling, vectorized)
# --------------------------------------------------------------------------- #
def _rank_compress(sa: np.ndarray, keys: np.ndarray) -> np.ndarray:
    """Assign equal ranks to equal keys (rank compression)."""
    n = len(sa)
    newrank = np.zeros(n, dtype=np.int64)
    r = 0
    for i in range(1, n):
        if keys[i] != keys[i - 1]:
            r += 1
        newrank[sa[i]] = r
    return newrank


def build_suffix_array(s: np.ndarray) -> np.ndarray:
    """s: int64 array including a unique smallest sentinel (value 0).
    Returns SA as int64 array of length len(s)."""
    n = len(s)
    # initial sort by single character (rank = char value)
    sa = np.argsort(s, kind="stable")
    keys0 = s[sa]
    rank = _rank_compress(sa, keys0)
    if rank[sa[-1]] == n - 1:
        return sa
    k = 1
    while True:
        # second-order rank: rank[i+k], with -1 (smallest) when out of range
        idx2 = sa + k
        valid = idx2 < n
        second = np.empty(n, dtype=np.int64)
        second[valid] = rank[idx2[valid]]
        second[~valid] = -1
        # combine (rank, second) into one sortable key
        key = rank[sa] * (n + 1) + (second + 1)
        order = np.argsort(key, kind="stable")
        sa = sa[order]
        rank = _rank_compress(sa, key[order])
        if rank[sa[-1]] == n - 1:
            break  # all ranks distinct -> SA complete
        k *= 2
        if k >= n:
            break
    return sa


# --------------------------------------------------------------------------- #
# FM-index
# --------------------------------------------------------------------------- #
class FMIndex:
    def __init__(self, text_bytes: bytes):
        # T with sentinel appended (unique, smallest)
        arr = np.frombuffer(text_bytes, dtype=np.uint8).astype(np.int64)
        T = np.concatenate([arr, np.array([SENT], dtype=np.int64)])
        n = len(T)
        self.n = n

        # distinct alphabet (excluding sentinel) in sorted order
        present = np.unique(T)
        self.codes = {int(c): i for i, c in enumerate(present)}
        self.sigma = len(present)

        # suffix array + BWT (L column): L[i] = T[(SA[i]-1) mod n]
        sa = build_suffix_array(T)
        self.sa = sa
        prev = (sa - 1) % n
        L = T[prev]                       # byte values
        self.L = L
        self.T = T

        # C array over codes (in sorted-by-value order == code order since
        # code assigned in sorted value order). C[code] = #chars with value < c.
        # counts of each code in the WHOLE text (== counts in L, same multiset)
        counts = np.zeros(self.sigma, dtype=np.int64)
        for c in present:
            counts[self.codes[int(c)]] = int(np.sum(T == c))
        self.C = np.concatenate([[0], np.cumsum(counts)]).astype(np.int64)
        # self.C[code] = #chars strictly smaller than that code's value

        # Occ matrix: occ[code, i] = # of that char in L[0:i], for i in 0..n
        occ = np.zeros((self.sigma, n + 1), dtype=np.int32)
        for c in present:
            code = self.codes[int(c)]
            occ[code, 1:] = np.cumsum(L == c)
        self.occ = occ

    def count(self, pattern: bytes) -> int:
        """Backward-search count of (overlapping) occurrences of pattern in text."""
        if len(pattern) == 0:
            return self.n  # convention: empty pattern matches everywhere
        m = len(pattern)
        l, r = 0, self.n  # half-open [l, r)
        for i in range(m - 1, -1, -1):
            c = pattern[i]
            code = self.codes.get(c)
            if code is None:
                return 0  # char not in alphabet -> pattern absent
            occ_l = int(self.occ[code, l])
            occ_r = int(self.occ[code, r])
            l = int(self.C[code]) + occ_l
            r = int(self.C[code]) + occ_r
            if l >= r:
                return 0
        return r - l


# --------------------------------------------------------------------------- #
# Brute-force overlapping count (reference)
# --------------------------------------------------------------------------- #
def brute_count(text: bytes, pattern: bytes) -> int:
    if len(pattern) == 0:
        return len(text) + 1
    cnt = 0
    start = 0
    while True:
        i = text.find(pattern, start)
        if i == -1:
            break
        cnt += 1
        start = i + 1  # overlapping
    return cnt


# --------------------------------------------------------------------------- #
# Text generators (fixed seeds)
# --------------------------------------------------------------------------- #
def gen_dna(length=200_000, seed=12345) -> bytes:
    rng = random.Random(seed)
    alphabet = b"ACGT"
    return bytes(alphabet[rng.randrange(4)] for _ in range(length))


# A small word list to build pseudo-English text
_WORDS = (
    "the of and to a in is it you that he was for on are with as his they "
    "at be this have from or one had by word but not what all were we when "
    "your can said there use an each which she do how their if will up other "
    "about out many then them these so some her would make like him into time "
    "has look two more write go see number no way could people my than first "
    "water been call who oil its now find long down day did get come made "
    "may part apple banana quickly brown fox jumps over lazy dog river forest "
    "mountain science history language computer algorithm data structure query "
    "pattern suffix array index memory buffer stream queue stack graph node edge"
).split()


def gen_english(length=200_000, seed=99999) -> bytes:
    rng = random.Random(seed)
    out = []
    cur = 0
    while cur < length:
        w = _WORDS[rng.randrange(len(_WORDS))]
        out.append(w)
        cur += len(w) + 1  # space
    text = " ".join(out)
    text = text[:length]
    return text.encode("ascii")


# --------------------------------------------------------------------------- #
# Pattern generation
# --------------------------------------------------------------------------- #
def make_patterns(text: bytes, rng: random.Random):
    n = len(text)
    patterns = []
    # (a) substrings of the text (guaranteed >=1 occurrence) of varied lengths
    for L in (1, 2, 3, 5, 8, 12, 20, 40):
        for _ in range(25):
            s = rng.randrange(n - L + 1)
            patterns.append(text[s:s + L])
    # (b) random patterns over the alphabet (may be absent)
    alpha = sorted(set(text))
    for L in (1, 3, 5, 10, 20):
        for _ in range(25):
            patterns.append(bytes(rng.choice(alpha) for _ in range(L)))
    # (c) edge cases
    patterns.append(text[:1])              # first char
    patterns.append(text[-1:])             # last char
    patterns.append(text[:20])             # prefix
    patterns.append(text[-20:])            # suffix
    patterns.append(b"A" * 10)             # homopolymer (DNA-relevant)
    patterns.append(b"AAAA")               # homopolymer short
    patterns.append(b"the")                # common word (English-relevant)
    patterns.append(b"qzx")                # unlikely trigram (absent-ish)
    patterns.append(text[:])               # whole text (1 occurrence)
    # a definitely-absent pattern using a byte not in text
    absent_byte = 0
    for cand in range(255, 0, -1):
        if cand not in set(text):
            absent_byte = cand
            break
    patterns.append(bytes([absent_byte]) * 5)
    return patterns


# --------------------------------------------------------------------------- #
# Main experiment
# --------------------------------------------------------------------------- #
def run_experiment(name, text, seed):
    print(f"\n===== {name}  (len={len(text)}) =====", flush=True)
    rng = random.Random(seed)
    fmi = FMIndex(text)
    patterns = make_patterns(text, rng)

    total = 0
    match = 0
    mismatch = 0
    mismatches = []
    bf_total_occ = 0
    fm_total_occ = 0
    absents = 0
    for p in patterns:
        bf = brute_count(text, p)
        fm = fmi.count(p)
        total += 1
        bf_total_occ += bf
        fm_total_occ += fm
        if bf == 0:
            absents += 1
        if bf == fm:
            match += 1
        else:
            mismatch += 1
            if len(mismatches) < 20:
                mismatches.append((p[:40], bf, fm))
    print(f"patterns         : {total}", flush=True)
    print(f"matched          : {match}", flush=True)
    print(f"mismatched       : {mismatch}", flush=True)
    print(f"absent-in-text   : {absents}", flush=True)
    print(f"sum brute occ    : {bf_total_occ}", flush=True)
    print(f"sum FM occ       : {fm_total_occ}", flush=True)
    print(f"match rate       : {match / total:.6f}", flush=True)
    if mismatches:
        print("SAMPLE MISMATCHES (pattern|brute|fm):", flush=True)
        for p, b, f in mismatches:
            print(f"  {p!r}  brute={b}  fm={f}", flush=True)
    return dict(
        name=name, n=len(text), total=total, match=match, mismatch=mismatch,
        absents=absents, bf_total_occ=bf_total_occ, fm_total_occ=fm_total_occ,
        sample_mismatches=mismatches,
    )


def main():
    results = []
    dna = gen_dna(200_000, seed=12345)
    results.append(run_experiment("random-DNA-200KB", dna, seed=777))

    eng = gen_english(200_000, seed=99999)
    results.append(run_experiment("pseudo-English-200KB", eng, seed=888))

    # smaller sanity text with known content
    sanity = b"banana" * 10 + b"mississippi" * 10
    results.append(run_experiment("sanity-banana-mississippi", sanity, seed=111))

    # dump machine-readable summary
    import json
    with open("results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nWrote results.json", flush=True)


if __name__ == "__main__":
    main()
