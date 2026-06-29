"""
HyperLogLog reproduction + precision-scaling experiment.

Implements the algorithm of Flajolet, Fusy, Gandouet, Meunier (2007)
"AoA'07 / DMTCS proc. AH, 2007, 127–146" — HyperLogLog.

Includes:
  * raw harmonic-mean estimator  E = alpha_m * m^2 / sum(2^-M[j])
  * small-range linear-counting correction (when E <= 2.5 m)
  * large-range correction       (when E > 2^L / 30)  [kept for completeness]
  * register-init at 0 (the "practical" form of Figure 3 in the paper).

Hashing: 64-bit mmh3 (city-style) hash; we treat the low 64 bits as the
stream of hashed bits used for register indexing and rho().
"""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass

import numpy as np
import mmh3


HASH_BITS = 64  # number of bits from the hash we keep


# --------------------------------------------------------------------------- #
# HyperLogLog estimator
# --------------------------------------------------------------------------- #

def _alpha(m: int) -> float:
    """Bias-correction constant alpha_m from the paper (eq. around Figure 3)."""
    if m == 16:
        return 0.673
    if m == 32:
        return 0.697
    if m == 64:
        return 0.709
    # m >= 128
    return 0.7213 / (1.0 + 1.079 / m)


def _rho(w: int, remaining_bits: int) -> int:
    """Position (1-indexed) of the leftmost 1-bit in a ``remaining_bits``-bit
    word ``w`` read from MSB. Returns ``remaining_bits + 1`` if w == 0."""
    if w == 0:
        return remaining_bits + 1
    # bit_length() = position of the highest set bit, 1-indexed from LSB.
    # Convert to position from MSB in a `remaining_bits`-wide window.
    return remaining_bits - w.bit_length() + 1


@dataclass
class HLL:
    p: int                       # precision parameter, registers count m = 2^p
    registers: np.ndarray        # length m, dtype uint8 — stores rho values up to 65

    def __post_init__(self) -> None:
        self.m = 1 << self.p
        self.alpha = _alpha(self.m)

    # ---- update -------------------------------------------------------- #
    def add(self, item_hash: int) -> None:
        """Register one item; ``item_hash`` is the 64-bit hash value."""
        # Split into: first p bits (register index), remaining 64-p bits (rho input).
        remaining = HASH_BITS - self.p
        j = item_hash >> remaining                       # top-p bits -> register
        w = item_hash & ((1 << remaining) - 1)          # remaining bits (low end)
        rho_w = _rho(w, remaining)
        # rho_w fits in 1..remaining+1 <= 57; store in uint8 (max 255).
        cur = self.registers[j]
        if rho_w > cur:
            self.registers[j] = rho_w

    # ---- estimate ------------------------------------------------------- #
    def estimate(self) -> float:
        m = self.m
        # Harmonic raw estimator: E = alpha_m * m^2 / sum_j 2^-M[j]
        inv = np.sum(np.power(2.0, -self.registers.astype(np.float64)))
        E = self.alpha * m * m / inv

        # Small-range correction (linear counting): when E <= 2.5 m and some
        # registers are still at the initial value 0, use Whang-style estimator.
        if E <= 2.5 * m:
            v = int(np.sum(self.registers == 0))
            if v != 0:
                return m * math.log(m / v)
            else:
                return E
        # Large-range correction: only relevant when E > 2^L / 30 (64-bit => 2^64/30).
        # Kept for completeness but never triggered at our n = 1e5, m >= 256.
        two_L = 1 << HASH_BITS
        if E > two_L / 30.0:
            return -two_L * math.log(1.0 - E / two_L)
        return E


# --------------------------------------------------------------------------- #
# Streaming driver
# --------------------------------------------------------------------------- #

def hll_cardinality(items, p: int, seed: int = 0) -> float:
    """Hash-and-add every item in ``items`` and return the final HLL estimate."""
    hll = HLL(p=p, registers=np.zeros(1 << p, dtype=np.uint8))
    salt = b"hll-exp"
    salt_int = int.from_bytes(salt, "little") ^ seed  # vary hash with seed
    for item in items:
        # mmh3 128-bit hash; take the (unsigned) low 64-bit half as our stream.
        h64 = mmh3.hash64(item, seed=seed, signed=False)[0]
        hll.add(int(h64))
    return hll.estimate()


def make_distinct_items(n: int, seed: int):
    """Return ``n`` distinct string items generated deterministically from seed."""
    rng = np.random.default_rng(seed)
    # Each item: 16 random bytes -> hex; total space >> n, collisions negligible.
    raw = rng.integers(0, 2**63 - 1, size=n, dtype=np.int64)
    # Map to strings; cheap & distinct.
    return [f"item-{x:016x}" for x in raw]


# --------------------------------------------------------------------------- #
# Experiment
# --------------------------------------------------------------------------- #

def main() -> None:
    n = int(1e5)
    p_values = [8, 10, 12, 14]
    seeds = list(range(1, 31))  # 30 seeds — tighter confidence on the std estimate

    print(f"HyperLogLog precision sweep: n={n}, p in {p_values}, seeds={seeds}")
    print(f"{'p':>3} {'m':>7} {'mean rel.err':>13} {'std rel.err':>13} "
          f"{'bytes':>10} {'mean est':>12} {'mean time(s)':>13}")

    results = {}  # p -> dict
    items_cache = {}

    for p in p_values:
        m = 1 << p
        rel_errs = []
        ests = []
        times = []

        for seed in seeds:
            key = (n, seed)
            if key not in items_cache:
                items_cache[key] = make_distinct_items(n, seed)

            items = items_cache[key]

            t0 = time.perf_counter()
            est = hll_cardinality(items, p=p, seed=seed)
            dt = time.perf_counter() - t0

            ests.append(est)
            rel_errs.append((est - n) / n)
            times.append(dt)

        mean_re = float(np.mean(rel_errs))
        std_re = float(np.std(rel_errs, ddof=1))
        mean_est = float(np.mean(ests))
        mean_dt = float(np.mean(times))

        # Memory: registers count m. Each register holds rho in {1..65},
        # fits in 1 byte (uint8). Bytes = m * 1.
        bytes_used = m

        results[p] = {
            "m": m,
            "mean_rel_err": mean_re,
            "std_rel_err": std_re,
            "mean_estimate": mean_est,
            "bytes": bytes_used,
            "mean_time_s": mean_dt,
            "all_rel_errs": rel_errs,
            "all_estimates": ests,
        }
        print(f"{p:>3} {m:>7d} {mean_re*100:>12.4f}% {std_re*100:>12.4f}% "
              f"{bytes_used:>10d} {mean_est:>12.1f} {mean_dt:>13.3f}")

    # ----- Validation of 1/sqrt(m) scaling ----- #
    # The theoretical law is for the *standard error*, i.e. the std-dev of
    # the relative error across trials. The mean relative error is ~0 by
    # design (unbiased estimator), so |mean|/|mean| is not informative.
    #
    # Our grid p in {8, 10, 12, 14} has m jumping by 4x between adjacent p
    # (p + 2 -> m * 4). Therefore adjacent-p std ratio should be sqrt(4)=2,
    # NOT sqrt(2)=1.414. (The task text says "m doubles"; that would be
    # valid only for a grid with p-step=1. Here we follow the data: m*4
    # between adjacent entries in the prescribed grid.)
    print("\n--- Scaling-law checks (use std of rel.err, the SE) ---")
    print("adjacent p (m x4): std ratio should be ~ 2 (= sqrt(4))")
    for i in range(len(p_values) - 1):
        p1, p2 = p_values[i], p_values[i + 1]
        s1 = results[p1]["std_rel_err"]
        s2 = results[p2]["std_rel_err"]
        m_factor = results[p2]["m"] / results[p1]["m"]
        print(f"  p={p1}->{p2} (m x{m_factor:.0f}): "
              f"std(p1)/std(p2) = {s1 / s2:.4f}  (theory sqrt({m_factor:.0f})={math.sqrt(m_factor):.4f})")

    p_lo, p_hi = p_values[0], p_values[-1]
    s_lo = results[p_lo]["std_rel_err"]
    s_hi = results[p_hi]["std_rel_err"]
    m_factor = results[p_hi]["m"] / results[p_lo]["m"]
    print(f"\np={p_lo}->{p_hi} (m factor = "
          f"{m_factor:.0f}x): "
          f"std(p_lo)/std(p_hi) = {s_lo / s_hi:.4f} "
          f"(theory sqrt({m_factor:.0f})={math.sqrt(m_factor):.4f})")

    # Theoretical standard errors
    beta_inf = math.sqrt(3 * math.log(2) - 1)  # ~1.03896
    print("\n--- Theory ---")
    print(f"  Theoretical SE = beta_m / sqrt(m); beta_inf ~ {beta_inf:.5f}")
    for p in p_values:
        m = 1 << p
        print(f"  p={p:>2}  m={m:>5d}  theory SE ~ {beta_inf / math.sqrt(m) * 100:.4f}%")


if __name__ == "__main__":
    main()