#!/usr/bin/env python3
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

with open("results.json") as fh:
    data = json.load(fh)

F = data["config"]["F_VALUES"]
R = data["config"]["R_VALUES"]

mean = {r: [] for r in R}
std = {r: [] for r in R}
for r in R:
    for f in F:
        m, s = data["summary"][f"{r},{f}"]
        mean[r].append(m)
        std[r].append(s)

fig, ax = plt.subplots(figsize=(7.2, 4.8))
ax.errorbar(F, mean[1], yerr=std[1], marker='o', ms=7, capsize=4,
            lw=2, color='#d62728', label='r = 1 (single successor)')
ax.errorbar(F, mean[16], yerr=std[16], marker='s', ms=7, capsize=4,
            lw=2, color='#1f77b4', label='r = 16 (successor list)')

# theoretical upper bound for r=1: P(responsible's ring-predecessor alive) = 1 - f
ax.plot(F, [1 - f for f in F], '--', color='#d62728', alpha=0.5,
        label='r=1 upper bound  1 − f')

ax.set_xlabel("failure fraction  f", fontsize=12)
ax.set_ylabel("lookup success rate", fontsize=12)
ax.set_title(f"Chord routing robustness vs node failure  (N = {data['config']['N']}, "
             f"{data['config']['N_QUERIES']} lookups/point)", fontsize=12)
ax.set_xticks(F)
ax.set_ylim(-0.03, 1.05)
ax.set_xlim(-0.02, 0.52)
ax.grid(True, alpha=0.3)
ax.legend(loc='upper right', fontsize=10)
fig.tight_layout()
fig.savefig("failure_tolerance_plot.png", dpi=130)
print("wrote failure_tolerance_plot.png")
