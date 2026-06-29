"""
Compare SimHash (cosine) vs MinHash (Jaccard) on the same random sparse binary sets.

We fix:
  * corpus: N random sparse binary sets over a universe of size U
  * set size K (number of 1s per set)
  * signature size b = 256 (same for both estimators)
  * random seed

Independent variable: the estimator.

For every pair (A, B) we compute
  * true cosine = |A∩B| / sqrt(|A||B|)        (Charikar 2002 §3 angle relation)
  * true Jaccard = |A∩B| / |A∪B|             (Broder et al. min-wise permutation)
  * SimHash estimate of cosine using b random hyperplanes (random hyperplane LSH).
    P[h(A)=h(B)] = 1 - θ(A,B)/π  ->  estimated θ̂ = π(1 - f)  ->  estimated cos = cos(θ̂)
  * MinHash estimate of Jaccard using b hash functions of form (a·x + b) mod p
    P[h(A)=h(B)] = Jaccard(A,B)  ->  estimated Jaccard = fraction of matching mins

We use TWO families of pairs to probe both ends of the similarity spectrum:
  (i)  "random" pairs — both sets drawn independently (low overlap, near-orthogonal).
  (ii) "controlled-overlap" pairs — second set constructed to share a target fraction
       of elements with the first.
"""

import json
import os
import numpy as np
from itertools import combinations

# -----------------------------------------------------------------------------
# Fixed experimental settings (per task spec)
# -----------------------------------------------------------------------------
SEED         = 20260528      # reproducible random seed
N_SETS       = 400           # how many random sparse binary sets
UNIVERSE     = 20_000        # size of the universe U (large => sparse)
K            = 120           # number of 1s in each set
B            = 256           # signature size (bits for SimHash, hash count for MinHash)
PRIME        = (1 << 61) - 1 # large Mersenne prime for MinHash linear hashing
N_RANDOM_PAIRS  = 4000
N_PER_OVERLAP   = 800        # pairs per controlled overlap level

# Overlap levels for the second family of pairs (intersection fraction of K)
OVERLAP_LEVELS = [0.10, 0.20, 0.30, 0.50, 0.70, 0.90]

rng = np.random.default_rng(SEED)

# -----------------------------------------------------------------------------
# 1. Generate random sparse binary sets (corpus)
# -----------------------------------------------------------------------------
sets = []   # list[set[int]]
for _ in range(N_SETS):
    s = set(rng.choice(UNIVERSE, size=K, replace=False).tolist())
    sets.append(s)
print(f"Generated {N_SETS} random sets of size {K} in universe of size {UNIVERSE}.")

# -----------------------------------------------------------------------------
# 2. Build two families of pairs
# -----------------------------------------------------------------------------
# (i) random pairs
all_pairs = list(combinations(range(N_SETS), 2))
rng_pick  = np.random.default_rng(SEED + 3)
idxs = rng_pick.choice(len(all_pairs), size=N_RANDOM_PAIRS, replace=False)
random_pairs = [all_pairs[k] for k in idxs]

# (ii) controlled-overlap pairs: choose first set, then build second with target overlap
controlled_pairs = []  # each entry: (A, B, overlap_target)
rng_ov = np.random.default_rng(SEED + 4)
for ovl_frac in OVERLAP_LEVELS:
    n_overlap = int(round(ovl_frac * K))
    for _ in range(N_PER_OVERLAP):
        # pick a random base set
        i = int(rng_ov.integers(0, N_SETS))
        A = sets[i]
        # intersection of size n_overlap
        common = list(rng_ov.choice(list(A), size=n_overlap, replace=False))
        # the rest of B is n_overlap .. K drawn fresh (avoid duplicating A∩B)
        remaining_pool = np.setdiff1d(np.arange(UNIVERSE), list(A), assume_unique=False)
        new_choices = rng_ov.choice(remaining_pool, size=K - n_overlap, replace=False)
        Bset = set(common) | set(new_choices.tolist())
        controlled_pairs.append((A, Bset, ovl_frac))

print(f"random pairs: {len(random_pairs)}, controlled pairs: {len(controlled_pairs)}")

# -----------------------------------------------------------------------------
# 3. SimHash — random hyperplane LSH (Charikar 2002, §3)
# -----------------------------------------------------------------------------
rng_sim = np.random.default_rng(SEED + 1)
hyperplanes = rng_sim.standard_normal(size=(B, UNIVERSE)).astype(np.float32)
hyperplanes /= np.linalg.norm(hyperplanes, axis=1, keepdims=True)

# Build indicator vectors for the *corpus* sets (vectorised dot product).
indicator = np.zeros((N_SETS, UNIVERSE), dtype=np.float32)
for i, s in enumerate(sets):
    indicator[i, list(s)] = 1.0

print("Computing SimHash signatures for corpus...")
sh_corpus = (indicator @ hyperplanes.T >= 0).astype(np.int8)   # (N_SETS, B)

# Hash the controlled-pair "B" sets on the fly
def simhash_arbitrary(s):
    v = np.zeros(UNIVERSE, dtype=np.float32)
    v[list(s)] = 1.0
    return (hyperplanes @ v >= 0).astype(np.int8)
print("  done.")

# -----------------------------------------------------------------------------
# 4. MinHash
# -----------------------------------------------------------------------------
rng_mh = np.random.default_rng(SEED + 2)
a_coeffs = rng_mh.integers(1, PRIME, size=B, dtype=np.int64)
b_coeffs = rng_mh.integers(0, PRIME, size=B, dtype=np.int64)

def minhash_signature(s):
    elems = np.fromiter(s, dtype=np.int64, count=len(s))
    hv = (a_coeffs[:, None] * elems[None, :] + b_coeffs[:, None]) % PRIME
    return hv.min(axis=1)

print("Computing MinHash signatures for corpus...")
mh_corpus = np.stack([minhash_signature(s) for s in sets])
print("  done.")

# -----------------------------------------------------------------------------
# 5. Evaluate every pair
# -----------------------------------------------------------------------------
def evaluate(sigA, sigB, sA, sB):
    inter = len(sA & sB)
    sA_n, sB_n = len(sA), len(sB)
    uni  = sA_n + sB_n - inter
    c_t  = inter / np.sqrt(sA_n * sB_n) if sA_n and sB_n else 0.0
    j_t  = inter / uni if uni > 0 else 0.0

    f_sh = float(np.mean(sigA == sigB))
    f_sh_clip = min(max(f_sh, 1e-6), 1 - 1e-6)
    theta_hat  = np.pi * (1.0 - f_sh_clip)
    c_e = float(np.cos(theta_hat))

    return c_t, j_t, c_e, f_sh

records = []   # list of dicts (one per pair)

print(f"Evaluating {len(random_pairs)} random pairs...")
for (i, j) in random_pairs:
    A, B = sets[i], sets[j]
    c_t, j_t, c_e, f_sh = evaluate(sh_corpus[i], sh_corpus[j],
                                    mh_corpus[i], mh_corpus[j], A, B) \
        if False else evaluate(  # we pass minhash signatures from the second slot
            sh_corpus[i], sh_corpus[j], A, B)
    # We need both the SimHash and MinHash match fractions; let's do it properly:
    f_sh = float(np.mean(sh_corpus[i] == sh_corpus[j]))
    f_mh = float(np.mean(mh_corpus[i] == mh_corpus[j]))
    c_t  = len(A & B) / np.sqrt(len(A) * len(B))
    j_t  = len(A & B) / (len(A) + len(B) - len(A & B))
    c_e  = float(np.cos(np.pi * (1.0 - min(max(f_sh, 1e-6), 1-1e-6))))
    records.append(dict(kind="random", i=int(i), j=int(j), ovl=None,
                        c_t=c_t, j_t=j_t, c_e=c_e, j_e=f_mh,
                        f_sh=f_sh, f_mh=f_mh))

print(f"Evaluating {len(controlled_pairs)} controlled-overlap pairs...")
for pair_idx, (A, Bset, ovl) in enumerate(controlled_pairs):
    sh_A = simhash_arbitrary(A)
    sh_B = simhash_arbitrary(Bset)
    mh_A = minhash_signature(A)
    mh_B = minhash_signature(Bset)
    f_sh = float(np.mean(sh_A == sh_B))
    f_mh = float(np.mean(mh_A == mh_B))
    c_t  = len(A & Bset) / np.sqrt(len(A) * len(Bset))
    j_t  = len(A & Bset) / (len(A) + len(Bset) - len(A & Bset))
    c_e  = float(np.cos(np.pi * (1.0 - min(max(f_sh, 1e-6), 1-1e-6))))
    records.append(dict(kind="controlled", i=-1, j=-1, ovl=ovl,
                        c_t=c_t, j_t=j_t, c_e=c_e, j_e=f_mh,
                        f_sh=f_sh, f_mh=f_mh))

print(f"Total pairs evaluated: {len(records)}")

# -----------------------------------------------------------------------------
# 6. Aggregate: overall errors, per-overlap errors, and per-similarity buckets
# -----------------------------------------------------------------------------
c_t   = np.array([r["c_t"] for r in records])
j_t   = np.array([r["j_t"] for r in records])
c_e   = np.array([r["c_e"] for r in records])
j_e   = np.array([r["j_e"] for r in records])
sh_err = np.abs(c_e - c_t)
mh_err = np.abs(j_e - j_t)

def stats(name, err):
    return (f"{name:<28} mean={err.mean():.4f}  median={np.median(err):.4f}  "
            f"rmse={np.sqrt(np.mean(err**2)):.4f}  max={err.max():.4f}")

print("\n=== Overall errors (absolute, all pairs) ===")
print("  " + stats("SimHash cosine error",  sh_err))
print("  " + stats("MinHash Jaccard error", mh_err))

print("\n=== Errors by controlled overlap (overlap_frac -> |A∩B|/K) ===")
print(f"{'overlap':>8s}  {'n':>5s}  {'true_cos':>9s}  {'true_jac':>9s}  "
      f"{'simhash_err':>11s}  {'minhash_err':>11s}  {'cos_est':>8s}  {'jac_est':>8s}")
for ovl in OVERLAP_LEVELS:
    sel = np.array([r["ovl"] == ovl for r in records])
    if sel.sum() == 0: continue
    sub = np.where(sel)[0]
    print(f"{ovl:>8.2f}  {sel.sum():>5d}  "
          f"{c_t[sub].mean():>9.4f}  {j_t[sub].mean():>9.4f}  "
          f"{sh_err[sub].mean():>11.4f}  {mh_err[sub].mean():>11.4f}  "
          f"{c_e[sub].mean():>8.4f}  {j_e[sub].mean():>8.4f}")

# Bucket by true cosine to show behaviour across the full range
print("\n=== Errors bucketed by true cosine ===")
edges = [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.01]
for lo, hi in zip(edges[:-1], edges[1:]):
    m = (c_t >= lo) & (c_t < hi)
    if m.sum() == 0:
        continue
    print(f"  cos in [{lo:.2f},{hi:.2f}): n={m.sum():5d}  "
          f"true_cos={c_t[m].mean():.3f}  true_jac={j_t[m].mean():.3f}  "
          f"SimHash err={sh_err[m].mean():.4f}  MinHash err={mh_err[m].mean():.4f}  "
          f"cos_est={c_e[m].mean():.3f}  jac_est={j_e[m].mean():.3f}")

# -----------------------------------------------------------------------------
# 7. Show that on the *same* pair, the two estimators produce *different numbers*
# -----------------------------------------------------------------------------
abs_diff = np.abs(c_e - j_e)
print(f"\n=== Estimator values differ on the same pair ===")
print(f"  mean |cos_est - jac_est|                   : {abs_diff.mean():.4f}")
print(f"  median |cos_est - jac_est|                 : {np.median(abs_diff):.4f}")
print(f"  max |cos_est - jac_est|                    : {abs_diff.max():.4f}")
print(f"  fraction of pairs with cos_est == jac_est  : {np.mean(c_e == j_e):.6f}")
print(f"  mean true_cos = {c_t.mean():.4f},  true_jac = {j_t.mean():.4f}")
print(f"  Note: cos_est estimates *cosine*, jac_est estimates *Jaccard* — "
      f"different similarity functions.")

# -----------------------------------------------------------------------------
# 8. Save data
# -----------------------------------------------------------------------------
out_dir = os.path.dirname(__file__)
data_path = os.path.join(out_dir, "results.json")

def _to_jsonable(o):
    if isinstance(o, (np.integer,)):    return int(o)
    if isinstance(o, (np.floating,)):   return float(o)
    if isinstance(o, (np.ndarray,)):    return o.tolist()
    if isinstance(o, (set, frozenset)): return sorted(list(o))
    return repr(o)

payload = {
    "settings": {
        "seed": SEED, "N_sets": N_SETS, "universe": UNIVERSE,
        "K": K, "b": B, "n_random_pairs": N_RANDOM_PAIRS,
        "n_per_overlap": N_PER_OVERLAP, "overlap_levels": OVERLAP_LEVELS,
    },
    "overall": {
        "simhash_err_mean":  float(sh_err.mean()),
        "simhash_err_median":float(np.median(sh_err)),
        "simhash_err_rmse":  float(np.sqrt(np.mean(sh_err**2))),
        "simhash_err_max":   float(sh_err.max()),
        "minhash_err_mean":  float(mh_err.mean()),
        "minhash_err_median":float(np.median(mh_err)),
        "minhash_err_rmse":  float(np.sqrt(np.mean(mh_err**2))),
        "minhash_err_max":   float(mh_err.max()),
    },
    "estimators_differ": {
        "mean_abs_cos_est_minus_jac_est": float(abs_diff.mean()),
        "median_abs_diff":                float(np.median(abs_diff)),
        "max_abs_diff":                   float(abs_diff.max()),
        "frac_pairs_identical":            float(np.mean(c_e == j_e)),
        "true_cos_mean":                  float(c_t.mean()),
        "true_jac_mean":                  float(j_t.mean()),
    },
    "examples": [
        # one example per overlap level (plus a random pair)
        *[{
            "kind":     r["kind"],
            "ovl":      r.get("ovl"),
            "true_cos": r["c_t"],
            "true_jac": r["j_t"],
            "cos_est":  r["c_e"],
            "jac_est":  r["j_e"],
            "sh_err":   float(abs(r["c_e"] - r["c_t"])),
            "mh_err":   float(abs(r["j_e"] - r["j_t"])),
        } for r in records if r["kind"] == "random"][:4],
        *[{
            "kind":     r["kind"],
            "ovl":      r["ovl"],
            "true_cos": r["c_t"],
            "true_jac": r["j_t"],
            "cos_est":  r["c_e"],
            "jac_est":  r["j_e"],
            "sh_err":   float(abs(r["c_e"] - r["c_t"])),
            "mh_err":   float(abs(r["j_e"] - r["j_t"])),
        } for ovl in OVERLAP_LEVELS
          for r in records if r["kind"] == "controlled" and r["ovl"] == ovl][:6],
    ],
    # per-pair arrays
    "per_pair": {
        "kind":  [r["kind"] for r in records],
        "ovl":   [r.get("ovl") for r in records],
        "cos_true": c_t.tolist(),
        "jac_true": j_t.tolist(),
        "cos_est":  c_e.tolist(),
        "jac_est":  j_e.tolist(),
        "sh_err":   sh_err.tolist(),
        "mh_err":   mh_err.tolist(),
    },
}
with open(data_path, "w") as f:
    json.dump(payload, f, indent=2, default=_to_jsonable)
print(f"\nWrote {data_path}")
