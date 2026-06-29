"""Render the empirical-vs-theory plot for the summary."""
import json
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

with open("results.json") as fh:
    res = json.load(fh)

fs = sorted(res.keys(), key=float)
ratio_th = [res[f]["ratio_theory"] for f in fs]
ratio_hat = [res[f]["ratio_hat_mean"] for f in fs]
eps_th = [res[f]["eps_theory"] for f in fs]
eps_hat = [res[f]["eps_hat_mean"] for f in fs]

# std across seeds for the empirical values (showing sampling noise)
ratio_std = [np.std([s["ratio_hat"] for s in res[f]["per_seed"]]) for f in fs]
eps_std = [np.std([s["eps_hat"] for s in res[f]["per_seed"]]) for f in fs]

fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

axes[0].errorbar(
    fs,
    ratio_hat,
    yerr=ratio_std,
    fmt="o-",
    color="C0",
    label="empirical $\\hat r$ (mean ± std across seeds)",
    capsize=4,
)
axes[0].plot(fs, ratio_th, "s--", color="C1", label="theory $(2-f)/f$")
axes[0].set_xlabel("f (PRR perturbation probability)")
axes[0].set_ylabel("probability ratio $r = P[1|b=1] / P[1|b=0]$")
axes[0].set_title("Empirical vs theoretical ratio")
axes[0].set_yscale("log")
axes[0].legend()
axes[0].grid(True, which="both", alpha=0.3)

axes[1].errorbar(
    fs,
    eps_hat,
    yerr=eps_std,
    fmt="o-",
    color="C0",
    label="empirical $\\hat\\varepsilon$ (mean ± std across seeds)",
    capsize=4,
)
axes[1].plot(fs, eps_th, "s--", color="C1", label="theory $\\ln((2-f)/f)$")
axes[1].set_xlabel("f (PRR perturbation probability)")
axes[1].set_ylabel("$\\varepsilon$ (natural log)")
axes[1].set_title("Empirical vs theoretical LDP budget")
axes[1].legend()
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("plot_ratio_eps.png", dpi=120)
print("wrote plot_ratio_eps.png")