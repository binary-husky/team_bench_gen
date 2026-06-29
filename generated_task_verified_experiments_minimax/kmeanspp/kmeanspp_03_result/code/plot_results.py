"""Generate a plot of approximation ratio distribution vs. k."""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

with open("raw_results.json") as f:
    data = json.load(f)

results = data["results"]
ks = [5, 10, 20, 50]

fig, axes = plt.subplots(1, 2, figsize=(13, 5))

# Left panel: boxplot of ratios per k
ax = axes[0]
ratios_by_k = [results[str(k)]["ratios"] for k in ks]
bp = ax.boxplot(ratios_by_k, positions=ks, widths=ks[0]*0.4, patch_artist=True)
for patch in bp["boxes"]:
    patch.set_facecolor("#a6cee3")
ax.set_xscale("log")
ax.set_xticks(ks)
ax.set_xticklabels([str(k) for k in ks])
ax.set_xlabel("k (number of clusters)")
ax.set_ylabel("Approximation ratio  inertia / OPT*")
ax.set_title("Approximation ratio distribution of k-means++")
ax.axhline(1.0, color="red", linestyle=":", alpha=0.5, label="ratio = 1.0")
ax.legend()
ax.grid(True, alpha=0.3)

# Right panel: empirical mean / max vs theoretical bounds
ax = axes[1]
means = [results[str(k)]["mean_ratio"] for k in ks]
maxs = [results[str(k)]["max_ratio"] for k in ks]
upper = [results[str(k)]["theoretical_bound_8_lnk_plus_2"] for k in ks]
lower = [results[str(k)]["theoretical_bound_2_lnk"] for k in ks]

ax.plot(ks, means, "o-", label="empirical mean ratio", color="#1f78b4")
ax.plot(ks, maxs, "s-", label="empirical max ratio (over 50 trials)", color="#e31a1c")
ax.plot(ks, upper, "^--", label=r"theoretical upper bound $8(\ln k + 2)$", color="#33a02c")
ax.plot(ks, lower, "v--", label=r"lower bound $2 \ln k$", color="#ff7f00")
ax.set_xscale("log")
ax.set_xticks(ks)
ax.set_xticklabels([str(k) for k in ks])
ax.set_xlabel("k (number of clusters)")
ax.set_ylabel("Approximation ratio")
ax.set_title("Empirical ratio vs. theoretical bounds")
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("approx_ratio.png", dpi=140)
print("Saved approx_ratio.png")
