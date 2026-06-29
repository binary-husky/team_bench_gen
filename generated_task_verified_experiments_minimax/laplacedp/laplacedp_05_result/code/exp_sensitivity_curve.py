"""
Complementary sweep: vary Δf over several orders of magnitude (with ε, n, seed
and trial count held fixed) and record the empirical mean absolute error of
the Laplace mechanism. This produces a clean "error vs Δf" curve that
complements the three discrete query examples required by the task.
"""

import numpy as np
import json
from pathlib import Path

SEED   = 42
EPS    = 1.0
TRIALS = 20000

rng = np.random.default_rng(SEED)

# pick a wide log-uniform range of sensitivities
delta_fs = np.logspace(-3, 2, 16)  # 0.001, ..., 100

# For each Δf we use a synthetic true value 0 (just the noise itself,
# since E|X| depends only on the noise scale, not on the true value).
records = []
for delta in delta_fs:
    scale = delta / EPS
    noise = rng.laplace(0.0, scale, size=TRIALS)
    records.append({
        "delta_f":      float(delta),
        "scale_b":      float(scale),
        "empirical_mae": float(np.mean(np.abs(noise))),
        "theoretical_mae": float(scale),  # E|X| = b for X~Lap(0,b)
    })

# print
print(f"Sweep: ε={EPS}, trials={TRIALS}, seed={SEED}\n")
print(f"{'Δf':>10} {'b=Δf/ε':>12} {'theory MAE':>12} {'empirical MAE':>16} {'ratio':>8}")
print("-" * 64)
for r in records:
    ratio = r["empirical_mae"] / r["theoretical_mae"]
    print(f"{r['delta_f']:>10.4f} {r['scale_b']:>12.4f} {r['theoretical_mae']:>12.4f} "
          f"{r['empirical_mae']:>16.4f} {ratio:>8.4f}")

out = Path(__file__).with_name("sensitivity_curve.json")
out.write_text(json.dumps(
    {"settings": {"epsilon": EPS, "trials": TRIALS, "seed": SEED},
     "records": records},
    indent=2))
print(f"\nSaved to {out}")
