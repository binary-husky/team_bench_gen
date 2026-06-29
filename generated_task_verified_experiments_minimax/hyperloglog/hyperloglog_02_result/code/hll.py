"""
HyperLogLog implementation following Flajolet et al. 2007 ("HyperLogLog:
the analysis of a near-optimal cardinality estimation algorithm"), §4.

Uses a 64-bit hash (mmh3). Registers: 2^p. Estimation pipeline:
  1) raw estimate:  E = alpha_m * m^2 * (sum 2^{-M[j]})^{-1}
  2) small-range linear-counting correction:  if E <= 2.5*m and V>0:  E* = m log(m/V)
  3) intermediate range:  E* = E  (no correction)
  4) large-range correction:  if E > 2^L/30 (L=64):  E* = -2^L log(1 - E/2^L)
"""
from __future__ import annotations

import math
import struct
from typing import Iterable

import mmh3
import numpy as np


# ---------- hashing ----------------------------------------------------

_HASH_SEED = 0xC0FFEE  # fixed salt so re-runs are bit-identical


def hash64(item_bytes: bytes) -> int:
    """Hash bytes to a 64-bit unsigned integer via mmh3."""
    h = mmh3.hash64(item_bytes, seed=_HASH_SEED, signed=False)
    # mmh3.hash64 returns a 2-tuple (low_64, high_64); take the low 64 bits.
    return int(h[0]) & 0xFFFFFFFFFFFFFFFF


def pack_uint64(x: int) -> bytes:
    return struct.pack("<Q", x & 0xFFFFFFFFFFFFFFFF)


# ---------- rank --------------------------------------------------------

def rho(w: int, bits: int) -> int:
    """Position of the leftmost 1-bit in the `bits`-bit word w, 1-indexed;
    returns `bits + 1` when w == 0 (i.e. the word is all zeros)."""
    if w == 0:
        return bits + 1
    # Python's int.bit_length() returns the index of the highest set bit + 1.
    # In a `bits`-bit word, the leading 1 is at position `bits - bit_length + 1`.
    return bits - w.bit_length() + 1


# ---------- the sketch --------------------------------------------------

class HyperLogLog:
    """HyperLogLog cardinality sketch. Uses 64-bit mmh3 hashing."""

    def __init__(self, p: int = 14):
        assert 4 <= p <= 16, "p must be in [4, 16]"
        self.p: int = p
        self.m: int = 1 << p  # 2^p registers
        self._mask: int = self.m - 1
        self.registers: np.ndarray = np.zeros(self.m, dtype=np.uint8)
        # alpha_m constants from paper (Figure 3 caption)
        if self.m == 16:
            self.alpha_m = 0.673
        elif self.m == 32:
            self.alpha_m = 0.697
        elif self.m == 64:
            self.alpha_m = 0.709
        else:
            self.alpha_m = 0.7213 / (1.0 + 1.079 / self.m)

    # ----- ingestion -----------------------------------------------------

    def add_uint64(self, x: int) -> None:
        """Add a single 64-bit unsigned integer."""
        h = hash64(pack_uint64(x))
        idx = h & self._mask
        w = h >> self.p
        r = rho(w, 64 - self.p)
        if r > self.registers[idx]:
            self.registers[idx] = r

    def add_uint64_array(self, xs: np.ndarray) -> None:
        """Add a numpy array of 64-bit unsigned integers (vectorized hash loop)."""
        m, p, mask = self.m, self.p, self._mask
        bits_for_rank = 64 - p
        regs = self.registers
        # Pre-pack all items to bytes (8 bytes each) in one shot.
        # np.uint64.tobytes() packs in little-endian by default.
        packed = xs.astype(np.uint64).tobytes()
        # 8 bytes per item
        n = xs.shape[0]
        # Hash each item individually via mmh3. mmh3 is a thin C wrapper,
        # so this loop is ~1 us / item — fast enough for our grid.
        for i in range(n):
            chunk = packed[i * 8 : (i + 1) * 8]
            h = mmh3.hash64(chunk, seed=_HASH_SEED, signed=False)
            h = int(h[0]) & 0xFFFFFFFFFFFFFFFF
            idx = h & mask
            w = h >> p
            r = rho(w, bits_for_rank)
            if r > regs[idx]:
                regs[idx] = r

    def add_strings(self, strings: Iterable[str]) -> None:
        """Add an iterable of arbitrary strings."""
        m, p, mask = self.m, self.p, self._mask
        bits_for_rank = 64 - p
        regs = self.registers
        for s in strings:
            sb = s.encode("utf-8")
            h = mmh3.hash64(sb, seed=_HASH_SEED, signed=False)
            h = int(h[0]) & 0xFFFFFFFFFFFFFFFF
            idx = h & mask
            w = h >> p
            r = rho(w, bits_for_rank)
            if r > regs[idx]:
                regs[idx] = r

    # ----- estimation ----------------------------------------------------

    def estimate(self) -> float:
        """Return the cardinality estimate, applying small/intermediate/large
        range corrections as in paper §4 / Figure 3."""
        regs = self.registers
        m = self.m
        # raw harmonic-mean estimate
        Z_inv = float(np.sum(np.power(2.0, -regs.astype(np.float64))))
        E = self.alpha_m * m * m / Z_inv

        # small range correction: linear counting
        if E <= 2.5 * m:
            V = int(np.sum(regs == 0))
            if V != 0:
                return m * math.log(m / V)
            return E  # all registers hit; fall through

        # large range correction: 64-bit hash space
        two_L = float(1 << 64)
        if E > two_L / 30.0:
            return -two_L * math.log(1.0 - E / two_L)

        # intermediate range: no correction
        return E

    # ----- diagnostics ---------------------------------------------------

    def n_zero_registers(self) -> int:
        return int(np.sum(self.registers == 0))

    def raw_estimate(self) -> float:
        regs = self.registers
        Z_inv = float(np.sum(np.power(2.0, -regs.astype(np.float64))))
        return self.alpha_m * self.m * self.m / Z_inv


# ---------- self-test ----------------------------------------------------

def _selftest() -> None:
    import random
    rng = np.random.default_rng(0)
    hll = HyperLogLog(p=14)
    n = 100_000
    xs = rng.integers(0, 2**63, size=n, dtype=np.int64).astype(np.uint64)
    hll.add_uint64_array(xs)
    est = hll.estimate()
    rel = abs(est - n) / n
    print(f"selftest n={n}  est={est:.1f}  rel_err={rel:.4%}")
    assert rel < 0.05, f"selftest failed: rel_err={rel}"


if __name__ == "__main__":
    _selftest()