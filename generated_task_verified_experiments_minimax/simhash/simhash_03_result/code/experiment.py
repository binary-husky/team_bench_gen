"""
SimHash + Hamming-threshold near-duplicate detection experiment.

Fixed settings:
  - d = 100  (vector dimension)
  - b = 256  (number of SimHash bits)
  - corpus size, random seed, perturbation strength
Sweep:
  - Hamming threshold T (the only independent variable)
Outputs:
  - ./results.npz with the per-T precision/recall curve
  - ./summary_near_duplicate.md with a write-up of the curve
"""

import numpy as np

# ----------------------------- fixed settings ------------------------------- #
SEED       = 42          # master seed; everything is reproducible from here
D          = 100         # vector dimension
B          = 256         # SimHash bit-width
N_PAIRS    = 150         # number of true near-duplicate pairs
N_DECOY    = 300         # additional unrelated vectors (low cosine similarity)
COS_TARGET = 0.95        # cosine similarity target between a base and its dup
T_MIN, T_MAX = 0, 160    # sweep range for the Hamming threshold T


def popcount_uint64(x: np.ndarray) -> np.ndarray:
    """SWAR popcount on a uint64 ndarray (vectorised)."""
    x = x - ((x >> 1) & np.uint64(0x5555555555555555))
    x = (x & np.uint64(0x3333333333333333)) + ((x >> 2) & np.uint64(0x3333333333333333))
    x = (x + (x >> 4)) & np.uint64(0x0F0F0F0F0F0F0F0F)
    return (x * np.uint64(0x0101010101010101)) >> np.uint64(56)


def build_corpus(rng: np.random.Generator):
    """Build the corpus of unit vectors and return the ground-truth pair set.

    Layout of returned `vectors`:
      [base_0, dup_0, base_1, dup_1, ..., base_{N-1}, dup_{N-1}, decoy_0, ..., decoy_{M-1}]
    where (base_k, dup_k) is a true near-duplicate pair (cosine == COS_TARGET)
    and every decoy is a random independent unit vector.
    """
    vectors = []

    for k in range(N_PAIRS):
        # base vector on the unit sphere
        base = rng.standard_normal(D)
        base /= np.linalg.norm(base)

        # random orthogonal direction (Gram-Schmidt against base)
        p = rng.standard_normal(D)
        p -= np.dot(p, base) * base
        p /= np.linalg.norm(p)

        # convex combination that yields exactly cos(v_new, base) == COS_TARGET
        dup = COS_TARGET * base + np.sqrt(1.0 - COS_TARGET ** 2) * p
        # dup already has unit norm because base ⟂ p and both have unit norm

        vectors.append(base)
        vectors.append(dup)

    for _ in range(N_DECOY):
        v = rng.standard_normal(D)
        v /= np.linalg.norm(v)
        vectors.append(v)

    return np.asarray(vectors, dtype=np.float64)


def simhash_bits(vectors: np.ndarray, hyperplanes: np.ndarray) -> np.ndarray:
    """Charikar-style random-hyperplane SimHash. Returns an (N, B) int8 array."""
    proj = vectors @ hyperplanes.T            # (N, B)
    return (proj >= 0).astype(np.int8)


def pack_bits(bits: np.ndarray) -> np.ndarray:
    """Pack B bits per row into ceil(B/64) uint64 words."""
    n, b = bits.shape
    n_words = (b + 63) // 64
    out = np.zeros((n, n_words), dtype=np.uint64)
    for k in range(b):
        w, r = divmod(k, 64)
        out[:, w] |= bits[:, k].astype(np.uint64) << np.uint64(r)
    return out


def pairwise_hamming(packed: np.ndarray) -> np.ndarray:
    """Return an (N, N) symmetric matrix of Hamming distances."""
    n = packed.shape[0]
    h = np.zeros((n, n), dtype=np.uint16)
    for w in range(packed.shape[1]):
        # Broadcasted XOR over the whole matrix; popcount is vectorised.
        xor = packed[:, w][:, None] ^ packed[:, w][None, :]
        h += popcount_uint64(xor).astype(np.uint16)
    return h


def main():
    rng = np.random.default_rng(SEED)

    # ---- 1. corpus ---------------------------------------------------------
    vectors = build_corpus(rng)
    N = vectors.shape[0]
    n_total = N
    n_true_pairs = N_PAIRS

    # Ground-truth: pair (2k, 2k+1) for k in [0, N_PAIRS).
    # Pair index r maps to (i, j) via the upper-triangle indexing.
    iu, ju = np.triu_indices(N, k=1)
    true_mask = np.zeros(iu.size, dtype=bool)
    for k in range(N_PAIRS):
        a, b = 2 * k, 2 * k + 1
        true_mask |= (iu == a) & (ju == b)

    # Sanity-check the corpus: cosine between true pairs should be ~0.95
    # and decoy-decoy cosine should be ~0.
    base_vecs = vectors[0:2 * N_PAIRS:2]
    dup_vecs  = vectors[1:2 * N_PAIRS:2]
    pos_cos = np.einsum("ij,ij->i", base_vecs, dup_vecs)
    decoy_cos_sample = []
    rng2 = np.random.default_rng(SEED + 1)  # independent sample for QC
    idx_a = rng2.integers(2 * N_PAIRS, N, size=2000)
    idx_b = rng2.integers(2 * N_PAIRS, N, size=2000)
    keep = idx_a != idx_b
    idx_a, idx_b = idx_a[keep], idx_b[keep]
    decoy_cos_sample = np.einsum("ij,ij->i", vectors[idx_a], vectors[idx_b])

    print(f"N vectors            : {N}")
    print(f"true near-dup pairs  : {N_PAIRS}")
    print(f"decoy vectors        : {N_DECOY}")
    print(f"cos(base, dup) mean  : {pos_cos.mean():.4f}  (target {COS_TARGET})")
    print(f"cos(decoy, decoy)    : mean={decoy_cos_sample.mean():.4f}  "
          f"std={decoy_cos_sample.std():.4f}")
    print(f"total candidate pairs: {iu.size}")

    # ---- 2. SimHash --------------------------------------------------------
    hyperplanes = rng.standard_normal((B, D))
    bits = simhash_bits(vectors, hyperplanes)
    packed = pack_bits(bits)

    # ---- 3. pairwise Hamming distances ------------------------------------
    H = pairwise_hamming(packed)
    hamming_pairs = H[iu, ju]                  # length N*(N-1)/2

    # ---- 4. sweep threshold T ---------------------------------------------
    records = []
    for T in range(T_MIN, T_MAX + 1):
        pred_pos = hamming_pairs <= T
        tp = int(np.sum(pred_pos & true_mask))
        fp = int(np.sum(pred_pos & ~true_mask))
        fn = int(np.sum(~pred_pos & true_mask))

        precision = tp / (tp + fp) if (tp + fp) else 1.0
        recall    = tp / (tp + fn) if (tp + fn) else 0.0
        f1        = (2 * precision * recall / (precision + recall)
                     if (precision + recall) else 0.0)

        records.append((T, tp, fp, fn, precision, recall, f1))

    # ---- 5. save + print ---------------------------------------------------
    arr = np.array(records, dtype=np.float64)
    np.savez("results.npz",
             records=arr,
             pos_cos_mean=float(pos_cos.mean()),
             pos_cos_std=float(pos_cos.std()),
             decoy_cos_mean=float(decoy_cos_sample.mean()),
             decoy_cos_std=float(decoy_cos_sample.std()),
             n=N, n_true_pairs=N_PAIRS, n_decoy=N_DECOY,
             d=D, b=B, seed=SEED, cos_target=COS_TARGET)
    print("\nT    TP    FP    FN   precision  recall    F1")
    for T, tp, fp, fn, p, r, f1 in records:
        print(f"{T:3d}  {tp:4d}  {fp:5d}  {fn:4d}   {p:7.4f}   {r:7.4f}  {f1:7.4f}")


if __name__ == "__main__":
    main()
