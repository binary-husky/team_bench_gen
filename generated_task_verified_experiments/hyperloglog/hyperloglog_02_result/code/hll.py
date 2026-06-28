"""
HyperLogLog (Flajolet-Fusy-Gandouet-Meunier 2007) reproduction.

Implements the full §4 estimation pipeline:
  - raw estimator  E = alpha_m * m^2 / Z ,  Z = sum_j 2^{-M[j]}
  - small-range linear-counting correction  (E <= 5/2 * m  and  V != 0)
  - large-range correction                  (E >  2^32 / 30)
  - mid-range: leave raw E as-is

64-bit hash via mmh3.hash64 (unsigned). p=14 -> m=2^14=16384 registers.
"""
import math
import numpy as np
import mmh3

P = 14
M_REG = 1 << P                     # 16384
ALPHA = 0.7213 / (1.0 + 1.079 / M_REG)   # paper eq. for m >= 128
B = 64 - P                         # width of the "w" window
TW32 = float(1 << 32)             # 2^32 (paper assumes 32-bit hash space)
MASK_W = (1 << B) - 1
MASK_IDX = M_REG - 1


def _hash_stream(items):
    """Return uint64 array of mmh3 hashes for a list of string items."""
    n = len(items)
    out = np.empty(n, dtype=np.uint64)
    for i, it in enumerate(items):
        out[i] = mmh3.hash64(it, signed=False)[0]
    return out


def _hash_stream_np(seed, n):
    """n distinct items 'seed:i' hashed with mmh3 -> uint64 array."""
    # build strings in python; mmh3 needs bytes/str
    items = [f"{seed}:{i}" for i in range(n)]
    return _hash_stream(items)


def estimate_from_hashes(h):
    """Run full HLL pipeline on a uint64 hash array -> cardinality estimate."""
    h = h.astype(np.uint64)
    # register index = top p bits
    idx = (h >> B).astype(np.uint64) & MASK_IDX
    # window w = low (64-p) bits
    w = (h & MASK_W).astype(np.uint64)

    # rho = position of leftmost 1 in w (1-indexed from the MSB of the B-bit window)
    # floor(log2(w)) = index k of highest set bit (0 = LSB). rho = B - k.
    nonzero = w > 0
    # compute k via bit_length using numpy: use np.log2 then correct
    k = np.zeros(len(w), dtype=np.int32)
    nz = w[nonzero]
    k_nz = np.floor(np.log2(nz.astype(np.float64))).astype(np.int32)
    # guard tiny float errors
    k[nonzero] = k_nz
    rho = (B - k).astype(np.int32)
    # if w==0 (vanishingly rare), set rho to B
    rho[~nonzero] = B
    rho = np.clip(rho, 0, B).astype(np.int32)

    M = np.zeros(M_REG, dtype=np.int32)
    # scatter-max
    np.maximum.at(M, idx, rho)

    # raw estimate
    # Z = sum 2^{-M[j]}
    # use 2.0**(-M) carefully
    Z = np.sum(np.power(2.0, -M.astype(np.float64)))
    E = ALPHA * (M_REG * M_REG) / Z

    V = int(np.count_nonzero(M == 0))
    if E <= 2.5 * M_REG and V != 0:
        E_star = M_REG * math.log(M_REG / V)        # linear counting
    elif E <= TW32 / 30.0:
        E_star = E                                   # mid range
    else:
        E_star = -TW32 * math.log(1.0 - E / TW32)   # large range
    return E_star, V, E


def run_one(seed, n):
    h = _hash_stream_np(seed, n)
    est, V, E_raw = estimate_from_hashes(h)
    return est


if __name__ == "__main__":
    import time
    seeds = [1, 2, 3, 4, 5, 7, 11]
    ns = [1e3, 5e3, 1e4, 5e4, 1e5, 5e5, 1e6]
    ns = [int(x) for x in ns]
    rows = []
    t0 = time.time()
    for n in ns:
        rels = []
        for s in seeds:
            est = run_one(s, n)
            rel = abs(est - n) / n
            rels.append(rel)
            print(f"n={n:>8d} seed={s:>3d}  est={est:12.1f}  rel_err={rel*100:6.3f}%")
        arr = np.array(rels)
        rows.append((n, arr.mean(), arr.std()))
    print("total time", round(time.time()-t0, 1), "s")
    print("\nsummary:")
    print(f"{'n':>10} {'mean_rel%':>10} {'std_rel%':>10}")
    for n, mu, sd in rows:
        print(f"{n:>10d} {mu*100:10.3f} {sd*100:10.3f}")
    # save
    np.save("results.npy", np.array(rows, dtype=object), allow_pickle=True)
