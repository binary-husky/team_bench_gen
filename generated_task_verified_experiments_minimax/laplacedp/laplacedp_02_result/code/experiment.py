"""
Empirical verification of ε-indistinguishability for the Laplace mechanism.

Frozen setup (the only varying parameter is ε):
- Counting query f(D) = count of rows with attribute = 1 (global sensitivity Δf = 1)
- Adjacent datasets D, D' differ by exactly one row → f(D) − f(D') = 1
- Laplace mechanism implemented from scratch via NumPy:
    M(D) = f(D) + Lap(Δf / ε)            (np.random.default_rng(...).laplace)
- ~1 × 10^5 outputs per dataset per ε
- Frozen binning: bin width = 2 · scale(ε), range = ±12 · scale(ε),
                  plus a "well-populated" gate (both counts ≥ 30)
- Reproducible per-ε seed (changes with ε only)

For each ε we compute, on identical bins:
    • max_t  Pr[M(D) = t] / Pr[M(D') = t]   (well-populated bins)
    • max_t  Pr[M(D') = t] / Pr[M(D) = t]   (dual direction)
and compare against the theoretical ε-indistinguishability bound e^ε.
"""
import numpy as np

# ---- Frozen experimental settings ----
N_TRIALS = 100_000
EPSILONS = [0.1, 0.5, 1.0, 2.0]
DELTA_F = 1
F_D = 100
F_DP = 99                   # differ by one row → f(D) − f(D') = 1
SEED_BASE = 20260528        # reproducible base
MIN_COUNT = 30              # min-count gate for "well-populated" bins

# Frozen relative binning
BIN_W_FACTOR = 2.0          # bin width = BIN_W_FACTOR × scale(ε)
MARGIN_FACTOR = 12.0        # range  = ± MARGIN_FACTOR × scale(ε)


def run_one_epsilon(eps: float) -> dict:
    """Run the Laplace mechanism experiment for a single ε."""
    scale = DELTA_F / eps
    seed = SEED_BASE + int(round(eps * 1_000_000))
    rng = np.random.default_rng(seed)

    # Laplace noise from scratch (NumPy)
    noise_D = rng.laplace(loc=0.0, scale=scale, size=N_TRIALS)
    noise_Dp = rng.laplace(loc=0.0, scale=scale, size=N_TRIALS)

    output_D = F_D + noise_D
    output_Dp = F_DP + noise_Dp

    # Frozen binning
    bin_width = BIN_W_FACTOR * scale
    margin = MARGIN_FACTOR * scale
    center = (F_D + F_DP) / 2.0
    lo = center - margin
    hi = center + margin
    n_bins = int(np.ceil((hi - lo) / bin_width))
    bin_edges = lo + np.arange(n_bins + 1) * bin_width

    counts_D, _ = np.histogram(output_D, bins=bin_edges)
    counts_Dp, _ = np.histogram(output_Dp, bins=bin_edges)
    prob_D = counts_D / N_TRIALS
    prob_Dp = counts_Dp / N_TRIALS

    with np.errstate(divide='ignore', invalid='ignore'):
        ratio_fwd = np.where(prob_Dp > 0, prob_D / prob_Dp, np.nan)
        ratio_rev = np.where(prob_D > 0, prob_Dp / prob_D, np.nan)

    # Well-populated bins only (avoid extreme tails dominated by sampling noise)
    good = (counts_D >= MIN_COUNT) & (counts_Dp >= MIN_COUNT)
    n_good = int(good.sum())
    max_fwd_good = float(np.nanmax(ratio_fwd[good])) if n_good else float('nan')
    max_rev_good = float(np.nanmax(ratio_rev[good])) if n_good else float('nan')

    # Bins that attain the well-populated max
    if n_good:
        idx = int(np.nanargmax(np.where(good, ratio_fwd, -np.inf)))
        max_bin = (bin_edges[idx], bin_edges[idx + 1])
    else:
        max_bin = (float('nan'), float('nan'))

    theoretical = float(np.exp(eps))
    return {
        "epsilon": eps,
        "scale": scale,
        "n_bins": n_bins,
        "n_good": n_good,
        "max_fwd_good": max_fwd_good,
        "max_rev_good": max_rev_good,
        "theoretical_bound": theoretical,
        "max_bin_fwd_good": max_bin,
        "ratio_fwd_all": ratio_fwd,
        "counts_D": counts_D,
        "counts_Dp": counts_Dp,
        "bin_edges": bin_edges,
    }


def main():
    print("Laplace mechanism — empirical ε-indistinguishability check")
    print(f"  N trials per dataset : {N_TRIALS:,}")
    print(f"  Frozen query         : f(D)={F_D}, f(D')={F_DP}, Δf={DELTA_F}")
    print(f"  Frozen binning       : width={BIN_W_FACTOR}·scale, "
          f"range=±{MARGIN_FACTOR}·scale, gate=both counts ≥ {MIN_COUNT}")
    print(f"  ε values             : {EPSILONS}")
    print()
    col_eps = "ε"
    col_scale = "scale"
    col_bins = "bins"
    col_good = "good"
    col_fwd = "max Pr[M(D)]/Pr[M(D')]"
    col_rev = "max Pr[M(D')]/Pr[M(D)]"
    col_ee = "e^ε"
    header = (f"{col_eps:>5} {col_scale:>6} {col_bins:>5} {col_good:>5} "
              f"{col_fwd:>22} {col_rev:>22} {col_ee:>8}")
    print(header)
    rows = []
    for eps in EPSILONS:
        r = run_one_epsilon(eps)
        rows.append(r)
        print(f"{eps:>5.2f} {r['scale']:>6.2f} {r['n_bins']:>5d} {r['n_good']:>5d} "
              f"{r['max_fwd_good']:>22.6f} "
              f"{r['max_rev_good']:>22.6f} "
              f"{r['theoretical_bound']:>8.5f}")
    print()
    return rows


if __name__ == "__main__":
    main()