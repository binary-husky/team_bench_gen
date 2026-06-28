"""
Reproduce HyperLogLog (Flajolet et al. 2007) from scratch with numpy + mmh3.

Goal: verify how the precision parameter m = 2^p controls BOTH the relative
estimation error (expected ~1/sqrt(m)) AND memory (linear in m).

Fixed setup (do not change):
  - true cardinality n = 1e5 distinct synthetic items
  - p in {8,10,12,14}  -> m in {256,1024,4096,16384}
  - >=5 different random seeds per p
  - CPU only
"""

import math
import numpy as np
import mmh3

# ---------------------------------------------------------------------------
# 64-bit hashing
# ---------------------------------------------------------------------------
def hash64(x, seed):
    """Return a 64-bit unsigned hash for object x with a seed."""
    h = mmh3.hash64(x, seed=seed, signed=False)
    # mmh3.hash64 returns two 64-bit values (a pair); use the first.
    return h[0]


def make_stream(n, seed):
    """n distinct items. Use deterministic-but-seed-dependent distinct ids."""
    # Distinct integers 0..n-1 transformed to bytes; seed perturbs via prefix
    # so different seeds see effectively independent hash streams while the
    # *items* remain distinct (true cardinality exactly n).
    for i in range(n):
        yield ("%d-%d" % (seed, i)).encode()


# ---------------------------------------------------------------------------
# HyperLogLog core
# ---------------------------------------------------------------------------
def alpha(m):
    # FlFuGaMe07 bias correction constant.
    if m < 16:
        # small-m specific constants (not needed here, m>=256) but kept for completeness
        small = {16: 0.673, 32: 0.697, 64: 0.709}
        if m in small:
            return small[m]
    return 0.7213 / (1.0 + 1.079 / m)


def rho(w, bits):
    """position of leftmost 1-bit in a `bits`-wide integer w (1-indexed).
    Returns bits+1 if w==0."""
    if w == 0:
        return bits + 1
    # number of leading zeros within `bits` width
    lz = bits - w.bit_length()
    return lz + 1


def hll_estimate(regs, p, m):
    """Return corrected HLL estimate (raw + small-range linear counting)."""
    a = alpha(m)
    # raw estimate
    sum_inv = np.sum(np.exp2(-regs.astype(np.float64)))  # sum 2^{-M[j]}
    E = a * (m * m) / sum_inv

    # small-range correction (linear counting)
    V = int(np.count_nonzero(regs == 0))
    if E <= 2.5 * m and V > 0:
        E = m * math.log(m / V)
    # large-range correction not needed (n=1e5 << 2^32)
    return E


def run_hll(p, stream, seed):
    """Run HLL with precision p on the given stream; return estimate."""
    m = 1 << p
    regs = np.zeros(m, dtype=np.int64)
    wbits = 64 - p  # width of the remaining hash bits used for rho

    for item in stream:
        h = hash64(item, seed)
        idx = h >> (64 - p)            # top p bits -> register index
        w = (h & ((1 << wbits) - 1))   # remaining bits
        r = rho(w, wbits)
        if r > regs[idx]:
            regs[idx] = r
    return hll_estimate(regs, p, m)


# ---------------------------------------------------------------------------
# Experiment
# ---------------------------------------------------------------------------
SEEDS = list(range(1001, 1031))   # 30 seeds (>=5; more for cleaner scaling)
PS = [8, 10, 12, 14]
N = 100_000


def main():
    print(f"true n = {N}")
    rows = []
    for p in PS:
        m = 1 << p
        errs = []
        for s in SEEDS:
            est = run_hll(p, make_stream(N, s), s)
            rel = (est - N) / N
            errs.append(rel)
            print(f"  p={p:2d} m={m:6d} seed={s:3d}  est={est:10.1f}  rel_err={rel*100:+.3f}%")
        errs = np.array(errs)
        mean = errs.mean()
        std = errs.std(ddof=1)
        rows.append({
            "p": p, "m": m,
            "mean_rel": mean,
            "std_rel": std,
            "mean_abs_rel": np.abs(errs).mean(),
        })
        print(f"  -> p={p} m={m}: mean_rel={mean*100:+.3f}%  std={std*100:.3f}%  |mean|={np.abs(errs).mean()*100:.3f}%")
        print()

    # report scaling
    print("\n=== scaling check ===")
    base = rows[0]
    for r in rows:
        r["theory_se"] = 1.04 / math.sqrt(r["m"])  # HLL std ~1.04/sqrt(m)
    for i in range(1, len(rows)):
        prev, cur = rows[i-1], rows[i]
        ratio = prev["std_rel"] / cur["std_rel"]
        print(f"  p {prev['p']}->{cur['p']} (m x{cur['m']//prev['m']}): std_ratio={ratio:.3f} (expect ~sqrt(2)={math.sqrt(2):.3f})")
    print(f"  p8->p14 (m x{rows[-1]['m']//rows[0]['m']}): std_ratio={rows[0]['std_rel']/rows[-1]['std_rel']:.3f} (expect ~8)")

    # save results for the summary writer
    import json
    with open("hll_results.json", "w") as f:
        json.dump({"N": N, "seeds": SEEDS, "rows": rows}, f, indent=2, default=float)
    print("\nsaved hll_results.json")


if __name__ == "__main__":
    main()
