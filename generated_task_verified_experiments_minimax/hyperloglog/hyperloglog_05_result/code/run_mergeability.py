"""
Mergeability experiment for HyperLogLog.

For each of >=5 random seeds:
  - Generate two disjoint streams A and B, each with n_A = n_B = 50_000 distinct items.
  - Build HLL sketch S_A on A and S_B on B (p = 14, m = 16_384).
  - Build merged sketch S_merge via per-register max: S_merge[j] = max(S_A[j], S_B[j]).
  - Build direct sketch S_direct on the union A | B (which has true cardinality n_A + n_B = 100_000).
  - Build dup sketch S_dup by merging A with a copy of itself (true cardinality still n_A).

Record:
  - E_merge, E_direct, E_dup.
  - merge_err_rel = |E_merge - (n_A + n_B)| / (n_A + n_B).
  - direct_err_rel = |E_direct - (n_A + n_B)| / (n_A + n_B).
  - dup_err_rel   = |E_dup   - n_A|       / n_A          (idempotency).
  - whether S_merge is EXACTLY equal to S_direct (register-by-register).
  - whether S_dup  is EXACTLY equal to S_A    (idempotency at the register level).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hll import HyperLogLog


P = 14
N_A = 50_000
N_B = 50_000
N_UNION = N_A + N_B  # 100_000 (streams are disjoint)
SEEDS = [11, 23, 47, 101, 211, 307, 503]  # 7 distinct seeds, well above the required 5


def disjoint_streams(seed: int, n_a: int, n_b: int):
    """Return two disjoint lists of unique items, generated deterministically
    from `seed`.  We use a counter-based generator so each item is unique."""
    rng = np.random.default_rng(seed)
    # pick n_a + n_b unique integers from a 64-bit space; rejection-sample
    # until we have enough.  We embed the seed in the high bits so A and B
    # are distinct per run.
    needed = n_a + n_b
    out = []
    while len(out) < needed:
        # batch of 2*needed random uint64s
        batch = rng.integers(0, 1 << 63, size=2 * needed, dtype=np.uint64)
        seen = set(out)
        for v in batch.tolist():
            if v not in seen:
                seen.add(v)
                out.append(v)
                if len(out) == needed:
                    break
    arr = np.array(out[:needed], dtype=np.uint64)
    a = arr[:n_a]
    b = arr[n_a:]
    assert len(set(a.tolist()) & set(b.tolist())) == 0
    return a, b


def main() -> None:
    rows = []
    register_equiv_count = 0  # number of seeds where S_merge == S_direct element-wise
    dup_equiv_count       = 0  # number of seeds where S_dup   == S_A element-wise

    t0 = time.time()
    for seed in SEEDS:
        a, b = disjoint_streams(seed, N_A, N_B)

        # Sketch A and B with the SAME hash seed so register comparisons are valid.
        s_a = HyperLogLog(p=P)
        s_a.set_seed(seed)
        s_a.add(a.tolist())

        s_b = HyperLogLog(p=P)
        s_b.set_seed(seed)
        s_b.add(b.tolist())

        # Merged: per-register max of A and B.
        s_merge = HyperLogLog.merged(s_a, s_b)

        # Direct: build a fresh sketch on the union stream A | B.
        s_direct = HyperLogLog(p=P)
        s_direct.set_seed(seed)
        s_direct.add(np.concatenate([a, b]).tolist())

        # Dup / idempotency: merge A with itself.
        s_dup = HyperLogLog.merged(s_a, s_a)

        e_merge  = s_merge.estimate()
        e_direct = s_direct.estimate()
        e_dup    = s_dup.estimate()
        e_a      = s_a.estimate()

        # register-level equivalence
        merge_eq_direct = bool(np.array_equal(s_merge.registers, s_direct.registers))
        dup_eq_a        = bool(np.array_equal(s_dup.registers,    s_a.registers))

        register_equiv_count += int(merge_eq_direct)
        dup_equiv_count       += int(dup_eq_a)

        merge_err = abs(e_merge - N_UNION) / N_UNION
        direct_err = abs(e_direct - N_UNION) / N_UNION
        dup_err = abs(e_dup - N_A) / N_A
        # baseline: what would naive E_A + E_B give?
        sum_naive = e_a + s_b.estimate()

        rows.append(dict(
            seed=seed,
            E_merge=e_merge,
            E_direct=e_direct,
            E_dup=e_dup,
            E_A=e_a,
            E_A_plus_E_B=sum_naive,
            merge_err_rel=merge_err,
            direct_err_rel=direct_err,
            dup_err_rel=dup_err,
            merge_eq_direct=merge_eq_direct,
            dup_eq_a=dup_eq_a,
            sum_naive_over_n_union=sum_naive / N_UNION,
        ))

    dt = time.time() - t0

    # Print per-seed table
    header = ("seed", "E_merge", "E_direct", "E_dup", "E_A", "E_A+E_B",
              "relErrMerge", "relErrDirect", "relErrDup",
              "S_merge==S_direct", "S_dup==S_A")
    fmt = "{:>4} {:>10} {:>10} {:>10} {:>10} {:>10} {:>11} {:>11} {:>10} {:>17} {:>12}"
    print(fmt.format(*header))
    for r in rows:
        print(fmt.format(
            r["seed"],
            f"{r['E_merge']:.0f}",
            f"{r['E_direct']:.0f}",
            f"{r['E_dup']:.0f}",
            f"{r['E_A']:.0f}",
            f"{r['E_A_plus_E_B']:.0f}",
            f"{r['merge_err_rel']:.4f}",
            f"{r['direct_err_rel']:.4f}",
            f"{r['dup_err_rel']:.4f}",
            str(r["merge_eq_direct"]),
            str(r["dup_eq_a"]),
        ))

    n = len(rows)
    print()
    print(f"Seeds run: {n}")
    print(f"Elapsed:   {dt:.2f} s")
    print()

    merge_errs  = np.array([r["merge_err_rel"]  for r in rows])
    direct_errs = np.array([r["direct_err_rel"] for r in rows])
    dup_errs    = np.array([r["dup_err_rel"]    for r in rows])

    print("Cross-seed statistics:")
    print(f"  merge_err_rel   mean = {merge_errs.mean():.4f}   std = {merge_errs.std(ddof=1):.4f}")
    print(f"  direct_err_rel  mean = {direct_errs.mean():.4f}   std = {direct_errs.std(ddof=1):.4f}")
    print(f"  dup_err_rel     mean = {dup_errs.mean():.4f}   std = {dup_errs.std(ddof=1):.4f}")
    print(f"  |E_merge - E_direct| (max over seeds) = {max(abs(r['E_merge']-r['E_direct']) for r in rows):.6f}")
    print(f"  |E_dup   - E_A|     (max over seeds) = {max(abs(r['E_dup']  -r['E_A'])     for r in rows):.6f}")
    print()
    print("Register-level equivalence:")
    print(f"  S_merge == S_direct  in {register_equiv_count}/{n} seeds")
    print(f"  S_dup   == S_A       in {dup_equiv_count}/{n} seeds")


if __name__ == "__main__":
    main()
