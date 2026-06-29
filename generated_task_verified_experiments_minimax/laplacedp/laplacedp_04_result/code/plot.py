"""Generate a plot of per-query error vs k."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

df = pd.read_csv("composition_table.csv")
fig, ax = plt.subplots(figsize=(7, 4.5))
ax.plot(df["k"], df["predicted |Y| = Δf/ε_q"], "o--",
        label=r"theory: $\Delta f/\varepsilon_q = k\cdot\Delta f/\varepsilon_{total}$")
ax.plot(df["k"], df["measured mean |Y|"], "s-",
        label="measured mean $|Y|$ (5 000 trials × k queries)")
ax.plot(df["k"], df["measured median |Y|"], "^-",
        label="measured median $|Y|$")
ax.set_xlabel("number of queries $k$")
ax.set_ylabel("per-query abs. error $|Y|$")
ax.set_title(r"Basic composition: per-query error vs $k$  "
             r"($\varepsilon_{total}=1,\;\Delta f=1$)")
ax.set_xticks(df["k"])
ax.legend()
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig("composition_plot.png", dpi=140)
print("Wrote composition_plot.png")
