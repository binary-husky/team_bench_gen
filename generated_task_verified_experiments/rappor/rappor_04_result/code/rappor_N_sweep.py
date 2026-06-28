"""
RAPPOR accuracy-vs-N sweep.

Reuses the *complete* RAPPOR encode-decode pipeline (Bloom -> PRR -> IRR ->
IRR+PRR debias -> non-negative least-squares over the candidate design matrix).

Goal: show that the aggregated frequency-estimation error falls ~ 1/sqrt(N).

Fixed (same as _03):
  M = 20 candidates, k = 128 bloom bits, h = 4 hashes,
  PRR f = 0.5, IRR p = 0.5, q = 0.75.
Swept: N in {2e3, 5e3, 1e4, 2e4, 5e4, 1e5}, >=3 seeds each.
"""

import hashlib
import json

import numpy as np
from scipy.optimize import nnls

# ---------------------------------------------------------------------------
# Fixed configuration
# ---------------------------------------------------------------------------
K = 128            # bloom bits
H = 4              # hashes per value
F = 0.5            # PRR
P = 0.5            # IRR p  (Pr[1 | 0])
Q = 0.75           # IRR q  (Pr[1 | 1])
M = 20             # candidates

CANDIDATES = [
    "google.com", "youtube.com", "facebook.com", "amazon.com", "reddit.com",
    "wikipedia.org", "twitter.com", "instagram.com", "netflix.com", "github.com",
    "linkedin.com", "discord.com", "spotify.com", "twitch.tv", "paypal.com",
    "dropbox.com", "slack.com", "zoom.us", "ebay.com", "craigslist.org",
]

# True frequency distribution: a few heavy hitters + a long tail.
# Hand-tuned to sum to 1.
RAW = np.array([
    0.18, 0.12, 0.09, 0.07, 0.06,
    0.05, 0.04, 0.035, 0.03, 0.025,
    0.02, 0.018, 0.015, 0.013, 0.011,
    0.009, 0.008, 0.007, 0.006, 0.004,
])
TRUE_FREQ = RAW / RAW.sum()
assert len(TRUE_FREQ) == M

N_GRID = [2_000, 5_000, 10_000, 20_000, 50_000, 100_000]
SEEDS = [11, 22, 33, 44]
CHUNK = 16_384


# ---------------------------------------------------------------------------
# Bloom encoding (deterministic, per candidate)
# ---------------------------------------------------------------------------
def hash_positions(value: str, idx: int) -> int:
    """h-th hash -> a bit position in [0, K)."""
    digest = hashlib.blake2b(f"{idx}|{value}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") % K


def bloom_vector(value: str) -> np.ndarray:
    v = np.zeros(K, dtype=np.int8)
    for i in range(H):
        v[hash_positions(value, i)] = 1
    return v


# Precompute design matrix X: shape (K, M), X[j, c] = 1 if cand c sets bit j.
BLOOM = np.stack([bloom_vector(c) for c in CANDIDATES])  # (M, K)
X = BLOOM.T.astype(np.float64)                            # (K, M)


# ---------------------------------------------------------------------------
# RAPPOR encode + aggregate
# ---------------------------------------------------------------------------
def estimate_freq(N: int, seed: int) -> np.ndarray:
    """Run full pipeline for N clients, return estimated freq vector (M,)."""
    rng = np.random.default_rng(seed)

    # Sample each client's true string from the true distribution.
    choices = rng.choice(M, size=N, p=TRUE_FREQ)
    # True bloom vectors for all clients: (N, K)
    # built in chunks to keep memory low.

    ones_sum = np.zeros(K, dtype=np.float64)  # sum of IRR 1-bits per position

    start = 0
    while start < N:
        end = min(start + CHUNK, N)
        idx = choices[start:end]
        B = BLOOM[idx]  # (b, K) int8

        # ---- PRR: with prob f replace bit with uniform bit, else keep ----
        r_mask = rng.random(B.shape) < F
        r_rand = (rng.random(B.shape) < 0.5).astype(np.int8)
        prr = np.where(r_mask, r_rand, B).astype(np.int8)

        # ---- IRR: Pr[1 | prr=1] = q,  Pr[1 | prr=0] = p ----
        r2 = rng.random(B.shape)
        irr = np.where(prr == 1, r2 < Q, r2 < P).astype(np.int8)

        ones_sum += irr.sum(axis=0)
        start = end

    t = ones_sum / N  # observed 1-fraction per bit

    # ---- Debias: remove IRR then PRR ----
    # Step 1 (IRR): y = (t - p)/(q - p)        -> Pr[PRR bit = 1]
    # Step 2 (PRR): s = (y - f/2)/(1 - f)      -> Pr[true Bloom bit = 1]
    y = (t - P) / (Q - P)
    s = (y - F / 2.0) / (1.0 - F)
    s = np.clip(s, 0.0, 1.0)  # (K,)

    # ---- Decode: solve s ≈ X @ freq,  freq >= 0 ----
    freq, _ = nnls(X, s)
    total = freq.sum()
    if total > 0:
        freq = freq / total
    return freq


def errors(p_hat: np.ndarray) -> tuple[float, float]:
    diff = p_hat - TRUE_FREQ
    return float(np.abs(diff).sum()), float(np.max(np.abs(diff)))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(f"{'N':>8} | {'L1_mean':>10} {'L1_std':>10} | "
          f"{'max_mean':>10} {'max_std':>10}")
    print("-" * 65)
    rows = []
    for N in N_GRID:
        l1s, maxs, phats = [], [], []
        for s in SEEDS:
            ph = estimate_freq(N, s)
            l1, mx = errors(ph)
            l1s.append(l1)
            maxs.append(mx)
            phats.append(ph)
        rows.append({
            "N": N,
            "L1_mean": float(np.mean(l1s)),
            "L1_std": float(np.std(l1s)),
            "L1_seeds": [float(x) for x in l1s],
            "max_mean": float(np.mean(maxs)),
            "max_std": float(np.std(maxs)),
            "max_seeds": [float(x) for x in maxs],
        })
        r = rows[-1]
        print(f"{N:>8} | {r['L1_mean']:>10.5f} {r['L1_std']:>10.5f} | "
              f"{r['max_mean']:>10.5f} {r['max_std']:>10.5f}")

    # --- 1/sqrt(N) regression on L1 (log-log) ---
    ns = np.array([r["N"] for r in rows], float)
    l1 = np.array([r["L1_mean"] for r in rows], float)
    mx = np.array([r["max_mean"] for r in rows], float)

    def fit_slope(y):
        a = np.log(ns); b = np.log(y)
        slope = np.polyfit(a, b, 1)[0]
        return float(slope)

    slope_l1 = fit_slope(l1)
    slope_max = fit_slope(mx)
    # doubling test: error ratio when N x4 (expect ~1/2 if slope -1/2)
    def ratio_x4(y):
        # compare first vs last grid points spanning N: 2e3 -> 1e5 (x50)
        return float(y[0] / y[-1])

    summary = {
        "params": {"K": K, "H": H, "F": F, "P": P, "Q": Q, "M": M,
                   "candidates": CANDIDATES, "true_freq": TRUE_FREQ.tolist(),
                  "seeds": SEEDS},
        "rows": rows,
        "loglog_slope_L1": slope_l1,
        "loglog_slope_max": slope_max,
        "L1_ratio_N0_over_Nlast": ratio_x4(l1),
        "max_ratio_N0_over_Nlast": ratio_x4(mx),
    }
    print(f"\nlog-log slope (L1)  = {slope_l1:.4f}  (expect ~ -0.50)")
    print(f"log-log slope (max) = {slope_max:.4f}  (expect ~ -0.50)")
    # N needed for L1 <= 0.1 by extrapolation
    # L1(N) ~ C / sqrt(N); use anchor at largest N (least bias floor).
    C = l1[-1] * np.sqrt(ns[-1])
    N_target = float((C / 0.1) ** 2)
    print(f"anchor C = L1*sqrt(N) at N=1e5: {C:.4f}")
    print(f"N needed for L1<=0.1 (extrap): {N_target:.3e}")
    summary["N_for_L1_le_0.1_extrap"] = N_target
    summary["anchor_C"] = float(C)

    # crude estimate at N0/4 doubling pairs
    pairs = [(0, 2), (1, 3), (2, 4), (3, 5)]  # roughly x4-ish steps? check
    # our grid: 2e3,5e3,1e4,2e4,5e4,1e5 -> x4 pairs: (2e3->2e4?) not exact.
    # Use consecutive ratios to show ~x2 error per ~x4 N.

    # consecutive-step ratios (error should drop ~ sqrt(N ratio))
    def consec(y):
        out = []
        for i in range(len(ns) - 1):
            out.append(float(y[i] / y[i + 1]))
        return out
    n_ratios = [float(ns[i] / ns[i + 1]) for i in range(len(ns) - 1)]
    sqrt_n_ratios = [float(np.sqrt(r)) for r in n_ratios]
    summary["consec_N_ratio"] = n_ratios
    summary["consec_sqrtN_ratio_expected"] = sqrt_n_ratios
    summary["consec_L1_ratio"] = consec(l1)
    summary["consec_max_ratio"] = consec(mx)

    # asymptotic slope using upper half (N >= 1e4), where small-N saturation
    # no longer distorts the fit
    half = len(ns) // 2
    slope_l1_asym = float(np.polyfit(np.log(ns[half:]), np.log(l1[half:]), 1)[0])
    slope_max_asym = float(np.polyfit(np.log(ns[half:]), np.log(mx[half:]), 1)[0])
    summary["loglog_slope_L1_asymptotic"] = slope_l1_asym
    summary["loglog_slope_max_asymptotic"] = slope_max_asym
    print(f"asymptotic slope (N>=1e4)  L1={slope_l1_asym:.4f}  max={slope_max_asym:.4f}")
    print("consec N ratios     :", [f"{x:.2f}" for x in n_ratios])
    print("expected sqrtN ratio:", [f"{x:.3f}" for x in sqrt_n_ratios])
    print("consec L1 ratios    :", [f"{x:.3f}" for x in summary["consec_L1_ratio"]])

    with open("results.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print("\nWrote results.json")

    # ---- plot ----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(6.5, 5))
        ax.loglog(ns, l1, "o-", label="L1 error $\\sum|\\hat p-p|$")
        ax.loglog(ns, mx, "s-", label="max abs error $\\max|\\hat p-p|$")
        # reference 1/sqrt(N) line, anchored at the largest N for L1
        ref = l1[-1] * np.sqrt(ns[-1]) / np.sqrt(ns)
        ax.loglog(ns, ref, ":", color="gray", label="$\\propto 1/\\sqrt{N}$ (ref)")
        ax.set_xlabel("number of clients $N$")
        ax.set_ylabel("frequency estimation error")
        ax.set_title("RAPPOR aggregated frequency error vs $N$\n"
                     f"k={K}, h={H}, f={F}, p={P}, q={Q}, M={M}")
        ax.grid(True, which="both", ls="-", alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig("error_vs_N.png", dpi=120)
        print("Wrote error_vs_N.png")
    except Exception as e:
        print("plot failed:", e)


if __name__ == "__main__":
    main()
