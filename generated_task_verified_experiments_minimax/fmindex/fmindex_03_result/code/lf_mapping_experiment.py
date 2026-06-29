"""
LF-mapping reversibility experiment.

Builds a BWT on a fixed-seed pseudo-random text (within 100KB-500KB),
then reconstructs the original text by repeated LF-mapping using only
BWT (L), the C array, and rank. Compares the result byte-by-byte to
the original.

Reference: Ferragina & Manzini (2000), "Opportunistic Data Structures
with Applications", Section 2 ("The reversible BW-transform"):
  a. L[i] precedes F[i] in T.
  b. r_i = rank of L[i] in L[1..i].
  c. LF[i] = C[L[i]] + r_i, and T is reconstructed backward from
     s = 1 (because M[1] = #T) by iterating s = LF[s].
"""

import os
import random
import time
import sys

import PySAIS  # SA-IS suffix array builder; gives us O(n) BWT

# ---------- Fixed experimental setup --------------------------------------

SEED = 20260628          # fixed RNG seed for reproducibility
TEXT_LEN = 200 * 1024    # 200 KiB, well inside the 100KB-500KB window
ALPHABET = (
    b"abcdefghijklmnopqrstuvwxyz"
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    b"0123456789"
    b" ,.;:!?()[]{}<>-_'\"`~/\\|+=*&\n\t"
)


# ---------- BWT construction ----------------------------------------------

def bwt(text: bytes, sentinel: int) -> list[int]:
    """Return BWT(L) as a list of ints of length len(text)+1.

    A sentinel byte strictly smaller than any text byte is prepended to the
    text, so the augmented string is ``# + text``. PySAIS builds the suffix
    array in O(n); the BWT column L is then ``aug[sa[i] - 1]`` for each i
    (with the wrap-around giving the last char of the rotation starting at
    sa[i]).
    """
    aug = bytes([sentinel]) + text
    sa = PySAIS.sais(aug)
    n = len(aug)
    return [aug[i - 1] for i in sa]   # wrap to last char of each rotation


# ---------- LF-mapping machinery -------------------------------------------

def build_C_and_rank(L: list[int], sigma: int):
    """Return C[c] for c in 1..sigma and rank[i] = occurrences of L[i] in L[0..i-1]."""
    n = len(L)
    counts = [0] * (sigma + 1)               # count of each byte in L (incl. sentinel)
    for c in L:
        counts[c] += 1
    # C[c] = number of symbols strictly smaller than c in the augmented alphabet.
    # Symbols are 0..sigma; we want C[c] = sum_{d < c} counts[d].
    C = [0] * (sigma + 1)
    acc = 0
    for c in range(sigma + 1):
        C[c] = acc
        acc += counts[c]
    rank = [0] * n
    seen = [0] * (sigma + 1)
    for i in range(n):
        c = L[i]
        rank[i] = seen[c]
        seen[c] += 1
    return C, rank


def reconstruct(L: list[int], C, rank):
    """Backward reconstruction via repeated LF-mapping.

    The LF walk over the m+1 rows of M is a single cycle of length m+1
    (m = len(text)). Starting from the sentinel row (s=0), the first L
    read gives text[m-1]; each subsequent LF step peels off the next
    earlier character. After m-1 LF applications we have read all m
    characters of T and the walk is one step short of returning to s=0,
    so we stop *before* the sentinel is read back.
    """
    n = len(L)
    m = n - 1
    out = bytearray(m)
    s = 0
    for i in range(m - 1, -1, -1):
        c = L[s]
        out[i] = c
        s = C[c] + rank[s]
    return bytes(out)


# ---------- Main experiment ------------------------------------------------

def main():
    rng = random.Random(SEED)
    text = bytes(rng.choice(ALPHABET) for _ in range(TEXT_LEN))
    sigma = 255                               # sentinel uses byte 0; alphabet is 1..255

    print(f"text length = {len(text)} bytes", flush=True)

    t0 = time.perf_counter()
    L = bwt(text, sentinel=0)
    t_bwt = time.perf_counter() - t0

    t0 = time.perf_counter()
    C, rank = build_C_and_rank(L, sigma)
    t_aux = time.perf_counter() - t0

    t0 = time.perf_counter()
    rec = reconstruct(L, C, rank)
    t_recon = time.perf_counter() - t0

    # Byte-wise comparison.
    n = len(text)
    first_mismatch = -1
    for i in range(n):
        if rec[i] != text[i]:
            first_mismatch = i
            break

    equal = (first_mismatch == -1)
    print(f"BWT build:    {t_bwt*1000:.2f} ms")
    print(f"C+rank build: {t_aux*1000:.2f} ms")
    print(f"reconstruct:  {t_recon*1000:.2f} ms")
    print(f"len(L) = {len(L)}, |C| = {len(C)}, |rank| = {len(rank)}")
    print(f"equal: {equal}")
    print(f"first mismatch: {first_mismatch}")

    # Sanity: report a small neighbourhood around any mismatch.
    if not equal:
        lo = max(0, first_mismatch - 5)
        hi = min(n, first_mismatch + 5)
        print(f"  text[{lo}:{hi}]   = {text[lo:hi]!r}")
        print(f"  rec [{lo}:{hi}]   = {rec[lo:hi]!r}")
        print(f"  text[{first_mismatch}]={text[first_mismatch]:#04x}  "
              f"rec[{first_mismatch}]={rec[first_mismatch]:#04x}")

    # Persist artefacts the summary may want to cite.
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "summary_metrics.txt"), "w") as f:
        f.write(f"seed={SEED}\n")
        f.write(f"text_len={n}\n")
        f.write(f"alphabet_size={sigma}\n")
        f.write(f"L_len={len(L)}\n")
        f.write(f"bwt_ms={t_bwt*1000:.4f}\n")
        f.write(f"aux_ms={t_aux*1000:.4f}\n")
        f.write(f"recon_ms={t_recon*1000:.4f}\n")
        f.write(f"equal={equal}\n")
        f.write(f"first_mismatch={first_mismatch}\n")

    return 0 if equal else 1


if __name__ == "__main__":
    sys.exit(main())
