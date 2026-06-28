"""
SimHash + Hamming-threshold near-duplicate detection precision/recall sweep.

Fixed settings (per task):
  d        = 100   (vector dimensionality)
  b        = 256   (SimHash bit width)
  corpus   = fixed (base vectors + near-duplicate perturbations + unrelated vectors)
  seed     = 42    (fixed random seed)
Only the Hamming decision threshold T is varied.

Reference: Charikar 2002, "Similarity Estimation Techniques from Rounding Algorithms".
For a random-projection SimHash sketch of b bits, Pr[a single bit agrees] = 1 - theta/pi,
so E[Hamming distance] = b * theta / pi, with theta = arccos(cosine similarity).
Thus a true near-duplicate pair (cos ~ 0.95+, theta small) yields a small Hamming
distance, while an unrelated pair (cos ~ 0, theta ~ pi/2) yields Hamming ~ b/2.
"""

import numpy as np

# ---------------------------------------------------------------------------
# Fixed configuration
# ---------------------------------------------------------------------------
SEED      = 42
D         = 100      # vector dimensionality
B         = 256      # SimHash bits
N_BASE    = 300      # number of independent base vectors
N_NEAR    = 150      # how many base vectors get a near-duplicate partner
COS_LO    = 0.90     # near-duplicate cosine lower bound (sampled uniformly)
COS_HI    = 0.99     # near-duplicate cosine upper bound
COS_GT    = 0.85     # ground-truth threshold: a "true" near-duplicate pair if cos >= this

rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------------------
# 1. Build the corpus
# ---------------------------------------------------------------------------
# Base vectors ~ N(0, I_d); normalize to unit length (scale is irrelevant to
# cosine and to SimHash bit signs, but normalization keeps cosine = dot product).
base = rng.standard_normal((N_BASE, D))
base = base / np.linalg.norm(base, axis=1, keepdims=True)

vectors = []          # list of (vector, tag)  tag in {"base","near"}
near_truth = set()    # set of (i,j) indices that are constructed near-dup pairs

# We will record, for every vector we add, its origin base index so we can
# build ground truth from the *constructed* pairs.
origin = []           # origin[k] = base index that vector k derives from
records = []          # list of vectors

for i in range(N_BASE):
    records.append(base[i])
    origin.append(i)

# Near-duplicate partners for the first N_NEAR base vectors.
# Construct v' = a*v + sqrt(1-a^2)*z with z a unit vector orthogonal to v,
# so that cosine(v, v') = a exactly (no finite-d residual).
for i in range(N_NEAR):
    a = rng.uniform(COS_LO, COS_HI)
    v = base[i]
    z = rng.standard_normal(D)
    z = z - (z @ v) * v          # Gram-Schmidt: make z orthogonal to v
    z = z / (np.linalg.norm(z) + 1e-12)
    c = np.sqrt(1.0 - a * a)
    vp = a * v + c * z
    vp = vp / (np.linalg.norm(vp) + 1e-12)
    records.append(vp)
    origin.append(i)

X = np.stack(records, axis=0)              # (N, D)
N = X.shape[0]
print(f"Corpus: {N} vectors, d={D}")

# ---------------------------------------------------------------------------
# 2. Ground-truth near-duplicate pairs
#    Ground truth = constructed (base, perturbation) pairs whose actual cosine
#    is >= COS_GT. (All constructed pairs satisfy this by design, but we verify
#    against the *measured* cosine to be honest about finite-d residuals.)
# ---------------------------------------------------------------------------
# Pairwise cosine similarity.
C = X @ X.T                      # (N, N) since rows are unit-norm
np.fill_diagonal(C, -1.0)        # ignore self

iu = np.triu_indices(N, k=1)
cos_pairs = C[iu]                # cosine of every unordered pair
pair_idx = list(zip(iu[0].tolist(), iu[1].tolist()))

true_mask = cos_pairs >= COS_GT
true_pairs = set(pair_idx[k] for k in np.where(true_mask)[0])
n_true = len(true_pairs)
print(f"Total unordered pairs: {len(cos_pairs)}")
print(f"Ground-truth near-duplicate pairs (cos>={COS_GT}): {n_true}")

# Sanity: report cosine stats for true pairs and for the rest
true_cos = cos_pairs[true_mask]
neg_cos  = cos_pairs[~true_mask]
print(f"  true-pair cosine:  min={true_cos.min():.4f} mean={true_cos.mean():.4f} max={true_cos.max():.4f}")
print(f"  other-pair cosine: min={neg_cos.min():.4f} mean={neg_cos.mean():.4f} max={neg_cos.max():.4f}")

# ---------------------------------------------------------------------------
# 3. SimHash with b=256 bits (random hyperplane / sign-of-projection LSH)
# ---------------------------------------------------------------------------
P = rng.standard_normal((D, B))           # B random Gaussian projection vectors
S = (X @ P) > 0.0                          # (N, B) boolean bits
S = S.astype(np.uint8)

# Pairwise Hamming distance between b-bit sketches.
# Use packed bits for speed.
packed = np.packbits(S, axis=1)            # (N, B/8)
# Hamming via XOR + popcount (bitcount) on bytes
def popcount_matrix(packed):
    # vectorized popcount lookup
    pc = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint16)
    n = packed.shape[0]
    H = np.zeros((n, n), dtype=np.uint16)
    # compute upper triangle
    cols = packed.shape[1]
    for i in range(n):
        xor = packed[i] ^ packed       # (n, cols)
        H[i] = pc[xor].sum(axis=1)
    return H

H = popcount_matrix(packed)
ham_pairs = H[iu]                         # Hamming dist of every unordered pair

print(f"\nSimHash: b={B} bits")
print(f"  true-pair Hamming: min={ham_pairs[true_mask].min()} "
      f"mean={ham_pairs[true_mask].mean():.1f} max={ham_pairs[true_mask].max()}")
print(f"  other-pair Hamming: min={ham_pairs[~true_mask].min()} "
      f"mean={ham_pairs[~true_mask].mean():.1f} max={ham_pairs[~true_mask].max()}")

# Theoretical expectation for reference
import math
def expected_ham(cos):
    return B * math.acos(max(-1.0, min(1.0, cos))) / math.pi
print(f"  E[Ham] for cos={COS_LO}: {expected_ham(COS_LO):.1f}, cos={COS_HI}: {expected_ham(COS_HI):.1f}, cos=0: {expected_ham(0.0):.1f}")

# ---------------------------------------------------------------------------
# 4. Sweep decision threshold T: predict "near-duplicate" iff Hamming <= T
# ---------------------------------------------------------------------------
rows = []
for T in range(0, B + 1, 1):
    pred = ham_pairs <= T
    tp = int(np.sum(pred & true_mask))
    fp = int(np.sum(pred & ~true_mask))
    fn = int(np.sum(~pred & true_mask))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0   # no predictions => define precision 1
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    rows.append((T, tp, fp, fn, precision, recall, f1))

# Save full table
np.savetxt("pr_table.csv",
           np.array([(r[0], r[4], r[5], r[6]) for r in rows]),
           header="T,precision,recall,f1", delimiter=",", fmt="%d,%.6f,%.6f,%.6f")

# Print a coarser sampled view for the summary
print("\n  T    prec    rec    f1    TP  FP  FN")
for r in rows:
    if r[0] % 4 == 0 or r[5] in (0.0, 1.0) or (0 < r[5] < 1):
        T, tp, fp, fn, p, rc, f1 = r
        if T <= 60 or T >= 96:
            print(f"  {T:3d}  {p:.3f}  {rc:.3f}  {f1:.3f}  {tp:3d} {fp:4d} {fn:3d}")

# Best F1
best = max(rows, key=lambda r: (r[6], r[5]))
print(f"\nBest F1: T={best[0]}  prec={best[4]:.4f}  rec={best[5]:.4f}  f1={best[6]:.4f}")
