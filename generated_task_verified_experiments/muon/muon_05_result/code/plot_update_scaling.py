"""Plot Muon update-scaling x weight-decay ablation."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load(path):
    return [json.loads(l) for l in open(path)]


SCALINGS = ["paper", "none", "sqrt_rows_cols", "rms_match", "spectral_clip"]
# File shortname (sqrt_rows_cols uses 'sqrt' in filenames)
SCALING_FN = {
    "paper":         "paper",
    "none":          "none",
    "sqrt_rows_cols": "sqrt",
    "rms_match":     "rms",
    "spectral_clip": "spec",
}
SCALING_LABEL = {
    "paper":         "paper\n(√max(1,r/c))",
    "none":          "none\n(1.0)",
    "sqrt_rows_cols": "sqrt_rows_cols\n(√r/c)",
    "rms_match":     "rms_match\n(rms(m)/rms(O))",
    "spectral_clip": "spectral_clip\n(cap ‖O‖₂)",
}
SCALING_COLOR = {
    "paper":         "#1F4E89",  # deep blue
    "none":          "#5B8E7D",  # green
    "sqrt_rows_cols": "#8B5CF6",  # purple
    "rms_match":     "#D62728",  # red
    "spectral_clip": "#D9843A",  # orange
}
WDS = ["wd0", "wd5e4", "wd2e3"]


def main():
    fig = plt.figure(figsize=(18, 11))
    gs = fig.add_gridspec(2, 3)

    # ---- Top row: 3 heatmaps (best_va, gap, ep_90) ----
    # (1) best val_acc heatmap
    ax = fig.add_subplot(gs[0, 0])
    data = np.zeros((len(SCALINGS), len(WDS)))
    for i, s in enumerate(SCALINGS):
        for j, w in enumerate(WDS):
            log = load(f"/home/fuqingxu/cc-workspace/muon/results/scaling_10ep/{SCALING_FN[s]}_{w}.jsonl")
            data[i, j] = max(r["val_acc"] for r in log)
    im = ax.imshow(data, cmap="viridis", aspect="auto", vmin=0.89, vmax=0.91)
    ax.set_xticks(range(len(WDS))); ax.set_xticklabels(WDS)
    ax.set_yticks(range(len(SCALINGS))); ax.set_yticklabels([SCALING_LABEL[s] for s in SCALINGS], fontsize=8)
    ax.set_title("10ep: best val_acc\n(higher = better)", fontsize=10)
    ax.set_xlabel("weight decay"); ax.set_ylabel("update scaling")
    for i in range(len(SCALINGS)):
        for j in range(len(WDS)):
            color = "white" if data[i, j] < 0.90 else "black"
            ax.text(j, i, f"{data[i, j]:.4f}", ha="center", va="center",
                    color=color, fontsize=8)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # (2) gap heatmap
    ax = fig.add_subplot(gs[0, 1])
    data = np.zeros((len(SCALINGS), len(WDS)))
    for i, s in enumerate(SCALINGS):
        for j, w in enumerate(WDS):
            log = load(f"/home/fuqingxu/cc-workspace/muon/results/scaling_10ep/{SCALING_FN[s]}_{w}.jsonl")
            data[i, j] = log[-1]["val_loss"] - log[-1]["train_loss"]
    im = ax.imshow(data, cmap="RdYlGn_r", aspect="auto", vmin=0.13, vmax=0.18)
    ax.set_xticks(range(len(WDS))); ax.set_xticklabels(WDS)
    ax.set_yticks(range(len(SCALINGS))); ax.set_yticklabels([SCALING_LABEL[s] for s in SCALINGS], fontsize=8)
    ax.set_title("10ep: gen gap = val_loss - train_loss\n(lower = better)", fontsize=10)
    ax.set_xlabel("weight decay"); ax.set_ylabel("update scaling")
    for i in range(len(SCALINGS)):
        for j in range(len(WDS)):
            ax.text(j, i, f"{data[i, j]:+.3f}", ha="center", va="center",
                    color="black", fontsize=8)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # (3) 90% epoch heatmap
    ax = fig.add_subplot(gs[0, 2])
    data = np.full((len(SCALINGS), len(WDS)), 99.0)
    for i, s in enumerate(SCALINGS):
        for j, w in enumerate(WDS):
            log = load(f"/home/fuqingxu/cc-workspace/muon/results/scaling_10ep/{SCALING_FN[s]}_{w}.jsonl")
            for r in log:
                if r["val_acc"] >= 0.90:
                    data[i, j] = r["epoch"]
                    break
    im = ax.imshow(data, cmap="RdYlGn_r", aspect="auto", vmin=7, vmax=15)
    ax.set_xticks(range(len(WDS))); ax.set_xticklabels(WDS)
    ax.set_yticks(range(len(SCALINGS))); ax.set_yticklabels([SCALING_LABEL[s] for s in SCALINGS], fontsize=8)
    ax.set_title("10ep: epoch to reach 90% val_acc\n(lower = faster)", fontsize=10)
    ax.set_xlabel("weight decay"); ax.set_ylabel("update scaling")
    for i in range(len(SCALINGS)):
        for j in range(len(WDS)):
            txt = f"{int(data[i, j])}" if data[i, j] < 50 else "not reached"
            ax.text(j, i, txt, ha="center", va="center", color="black", fontsize=8)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # ---- Bottom row: 30ep + 30ep gap + compute cost ----
    # (4) 30ep val_acc curves for 5 selected configs
    ax = fig.add_subplot(gs[1, 0])
    cfgs_30 = [
        ("paper_wd2e3", "paper + wd=2e-3 (winner)", "#1F4E89", 3.0),
        ("none_wd5e4",  "none + wd=5e-4",            "#5B8E7D", 2.0),
        ("paper_wd5e4", "paper + wd=5e-4 (default)", "#1F4E89", 2.0),
        ("spec_wd0",    "spectral_clip + wd=0",      "#D9843A", 2.0),
        ("rms_wd5e4",   "rms_match + wd=5e-4",       "#D62728", 2.0),
    ]
    for tag, lbl, col, lw in cfgs_30:
        log = load(f"/home/fuqingxu/cc-workspace/muon/results/scaling_30ep/{tag}.jsonl")
        ep = [r["epoch"] for r in log]
        va = [r["val_acc"] for r in log]
        ax.plot(ep, va, label=lbl, color=col, lw=lw)
        ax.annotate(f"{va[-1]:.4f}", xy=(ep[-1], va[-1]),
                    xytext=(5, 0), textcoords="offset points",
                    color=col, fontsize=8,
                    fontweight="bold" if "winner" in lbl else "normal")
    ax.axvline(20, ls="--", color="gray", alpha=0.4)
    ax.axvline(25, ls="--", color="gray", alpha=0.4)
    ax.set_title("30ep: val_acc of 5 representative configs", fontsize=10)
    ax.set_xlabel("Epoch"); ax.set_ylabel("Val acc")
    ax.grid(alpha=0.3); ax.legend(fontsize=7, loc="lower right")
    ax.set_ylim(0.86, 0.93)

    # (5) 30ep final gap = val_loss - train_loss
    ax = fig.add_subplot(gs[1, 1])
    gap_data = []
    for tag, lbl, col, _ in cfgs_30:
        log = load(f"/home/fuqingxu/cc-workspace/muon/results/scaling_30ep/{tag}.jsonl")
        gap = log[-1]["val_loss"] - log[-1]["train_loss"]
        gap_data.append((lbl, gap, col))
    gap_data.sort(key=lambda x: x[1])
    lbls = [d[0] for d in gap_data]
    gaps = [d[1] for d in gap_data]
    cols = [d[2] for d in gap_data]
    ax.barh(range(len(lbls)), gaps, color=cols, edgecolor="black", linewidth=0.5)
    ax.set_yticks(range(len(lbls))); ax.set_yticklabels(lbls, fontsize=8)
    ax.set_xlabel("gap = val_loss - train_loss")
    ax.set_title("30ep: final gen gap", fontsize=10)
    ax.grid(axis="x", alpha=0.3); ax.invert_yaxis()
    for i, g in enumerate(gaps):
        ax.text(g + 0.002, i, f"{g:+.3f}", va="center", fontsize=8)
    ax.set_xlim(0.28, 0.33)

    # (6) compute cost per epoch
    ax = fig.add_subplot(gs[1, 2])
    costs = {"paper": 3.6, "none": 4.5, "sqrt_rows_cols": 3.6,
             "rms_match": 3.8, "spectral_clip": 14.8}
    names = list(costs.keys())
    vals = [costs[n] for n in names]
    cols = [SCALING_COLOR[n] for n in names]
    bars = ax.bar(range(len(names)), vals, color=cols, edgecolor="black", linewidth=0.5)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels([SCALING_LABEL[n] for n in names], fontsize=7)
    ax.set_ylabel("seconds per epoch (1.26M model, A100)")
    ax.set_title("Compute cost: spectral_clip is 4x slower", fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.3, f"{v:.1f}s", ha="center", fontsize=9)
    ax.set_ylim(0, 18)

    plt.suptitle("Muon update scaling x weight decay · SmallCNN (1.26M) · CIFAR-10 · seed=42",
                 fontsize=13, fontweight="bold", y=1.00)
    plt.tight_layout()
    plt.savefig("figures/update_scaling.png", dpi=150, bbox_inches="tight")
    print("[done] -> figures/update_scaling.png")


if __name__ == "__main__":
    main()
