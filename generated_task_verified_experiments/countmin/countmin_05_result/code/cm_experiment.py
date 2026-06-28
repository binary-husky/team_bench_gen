"""
Count-Min Sketch: point query vs self-join (F2) relative error.

Self-implemented CM sketch (numpy), d pairwise-independent hash functions.
Fixed setup: w=2048, d=8; stream 1e6 updates, 1e5 distinct items, Zipfian s~1.0.
Goal: compare relative error of point query vs F2 (self-join) on the SAME sketch.
"""

import numpy as np
import json

# ---------------- fixed experimental setup (do not change) ----------------
W = 2048           # sketch width
D = 8              # sketch depth (# pairwise-independent hashes)
N_ITEMS = 100_000  # distinct items (domain size)
N_UPDATES = 1_000_000  # total stream updates
ZIPF_S = 1.0       # Zipfian exponent
N_SEEDS = 20       # >= 10 different hash seeds

# frequency buckets for the point-query breakdown
FREQ_BINS = [(1, 1), (2, 4), (5, 9), (10, 99), (100, 999), (1000, 10**9)]

# pairwise-independent family:  h_j(x) = ((a_j * x + b_j) mod p) mod w
# p = 2^31 - 1 (Mersenne prime). a_j*x <= 2.1e9 * 1e5 = 2.1e14 < int64 max.
P = 2147483647


def build_true_stream():
    """Return true frequency vector a[i] for the fixed Zipfian stream."""
    rng = np.random.default_rng(12345)  # fixed stream realization
    idx = np.arange(1, N_ITEMS + 1, dtype=np.float64)
    w_ = idx ** (-ZIPF_S)
    w_ /= w_.sum()                       # truncated Zipfian PMF over N_ITEMS
    # +1 base per item guarantees all N_ITEMS distinct items appear (coverage)
    a = np.ones(N_ITEMS, dtype=np.int64)
    remaining = N_UPDATES - N_ITEMS
    draws = rng.choice(N_ITEMS, size=remaining, p=w_)
    a += np.bincount(draws, minlength=N_ITEMS).astype(np.int64)
    assert a.sum() == N_UPDATES
    return a


def run_one_seed(a, x, seed):
    """Build one CM sketch (fresh hash seed) and compute both metrics + diagnostics."""
    rng = np.random.default_rng(seed)
    a_coef = rng.integers(1, P, size=D)
    b_coef = rng.integers(0, P, size=D)

    counts = np.zeros((D, W), dtype=np.int64)
    buckets = np.empty((D, N_ITEMS), dtype=np.int64)  # h_j(i) for every item, every row
    for j in range(D):
        hj = ((a_coef[j] * x + b_coef[j]) % P) % W
        buckets[j] = hj
        np.add.at(counts[j], hj, a)          # count[j, h_j(i)] += a[i]   (== processing the +1 stream)

    # ---- point query:  a_hat[i] = min_j count[j, h_j(i)] ----
    gathered = np.empty((D, N_ITEMS), dtype=np.int64)
    for j in range(D):
        gathered[j] = counts[j, buckets[j]]
    a_hat = gathered.min(axis=0)             # length N_ITEMS, a_hat[i] >= a[i]

    denom = np.maximum(a, 1)
    over_abs = a_hat - a                     # >= 0 (one-sided)
    pq_rel_all = (over_abs / denom).mean()

    # diagnostics: relative overestimate restricted to heavy / mid / rare items
    order = np.argsort(-a)                   # descending frequency
    top1 = order[:1]
    top10 = order[:10]
    top100 = order[:100]
    top1pct = order[: N_ITEMS // 100]
    top10pct = order[: N_ITEMS // 10]
    pq_rel_heavy1 = (over_abs[top1pct] / denom[top1pct]).mean()
    pq_rel_heavy10 = (over_abs[top10pct] / denom[top10pct]).mean()
    pq_rel_top100 = (over_abs[top100] / denom[top100]).mean()
    pq_rel_top10 = (over_abs[top10] / denom[top10]).mean()
    pq_rel_top1 = float(over_abs[top1][0] / denom[top1][0])

    # ---- F2 (self-join) estimate:  F2_hat = min_j sum_l count[j,l]^2 ----
    f2_rows = (counts.astype(np.float64) ** 2).sum(axis=1)   # per-row estimate
    f2_hat = f2_rows.min()
    f2_true = float((a.astype(np.float64) ** 2).sum())
    f2_rel = (f2_hat - f2_true) / f2_true
    f2_perrow_rel = ((f2_rows - f2_true) / f2_true).mean()

    # point-query rel overestimate per frequency bucket (mean over items in bucket)
    bucket_rel = {}
    for lo, hi in FREQ_BINS:
        mask = (a >= lo) & (a <= hi)
        if mask.sum() == 0:
            bucket_rel[f"{lo}-{hi}"] = (0, 0)
        else:
            r = (over_abs[mask] / denom[mask]).mean()
            bucket_rel[f"{lo}-{hi}"] = (float(r), int(mask.sum()))

    return dict(
        pq_rel_all=pq_rel_all,
        pq_rel_heavy1=pq_rel_heavy1,
        pq_rel_heavy10=pq_rel_heavy10,
        pq_rel_top100=pq_rel_top100,
        pq_rel_top10=pq_rel_top10,
        pq_rel_top1=pq_rel_top1,
        over_abs_mean=float(over_abs.mean()),
        f2_rel=f2_rel,
        f2_perrow_rel=float(f2_perrow_rel),
        f2_hat=float(f2_hat),
        bucket_rel=bucket_rel,
    )


def main():
    a = build_true_stream()
    x = np.arange(N_ITEMS, dtype=np.int64)
    L1 = int(a.sum())
    F2_true = float((a.astype(np.float64) ** 2).sum())
    Hn = float(np.sum(1.0 / np.arange(1, N_ITEMS + 1)))
    # theoretical expected per-row F2 overestimate: (||a||_1^2 - F2) / w
    f2_exp_over = (L1 ** 2 - F2_true) / W

    print("=" * 70)
    print(f"Stream:  N_items={N_ITEMS}  N_updates={N_UPDATES}  Zipf s={ZIPF_S}")
    print(f"||a||_1 = {L1}   F2 = {a@a}  (=sum a_i^2)")
    print(f"Harmonic H_{N_ITEMS} = {Hn:.4f}   top-item freq ~= {int(round(N_UPDATES/Hn))}")
    print(f"a: min={a.min()} max={a.max()} mean={a.mean():.2f}  "
          f"items with a==1: {int((a==1).sum())}  a>=1000: {int((a>=1000).sum())}")
    print(f"||a||_1^2 / F2 = {L1**2/F2_true:.2f}   "
          f"E[F2 overestimate per row] ~ (||a||_1^2 - F2)/w = {f2_exp_over:.3e} "
          f"({f2_exp_over/F2_true*100:.2f}% of F2)")
    print(f"Sketch: w={W} d={D}   eps ~= e/w = {np.e/W:.5f}")
    print("=" * 70)

    results = [run_one_seed(a, x, 1000 + s) for s in range(N_SEEDS)]

    def agg(key):
        v = np.array([r[key] for r in results])
        return v.mean(), v.std()

    pq_m, pq_s = agg("pq_rel_all")
    pqh1_m, _ = agg("pq_rel_heavy1")
    pqh10_m, _ = agg("pq_rel_heavy10")
    pqt100_m, _ = agg("pq_rel_top100")
    pqt10_m, _ = agg("pq_rel_top10")
    pqt1_m, _ = agg("pq_rel_top1")
    oa_m, _ = agg("over_abs_mean")
    f2_m, f2_s = agg("f2_rel")
    f2pr_m, _ = agg("f2_perrow_rel")

    print(f"\nAcross {N_SEEDS} hash seeds (mean +/- std):")
    print(f"  Point query rel. overestimate, MEAN over ALL items : "
          f"{pq_m:.4f}  (+/-{pq_s:.4f})   i.e. {pq_m*100:.1f}%")
    print(f"  Point query rel. overestimate, top-1% heavy items : {pqh1_m:.4f}  ({pqh1_m*100:.2f}%)")
    print(f"  Point query rel. overestimate, top-10% heavy items: {pqh10_m:.4f}  ({pqh10_m*100:.2f}%)")
    print(f"  Point query rel. overestimate, top-100 items      : {pqt100_m:.4f}  ({pqt100_m*100:.2f}%)")
    print(f"  Point query rel. overestimate, top-10 items       : {pqt10_m:.4f}  ({pqt10_m*100:.2f}%)")
    print(f"  Point query rel. overestimate, #1 item            : {pqt1_m:.6f}  ({pqt1_m*100:.4f}%)")
    print(f"  Point query ABSOLUTE overestimate (mean per item) : {oa_m:.2f}")
    print(f"  F2 rel. error  (min over d rows)                  : "
          f"{f2_m:.4f}  (+/-{f2_s:.4f})   i.e. {f2_m*100:.2f}%")
    print(f"  F2 rel. error  (per-row, BEFORE min)              : {f2pr_m:.4f}  ({f2pr_m*100:.2f}%)")
    print(f"\n  Ratio  F2_rel / pointquery_rel(all items) = {f2_m/max(pq_m,1e-12):.5f}")
    print(f"  Ratio  pointquery_rel(all) / F2_rel        = {pq_m/max(f2_m,1e-12):.2f}x")

    # point-query rel overestimate bucketed by true frequency (averaged over seeds)
    print("\n  Point-query relative overestimate by true-frequency bucket "
          "(mean over seeds):")
    for lo, hi in FREQ_BINS:
        key = f"{lo}-{hi}"
        vals = [r["bucket_rel"][key][0] for r in results]
        cnt = results[0]["bucket_rel"][key][1]
        m = float(np.mean(vals))
        hi_lab = "inf" if hi >= 10**8 else str(hi)
        print(f"    a in [{lo}, {hi_lab:>5}]:  n_items={cnt:>7} "
              f"({cnt/N_ITEMS*100:5.1f}%)   rel_over = {m*100:9.1f}%")

    summary = dict(
        setup=dict(w=W, d=D, n_items=N_ITEMS, n_updates=N_UPDATES, zipf_s=ZIPF_S,
                   n_seeds=N_SEEDS, L1=L1, F2=F2_true, Hn=Hn,
                   f2_expected_perrow_over=f2_exp_over),
        point_query_rel_overestimate_allitems_mean=pq_m,
        point_query_rel_overestimate_allitems_std=pq_s,
        point_query_rel_overestimate_top1pct=pqh1_m,
        point_query_rel_overestimate_top10pct=pqh10_m,
        point_query_abs_overestimate_mean=oa_m,
        f2_rel_error_min_mean=f2_m,
        f2_rel_error_min_std=f2_s,
        f2_rel_error_perrow_before_min=f2pr_m,
        ratio_f2_over_pq=f2_m / max(pq_m, 1e-12),
        ratio_pq_over_f2=pq_m / max(f2_m, 1e-12),
        point_query_rel_overestimate_top100=pqt100_m,
        point_query_rel_overestimate_top10=pqt10_m,
        point_query_rel_overestimate_top1=pqt1_m,
        f2_rel_error_theory_perrow=float(f2_exp_over / F2_true),
    )
    with open("results.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("\nWrote results.json")


if __name__ == "__main__":
    main()
