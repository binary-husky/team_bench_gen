"""
FM-index from scratch (educational).

Components:
  - Build BWT via suffix array (using PySAIS for linear-time construction)
  - Build C array:  C[c] = # of text characters lex-smaller than c
  - Build Occ on L (BWT):  a per-character cumulative-count array
  - backward-search count  (Ferragina & Manzini, 2000, Algorithm BW_Search, Fig. 1)
"""

from __future__ import annotations

import bisect

import numpy as np
import PySAIS


# ---------------------------------------------------------------------------
# BWT
# ---------------------------------------------------------------------------
def build_bwt(text: bytes, sa: np.ndarray) -> np.ndarray:
    """
    Build the BWT (last column L) of `text` from its suffix array `sa`.

    L[i] = text[ (sa[i] - 1) mod n ]  -- the char preceding the suffix at SA[i].
    For sa[i] == 0, the predecessor is the sentinel (last byte of text).
    """
    n = len(text)
    text_arr = np.frombuffer(text, dtype=np.uint8)
    prev = (sa - 1) % n
    return text_arr[prev].copy()


# ---------------------------------------------------------------------------
# C array -- as a 256-entry cumulative table (so C(b) is O(1))
# ---------------------------------------------------------------------------
def build_c_array(text_bytes: bytes) -> tuple[np.ndarray, int]:
    """
    Return a 256-entry numpy int64 array `c_arr` such that
        c_arr[b] = # of chars in text_bytes that are strictly < b.
    Also return the alphabet minimum (the smallest byte in text_bytes).
    """
    counts = np.bincount(np.frombuffer(text_bytes, dtype=np.uint8), minlength=256)
    cum = np.zeros(256, dtype=np.int64)
    cum[1:] = np.cumsum(counts[:-1])
    c_min = int(np.argmax(counts > 0))
    return cum, c_min


# ---------------------------------------------------------------------------
# Occ on the BWT -- per-character 0-indexed inclusive cumulative arrays
# ---------------------------------------------------------------------------
def build_occ(bwt: np.ndarray) -> dict[int, np.ndarray]:
    """
    For each distinct byte value b in BWT, return occ_b such that
        occ_b[k] = # of occurrences of b in bwt[0..k]  (0-indexed, inclusive prefix)
    """
    occ: dict[int, np.ndarray] = {}
    for b in np.unique(bwt):
        occ[int(b)] = np.cumsum(bwt == b, dtype=np.int64)
    return occ


# ---------------------------------------------------------------------------
# Backward-search count
# ---------------------------------------------------------------------------
def count_pattern(pattern: bytes,
                  c_arr: np.ndarray,
                  occ: dict[int, np.ndarray],
                  n: int) -> int:
    """
    Implements BW_Search (counting version) of Ferragina-Manzini 2000, Fig. 1.

    Returns the number of occurrences of `pattern` in the indexed text,
    or 0 if the pattern does not occur.

    Conventions (1-indexed, paper):
        C[c]          : # of chars in text strictly < c  (C is indexed by char)
        Occ(c, 1, k)  : # of occurrences of c in L[1..k]
        sp, ep        : 1-indexed row range of suffixes prefixed by current prefix

    Our 0-indexed occ_b satisfies occ_b[k] = # of b in L[0..k].
        => Occ(c, 1, k) = occ_b[k-1]    (paper's k = our k-1)
    """
    m = len(pattern)
    if m == 0:
        return 0

    # Step 1: i = p = m,  c = P[p]
    i = m
    c = pattern[-1]

    # Step 2: sp = C[c] + 1,  ep = C[c+1] (= C[c] + count of c)
    C_c = int(c_arr[c])
    cnt_c = int(occ[c][-1]) if c in occ else 0
    sp = C_c + 1
    ep = C_c + cnt_c
    if sp > ep:
        return 0

    # Step 3
    while sp <= ep and i >= 2:
        c = pattern[i - 2]  # paper: c = P[i-1] in 1-indexed
        C_c = int(c_arr[c])
        if c in occ:
            occ_arr = occ[c]
            occ_sp_minus_1 = int(occ_arr[sp - 2]) if sp >= 2 else 0
            occ_ep = int(occ_arr[ep - 1])
        else:
            occ_sp_minus_1 = 0
            occ_ep = 0
        sp = C_c + occ_sp_minus_1 + 1
        ep = C_c + occ_ep
        i -= 1

    if ep < sp:
        return 0
    return ep - sp + 1


# ---------------------------------------------------------------------------
# High-level wrapper
# ---------------------------------------------------------------------------
class FMIndex:
    def __init__(self, text: bytes):
        # Append a sentinel smaller than any real char.
        if 0 in text:
            sentinel = 1 if 1 not in text else 2
        else:
            sentinel = 0
        self.text = bytes([sentinel]) + text
        self.n = len(self.text)

        # Suffix array
        sa_list = PySAIS.sais(self.text)
        self.sa = np.array(sa_list, dtype=np.int64)

        # BWT
        self.bwt = build_bwt(self.text, self.sa)

        # C table (256-entry)
        self.c_arr, self.c_min = build_c_array(self.text)

        # Occ on BWT
        self.occ = build_occ(self.bwt)

    def count(self, pattern: bytes) -> int:
        """Count occurrences of `pattern` in the original text (sentinel excluded)."""
        # Patterns that contain a byte not in the text cannot occur.
        if len(pattern) == 0:
            return 0
        for b in pattern:
            if self.c_arr[b] == self.c_arr[b + 1] and b + 1 < 256:
                # byte b does not appear in text  (this is approximate; see below)
                pass
        # Simpler check: every byte in the pattern must appear in the BWT.
        bwt_unique = set(int(x) for x in np.unique(self.bwt))
        for b in pattern:
            if b not in bwt_unique:
                return 0
        return count_pattern(pattern, self.c_arr, self.occ, self.n)


# ---------------------------------------------------------------------------
# Brute-force verification
# ---------------------------------------------------------------------------
def brute_force_count(text: bytes, pattern: bytes) -> int:
    if len(pattern) == 0 or len(pattern) > len(text):
        return 0
    return text.count(pattern)


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    text = b"abracadabra"
    print("text:", text)
    fmi = FMIndex(text)
    print("sa  :", fmi.sa.tolist())
    print("bwt :", fmi.bwt.tolist())
    print("c_arr[ord('a')]:", int(fmi.c_arr[97]))
    print("c_arr[ord('b')]:", int(fmi.c_arr[98]))
    for p in [b"abra", b"a", b"ra", b"ab", b"abr", b"z", b"", b"abracadabra", b"a" * 5,
              b"aca", b"aca" * 2]:
        bf = brute_force_count(text, p)
        bs = fmi.count(p)
        ok = "OK" if bf == bs else "FAIL"
        print(f"  pattern={p!r:25s} brute={bf:3d}  bs={bs:3d}  {ok}")
