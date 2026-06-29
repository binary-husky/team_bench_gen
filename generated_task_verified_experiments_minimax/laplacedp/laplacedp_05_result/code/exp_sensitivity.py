"""
Empirical study of how query sensitivity Δf drives the noise/utility of the
Laplace mechanism (Dwork, McSherry, Nissim, Smith 2006).

For a fixed privacy budget ε we evaluate the Laplace mechanism on three queries
with very different global sensitivities:

    (a) count query      f(x) = Σ x_i,  x_i ∈ {0,1}      -> Δf = 1
    (b) bounded sum      f(x) = Σ x_i,  x_i ∈ [0, B]    -> Δf = B
    (c) mean query       f(x) = (1/n) Σ x_i, x_i ∈ [0,1] -> Δf = 1/n

For each query we:
    1. sample one "true" database (data size n, fixed seed),
    2. compute the true answer f(x) once,
    3. add i.i.d. Laplace noise of scale b = Δf / ε to the true answer,
    4. repeat the noisy release `trials` times and average the
       mean absolute error  E[ |M(x) − f(x)| ].

Everything is reproducible (seed=42). The only independent variable is the
query type — i.e. Δf. ε, n, trials and the seed are held constant.
"""

import numpy as np
import json
from pathlib import Path

# ---------- fixed experimental settings ----------
SEED       = 42
EPS        = 1.0          # privacy budget ε  (FIXED)
N          = 1000         # data size n       (FIXED)
TRIALS     = 20000        # Monte-Carlo trials (FIXED)
B          = 10.0         # upper bound of x_i for the bounded-sum query

rng = np.random.default_rng(SEED)


# ---------- the three query types ----------
def make_data():
    """Sample one database per query type, sharing the same global seed."""
    # (a) binary vector, one Bernoulli(0.5) draw per row
    x_bin = rng.integers(0, 2, size=N).astype(float)
    # (b) bounded vector, uniform on [0, B]
    x_sum = rng.uniform(0.0, B, size=N)
    # (c) mean: same bounded vector, rescaled to [0,1] for a clean 1/n sensitivity
    x_mean = rng.uniform(0.0, 1.0, size=N)
    return x_bin, x_sum, x_mean


def laplace_noise(scale, size, rng):
    """Draw `size` i.i.d. samples from Lap(0, scale)."""
    return rng.laplace(loc=0.0, scale=scale, size=size)


def run_query(true_value, sensitivity, eps, trials, rng):
    """Run Laplace mechanism `trials` times, return mean absolute error."""
    scale = sensitivity / eps
    noise = laplace_noise(scale, trials, rng)
    noisy = true_value + noise
    mae = float(np.mean(np.abs(noisy - true_value)))
    # also report std-of-error and theoretical MAE = scale (E|X| = b for Lap(b))
    return {
        "sensitivity": float(sensitivity),
        "scale_b":     float(scale),
        "theoretical_mae": float(scale),                 # E|X| = b for X~Lap(0,b)
        "empirical_mae":  mae,
        "empirical_std":  float(np.std(np.abs(noisy - true_value))),
    }


# ---------- main ----------
x_bin, x_sum, x_mean = make_data()

queries = [
    ("a) Count query       (binary, Δf=1)",
        float(x_bin.sum()), 1.0),

    ("b) Bounded sum query  (x_i ∈ [0,B], Δf=B, B=10)",
        float(x_sum.sum()), float(B)),

    ("c) Mean query         (x_i ∈ [0,1],   Δf=1/n)",
        float(x_mean.mean()), 1.0 / N),
]

results = []
for name, true_val, sens in queries:
    res = run_query(true_val, sens, EPS, TRIALS, rng)
    res["name"] = name
    res["true_value"] = true_val
    results.append(res)

# ---------- pretty print ----------
print(f"Settings: ε={EPS}, n={N}, trials={TRIALS}, seed={SEED}\n")
print(f"{'query':<46} {'Δf':>10} {'b=Δf/ε':>10} {'theory MAE':>12} {'empirical MAE':>16}")
print("-" * 96)
for r in results:
    print(f"{r['name']:<46} {r['sensitivity']:>10.4f} {r['scale_b']:>10.4f} "
          f"{r['theoretical_mae']:>12.4f} {r['empirical_mae']:>16.4f}")

# Empirical law: MAE ≈ Δf / ε
print("\nRatio empirical/theoretical MAE (should be ≈ 1):")
for r in results:
    ratio = r["empirical_mae"] / r["theoretical_mae"]
    print(f"  {r['name']:<46}  {ratio:.4f}")

# ---------- save to JSON for the report ----------
out_path = Path(__file__).with_name("sensitivity_results.json")
out_path.write_text(json.dumps(
    {
        "settings": {"epsilon": EPS, "n": N, "trials": TRIALS, "seed": SEED, "B": B},
        "results": results,
    },
    indent=2,
))
print(f"\nResults saved to {out_path}")
