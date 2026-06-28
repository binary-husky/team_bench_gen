"""
Compare SimHash (cosine) vs MinHash (Jaccard) on the same corpus of random
sparse binary feature vectors / sets.

Fixed settings:
  - universe size D = 2^14 = 16384 (feature id space)
  - vector/set size n = 256 active features per vector
  - number of vectors N = 500
  - SimHash bits b = 256 (256 random hyperplanes)
  - MinHash: same number of hashes = 256
  - random seed = 42
Independent variable: the estimator (SimHash vs MinHash).

For every pair we compute:
  - true cosine  = |A∩B| / sqrt(|A|*|B|)        (|A|=|B|=n -> = |A∩B|/n)
  - true Jaccard = |A∩B| / |A∪B|
  - SimHash-estimated cosine  (via cos(pi * hamming/b) and linear 1-2*hamming/b)
  - MinHash-estimated Jaccard (datasketch MinHash)
Errors = |estimate - truth|.
"""

import numpy as np
# MinHash is implemented manually below (no datasketch dependency needed).

# ---------------- fixed settings ----------------
SEED = 42
D = 1 << 14          # 16384 universe of feature ids
N = 500              # number of vectors
NSET = 256           # active features per vector
B = 256              # SimHash bits == MinHash num_perm
rng = np.random.default_rng(SEED)

# ---------------- generate corpus ----------------
# Each vector: NSET distinct feature ids in [0, D)
sets = []
for i in range(N):
    s = rng.choice(D, size=NSET, replace=False)
    sets.append(set(int(x) for x in s))

# Build (N x D) sparse-ish binary matrix for dot products. D=16384, N=500 -> 8.2M
# entries, fine in memory as float32 (~33MB).
mat = np.zeros((N, D), dtype=np.float32)
for i, s in enumerate(sets):
    idx = np.fromiter(s, dtype=np.int64)
    mat[i, idx] = 1.0

# ---------------- ground truth similarities ----------------
inter = mat @ mat.T            # |A∩B| since binary
inter = np.array(inter, dtype=np.float64)
sizes = np.array([len(s) for s in sets], dtype=np.float64)
# cosine = |A∩B| / sqrt(|A||B|) ; here |A|=|B|=NSET
cos_true = inter / NSET
# Jaccard = |A∩B| / |A∪B| = |A∩B| / (|A|+|B|-|A∩B|)
union = (sizes[:, None] + sizes[None, :] - inter)
jac_true = inter / union
np.fill_diagonal(cos_true, 1.0)
np.fill_diagonal(jac_true, 1.0)

# ---------------- SimHash (Charikar 2002) ----------------
# b random hyperplanes drawn from N(0,1). Hash bit = sign(v . plane).
planes = rng.standard_normal((D, B))                 # (D, B)
proj = mat @ planes                                  # (N, B)
simhash_bits = (proj > 0).astype(np.uint8)           # (N, B)

# pairwise hamming distance (fraction of differing bits)
# compute via matrix of XOR counts
# hamming[i,j] = sum_k (bits[i,k] != bits[j,k])
# efficient: hamming = B - (bits @ bits.T + (1-bits)@(1-bits).T)
bmat = simhash_bits.astype(np.float32)
agree = bmat @ bmat.T + (1 - bmat) @ (1 - bmat).T
ham = (B - np.array(agree, dtype=np.float64))   # number of differing bits
ham_frac = ham / B

# SimHash cosine estimate (MLE / principled): angle = pi * ham_frac
cos_est_princ = np.cos(np.pi * ham_frac)
# SimHash cosine estimate (linear Charikar form): 1 - 2*ham_frac
cos_est_lin = 1.0 - 2.0 * ham_frac
np.fill_diagonal(cos_est_princ, 1.0)
np.fill_diagonal(cos_est_lin, 1.0)

# ---------------- MinHash (Jaccard) ----------------
# Build minhash signatures manually for speed with shared permutation via
# numpy: for each permutation, the min hash over active ids.
# Use B permutations of range(D). signature[i,k] = min perm_k over set i.
signatures = np.full((N, B), D, dtype=np.int64)  # D = "infinity"
for k in range(B):
    perm = rng.permutation(D)   # perm[orig_id] = rank
    # For each set, min rank among its members
    for i in range(N):
        idx = np.fromiter(sets[i], dtype=np.int64)
        signatures[i, k] = perm[idx].min()

# Jaccard estimate = fraction of equal signature columns
sig_eq = (signatures[:, None, :] == signatures[None, :, :]).sum(axis=2)
jac_est = sig_eq.astype(np.float64) / B
np.fill_diagonal(jac_est, 1.0)

# ---------------- errors (upper triangle, exclude diagonal) ----------------
iu = np.triu_indices(N, k=1)

cos_true_p = cos_true[iu]
cos_est_p  = cos_est_princ[iu]
cos_est_l  = cos_est_lin[iu]
jac_true_p = jac_true[iu]
jac_est_p  = jac_est[iu]

simhash_err = np.abs(cos_est_p - cos_true_p)      # principled cosine estimate
simhash_err_lin = np.abs(cos_est_l - cos_true_p) # linear cosine estimate
minhash_err  = np.abs(jac_est_p - jac_true_p)

def stats(a):
    return dict(mean=float(a.mean()), median=float(np.median(a)),
                p95=float(np.percentile(a, 95)), max=float(a.max()),
                std=float(a.std()))

print("=== Fixed settings ===")
print(f"universe D={D}, N={N} vectors, set size={NSET}, "
      f"SimHash bits B={B}, MinHash perms={B}, seed={SEED}")
print(f"pairs evaluated = {len(iu[0])}")

print("\n=== True similarity distribution (pairs) ===")
print(f"cosine  true: mean={cos_true_p.mean():.4f} "
      f"min={cos_true_p.min():.4f} max={cos_true_p.max():.4f}")
print(f"jaccard true: mean={jac_true_p.mean():.4f} "
      f"min={jac_true_p.min():.4f} max={jac_true_p.max():.4f}")

print("\n=== SimHash error on cosine (estimate cos(pi*H/B)) ===")
print(stats(simhash_err))
print("=== SimHash error on cosine (linear 1-2H/B) ===")
print(stats(simhash_err_lin))
print("=== MinHash error on Jaccard ===")
print(stats(minhash_err))

print("\n=== Aggregate comparison ===")
print(f"SimHash MAE (cosine, principled) = {simhash_err.mean():.5f}")
print(f"SimHash MAE (cosine, linear)     = {simhash_err_lin.mean():.5f}")
print(f"MinHash MAE (jaccard)            = {minhash_err.mean():.5f}")

# Numerical difference on the same pair: estimate values themselves
# (note: different metrics, but the task wants to highlight they differ numerically)
diff_est = np.abs(cos_est_p - jac_est_p)
print("\n=== |SimHash-cos-est - MinHash-jac-est| on same pairs ===")
print(stats(diff_est))
print(f"pairs where they differ by > 0.01: {(diff_est>0.01).sum()} / {len(diff_est)}")

# Correlation between the two estimates and their truths
corr_est = np.corrcoef(cos_est_p, jac_est_p)[0,1]
print(f"\nPearson corr(SimHash-cos-est, MinHash-jac-est) = {corr_est:.4f}")
corr_truth = np.corrcoef(cos_true_p, jac_true_p)[0,1]
print(f"Pearson corr(cos-true, jac-true) = {corr_truth:.4f}")

# Relationship: for sets of equal size, jaccard = cos^2 / (2 - cos^2)?
# With |A|=|B|: jac = i/(2n-i), cos = i/n  =>  i = cos*n ; jac = cos*n/(2n-cos*n)=cos/(2-cos)
# Verify
jac_from_cos = cos_true_p / (2 - cos_true_p)
print(f"\nmax |jac_true - cos/(2-cos)| = {np.max(np.abs(jac_true_p-jac_from_cos)):.2e} "
      "(sanity: for equal-size sets jac=cos/(2-cos))")

# Save a few example pairs
print("\n=== Sample pairs (first 8) ===")
print("i  j | cosT cosE princ | cosE lin | jacT jacE")
for k in range(8):
    i,j = iu[0][k], iu[1][k]
    print(f"{i:3d}{j:4d} | {cos_true_p[k]:.3f} {cos_est_p[k]:.3f} | "
          f"{cos_est_l[k]:.3f} | {jac_true_p[k]:.3f} {jac_est_p[k]:.3f}")

# Persist numbers for the summary
import json
out = dict(
    settings=dict(D=D, N=N, NSET=NSET, B=B, seed=SEED, pairs=int(len(iu[0]))),
    truth=dict(cos_mean=float(cos_true_p.mean()), cos_min=float(cos_true_p.min()),
               cos_max=float(cos_true_p.max()),
               jac_mean=float(jac_true_p.mean()), jac_min=float(jac_true_p.min()),
               jac_max=float(jac_true_p.max())),
    simhash_princ=stats(simhash_err),
    simhash_linear=stats(simhash_err_lin),
    minhash=stats(minhash_err),
    diff_est=stats(diff_est),
    diff_est_gt001=int((diff_est>0.01).sum()),
    corr_est=float(corr_est), corr_truth=float(corr_truth),
)
with open("results.json","w") as f:
    json.dump(out, f, indent=2)
print("\nwrote results.json")
