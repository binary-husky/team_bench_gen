"""
Reproduce HyperLogLog (FlFuGaMe07) and study its mergeability.

Mergeability claim: M[j] = max(A[j], B[j]) on two same-precision HLL sketches
yields the sketch of the *union* stream (cardinality of union, NOT sum), and is
bit-for-bit identical at the register level to a sketch built directly on A∪B.
Idempotency: merging a stream with its own duplicate returns the original
cardinality (dedup semantics).

Fixed setup:
  p = 14, m = 2^14 = 16384
  n_A = n_B = 5e4 disjoint items, true union = 1e5
  >=5 different random seeds
CPU-only.
"""
import numpy as np

P = 14
M = 1 << P               # 16384
# bias correction constant for m >= 128 (FlFuGaMe07, eq. for alpha_m)
ALPHA = 0.7213 / (1.0 + 1.079 / M)
THRESH_SMALL = 2.5 * M   # small-range correction trigger
THRESH_LARGE = (1 << 32) / 30.0  # large-range correction trigger (32-bit space)


def hash64(x):
    """64-bit hash of an array of uint64 items via MurmurHash3 64-bit finalizer.

    Operates purely with numpy uint64 modular arithmetic. Good avalanche, so
    distinct inputs give well-spread, near-uniform 64-bit hashes.
    """
    x = x.astype(np.uint64, copy=True)
    x ^= x >> np.uint64(33)
    x *= np.uint64(0xff51afd7ed558ccd)
    x ^= x >> np.uint64(33)
    x *= np.uint64(0xc4ceb9fe1a85ec53)
    x ^= x >> np.uint64(33)
    return x


def rho(h):
    """Position of the leftmost 1-bit of the 64-bit hash, after the p index bits.

    rho = number of leading zeros in the (64-p)-bit "tail" + 1.
    We use the top p bits as the register index (so the tail is the low 64-p bits).
    """
    # tail = low (64-P) bits
    tail = h & np.uint64((1 << (64 - P)) - 1)
    # position of leftmost set bit in a (64-P)-bit value, counted from the top.
    # 64 - P - bits_needed gives leading-zero count; rho = lz + 1.
    # Use np.clz via bit_length on python ints is slow; do it vectorized.
    width = 64 - P
    # leading zeros within `width` bits
    lz = width - np.zeros_like(tail)
    # compute bit length vectorized
    bl = np.zeros_like(tail, dtype=np.int32)
    t = tail.copy()
    for i in range(width - 1, -1, -1):
        # where t has this bit set, bl = max(bl, i+1); we can compute bit length
        pass
    # Simpler: bit_length via clp2 approach using uint comparisons.
    bl = _bit_length(tail, width)
    rho = (width - bl) + 1  # leading zeros + 1
    # special: tail == 0 -> rho = width + 1
    rho = np.where(tail == 0, width + 1, rho)
    return rho.astype(np.int32)


def _bit_length(x, width):
    """Vectorized bit_length for uint array, capped at width bits."""
    bl = np.zeros(x.shape, dtype=np.int32)
    t = x.astype(np.uint64)
    # binary-ish: shift and compare
    for i in (32, 16, 8, 4, 2, 1):
        # placeholder, replaced below
        pass
    # Direct method: log2 of nonzero. Use a lookup-free approach:
    bl = np.zeros(x.shape, dtype=np.int32)
    val = x.astype(np.uint64)
    # find highest set bit position
    hi = np.zeros(x.shape, dtype=np.int32)
    for i in range(width):
        bit = (val >> np.uint64(i)) & np.uint64(1)
        hi = np.where(bit != 0, i + 1, hi)
    return hi


def build_sketch(items):
    """Build HLL register array from iterable/array of distinct-ish items.

    items: uint64 array of item identifiers.
    Returns int32 array of length M with rho values (register state, 1-init).
    """
    items = np.asarray(items)
    if items.size == 0:
        return np.zeros(M, dtype=np.int32)
    h = hash64(items)
    # index = top p bits
    idx = (h >> np.uint64(64 - P)).astype(np.int64)
    r = rho(h)
    regs = np.zeros(M, dtype=np.int32)
    np.maximum.at(regs, idx, r)
    return regs


def estimate(regs):
    """HLL cardinality estimate with small/large range corrections."""
    Z = 1.0 / np.sum(np.power(2.0, -regs.astype(np.float64)))
    E = ALPHA * (M * M) * Z
    # small range correction
    if E <= THRESH_SMALL:
        V = np.count_nonzero(regs == 0)
        if V != 0:
            E = M * np.log(M / V)
    # large range correction
    if E > THRESH_LARGE:
        E = -(1 << 32) * np.log1p(-E / (1 << 32))
    return E


def merge(a_regs, b_regs):
    """Per-register max merge."""
    return np.maximum(a_regs, b_regs)


def make_streams(seed, n_A=50000, n_B=50000):
    """Generate two disjoint streams of distinct items.

    Use a 64-bit space large enough that random sampling yields distinct items;
    we draw A and B from disjoint halves of the 64-bit space to guarantee
    A ∩ B = ∅ and within-stream distinctness via uniqueness sampling.
    """
    rng = np.random.default_rng(seed)
    # A from one region, B from another disjoint region, guaranteeing A∩B=∅
    A = rng.integers(0, 1 << 62, size=n_A)
    B = rng.integers(1 << 62, 1 << 63, size=n_B)
    # enforce within-stream distinctness (collision probability tiny; still clean)
    A = np.unique(A)
    B = np.unique(B)
    # if collisions shrank sizes, top up A
    while A.size < n_A:
        extra = rng.integers(0, 1 << 62, size=n_A - A.size)
        A = np.unique(np.concatenate([A, extra]))
    while B.size < n_B:
        extra = rng.integers(1 << 62, 1 << 63, size=n_B - B.size)
        B = np.unique(np.concatenate([B, extra]))
    return A, B


def run_seed(seed):
    A, B = make_streams(seed)
    nA, nB = A.size, B.size
    true_union = nA + nB  # disjoint

    S_A = build_sketch(A)
    S_B = build_sketch(B)
    S_merge = merge(S_A, S_B)
    E_merge = estimate(S_merge)

    # control 1: direct sketch over A ∪ B
    S_direct = build_sketch(np.concatenate([A, B]))
    E_direct = estimate(S_direct)

    # control 2: idempotency / dedup — merge A with a copy of A
    S_dup = merge(S_A, S_A)
    E_dup = estimate(S_dup)

    # register-level equivalence: is S_merge == S_direct register-by-register?
    reg_equal = bool(np.array_equal(S_merge, S_direct))
    # also the estimate-level equivalence
    est_equal = (E_merge == E_direct)

    return {
        "seed": seed,
        "nA": nA, "nB": nB, "true_union": true_union,
        "E_merge": E_merge,
        "E_direct": E_direct,
        "E_dup": E_dup,
        "merge_rel_err": abs(E_merge - true_union) / true_union,
        "direct_rel_err": abs(E_direct - true_union) / true_union,
        "reg_equal": reg_equal,
        "est_equal": est_equal,
        "dup_ratio_over_nA": E_dup / nA,   # ~1 means idempotent/dedup, ~2 means sum
    }


def main():
    seeds = [1, 2, 3, 4, 5, 6, 7]
    results = [run_seed(s) for s in seeds]

    print(f"{'seed':>4} {'nA':>6} {'nB':>6} {'true':>8} {'E_merge':>12} "
          f"{'E_direct':>12} {'E_dup':>10} {'merge_err':>10} {'reg==dir':>9} "
          f"{'dup/nA':>8}")
    for r in results:
        print(f"{r['seed']:>4} {r['nA']:>6} {r['nB']:>6} {r['true_union']:>8} "
              f"{r['E_merge']:>12.1f} {r['E_direct']:>12.1f} {r['E_dup']:>10.1f} "
              f"{r['merge_rel_err']*100:>9.3f}% {str(r['reg_equal']):>9} "
              f"{r['dup_ratio_over_nA']:>8.4f}")

    merge_errs = np.array([r["merge_rel_err"] for r in results])
    direct_errs = np.array([r["direct_rel_err"] for r in results])
    dup_ratios = np.array([r["dup_ratio_over_nA"] for r in results])
    reg_all = all(r["reg_equal"] for r in results)
    est_all = all(r["est_equal"] for r in results)

    print()
    print(f"merge rel err : mean={merge_errs.mean()*100:.3f}%  "
          f"std={merge_errs.std()*100:.3f}%")
    print(f"direct rel err: mean={direct_errs.mean()*100:.3f}%  "
          f"std={direct_errs.std()*100:.3f}%")
    print(f"register-level S_merge == S_direct on every seed: {reg_all}")
    print(f"estimate-level E_merge == E_direct on every seed : {est_all}")
    print(f"idempotency E_dup/nA : mean={dup_ratios.mean():.4f}  "
          f"std={dup_ratios.std():.4f}  (1.0=idempotent/dedup, 2.0=sum)")

    # also compare S_merge vs S_direct register equality counts per seed
    print()
    print("Per-seed register equality (S_merge vs S_direct):")
    for r in results:
        print(f"  seed {r['seed']:>2}: reg_equal={r['reg_equal']}  "
              f"est_equal={r['est_equal']}")

    # save results
    import json
    out = {
        "config": {"p": P, "m": M, "alpha": ALPHA, "n_A": 50000, "n_B": 50000,
                   "true_union": 100000, "seeds": seeds},
        "results": results,
        "summary": {
            "merge_rel_err_mean_pct": float(merge_errs.mean() * 100),
            "merge_rel_err_std_pct": float(merge_errs.std() * 100),
            "direct_rel_err_mean_pct": float(direct_errs.mean() * 100),
            "direct_rel_err_std_pct": float(direct_errs.std() * 100),
            "register_equal_all_seeds": bool(reg_all),
            "estimate_equal_all_seeds": bool(est_all),
            "dup_ratio_mean": float(dup_ratios.mean()),
            "dup_ratio_std": float(dup_ratios.std()),
        },
    }
    with open("results_hll_05.json", "w") as f:
        json.dump(out, f, indent=2, default=float)
    print("\nWrote results_hll_05.json")


if __name__ == "__main__":
    main()
