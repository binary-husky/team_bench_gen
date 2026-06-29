"""Generate relative-error-vs-n plot from experiment_results.json."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
with open(HERE / "experiment_results.json") as f:
    data = json.load(f)

P = data["p"]
M = data["m"]
SE = data["theoretical_SE"]
summary = data["summary"]
raw = data["raw"]

ns = [s["n"] for s in summary]
means = np.array([s["mean_rel_err"] for s in summary])
stds = np.array([s["std_rel_err"] for s in summary])
mins = np.array([s["min_rel_err"] for s in summary])
maxs = np.array([s["max_rel_err"] for s in summary])

fig, ax = plt.subplots(figsize=(7.5, 4.6))
ax.errorbar(ns, means * 100, yerr=stds * 100,
            marker="o", linewidth=1.4, capsize=4, color="#1f77b4",
            label=f"empirical mean ± std (5 seeds, p={P}, m={M})")
# scatter the individual runs
ax.scatter([r["n"] for r in raw],
           [r["rel_err"] * 100 for r in raw],
           s=20, alpha=0.55, color="#1f77b4", zorder=2)
# theoretical SE
ax.axhline(SE * 100, linestyle="--", color="green",
           label=f"theoretical SE = 1.04/√m = {SE*100:.3f}%")
ax.axhline(-SE * 100, linestyle="--", color="green")

ax.set_xscale("log")
ax.set_xticks(ns)
ax.set_xticklabels([f"{n:,}" for n in ns])
ax.set_xlabel("true cardinality n")
ax.set_ylabel("relative error  |Ê − n| / n  (%)")
ax.set_title(f"HyperLogLog relative error vs n (p={P}, m={M} registers)")
ax.grid(True, which="both", linestyle=":", alpha=0.5)
ax.legend(loc="upper right", framealpha=0.9)
ax.set_ylim(-1.7, 1.7)

fig.tight_layout()
out = HERE / "rel_err_vs_n.png"
fig.savefig(out, dpi=130)
print(f"wrote {out}")