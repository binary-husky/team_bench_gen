"""
Differential Privacy Composition Experiment

Per the task: For k queries, the basic composition theorem allocates
ε_q = ε_total/k per query, with each query's Laplace noise scale
= Δf/ε_q. The per-query error should grow linearly with k
(Δf/ε_q = k·Δf/ε_total).
"""

import numpy as np
import pandas as pd

# ----- Fixed parameters -----
EPS_TOTAL = 1.0          # total privacy budget
DELTA_F   = 1.0          # sensitivity of a sum query (binary DB)
N         = 100_000      # database size
TRIALS    = 5_000        # Monte-Carlo repetitions
SEED      = 42           # reproducibility
KS        = [1, 5, 10, 20, 50]

rng = np.random.default_rng(SEED)

# Synthesise a fixed database of binary entries.
true_db = rng.integers(0, 2, size=N)
true_sum = int(true_db.sum())   # true answer

# Pre-define a deterministic sequence of k "queries". A query f_i is
# identified by a boolean mask; for the sum-of-rows case all f_i are
# the same linear sum, so what matters is the *per-query* noise.
# We simulate this as k re-evaluations of the same noisy sum each round.
# A single "noisy release" for query i is:
#     y_i = sum(masked rows) + Lap(Δf / ε_q)
# Error_i = |y_i - true answer for that query|.

print(f"true_sum = {true_sum}")
print(f"Δf = {DELTA_F}, ε_total = {EPS_TOTAL}, N = {N}, trials = {TRIALS}\n")

records = []
abs_errs_by_k = {}

# We share one big random stream across all k so that the per-query
# noise is drawn i.i.d. conditional on ε_q — this keeps the comparison
# between k values statistically clean and independent of any one seed.
# We pre-draw an array of uniform uniforms → invert the Laplace CDF.

def laplace_noise(scale, n, gen):
    """Sample n i.i.d. Laplace(0, scale) using inverse-CDF."""
    u = gen.uniform(-0.5, 0.5, size=n)
    return -scale * np.sign(u) * np.log(1 - 2 * np.abs(u))

for k in KS:
    eps_q   = EPS_TOTAL / k                # budget per query
    scale   = DELTA_F / eps_q              # Laplace scale b = Δf/ε_q
    expected_err = scale                   # E|Y| = b  (mean abs. dev.)

    # TRIALS independent replications; in each replication all k queries
    # are evaluated once. Total noise draws = TRIALS * k.
    all_errs = np.empty(TRIALS * k)
    # Draw all k*TRIALS i.i.d. Laplace noises at once.
    noise = laplace_noise(scale, TRIALS * k, rng)
    # The per-query error = |noise|.  Reshape to (TRIALS, k).
    errs = np.abs(noise).reshape(TRIALS, k)
    mean_err   = errs.mean()                # mean abs error
    median_err = np.median(errs)            # median abs error
    std_err    = errs.std(ddof=1) / np.sqrt(TRIALS * k)  # SEM

    abs_errs_by_k[k] = errs.mean(axis=0)    # store per-trial mean error

    records.append({
        "k": k,
        "eps_q = eps_total/k": eps_q,
        "scale = Δf/ε_q": scale,
        "predicted |Y| = Δf/ε_q": expected_err,
        "measured mean |Y|": mean_err,
        "measured median |Y|": median_err,
        "SEM (mean)": std_err,
        "ratio measured/predicted": mean_err / expected_err,
    })
    print(
        f"k={k:>3d}  ε_q={eps_q:.4f}  scale={scale:7.4f}  "
        f"mean |Y|={mean_err:7.4f}  median |Y|={median_err:7.4f}  "
        f"ratio={mean_err/expected_err:.4f}"
    )

df = pd.DataFrame(records)
print("\n", df.to_string(index=False), "\n")

# ----- Sanity checks -----
print("=== Composition sanity checks ===")
# 1. mean |Y| should scale linearly with k.
xs = np.array([r["k"]             for r in records])
ys = np.array([r["measured mean |Y|"] for r in records])
slope, intercept = np.polyfit(xs, ys, 1)
print(f"Linear fit: mean|Y| ≈ {slope:.4f}·k + {intercept:.4f}")
print(f"  (theory: slope = Δf/ε_total = {DELTA_F/EPS_TOTAL})")

# 2. total noise injected across the k queries grows as k·scale.
total_noise_sq = sum(((DELTA_F / (EPS_TOTAL / k)) ** 2) * k for k in KS)
print(f"Sum of k·scale² across all k: {total_noise_sq:.4f}  (should be constant ="
      f" {KS[-1]*(DELTA_F/(EPS_TOTAL/KS[-1]))**2:.4f} for largest k)")

# Save the table.
df.to_csv("composition_table.csv", index=False)
print("\nWrote composition_table.csv")
