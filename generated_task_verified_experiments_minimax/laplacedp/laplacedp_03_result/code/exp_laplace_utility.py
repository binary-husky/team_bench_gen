"""
Experiment: How does the privacy budget ε affect the utility (MAE / RMSE)
of a count query under the Laplace mechanism?

We follow Dwork et al. (2006) "Calibrating Noise to Sensitivity in Private
Data Analysis". For a query f with L1-sensitivity S(f)=Δf, the Laplace
mechanism releases f(x) + Y where Y ~ Lap(0, Δf/ε). This release is
ε-indistinguishable.

We fix:
  - query: count of 1s in a binary database of n=10,000 rows
  - Δf = 1  (changing a single row changes the count by at most 1)
  - true count: c = 4723
  - number of trials per ε: 50,000
  - random seed: 42
And sweep ε in {0.01, 0.1, 0.5, 1, 2, 5}.

For Laplace(0, b):
  E[|Y|] = b        → theoretical MAE  = Δf/ε
  E[Y^2] = 2 b^2    → theoretical RMSE = sqrt(2) · Δf/ε
"""

import json
import numpy as np

# -----------------------------------------------------------------------
# Fixed experiment parameters
# -----------------------------------------------------------------------
N = 10_000                 # database size
TRUE_COUNT = 4_723         # true number of 1s in the database
DELTA_F = 1                # L1-sensitivity of a count query
EPSILONS = [0.01, 0.1, 0.5, 1.0, 2.0, 5.0]
TRIALS = 50_000
SEED = 42

rng = np.random.default_rng(SEED)

# -----------------------------------------------------------------------
# Theory: closed-form MAE and RMSE for Lap(0, Δf/ε)
# -----------------------------------------------------------------------
def laplace_mae_theory(eps, delta_f=DELTA_F):
    b = delta_f / eps
    return b                                # E[|Y|] for Lap(0, b)

def laplace_rmse_theory(eps, delta_f=DELTA_F):
    b = delta_f / eps
    return np.sqrt(2.0) * b                 # sqrt(E[Y^2]) for Lap(0, b)

# -----------------------------------------------------------------------
# Run the experiment
# -----------------------------------------------------------------------
rows = []
raw_err = {}      # store a small sample of errors for histograms
for eps in EPSILONS:
    b = DELTA_F / eps
    noise = rng.laplace(loc=0.0, scale=b, size=TRIALS)
    noisy_output = TRUE_COUNT + noise
    errors = noisy_output - TRUE_COUNT     # == noise, but kept symbolic
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    mae_th = laplace_mae_theory(eps)
    rmse_th = laplace_rmse_theory(eps)
    rows.append({
        "epsilon": eps,
        "noise_scale_b": b,
        "mae_empirical": mae,
        "mae_theory": mae_th,
        "mae_ratio": mae / mae_th,
        "rmse_empirical": rmse,
        "rmse_theory": rmse_th,
        "rmse_ratio": rmse / rmse_th,
        "abs_bias": float(np.mean(errors)),     # ~0 for symmetric noise
    })
    raw_err[eps] = errors[:2000]                 # subsample for plotting
    print(f"ε={eps:>5}: b={b:>8.2f}  "
          f"MAE  emp={mae:>9.4f}  th={mae_th:>9.4f}  "
          f"RMSE emp={rmse:>9.4f}  th={rmse_th:>9.4f}")

# -----------------------------------------------------------------------
# Save results
# -----------------------------------------------------------------------
with open("exp_results.json", "w") as f:
    json.dump({
        "fixed": {
            "N": N,
            "true_count": TRUE_COUNT,
            "delta_f": DELTA_F,
            "trials_per_epsilon": TRIALS,
            "random_seed": SEED,
            "query": "count of 1s in {0,1}^n (Δf = 1)",
        },
        "rows": rows,
    }, f, indent=2)

# -----------------------------------------------------------------------
# Plot MAE / RMSE vs ε
# -----------------------------------------------------------------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

eps_arr = np.array(EPSILONS)
mae_emp = np.array([r["mae_empirical"] for r in rows])
rmse_emp = np.array([r["rmse_empirical"] for r in rows])
mae_th = np.array([r["mae_theory"] for r in rows])
rmse_th = np.array([r["rmse_theory"] for r in rows])

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Linear scale
ax = axes[0]
ax.plot(eps_arr, mae_emp, "o-",  label="MAE empirical")
ax.plot(eps_arr, rmse_emp, "s-", label="RMSE empirical")
ax.plot(eps_arr, mae_th,  "o--", color="C0", alpha=0.5, label="MAE theory  (Δf/ε)")
ax.plot(eps_arr, rmse_th, "s--", color="C1", alpha=0.5, label="RMSE theory (√2·Δf/ε)")
ax.set_xlabel("ε (privacy budget)")
ax.set_ylabel("Error")
ax.set_title("Utility vs ε — linear scale")
ax.set_xticks(eps_arr)
ax.set_xticklabels([str(e) for e in eps_arr])
ax.grid(True, alpha=0.3)
ax.legend()

# Log-log scale
ax = axes[1]
ax.loglog(eps_arr, mae_emp,  "o-",  label="MAE empirical")
ax.loglog(eps_arr, rmse_emp, "s-",  label="RMSE empirical")
ax.loglog(eps_arr, mae_th,   "o--", color="C0", alpha=0.5, label="MAE theory  (Δf/ε)")
ax.loglog(eps_arr, rmse_th,  "s--", color="C1", alpha=0.5, label="RMSE theory (√2·Δf/ε)")
# Reference 1/ε lines
ref = 1.0 / eps_arr
ax.loglog(eps_arr, ref,   ":", color="gray", label="∝ 1/ε reference")
ax.loglog(eps_arr, np.sqrt(2) * ref, ":", color="lightgray", label="∝ √2/ε reference")
ax.set_xlabel("ε (privacy budget, log)")
ax.set_ylabel("Error (log)")
ax.set_title("Utility vs ε — log-log scale (slope −1 ⇒ ∝ 1/ε)")
ax.grid(True, which="both", alpha=0.3)
ax.legend()

fig.suptitle("Laplace mechanism on a count query (Δf=1, n=10,000, true=4723, 50,000 trials)")
fig.tight_layout()
fig.savefig("utility_vs_epsilon.png", dpi=130)
plt.close(fig)
print("\nSaved: exp_results.json, utility_vs_epsilon.png")

# -----------------------------------------------------------------------
# Error-distribution plots for a couple of ε values
# -----------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
for ax, eps in zip(axes, [0.1, 1.0]):
    b = DELTA_F / eps
    errs = raw_err[eps]
    ax.hist(errs, bins=60, density=True, alpha=0.6, label="empirical (2000)")
    # theoretical Laplace pdf
    xs = np.linspace(errs.min(), errs.max(), 400)
    pdf = (1.0 / (2 * b)) * np.exp(-np.abs(xs) / b)
    ax.plot(xs, pdf, "r-", lw=2, label=f"Lap(0, Δf/ε) pdf, b={b}")
    ax.set_title(f"ε={eps}, b=Δf/ε={b}")
    ax.set_xlabel("error (noisy − true)")
    ax.set_ylabel("density")
    ax.grid(True, alpha=0.3)
    ax.legend()
fig.suptitle("Error distributions vs theoretical Laplace(Δf/ε)")
fig.tight_layout()
fig.savefig("error_distributions.png", dpi=130)
plt.close(fig)
print("Saved: error_distributions.png")
