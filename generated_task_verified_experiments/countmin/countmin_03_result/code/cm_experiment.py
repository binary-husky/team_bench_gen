"""
Count-Min Sketch: depth d vs tail-failure probability.

Reproduces CM sketch (Cormode & Muthukrishnan) from scratch with d pairwise-
independent Carter-Wegman hash rows. Goal: at fixed width w, show that the
point-query tail-failure probability Pr[ a_hat_i > a_i + eps*||a||_1 ] decays
~exponentially in d (theory bound: <= (1/e)^d = e^{-d}).
"""
import numpy as np
import csv, json, time

# ---------------- Fixed experiment parameters ----------------
w       = 1024                       # fixed width
EPS     = np.e / w                   # epsilon = e/w  (->  err threshold = eps*||a||_1)
N       = 100_000                    # universe of item ids 0..N-1  ("1e5 distinct items")
N_UPD   = 1_000_000                  # 1e6 updates, all +1 (cash-register / non-negative)
S_ZIPF  = 1.0                        # Zipfian exponent
DEPTHS  = [1, 2, 3, 4, 5, 8]
N_SEEDS = 3000                       # >= 20 seeds; many seeds -> resolve tiny deep-d rates
P_PRIME = 2147483647                 # 2^31 - 1  (Mersenne prime) for Carter-Wegman
D_MAX   = max(DEPTHS)

# ---------------- 1. Build the stream (frequencies) ----------------
# Sample N_UPD item ids i.i.d. from Zipfian(s) over ranks 1..N.
# The CM sketch is LINEAR in the +1 updates, so count[j,h(i)] equals the
# scatter-add of the true frequency vector a -> we may build the sketch from a.
rng_data = np.random.default_rng(20240601)
ranks = np.arange(1, N + 1, dtype=np.float64)
pmf = 1.0 / np.power(ranks, S_ZIPF)
pmf /= pmf.sum()
cdf = np.cumsum(pmf)
u = rng_data.random(N_UPD)
ids_stream = np.searchsorted(cdf, u, side="right")          # 0..N-1
a = np.bincount(ids_stream, minlength=N).astype(np.float64) # true frequencies
L1 = a.sum()                                                 # ||a||_1
distinct = int((a > 0).sum())
T = EPS * L1                                                 # error threshold

ids_all = np.arange(N, dtype=np.int64)
print(f"||a||_1 = {L1:.0f}   distinct items present = {distinct}/{N}")
print(f"w={w}  eps=e/w={EPS:.6f}   T = eps*||a||_1 = {T:.3f}")
print(f"max a_i = {a.max():.0f}  (a_1 expected ~ {N_UPD*pmf[0]:.0f})")
print(f"||a||_1 / w = {L1/w:.2f}  (= E[collision noise per row],  T/e = {T/np.e:.2f})")
print()

# ---------------- 2. CM sketch: per-seed build + point query ----------------
def make_hashes(rng, d):
    """Return d independent (a,b) pairs -> pairwise-independent h(x)=((a*x+b)%p)%w."""
    return rng.integers(1, P_PRIME, size=d), rng.integers(0, P_PRIME, size=d)

results = {d: np.empty(N_SEEDS) for d in DEPTHS}
under_count = 0

t0 = time.time()
for seed in range(N_SEEDS):
    rng = np.random.default_rng(7 + seed * 101)
    aj, bj = make_hashes(rng, D_MAX)

    # build all D_MAX rows: bucket array + count row via weighted histogram
    rows   = np.empty((D_MAX, w), dtype=np.float64)
    bucket = np.empty((D_MAX, N), dtype=np.int64)
    for j in range(D_MAX):
        bkt = ((aj[j] * ids_all + bj[j]) % P_PRIME) % w
        bucket[j] = bkt
        rows[j] = np.bincount(bkt, weights=a, minlength=w)   # count[j,k]=sum_{h(i)=k} a[i]

    # point query every item for each requested depth
    for d in DEPTHS:
        ahat = rows[0, bucket[0]].copy()
        for j in range(1, d):
            np.minimum(ahat, rows[j, bucket[j]], out=ahat)
        fail = ahat > (a + T)                       # strictly exceed threshold
        results[d][seed] = fail.mean()
        if d == DEPTHS[-1]:
            # cash-register invariant: estimate never below truth (Theorem 1)
            under_count += int((ahat < a).sum())

    if (seed + 1) % 500 == 0:
        print(f"  seed {seed+1}/{N_SEEDS}  ({time.time()-t0:.1f}s)")

dt = time.time() - t0
print(f"\nDone {N_SEEDS} seeds in {dt:.1f}s\n")

# ---------------- 3. Summarize ----------------
mean = {d: results[d].mean() for d in DEPTHS}
sem  = {d: results[d].std(ddof=1) / np.sqrt(N_SEEDS) for d in DEPTHS}
FLOOR = 1.0 / (N * N_SEEDS)            # smallest non-zero item fraction resolvable

print(f"\ncash-register invariant violations (a_hat < a, over all item-seed at d={DEPTHS[-1]}): "
      f"{under_count}  -> {'OK (never underestimates)' if under_count==0 else 'VIOLATED'}")
print(f"measurement floor (1/(N*N_SEEDS)) = {FLOOR:.2e}\n")

# per-row rate p1 = measured d=1 failure rate; independence-across-rows predicts rate[d] = p1^d
p1 = mean[1]
print(f"per-row (d=1) failure rate  p1 = {p1:.4e}   (theory upper bound 1/e = {1/np.e:.4e})\n")

print(f"{'d':>3} {'mean fail-rate':>14} {'±sem':>11} {'e^-d bound':>12} "
      f"{'p1^d pred':>12} {'meas/bound':>11} {'meas/p1^d':>10}")
rows_out = []
for d in DEPTHS:
    theo = np.exp(-d)
    pred = p1 ** d
    m, s = mean[d], sem[d]
    rb = (m / theo) if theo else float("nan")
    rp = (m / pred) if pred else float("nan")
    print(f"{d:>3} {m:>14.4e} {s:>11.1e} {theo:>12.4e} {pred:>12.4e} {rb:>11.0e} {rp:>10.2f}")
    rows_out.append((d, m, s, theo, pred))

# per-row geometric multiplier between successive depths
print("\nper-row multiplier mean[d]/mean[d-1]  (constant <==> exponential in d; bound = 1/e):")
for d0, d1 in zip(DEPTHS[:-1], DEPTHS[1:]):
    if mean[d0] > 0 and mean[d1] > 0:
        print(f"  d={d0}->d={d1}:  {mean[d1]/mean[d0]:.4f}")
    elif mean[d0] > 0:
        print(f"  d={d0}->d={d1}:  < {FLOOR/mean[d0]:.2e}  (numerator below measurement floor)")

# log-linear fit of ln(rate) vs d over NONZERO measurements (slope -> per-row multiplier)
ds = np.array(DEPTHS, dtype=float)
ms = np.array([mean[d] for d in DEPTHS])
nz = ms > 0
slope, intercept = np.polyfit(ds[nz], np.log(ms[nz]), 1)
print(f"\nlog-linear fit on nonzero points (d={list(ds[nz].astype(int))}):")
print(f"  ln(rate) = {slope:.4f}*d + {intercept:.4f}")
print(f"  fitted per-row multiplier = exp(slope) = {np.exp(slope):.4f}   "
      f"(theory bound 1/e = {1/np.e:.4f})")
print(f"  fitted rate[d=1] = exp(intercept) = {np.exp(intercept):.4e}  (measured p1 = {p1:.4e})")

# ---------------- 4. Persist raw data ----------------
with open("cm_results_raw.csv", "w", newline="") as f:
    wr = csv.writer(f)
    wr.writerow(["seed"] + [f"d{d}" for d in DEPTHS])
    for s in range(N_SEEDS):
        wr.writerow([s] + [f"{results[d][s]:.6e}" for d in DEPTHS])

summary = dict(w=w, eps=float(EPS), N=N, N_UPD=N_UPD, S_ZIPF=S_ZIPF,
               L1=float(L1), distinct=distinct, T=float(T),
               N_SEEDS=N_SEEDS, P_PRIME=P_PRIME, FLOOR=float(FLOOR),
               under_count=under_count,
               mean={str(d): float(mean[d]) for d in DEPTHS},
               sem={str(d): float(sem[d]) for d in DEPTHS},
               theory={str(d): float(np.exp(-d)) for d in DEPTHS},
               p1=float(p1), p1_pow_d={str(d): float(p1**d) for d in DEPTHS},
               fit_slope=float(slope), fit_intercept=float(intercept),
               fit_multiplier=float(np.exp(slope)))
with open("cm_results_summary.json", "w") as f:
    json.dump(summary, f, indent=2)

# ---------------- 5. Plot ----------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(7.2, 5))
mm = np.array([max(mean[d], FLOOR * 0.3) for d in DEPTHS])   # keep zeros visible on log axis
ss = np.array([sem[d] for d in DEPTHS])
ax.errorbar(DEPTHS, mm, yerr=ss, fmt="o-", color="C0", capsize=4, ms=6,
            label=f"empirical tail-failure rate (mean ± sem, {N_SEEDS} seeds)")
ax.plot(ds, np.exp(-ds), "k--", lw=1.4, label=r"theory bound  $(1/e)^d = e^{-d}$")
ax.plot(ds, p1 ** ds, "C1:", lw=1.6,
        label=rf"independence prediction  $p_1^{{d}},\ p_1={p1:.3f}$")
ax.axhline(FLOOR, color="grey", ls="-.", lw=1, label=f"measurement floor ({FLOOR:.0e})")
ax.set_yscale("log")
ax.set_xlabel("depth d  (number of independent pairwise-independent hash rows)")
ax.set_ylabel(r"Pr$[\hat a_i > a_i + \varepsilon\|a\|_1]$   (fraction of items)")
ax.set_title(f"Count-Min tail-failure vs depth   "
             f"(w={w}, eps=e/w={EPS:.4f}, ||a||$_1$={L1:.0f}, Zipf s={S_ZIPF})")
ax.set_xticks(DEPTHS)
ax.grid(True, which="both", ls=":", alpha=0.5)
ax.legend(fontsize=8, loc="upper right")
fig.tight_layout()
fig.savefig("cm_depth_vs_tail.png", dpi=130)
print("\nSaved cm_results_raw.csv, cm_results_summary.json, cm_depth_vs_tail.png")
