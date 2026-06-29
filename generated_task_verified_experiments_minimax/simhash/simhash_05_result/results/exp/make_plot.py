"""Make a small plot from the experiment results."""
import json
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

here = os.path.dirname(__file__)
with open(os.path.join(here, "results.json")) as f:
    d = json.load(f)
pp = d["per_pair"]
c_t  = np.array(pp["cos_true"])
j_t  = np.array(pp["jac_true"])
c_e  = np.array(pp["cos_est"])
j_e  = np.array(pp["jac_est"])
sh_err = np.abs(c_e - c_t)
mh_err = np.abs(j_e - j_t)

# Three panels
fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

# Panel 1: error vs true cosine
ax = axes[0]
ax.scatter(c_t, sh_err, s=4, alpha=0.25, label="SimHash (cosine)")
ax.scatter(c_t, mh_err, s=4, alpha=0.25, label="MinHash (Jaccard)")
ax.set_xlabel("true cosine")
ax.set_ylabel("|estimate − true|")
ax.set_title("Per-pair error vs. true cosine")
ax.set_xlim(-0.05, 1.05)
ax.set_ylim(0, 0.45)
ax.legend(loc="upper right")
ax.grid(alpha=0.3)

# Panel 2: error distribution (overall)
ax = axes[1]
bins = np.linspace(0, 0.45, 46)
ax.hist(sh_err, bins=bins, alpha=0.6, label=f"SimHash (mean {sh_err.mean():.3f})", density=True)
ax.hist(mh_err, bins=bins, alpha=0.6, label=f"MinHash (mean {mh_err.mean():.3f})", density=True)
ax.set_xlabel("absolute estimation error")
ax.set_ylabel("density")
ax.set_title("Error distribution (all 8800 pairs)")
ax.set_xlim(0, 0.45)
ax.legend()
ax.grid(alpha=0.3)

# Panel 3: estimator vs estimator on the same pair
ax = axes[2]
ax.scatter(c_t, c_e, s=4, alpha=0.25, label="SimHash est. (cos)")
ax.scatter(j_t, j_e, s=4, alpha=0.25, label="MinHash est. (jac)")
xx = np.linspace(0, 1, 100)
ax.plot(xx, xx, "k--", lw=0.8, label="ideal")
ax.set_xlabel("true similarity")
ax.set_ylabel("estimated similarity")
ax.set_title("Estimators on the same pairs")
ax.set_xlim(-0.05, 1.05)
ax.set_ylim(-0.25, 1.05)
ax.legend()
ax.grid(alpha=0.3)

plt.tight_layout()
out = os.path.join(here, "results.png")
plt.savefig(out, dpi=120)
print("wrote", out)
