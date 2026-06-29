"""Build the privacy-utility figure from results_raw.json."""
import json
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


with open("results_raw.json") as fp:
    data = json.load(fp)

f_values = data["settings"]["f_values"]
rappor   = data["rappor"]
baseline = data["baseline"]

# Aggregate per-f (mean +/- std across seeds)
agg = {}
for r in rappor:
    agg.setdefault(r["f"], {"l1": [], "mx": [], "eps": r["epsilon_perm"]})
    agg[r["f"]]["l1"].append(r["l1_error"])
    agg[r["f"]]["mx"].append(r["max_abs_error"])

fs = sorted(agg.keys())
eps = [agg[f]["eps"] for f in fs]
l1_mean = [np.mean(agg[f]["l1"]) for f in fs]
l1_std  = [np.std(agg[f]["l1"])  for f in fs]
mx_mean = [np.mean(agg[f]["mx"]) for f in fs]
mx_std  = [np.std(agg[f]["mx"])  for f in fs]

# Two panels: error vs epsilon (privacy-utility trade-off), error vs f
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

ax = axes[0]
ax.errorbar(eps, l1_mean, yerr=l1_std, marker="o", lw=2, capsize=4,
            label="RAPPOR L1 error")
ax.errorbar(eps, mx_mean, yerr=mx_std, marker="s", lw=2, capsize=4,
            label="RAPPOR max-abs error")
ax.axhline(baseline["l1_mean"],  ls="--", color="C0",
           label=f"non-private L1 = {baseline['l1_mean']:.1f}")
ax.axhline(baseline["max_mean"], ls="--", color="C1",
           label=f"non-private max = {baseline['max_mean']:.1f}")
ax.set_xlabel(r"$\varepsilon_{\rm perm} = \ln\!\left(\frac{2-f}{f}\right)$")
ax.set_ylabel("Frequency-estimation error (count units)")
ax.set_title("Privacy–utility trade-off (lower ε = stronger privacy)")
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

ax = axes[1]
ax.errorbar(fs, l1_mean, yerr=l1_std, marker="o", lw=2, capsize=4,
            label="RAPPOR L1 error")
ax.errorbar(fs, mx_mean, yerr=mx_std, marker="s", lw=2, capsize=4,
            label="RAPPOR max-abs error")
ax.axhline(baseline["l1_mean"],  ls="--", color="C0",
           label=f"non-private L1 = {baseline['l1_mean']:.1f}")
ax.axhline(baseline["max_mean"], ls="--", color="C1",
           label=f"non-private max = {baseline['max_mean']:.1f}")
ax.set_xlabel("PRR parameter  f  (probability of replacing a Bloom bit)")
ax.set_ylabel("Frequency-estimation error (count units)")
ax.set_title("Error grows as f increases (privacy ↑, utility ↓)")
ax.set_xticks(fs)
ax.legend(fontsize=8)
ax.grid(alpha=0.3)

fig.tight_layout()
fig.savefig("privacy_utility.png", dpi=130)
print("saved privacy_utility.png")

# Also a text summary table
print()
print(f"{'f':>6} {'eps_perm':>9} {'L1 mean':>10} {'L1 std':>9} "
      f"{'max mean':>10} {'max std':>9}")
for f, e, lm, ls, mm, ms in zip(fs, eps, l1_mean, l1_std, mx_mean, mx_std):
    print(f"{f:6.2f} {e:9.4f} {lm:10.2f} {ls:9.2f} {mm:10.2f} {ms:9.2f}")
print(f"\nBaseline (non-private): L1 = {baseline['l1_mean']:.2f} +/- "
      f"{baseline['l1_std']:.2f},  max = {baseline['max_mean']:.2f} +/- "
      f"{baseline['max_std']:.2f}")