"""Plot the distinct-final-states count per CRDT / control as a bar chart."""

import json
import os
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


HERE = os.path.dirname(os.path.abspath(__file__))


def plot():
    with open(os.path.join(HERE, "results.json")) as f:
        data = json.load(f)
    summary = data["summary"]
    n_scenarios = next(iter(summary.values()))["n_scenarios"]

    # Display order
    order = [
        ("g_counter", "G-Counter (CRDT)"),
        ("pn_counter", "PN-Counter (CRDT)"),
        ("lww", "LWW-Register (CRDT)"),
        ("or_set", "OR-Set (CRDT)"),
        ("naive_last_write", "Naive last-write (control)"),
        ("naive_accum", "Naive accumulator (control)"),
    ]

    keys = [k for k, _ in order]
    labels = [lbl for _, lbl in order]
    distinct = [summary[k]["n_distinct"] for k in keys]

    colors = ["#2a9d8f"] * 4 + ["#e76f51"] * 2

    fig, ax = plt.subplots(figsize=(9, 5.5))
    bars = ax.bar(labels, distinct, color=colors, edgecolor="black")
    ax.set_ylabel(f"Distinct final states (out of {n_scenarios})")
    ax.set_xlabel("Type")
    ax.set_title(f"CRDT merge convergence under {n_scenarios} out-of-order + duplicate deliveries")
    ax.set_ylim(0, max(distinct) * 1.15)
    ax.axhline(1, color="grey", linestyle="--", linewidth=0.7, label="target = 1")
    for bar, v in zip(bars, distinct):
        ax.text(bar.get_x() + bar.get_width() / 2, v + max(distinct) * 0.01,
                str(v), ha="center", va="bottom", fontsize=10)
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    out_path = os.path.join(HERE, "distinct_states.png")
    plt.savefig(out_path, dpi=140)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    plot()