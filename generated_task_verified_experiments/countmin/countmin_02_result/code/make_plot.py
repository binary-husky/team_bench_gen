"""Analyse results_cm_02.json: power-law fit (log-log slope ~ -1) + figure."""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

with open("results_cm_02.json") as f:
    R = json.load(f)

fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
colors = {"zipf": "tab:red", "uniform": "tab:blue"}
labels = {"zipf": "Zipfian (s≈1.0)", "uniform": "Uniform"}

print("=== power-law fit  error ≈ const * w^slope  (expect slope ≈ -1) ===")
for dist in ["zipf", "uniform"]:
    rows = R[dist]["rows"]
    w = np.array([r["w"] for r in rows], dtype=float)
    for stat in ["mean", "p99"]:
        y = np.array([r[stat] for r in rows], dtype=float)
        slope, intercept = np.polyfit(np.log2(w), np.log2(y), 1)
        print(f"  {dist:8s} {stat:5s}: slope = {slope:.3f}")
    for ax, stat, title in [(axes[0], "mean", "Mean over-estimate  â[i]-a[i]"),
                            (axes[1], "p99", "99th-percentile over-estimate")]:
        y = np.array([r[stat] for r in rows], dtype=float)
        ax.loglog(w, y, "o-", color=colors[dist], label=labels[dist], lw=2, ms=7)

# reference 1/w line anchored at w=128, uniform-mean value
for ax in axes:
    w = np.array([r["w"] for r in R["uniform"]["rows"]], dtype=float)
    y0 = R["uniform"]["rows"][0]["mean"] if ax is axes[0] else R["uniform"]["rows"][0]["p99"]
    ref = y0 * (w[0] / w)  # pure 1/w
    ax.loglog(w, ref, "k--", alpha=0.4, label="∝ 1/w reference")
    ax.set_xlabel("width w (buckets, log scale)")
    ax.set_ylabel("over-estimate (log scale)")
    ax.set_title(title)
    ax.grid(True, which="both", ls=":", alpha=0.5)
    ax.legend()
    ax.set_xticks(w)
    ax.set_xticklabels([str(int(x)) for x in w], rotation=30)

fig.suptitle("Count-Min Sketch (d=5): point-query over-estimate vs width w  "
             "(1e6 updates, 1e5-item universe, mean of 5 seeds)", fontsize=12)
fig.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig("cm_02_width_vs_error.png", dpi=130)
print("wrote cm_02_width_vs_error.png")
