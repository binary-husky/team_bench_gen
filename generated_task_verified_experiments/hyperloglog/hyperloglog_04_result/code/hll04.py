"""
Reproduce HyperLogLog (FlFuGaMe07) and compare two estimators on the same
registers:
  (A) raw       = alpha_m * m^2 * (sum_j 2^{-M[j]})^{-1}   (no range correction)
  (B) corrected = linear counting when E_raw <= 2.5*m and V>0, else E_raw

Goal: characterize raw estimator bias for n ≲ 2.5*m and verify linear-counting
correction removes it.

Fixed setup: p=10 (m=1024), threshold 2.5*m = 2560.
n grid: {100,500,1000,1500,2000,2560,3500,5000,8000}
>=5 seeds per n. Record signed relative error (E-n)/n for both estimators.
CPU only.
"""

import numpy as np
import math

# ---------- hashing ----------
# Use a 64-bit hash. We mix a 64-bit splitmix64-style finalizer over a seed
# and an index so that distinct (seed, item) pairs give independent-looking
# 64-bit hashes. splitmix64 is a good, dependency-free 64-bit mixing function.

def splitmix64(x):
    # x: uint64 (python int). returns uint64.
    x = (x + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    x = x ^ (x >> 31)
    return x & 0xFFFFFFFFFFFFFFFF

def make_hash(seed):
    # returns a function idx -> 64-bit hash
    def h(i):
        return splitmix64((seed * 0x100000001b3 + (i & 0xFFFFFFFFFFFFFFFF)) & 0xFFFFFFFFFFFFFFFF)
    return h

# ---------- HLL core ----------
def alpha_m(m):
    # standard bias-correction constant from the paper
    if m == 16:
        return 0.673
    if m == 32:
        return 0.697
    if m == 64:
        return 0.709
    # m >= 128
    return 0.7213 / (1.0 + 1.079 / m)

def compute_registers(n_items, p, seed):
    """Build HLL registers M[0..m-1] from n_items distinct items."""
    m = 1 << p
    M = np.zeros(m, dtype=np.int32)
    # 64-bit hash via vectorized splitmix64 over (seed*MULT + idx), uint64.
    MULT = np.uint64(0x100000001b3)
    SEED = np.uint64(seed)
    idx = np.arange(n_items, dtype=np.uint64)
    x = idx * MULT + SEED  # uint64 arithmetic, wraps mod 2^64
    x = x + np.uint64(0x9E3779B97F4A7C15)
    x = x ^ (x >> np.uint64(30))
    x = x * np.uint64(0xBF58476D1CE4E5B9)
    x = x ^ (x >> np.uint64(27))
    x = x * np.uint64(0x94D049BB133111EB)
    x = x ^ (x >> np.uint64(31))
    hashes = x  # uint64

    # register index = top p bits
    reg_idx = (hashes >> np.uint64(64 - p)).astype(np.int64)
    # remaining (64-p)-bit field; rho = (#leading zeros in field) + 1.
    w = 64 - p
    rem = hashes & np.uint64((1 << w) - 1)
    # bit_length per element via object dtype (n small, fine)
    a = rem.astype(object)
    bl = np.fromiter((int(v).bit_length() for v in a), dtype=np.int32, count=len(a))
    rho = (w + 1 - bl).astype(np.int32)  # in [1, w+1]
    np.maximum.at(M, reg_idx, rho)
    return M

def estimate_raw(M, p):
    m = 1 << p
    a = alpha_m(m)
    s = np.sum(np.power(2.0, -M.astype(np.float64)))
    E = a * (m * m) / s
    return E

def estimate_corrected(M, p):
    m = 1 << p
    E_raw = estimate_raw(M, p)
    V = int(np.count_nonzero(M == 0))
    if E_raw <= 2.5 * m and V > 0:
        return m * math.log(m / V)
    return E_raw

# ---------- experiment ----------
def main():
    p = 10
    m = 1 << p
    threshold = 2.5 * m
    n_grid = [100, 500, 1000, 1500, 2000, 2560, 3500, 5000, 8000]
    seeds = [1, 2, 3, 4, 5, 6, 7, 8]  # >=5 seeds

    rows = []
    for n in n_grid:
        raw_errs = []
        cor_errs = []
        V_count = 0
        lc_count = 0
        for s in seeds:
            M = compute_registers(n, p, s)
            Er = estimate_raw(M, p)
            Ec = estimate_corrected(M, p)
            raw_errs.append((Er - n) / n)
            cor_errs.append((Ec - n) / n)
            V = int(np.count_nonzero(M == 0))
            if V > 0:
                V_count += 1
            if Er <= threshold and V > 0:
                lc_count += 1
        raw_errs = np.array(raw_errs)
        cor_errs = np.array(cor_errs)
        rows.append(dict(
            n=n,
            raw_mean=raw_errs.mean(), raw_std=raw_errs.std(ddof=1),
            cor_mean=cor_errs.mean(), cor_std=cor_errs.std(ddof=1),
            lc_activated=lc_count, n_seeds=len(seeds),
        ))

    # print table
    print(f"m={m}  2.5*m={threshold}  seeds={len(seeds)}")
    print(f"{'n':>6} | {'raw mean±std (rel)':>26} | {'corr mean±std (rel)':>26} | LC-on")
    print("-"*80)
    for r in rows:
        print(f"{r['n']:>6} | {r['raw_mean']*100:+8.2f}% ± {r['raw_std']*100:6.2f}% | "
              f"{r['cor_mean']*100:+8.2f}% ± {r['cor_std']*100:6.2f}% | {r['lc_activated']}/{r['n_seeds']}")

    # save to npz for the summary writer
    np.savez("hll04_results.npz",
             n_grid=np.array(n_grid),
             raw_mean=np.array([r['raw_mean'] for r in rows]),
             raw_std=np.array([r['raw_std'] for r in rows]),
             cor_mean=np.array([r['cor_mean'] for r in rows]),
             cor_std=np.array([r['cor_std'] for r in rows]),
             lc_activated=np.array([r['lc_activated'] for r in rows]),
             m=m, threshold=threshold, n_seeds=len(seeds))
    print("saved hll04_results.npz")

if __name__ == "__main__":
    main()
