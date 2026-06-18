"""Plot parameter-policy comparison (10-epoch screen + 30-epoch follow-up)."""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


COLORS = {
    "hidden_2d":     "#1F4E89",
    "no_first_conv": "#8B5CF6",
    "conv_only":     "#2ca02c",
    "all_2d":        "#D62728",
    "no_shortcut":   "#FF8C00",
}
LABEL = {
    "hidden_2d":     "hidden_2d   (baseline, paper)",
    "no_first_conv": "no_first_conv (stem→AdamW)",
    "conv_only":     "conv_only    (fc1/fc2→AdamW)",
    "all_2d":        "all_2d       (head→Muon)",
    "no_shortcut":   "no_shortcut  (shortcut→AdamW)",
}


def main():
    # 10-epoch data (all 5)
    ep10 = {}
    for p in ["hidden_2d", "no_first_conv", "conv_only", "all_2d", "no_shortcut"]:
        ep10[p] = [json.loads(l) for l in open(f"/tmp/policy_ep10/{p}.jsonl")]

    # 30-epoch data (3 policies)
    ep30 = {}
    for p in ["hidden_2d", "conv_only", "all_2d"]:
        ep30[p] = [json.loads(l) for l in open(f"/tmp/policy_ep30/{p}.jsonl")]

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))

    # Top-left: 10-epoch val_acc
    for p, log in ep10.items():
        ep = [r["epoch"] for r in log]
        va = [r["val_acc"] for r in log]
        axes[0, 0].plot(ep, va, label=LABEL[p], color=COLORS[p], lw=2)
        axes[0, 0].annotate(f"{va[-1]:.4f}", xy=(ep[-1], va[-1]),
                            xytext=(5, 0), textcoords="offset points",
                            color=COLORS[p], fontsize=8)
    axes[0, 0].set_title("10-epoch screen: validation accuracy (all 5 policies)")
    axes[0, 0].set_xlabel("Epoch"); axes[0, 0].set_ylabel("Val acc")
    axes[0, 0].grid(alpha=0.3); axes[0, 0].legend(fontsize=8, loc="lower right")
    axes[0, 0].set_ylim(0.65, 0.95)

    # Top-right: 10-epoch val_loss
    for p, log in ep10.items():
        ep = [r["epoch"] for r in log]
        vl = [r["val_loss"] for r in log]
        axes[0, 1].plot(ep, vl, label=LABEL[p], color=COLORS[p], lw=2)
        axes[0, 1].annotate(f"{vl[-1]:.3f}", xy=(ep[-1], vl[-1]),
                            xytext=(5, 0), textcoords="offset points",
                            color=COLORS[p], fontsize=8)
    axes[0, 1].set_title("10-epoch screen: validation loss (all 5 policies)")
    axes[0, 1].set_xlabel("Epoch"); axes[0, 1].set_ylabel("Val loss")
    axes[0, 1].grid(alpha=0.3); axes[0, 1].legend(fontsize=8, loc="upper right")

    # Bottom-left: 30-epoch val_acc
    for p, log in ep30.items():
        ep = [r["epoch"] for r in log]
        va = [r["val_acc"] for r in log]
        axes[1, 0].plot(ep, va, label=LABEL[p], color=COLORS[p], lw=2)
        axes[1, 0].annotate(f"{va[-1]:.4f}", xy=(ep[-1], va[-1]),
                            xytext=(5, 0), textcoords="offset points",
                            color=COLORS[p], fontsize=8)
    axes[1, 0].axvline(20, ls="--", color="gray", alpha=0.4)
    axes[1, 0].axvline(25, ls="--", color="gray", alpha=0.4)
    axes[1, 0].set_title("30-epoch follow-up: val accuracy (hidden_2d, conv_only, all_2d)")
    axes[1, 0].set_xlabel("Epoch"); axes[1, 0].set_ylabel("Val acc")
    axes[1, 0].grid(alpha=0.3); axes[1, 0].legend(fontsize=9, loc="lower right")
    axes[1, 0].set_ylim(0.65, 0.95)

    # Bottom-right: 30-epoch val_loss
    for p, log in ep30.items():
        ep = [r["epoch"] for r in log]
        vl = [r["val_loss"] for r in log]
        axes[1, 1].plot(ep, vl, label=LABEL[p], color=COLORS[p], lw=2)
        axes[1, 1].annotate(f"{vl[-1]:.3f}", xy=(ep[-1], vl[-1]),
                            xytext=(5, 0), textcoords="offset points",
                            color=COLORS[p], fontsize=8)
    axes[1, 1].axvline(20, ls="--", color="gray", alpha=0.4)
    axes[1, 1].axvline(25, ls="--", color="gray", alpha=0.4)
    axes[1, 1].set_title("30-epoch follow-up: val loss (lower = better)")
    axes[1, 1].set_xlabel("Epoch"); axes[1, 1].set_ylabel("Val loss")
    axes[1, 1].grid(alpha=0.3); axes[1, 1].legend(fontsize=9, loc="upper right")

    plt.tight_layout()
    plt.savefig("figures/param_policy.png", dpi=150)
    print("[done] -> figures/param_policy.png")


if __name__ == "__main__":
    main()
