"""Render a small comparison bar chart from results.json.

Kept separate from ``experiment.py`` so the experiment itself stays a
pure-data producer.  Saves ``coverage_comparison.png`` next to
``results.json`` for the summary report.
"""

import json
import matplotlib

matplotlib.use("Agg")                       # no display, just write file
import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    data = json.load(open("results.json"))

    seeds = data["config"]["seeds"]
    sym_per = [r["coverage_pct"] for r in data["symex"] if r["seed"] != -1]
    rnd_per = [r["coverage_pct"] for r in data["random"] if r["seed"] != -1]
    sym_agg = next(r["coverage_pct"] for r in data["symex"] if r["seed"] == -1)
    rnd_agg = next(r["coverage_pct"] for r in data["random"] if r["seed"] == -1)

    fig, ax = plt.subplots(figsize=(7.5, 4.2))

    # per-seed bars
    x = np.arange(len(seeds))
    width = 0.35
    ax.bar(x - width / 2, sym_per, width, label="Symbolic execution (DSE)",
           color="#1f77b4", edgecolor="black")
    ax.bar(x + width / 2, rnd_per, width, label="Random testing",
           color="#ff7f0e", edgecolor="black")

    # aggregate dashed line
    ax.axhline(sym_agg, color="#1f77b4", linestyle="--", linewidth=1,
               label=f"SymEx aggregate = {sym_agg:.0f}%")
    ax.axhline(rnd_agg, color="#ff7f0e", linestyle="--", linewidth=1,
               label=f"Random aggregate = {rnd_agg:.0f}%")

    ax.set_xticks(x)
    ax.set_xticklabels([f"seed={s}" for s in seeds])
    ax.set_ylabel("Branch coverage (%)")
    ax.set_ylim(0, 110)
    ax.set_title(
        "Symbolic execution vs. random testing\n"
        "target: f(x) with magic branch  x == 12345"
    )
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(axis="y", linestyle=":", alpha=0.6)
    for i, (a, b) in enumerate(zip(sym_per, rnd_per)):
        ax.text(i - width / 2, a + 1.5, f"{a:.1f}%", ha="center", fontsize=8)
        ax.text(i + width / 2, b + 1.5, f"{b:.1f}%", ha="center", fontsize=8)

    fig.tight_layout()
    fig.savefig("coverage_comparison.png", dpi=130)
    print("Wrote coverage_comparison.png")


if __name__ == "__main__":
    main()
