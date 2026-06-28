import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

d = np.load("results.npz")
kmpp = d["kmpp"]; rand = d["rand"]

fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

# Histogram overlay
ax = axes[0]
bins = np.linspace(8800, 15500, 24)
ax.hist(kmpp, bins=bins, alpha=0.6, label="k-means++", color="#2ca02c")
ax.hist(rand, bins=bins, alpha=0.6, label="random", color="#d62728")
ax.axvline(kmpp.mean(), color="#2ca02c", ls="--", lw=1.5,
           label=f"km++ mean={kmpp.mean():.0f}")
ax.axvline(rand.mean(), color="#d62728", ls="--", lw=1.5,
           label=f"random mean={rand.mean():.0f}")
ax.set_xlabel("final inertia"); ax.set_ylabel("# runs (out of 30)")
ax.set_title("Inertia distribution"); ax.legend(fontsize=8)

# Boxplot
ax = axes[1]
bp = ax.boxplot([kmpp, rand], labels=["k-means++", "random"],
                patch_artist=True, showmeans=True,
                meanprops=dict(marker="D", markerfacecolor="black", markersize=5))
for patch, c in zip(bp["boxes"], ["#2ca02c", "#d62728"]):
    patch.set_facecolor(c); patch.set_alpha(0.5)
ax.set_ylabel("final inertia")
ax.set_title("Spread & worst-case")

plt.tight_layout()
plt.savefig("inertia_distribution.png", dpi=120)
print("saved plot")
