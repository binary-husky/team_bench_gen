"""
Privacy-utility tradeoff experiment: effect of epsilon on utility of the
Laplace mechanism for a counting query.

Fixed setting:
  - Query        : count of records satisfying a predicate in a dataset of N=10000
                   (true value = f(D))
  - Sensitivity  : Delta_f = 1   (adding/removing one record changes the count by at most 1)
  - Mechanism    : Laplace(scale = Delta_f / epsilon)
  - Trials       : T = 200000 independent noise draws per epsilon
  - Random seed  : fixed (seed=0) for reproducibility
Only independent variable: epsilon in {0.01, 0.1, 0.5, 1, 2, 5}
Metrics: MAE and RMSE of the noisy output w.r.t. the true value.
"""

import numpy as np

# ---- Fixed experimental setup ----
SEED = 0
N_TRIALS = 200_000
Delta_f = 1.0          # sensitivity of a counting query
TRUE_VALUE = 1234.0    # arbitrary true count; utility metrics are shift-invariant
EPSILONS = [0.01, 0.1, 0.5, 1.0, 2.0, 5.0]

rng = np.random.default_rng(SEED)

print(f"Fixed: Delta_f={Delta_f}, true_value={TRUE_VALUE}, trials={N_TRIALS}, seed={SEED}")
print(f"{'eps':>6} {'scale':>10} {'MAE':>12} {'RMSE':>12} {'theo_MAE':>10} {'theo_RMSE':>10} {'theo_std':>10}")
print("-" * 82)

rows = []
for eps in EPSILONS:
    scale = Delta_f / eps
    # Laplace noise, location 0, scale = scale
    noise = rng.laplace(loc=0.0, scale=scale, size=N_TRIALS)
    noisy = TRUE_VALUE + noise
    err = noisy - TRUE_VALUE            # = noise
    mae = np.mean(np.abs(err))
    rmse = np.sqrt(np.mean(err ** 2))

    # Theoretical values for a Laplace(0, b) distribution:
    #   E|X|   = b          (mean absolute deviation)
    #   E[X^2] = 2 b^2      => RMSE = b * sqrt(2)
    #   std    = b * sqrt(2)
    theo_mae = scale
    theo_rmse = scale * np.sqrt(2.0)
    theo_std = scale * np.sqrt(2.0)

    rows.append((eps, scale, mae, rmse, theo_mae, theo_rmse, theo_std))
    print(f"{eps:6.2f} {scale:10.4f} {mae:12.4f} {rmse:12.4f} "
          f"{theo_mae:10.4f} {theo_rmse:10.4f} {theo_std:10.4f}")

# Save to a small csv for reference
import csv
with open("results.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["epsilon", "scale_Df_over_eps", "MAE", "RMSE",
                "theoretical_MAE", "theoretical_RMSE", "theoretical_std"])
    for r in rows:
        w.writerow([f"{x:.6f}" for x in r])
print("\nSaved results.csv")
