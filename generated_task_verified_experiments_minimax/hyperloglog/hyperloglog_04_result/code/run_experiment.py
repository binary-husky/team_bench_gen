"""
HyperLogLog: comparing raw estimator vs. small-range (linear counting) corrected estimator.

Based on the paper "HyperLogLog: the analysis of a near-optimal cardinality estimation algorithm"
(Flajolet, Fusy, Gandouet, Meunier, 2007).

The script implements the HyperLogLog algorithm from scratch using a 64-bit splitmix64 hash,
runs both the raw estimator and the small-range corrected estimator over a grid of cardinalities
that straddle the 2.5*m threshold, and records signed relative error statistics.
"""
import numpy as np
import json
from pathlib import Path

# ---- Hash function: splitmix64 (a good 64-bit hash) ----------------------------
def splitmix64(x):
    """Apply the splitmix64 finalizer to a uint64 value (vectorized)."""
    x = x.astype(np.uint64)
    x = (x ^ (x >> np.uint64(30))) * np.uint64(0xbf58476d1ce4e5b9)
    x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94d049bb133111eb)
    x = x ^ (x >> np.uint64(31))
    return x


def generate_hashes(n: int, seed: int) -> np.ndarray:
    """Generate n deterministic 64-bit 'hash' values using a splitmix64 stream seeded by `seed`."""
    # Use a distinct seed-offset per seed so different seeds produce disjoint streams.
    state = np.uint64(seed) * np.uint64(0x9E3779B97F4A7C15) + np.uint64(0x123456789ABCDEF0)
    hashes = np.empty(n, dtype=np.uint64)
    for i in range(n):
        state = state + np.uint64(0x9E3779B97F4A7C15)
        hashes[i] = splitmix64(state)
    return hashes


# ---- HyperLogLog core ---------------------------------------------------------
def hll_compute(hashes: np.ndarray, p: int = 10):
    """Given an array of 64-bit hash values, run HyperLogLog.

    Returns (E_raw, E_corrected, V) where:
      - E_raw: alpha_m * m^2 / sum_j 2^(-M[j])        (no correction)
      - E_corrected: linear-counting-corrected version using V zero registers
                      if E_raw <= 2.5*m and V > 0, else same as E_raw
      - V: number of zero registers
    """
    m = 1 << p                  # number of registers = 1024
    num_bits = 64 - p           # remaining bits = 54

    # Split the hash: low p bits = register index, high (64-p) bits = rank source
    register_idx = (hashes & np.uint64(m - 1)).astype(np.int32)
    remaining = hashes >> np.uint64(p)

    # rho = position of leftmost 1-bit in `remaining` + 1 (1-indexed from MSB).
    # If `remaining` is 0, rho = num_bits + 1.
    rho = np.full(hashes.shape, num_bits + 1, dtype=np.int8)
    not_yet = np.ones(hashes.shape, dtype=bool)
    for k in range(num_bits):
        bit = np.uint64(1) << np.uint64(num_bits - 1 - k)
        is_set = (remaining & bit) != 0
        new_set = is_set & not_yet
        rho = np.where(new_set, k + 1, rho)
        not_yet = not_yet & ~new_set

    # Update registers: M[j] = max(M[j], rho)
    M = np.zeros(m, dtype=np.int8)
    np.maximum.at(M, register_idx, rho)

    # Raw estimator (eq. (3) in the paper, but without any corrections).
    # For m >= 128 the paper gives alpha_m = 0.7213 / (1 + 1.079/m); m=1024 is well above.
    alpha_m = 0.7213 / (1.0 + 1.079 / m)
    indicator_sum = float(np.sum(2.0 ** (-M.astype(np.float64))))
    E_raw = alpha_m * m * m / indicator_sum

    # Small-range correction (linear counting, paper section 4).
    V = int(np.sum(M == 0))
    threshold = 2.5 * m  # 2560 for m=1024
    if E_raw <= threshold and V > 0:
        E_corrected = m * np.log(m / V)
    else:
        E_corrected = E_raw

    return float(E_raw), float(E_corrected), V


# ---- Main experiment ----------------------------------------------------------
def main():
    p = 10
    m = 1 << p
    threshold = 2.5 * m

    n_grid = [100, 500, 1000, 1500, 2000, 2560, 3500, 5000, 8000]
    seeds = list(range(8))  # 8 seeds (>= 5 as required)

    rows = []
    for n in n_grid:
        raw_errors = []
        corr_errors = []
        V_list = []
        E_raw_list = []
        E_corr_list = []
        for seed in seeds:
            hashes = generate_hashes(n, seed)
            E_raw, E_corr, V = hll_compute(hashes, p=p)
            raw_errors.append((E_raw - n) / n)
            corr_errors.append((E_corr - n) / n)
            V_list.append(V)
            E_raw_list.append(E_raw)
            E_corr_list.append(E_corr)

        raw_mean = float(np.mean(raw_errors))
        raw_std = float(np.std(raw_errors, ddof=1))
        corr_mean = float(np.mean(corr_errors))
        corr_std = float(np.std(corr_errors, ddof=1))
        rows.append({
            "n": n,
            "n_over_m": n / m,
            "threshold_active": n <= threshold,
            "V_mean": float(np.mean(V_list)),
            "E_raw_mean": float(np.mean(E_raw_list)),
            "E_corr_mean": float(np.mean(E_corr_list)),
            "raw_signed_rel_err_mean": raw_mean,
            "raw_signed_rel_err_std": raw_std,
            "corrected_signed_rel_err_mean": corr_mean,
            "corrected_signed_rel_err_std": corr_std,
        })

    out = {
        "p": p,
        "m": m,
        "small_range_threshold": threshold,
        "alpha_m": 0.7213 / (1.0 + 1.079 / m),
        "hash": "splitmix64",
        "n_grid": n_grid,
        "seeds": seeds,
        "rows": rows,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()