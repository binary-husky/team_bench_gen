"""Extra statistics on the Hamming-distance distributions of the experiment."""

import numpy as np

data = np.load("results.npz", allow_pickle=False)
records = data["records"]

# Re-derive from the saved seed using the same recipe.
SEED       = 42
D          = 100
B          = 256
N_PAIRS    = 150
N_DECOY    = 300
COS_TARGET = 0.95


def popcount_uint64(x):
    x = x - ((x >> 1) & np.uint64(0x5555555555555555))
    x = (x & np.uint64(0x3333333333333333)) + ((x >> 2) & np.uint64(0x3333333333333333))
    x = (x + (x >> 4)) & np.uint64(0x0F0F0F0F0F0F0F0F)
    return (x * np.uint64(0x0101010101010101)) >> np.uint64(56)


def build_corpus(rng):
    vectors = []
    for _ in range(N_PAIRS):
        base = rng.standard_normal(D); base /= np.linalg.norm(base)
        p = rng.standard_normal(D)
        p -= np.dot(p, base) * base; p /= np.linalg.norm(p)
        dup = COS_TARGET * base + np.sqrt(1 - COS_TARGET ** 2) * p
        vectors.append(base); vectors.append(dup)
    for _ in range(N_DECOY):
        v = rng.standard_normal(D); v /= np.linalg.norm(v)
        vectors.append(v)
    return np.asarray(vectors)


def simhash(vectors, hyperplanes):
    return (vectors @ hyperplanes.T >= 0).astype(np.int8)


def pack(bits):
    n, b = bits.shape
    n_words = (b + 63) // 64
    out = np.zeros((n, n_words), dtype=np.uint64)
    for k in range(b):
        w, r = divmod(k, 64)
        out[:, w] |= bits[:, k].astype(np.uint64) << np.uint64(r)
    return out


def hamming(packed):
    n = packed.shape[0]
    h = np.zeros((n, n), dtype=np.uint16)
    for w in range(packed.shape[1]):
        xor = packed[:, w][:, None] ^ packed[:, w][None, :]
        h += popcount_uint64(xor).astype(np.uint16)
    return h


rng = np.random.default_rng(SEED)
vectors = build_corpus(rng)
hyperplanes = rng.standard_normal((B, D))
packed = pack(simhash(vectors, hyperplanes))
H = hamming(packed)
N = vectors.shape[0]

iu, ju = np.triu_indices(N, k=1)
is_true = np.zeros(iu.size, dtype=bool)
for k in range(N_PAIRS):
    is_true |= (iu == 2 * k) & (ju == 2 * k + 1)

pos = H[iu, ju][is_true]
neg = H[iu, ju][~is_true]

# Theoretical expected Hamming distance for a pair at angle theta, with b bits
# E[H] = b * theta / pi
theta_pos = np.arccos(COS_TARGET)
exp_pos = B * theta_pos / np.pi
# Two random unit vectors in d dims: expected cos ~ 0, std ~ 1/sqrt(d)
# So theta ~ pi/2, E[H] ~ b/2 = 128
exp_neg = B * 0.5

print("=== Hamming-distance distribution ===")
print(f"positive pairs (cos≈{COS_TARGET}):  n={pos.size:>6}  "
      f"mean={pos.mean():7.3f}  std={pos.std():6.3f}  "
      f"min={pos.min():3d}  max={pos.max():3d}  "
      f"theory E[H]={exp_pos:.3f}")
print(f"negative pairs (cos≈ 0)        :  n={neg.size:>6}  "
      f"mean={neg.mean():7.3f}  std={neg.std():6.3f}  "
      f"min={neg.min():3d}  max={neg.max():3d}  "
      f"theory E[H]={exp_neg:.3f}")
print(f"gap of means = {neg.mean() - pos.mean():.3f}")
print(f"effect size   = {(neg.mean() - pos.mean()) / np.sqrt((pos.std()**2 + neg.std()**2) / 2):.3f} std")

# Save clean slice for the markdown
np.savez("dist_stats.npz",
         pos_H=pos, neg_H=neg,
         exp_pos=exp_pos, exp_neg=exp_neg,
         pos_mean=pos.mean(), pos_std=pos.std(),
         neg_mean=neg.mean(), neg_std=neg.std(),
         pos_min=int(pos.min()), pos_max=int(pos.max()),
         neg_min=int(neg.min()), neg_max=int(neg.max()))
