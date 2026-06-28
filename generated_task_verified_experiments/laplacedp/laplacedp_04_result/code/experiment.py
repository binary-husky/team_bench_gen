"""
Composition of privacy loss experiment.

Fixed: a counting query, sensitivity Df, total budget eps_total, #trials, seed.
Only k (number of queries) varies in {1,5,10,20,50}.
Budget is split evenly: eps_q = eps_total / k.
Per query, Laplace mechanism with scale = Df / eps_q.
Record the average per-query absolute error (should scale ~ Df/eps_q = k*Df/eps_total).
"""
import numpy as np

# ---- Fixed setup (the ONLY free variable below is k) ----
eps_total = 1.0          # fixed total privacy budget
Df = 1.0                 # fixed sensitivity of the counting query
true_answer = 42.0       # fixed true (non-private) query answer
n_trials = 200000        # fixed number of trials per k
seed = 12345             # fixed random seed

ks = [1, 5, 10, 20, 50]

rng = np.random.default_rng(seed)

print(f"eps_total={eps_total}, Df={Df}, true_answer={true_answer}, "
      f"n_trials={n_trials}, seed={seed}")
print(f"{'k':>4} {'eps_q':>10} {'scale=Df/eps_q':>16} {'avg|err|':>12} "
      f"{'theory=k*Df/eps_total':>22} {'ratio_emp/theory':>16}")

results = []
for k in ks:
    eps_q = eps_total / k
    scale = Df / eps_q            # = k * Df / eps_total
    # Draw Laplace noise for n_trials independent queries (per-query error)
    noise = rng.laplace(loc=0.0, scale=scale, size=n_trials)
    # each query answers true_answer + noise; absolute error = |noise|
    abs_err = np.abs(noise)
    avg_err = abs_err.mean()
    theory = k * Df / eps_total   # = scale (mean abs deviation of Laplace(0,b) = b)
    ratio = avg_err / theory
    results.append((k, eps_q, scale, avg_err, theory, ratio))
    print(f"{k:>4} {eps_q:>10.6f} {scale:>16.6f} {avg_err:>12.6f} "
          f"{theory:>22.6f} {ratio:>16.6f}")

# Save raw results for the summary
import json
with open("results.json", "w") as f:
    json.dump({
        "eps_total": eps_total, "Df": Df, "true_answer": true_answer,
        "n_trials": n_trials, "seed": seed,
        "rows": [dict(k=r[0], eps_q=r[1], scale=r[2], avg_abs_err=r[3],
                      theory_mean_abs=r[4], ratio=r[5]) for r in results],
    }, f, indent=2)
print("\nSaved results.json")
