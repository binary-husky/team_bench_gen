"""
LF-mapping reversibility verification.

Goal: on a fixed ~100KB-500KB text (fixed seed, fixed implementation),
build the BWT, then reconstruct the original text backwards using *only*
  - L  (the BWT last column),
  - C  array (cumulative character counts),
  - Occ/rank (number of occurrences of a char in a prefix of L),
i.e. pure LF-mapping.  Compare the reconstruction byte-for-byte with the
original and report equality / first mismatch position.

Reference: Ferragina & Manzini (2000), "Opportunistic Data Structures for
Searching and Compression" (fmindex_material/...pdf).  The LF mapping is
  LF(i) = C[ L[i] ] + Occ( L[i], i )
and iterating it from the sentinel row walks the text in reverse order,
which is the basis of the FM-index backward reconstruction.
"""

import random
import bisect
import time

from pydivsufsort import divsufsort

# ----------------------------------------------------------------------
# 0. Fixed text (~256 KB), fixed seed, fixed implementation.
#    Alphabet: bytes 1..255  (byte 0 is reserved as the unique sentinel,
#    which is strictly smaller than every text symbol => a valid BWT
#    terminator without colliding with text content).
# ----------------------------------------------------------------------
SEED = 20240626
N = 1 << 18  # 262144 bytes  (~256 KB), within the 100KB-500KB range
SENTINEL = 0  # '$' analogue: unique, lexicographically smallest

random.seed(SEED)
raw = random.randbytes(N)
# forbid the sentinel value inside the text so the terminator is unique
text = bytes(b if b != 0 else 1 for b in raw)
assert len(text) == N
assert SENTINEL not in text, "sentinel must not appear in text"

# ----------------------------------------------------------------------
# 1. Build the BWT.
#    Append the sentinel, compute the suffix array of T' = text + SENTINEL,
#    then  L[i] = T'[ SA[i] - 1 ]   (with SA[i]==0 -> L[i] = SENTINEL).
# ----------------------------------------------------------------------
Tp = text + bytes([SENTINEL])
n = len(Tp)

t0 = time.time()
sa = divsufsort(Tp)            # int64 array of length n, 0-based
sa = list(sa)
L = bytearray(n)
for i in range(n):
    j = sa[i]
    L[i] = Tp[j - 1] if j != 0 else Tp[-1]  # Tp[-1] == SENTINEL here
# (When j==0, the rotation is the one starting at the sentinel; its last
#  column is the char physically before the sentinel = Tp[n-1] = SENTINEL.)
L = bytes(L)
print(f"BWT built in {time.time()-t0:.2f}s, n={n}")

# ----------------------------------------------------------------------
# 2. Build C array and Occ structure, using ONLY L (as the FM-index does).
#    C[c]  = #{ symbols < c in T' }   (equivalently prefix count over L)
#    positions[c] = sorted indices where L[i]==c  -> Occ(c,i)=bisect_left
# ----------------------------------------------------------------------
counts = [0] * 256
for c in L:
    counts[c] += 1

C = [0] * 256
running = 0
for c in range(256):
    C[c] = running
    running += counts[c]
# sanity: total occurrences == n
assert running == n

positions = [[] for _ in range(256)]
for i, c in enumerate(L):
    positions[c].append(i)   # ascending by construction

def occ(c, i):
    """Number of occurrences of c in L[0:i]."""
    return bisect.bisect_left(positions[c], i)

def lf(i):
    c = L[i]
    return C[c] + occ(c, i)

# ----------------------------------------------------------------------
# 3. Reconstruct T' (hence T) backwards via pure LF-mapping.
#    Row 0 of the sorted-rotation matrix is the rotation starting at the
#    sentinel, so its last column L[0] is the last character of the text.
#    Iterating  i <- LF(i)  yields the text in reverse order.
# ----------------------------------------------------------------------
t0 = time.time()
i = 0
rev = bytearray(n - 1)          # T (without sentinel) reconstructed reversed
for k in range(n - 1):
    c = L[i]
    rev[k] = c
    i = lf(c if False else i)   # lf(i) reads L[i] internally
reconstructed = bytes(rev[::-1])
print(f"Reconstruction done in {time.time()-t0:.2f}s")

# ----------------------------------------------------------------------
# 4. Byte-for-byte comparison with the original text.
# ----------------------------------------------------------------------
equal = (reconstructed == text)
first_mismatch = -1
if not equal:
    for k in range(N):
        if reconstructed[k] != text[k]:
            first_mismatch = k
            break

print("=" * 60)
print(f"text length          : {N} bytes")
print(f"seed                 : {SEED}")
print(f"fully equal          : {equal}")
print(f"first mismatch index : {first_mismatch}")

# extra self-checks for the report
assert L.count(SENTINEL) == 1, "BWT must contain exactly one sentinel"
sentinel_row = L.index(SENTINEL)
print(f"sentinel row in BWT  : {sentinel_row}")
print(f"LF(0)                : {lf(0)}  (should walk the chain)")
print(f"C[SENTINEL]          : {C[SENTINEL]} (==0, smallest symbol)")

# Save raw metrics for the summary
import json
with open("lf_mapping_metrics.json", "w") as f:
    json.dump({
        "seed": SEED,
        "text_length": N,
        "n_with_sentinel": n,
        "fully_equal": equal,
        "first_mismatch": first_mismatch,
        "sentinel_row_in_BWT": sentinel_row,
        "C_sentinel": C[SENTINEL],
        "reconstruction_time_s": round(time.time() - t0, 3),
    }, f, indent=2)
