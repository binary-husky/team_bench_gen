"""
Experiment: effect of query sensitivity Δf on Laplace-mechanism error.

Material: Dwork, McSherry, Nissim, Smith (2006), "Calibrating Noise to
Sensitivity in Private Data Analysis". The Laplace mechanism adds noise with
scale b = Δf / ε, where Δf = S(f) is the L1 sensitivity of the query f and ε
is the privacy parameter. We fix ε and the data, vary the query type (i.e. Δf),
and measure the mean absolute error (MAE) of the released answer.

Queries:
  (a) count query : Δf = 1
  (b) sum query on [0, B] with B = 10 : Δf = B = 10
  (c) mean query over n records : Δf = 1/n

Theory: Laplace(0, b) has E|X| = b = Δf/ε, so MAE should be linear in Δf
(and equal to 1/ε · Δf) and independent of the database size for a fixed query.
"""
import numpy as np

# ---- fixed settings ----
EPSILON = 1.0          # privacy parameter ε (fixed)
N = 1000               # data size (number of records)
B = 10                 # range bound for sum query values in [0, B]
TRIALS = 200_000       # number of noisy releases per query
SEED = 20260626        # fixed random seed for reproducibility

rng = np.random.default_rng(SEED)

# Build a fixed database once.
# count query: count of records satisfying a predicate (here, value > 0).
# sum query : sum of values in [0, B].
# mean query: mean of values.
# We use non-negative integer-ish values in [0, B]; for the count we count
# records with value >= 1 (predicate is_binary = value>=1).
values = rng.integers(low=0, high=B + 1, size=N)  # values in {0,...,B}

true_count = int(np.sum(values >= 1))   # (a) count query
true_sum   = float(np.sum(values))      # (b) sum query
true_mean  = float(np.mean(values))     # (c) mean query

def laplace_release(true_answer, sensitivity, eps, n_trials, rng):
    """Release true_answer + Laplace(0, sensitivity/eps), n_trials times."""
    scale = sensitivity / eps
    noise = rng.laplace(loc=0.0, scale=scale, size=n_trials)
    releases = true_answer + noise
    return releases

# Sensitivities
delta_count = 1.0          # (a)
delta_sum   = float(B)     # (b) = B
delta_mean  = 1.0 / N      # (c)

# Run experiments (one independent stream per query, all from same seed root)
rel_count = laplace_release(true_count, delta_count, EPSILON, TRIALS, rng)
rel_sum   = laplace_release(true_sum,   delta_sum,   EPSILON, TRIALS, rng)
rel_mean  = laplace_release(true_mean,  delta_mean,  EPSILON, TRIALS, rng)

mae_count = np.mean(np.abs(rel_count - true_count))
mae_sum   = np.mean(np.abs(rel_sum   - true_sum))
mae_mean  = np.mean(np.abs(rel_mean  - true_mean))

# Theoretical MAE = scale = Δf / ε
th_count = delta_count / EPSILON
th_sum   = delta_sum   / EPSILON
th_mean  = delta_mean  / EPSILON

print("=" * 72)
print(f"Fixed: epsilon={EPSILON}, N={N}, B={B}, trials={TRIALS}, seed={SEED}")
print(f"true count={true_count}, true sum={true_sum}, true mean={true_mean:.4f}")
print("=" * 72)
print(f"{'query':<14}{'Δf':>10}{'scale=Δf/ε':>14}{'MAE meas':>14}{'MAE theory':>14}")
print("-" * 72)
print(f"{'count':<14}{delta_count:>10.4f}{th_count:>14.4f}{mae_count:>14.4f}{th_count:>14.4f}")
print(f"{'sum [0,B]':<14}{delta_sum:>10.4f}{th_sum:>14.4f}{mae_sum:>14.4f}{th_sum:>14.4f}")
print(f"{'mean':<14}{delta_mean:>10.6f}{th_mean:>14.6f}{mae_mean:>14.6f}{th_mean:>14.6f}")
print("-" * 72)
print(f"ratio MAE_sum / MAE_count   = {mae_sum/mae_count:.4f}  (theory {delta_sum/delta_count:.4f})")
print(f"ratio MAE_count / MAE_mean  = {mae_count/mae_mean:.4f}  (theory {delta_count/delta_mean:.4f})")
print(f"linear fit slope MAE vs Δf  = {np.polyfit([delta_mean, delta_count, delta_sum], [mae_mean, mae_count, mae_sum], 1)[0]:.6f}  (theory 1/ε={1/EPSILON})")

# Persist machine-readable numbers for the summary
import json
out = {
    "epsilon": EPSILON, "N": N, "B": B, "trials": TRIALS, "seed": SEED,
    "true_count": true_count, "true_sum": true_sum, "true_mean": true_mean,
    "queries": [
        {"name": "count",    "delta_f": delta_count, "scale": th_count, "mae": float(mae_count), "mae_theory": th_count},
        {"name": "sum[0,B]", "delta_f": delta_sum,   "scale": th_sum,   "mae": float(mae_sum),   "mae_theory": th_sum},
        {"name": "mean",     "delta_f": delta_mean,  "scale": th_mean,  "mae": float(mae_mean),  "mae_theory": th_mean},
    ],
}
with open("results.json", "w") as f:
    json.dump(out, f, indent=2)
print("\nwrote results.json")
