"""
Empirical verification of epsilon-indistinguishability of the Laplace mechanism.

FIXED setup (only epsilon varies):
  - Query  f = #{rows with attribute==1}; global sensitivity Df = 1.
  - Adjacent D, D' differing in one row, f(D)-f(D') = 1:
        D  = [1,1,1,1,1]  -> f(D)  = 5
        D' = [1,1,1,1,0]  -> f(D') = 4
  - Mechanism  M(D) = f(D) + Lap(0, b),  b = Df/eps = 1/eps
    (np.random.laplace(scale=1/eps)).
  - 1e5 independent draws of M(D) and of M(D') per eps.
  - Fixed random seed per eps.
  - Common histogram grid (same edges for D and D').

Theory (Dwork et al. 2006, epsilon-indistinguishability):
  For ANY measurable set S,  Pr[M(D) in S] <= e^eps * Pr[M(D') in S].
  For the point density ratio r(t)=p_D(t)/p_D'(t) one can show exactly
      r(t) = exp((|t-f(D')|-|t-f(D)|)/b),
  which equals  e^eps  on the whole right tail t>=f(D), equals e^{-eps} on
  the left tail t<=f(D'), and interpolates in between. Hence the TRUE max
  ratio is exactly e^eps. We compare empirical estimates to this bound.

Two empirical metrics per eps:
  (A) max per-bin empirical ratio over bins with adequate support in BOTH
      datasets (>= MIN_COUNT samples each) -- the literal "max over bins".
      Because we take a max over many noisy bin estimates, this can slightly
      exceed e^eps purely from finite-sample order statistics.
  (B) pooled right-tail ratio over [f(D), f(D)+TAIL]: a single low-variance
      estimate of the population ratio in the region where it equals e^eps.
"""
import numpy as np
import json

SEED = 20240626
N_TRIALS = 100_000
EPSILONS = [0.1, 0.5, 1.0, 2.0]

D = np.array([1, 1, 1, 1, 1])
Dp = np.array([1, 1, 1, 1, 0])

def f(db):
    return int(np.sum(db == 1))

fD, fDp = f(D), f(Dp)
Delta = abs(fD - fDp)
assert Delta == 1

# Common grid: wide enough for eps=0.1 (b=10), fine bins.
BIN_WIDTH = 0.5
GRID_MIN = min(fD, fDp) - 80.0
GRID_MAX = max(fD, fDp) + 80.0
edges = np.arange(GRID_MIN, GRID_MAX + BIN_WIDTH, BIN_WIDTH)
centers = 0.5 * (edges[:-1] + edges[1:])

MIN_COUNT = 30          # min samples in BOTH D and D' for a bin to count in (A)
TAIL = 30.0             # right-tail window [f(D), f(D)+TAIL] for pooled metric (B)

print(f"f(D)={fD}, f(D')={fDp}, |f(D)-f(D')|={Delta} (=Df=1)")
print(f"D,D' differ in {(D!=Dp).sum()} row. Trials={N_TRIALS}, bin_width={BIN_WIDTH}")
print("-" * 92)

rows = []
for eps in EPSILONS:
    b = Delta / eps
    rng = np.random.default_rng(SEED)
    MD  = fD  + rng.laplace(0.0, b, size=N_TRIALS)
    MDp = fDp + rng.laplace(0.0, b, size=N_TRIALS)

    cD, _  = np.histogram(MD,  bins=edges)
    cDp, _ = np.histogram(MDp, bins=edges)
    pD, pDp = cD / N_TRIALS, cDp / N_TRIALS

    # (A) per-bin max over well-supported bins
    mask = (cD >= MIN_COUNT) & (cDp >= MIN_COUNT)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(mask, pD / pDp, np.nan)
    ratio_masked = np.where(mask, ratio, -np.inf)
    idx_max = int(np.argmax(ratio_masked))
    max_ratio = float(ratio_masked[idx_max]) if mask.any() else float("nan")
    t_max = float(centers[idx_max]) if mask.any() else float("nan")

    # (B) pooled right-tail ratio over [fD, fD+TAIL] (true ratio == e^eps here)
    in_tail = (centers >= fD) & (centers <= fD + TAIL)
    sumD  = int(cD[in_tail].sum())
    sumDp = int(cDp[in_tail].sum())
    pooled = sumD / sumDp if sumDp else float("nan")

    bound = float(np.exp(eps))
    rows.append(dict(eps=eps, b=b, max_ratio=max_ratio, t_max=t_max,
                     pooled=pooled, sumD=sumD, sumDp=sumDp, bound=bound))

hdr = (f"{'eps':>4} | {'b':>6} | {'max bin-ratio(A)':>16} | {'t*':>7} | "
       f"{'pooled rt-tail(B)':>17} | {'e^eps':>7} | {'B/e^eps':>8}")
print(hdr)
print("-" * 92)
for r in rows:
    print(f"{r['eps']:4.1f} | {r['b']:6.3f} | {r['max_ratio']:16.4f} | {r['t_max']:7.2f} | "
          f"{r['pooled']:17.4f} | {r['bound']:7.4f} | {r['pooled']/r['bound']:8.4f}")
print("-" * 92)
print("(A) max per-bin empirical ratio over bins with >=30 samples in both D and D'.")
print("(B) pooled ratio over right tail [f(D), f(D)+30], where the TRUE ratio == e^eps.")
print("    B/e^eps near 1.0 confirms the mechanism saturates the bound at e^eps.")

with open("results.json", "w") as fh:
    json.dump(dict(seed=SEED, n_trials=N_TRIALS, fD=fD, fDp=fDp, Delta=Delta,
                   bin_width=BIN_WIDTH, min_count=MIN_COUNT, tail=TAIL,
                   results=rows), fh, indent=2)
print("\nWrote results.json")
