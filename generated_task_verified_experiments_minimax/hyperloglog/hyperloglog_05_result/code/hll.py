"""
HyperLogLog implementation following Flajolet, Fusy, Gandouet, Meunier (2007).

p  : precision in [4, 16]
m  : number of registers = 2^p
Each register stores rho(w) -- the position of the leftmost 1-bit in w + 1.
A 64-bit hash is used (mmh3.hash128 truncated to 64 bits).
"""

from __future__ import annotations

import numpy as np
import mmh3


# Precomputed alpha_m from Eq.(3) of the paper.
# For m in {16, 32, 64} we use the exact tabulated values; for m >= 128 we use
# the asymptotic form alpha_m = 1 / (2 log 2)^2 * (integral)^{-1} which in
# practice is well-approximated by 0.7213/(1 + 1.079/m) (this is the form given
# in Heule et al. and reproduced in many implementations of HLL++).
_ALPHA = {
    16: 0.673,
    32: 0.697,
    64: 0.709,
}


def _alpha_m(m: int) -> float:
    if m in _ALPHA:
        return _ALPHA[m]
    return 0.7213 / (1.0 + 1.079 / m)


def _hash64_batch(items, seed: int = 0) -> np.ndarray:
    """Hash an iterable of items to a uint64 numpy array via mmh3.hash128."""
    out = np.empty(len(items), dtype=np.uint64)
    for i, v in enumerate(items):
        if isinstance(v, str):
            v = v.encode("utf-8")
        elif not isinstance(v, (bytes, bytearray)):
            v = str(v).encode("utf-8")
        h = mmh3.hash128(v, seed=seed, signed=False)
        # lower 64 bits (uniform on uint64 for mmh3)
        out[i] = h & 0xFFFFFFFFFFFFFFFF
    return out


def _rank64(w: np.ndarray, bits: int = 64) -> np.ndarray:
    """For each `bits`-wide unsigned integer w, return rho(w) following the
    Flajolet et al. convention: rho is the position of the leftmost 1-bit in
    w, counted from the most-significant bit.  rho("100...0") = 1, and
    rho("0...0") = bits + 1 (the all-zero sentinel).
    """
    w = w.astype(np.uint64, copy=False)
    nz = w != 0
    # bit_length returns floor(log2(w)) + 1 = position of the highest set bit
    # (counted from the LSB).  In an `bits`-wide representation, the number
    # of leading zeros is `bits - bit_length`.  So rho = leading_zeros + 1
    # = bits - bit_length + 1.
    bit_len = np.fromiter(
        (vv.bit_length() for vv in w.tolist()), dtype=np.int64, count=len(w)
    )
    rho = np.where(nz, bits - bit_len + 1, bits + 1).astype(np.uint8)
    return rho


class HyperLogLog:
    """HyperLogLog sketch with p bits of precision (m = 2^p registers)."""

    def __init__(self, p: int = 14):
        if not 4 <= p <= 16:
            raise ValueError("p must be in [4, 16]")
        self.p = p
        self.m = 1 << p
        self.alpha = _alpha_m(self.m)
        self.registers = np.zeros(self.m, dtype=np.uint8)
        self._hash_seed = 0

    def set_seed(self, seed: int) -> None:
        self._hash_seed = seed

    def add_hashed(self, h: np.ndarray) -> None:
        """Add a uint64 array of hashes.  First p bits -> index, remaining
        bits -> rank (leftmost 1-bit position, counted from MSB)."""
        h = h.astype(np.uint64, copy=False)
        index = (h >> np.uint64(64 - self.p)) & np.uint64(self.m - 1)
        w = h & np.uint64((1 << (64 - self.p)) - 1)
        rho = _rank64(w, bits=(64 - self.p))
        np.maximum.at(self.registers, index, rho)

    def add(self, items) -> None:
        h = _hash64_batch(items, seed=self._hash_seed)
        self.add_hashed(h)

    def merge(self, other: "HyperLogLog") -> None:
        if other.p != self.p:
            raise ValueError("precision mismatch")
        np.maximum(self.registers, other.registers, out=self.registers)

    @classmethod
    def merged(cls, a: "HyperLogLog", b: "HyperLogLog") -> "HyperLogLog":
        out = cls(p=a.p)
        out.registers = np.maximum(a.registers, b.registers)
        return out

    def estimate(self) -> float:
        """Cardinality estimate with small/large range corrections (Fig. 3)."""
        m = self.m
        regs = self.registers
        # Raw estimate
        indicator = np.power(2.0, -regs.astype(np.float64))
        Z = 1.0 / indicator.sum()
        E = self.alpha * m * m * Z

        # Small range correction (linear counting when E <= 2.5*m)
        if E <= 2.5 * m:
            V = int((regs == 0).sum())
            if V != 0:
                E_star = m * np.log(m / V)
            else:
                E_star = E
        elif E <= (1.0 / 30.0) * (1 << 32):
            E_star = E
        else:
            # Large range correction (we won't hit this with our n's; use the
            # 64-bit formula anyway for completeness).
            E_star = -(1 << 64) * np.log(1.0 - E / (1 << 64))
        return float(E_star)

    def __repr__(self) -> str:
        return f"HyperLogLog(p={self.p}, m={self.m})"


if __name__ == "__main__":
    # smoke test
    import random
    random.seed(0)
    hll = HyperLogLog(p=14)
    hll.add([f"item-{i}" for i in range(1000)])
    print("estimate for 1000:", hll.estimate())
