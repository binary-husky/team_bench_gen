"""Plot Muon generalization-gap + regularization ablation."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load(path):
    return [json.loads(l) for l in open(path)]


# Colors
C_BASE = "#1F4E89"  # Muon (deep blue)
C_SGD  = "#5B8E7D"  # green
C_ADAM = "#D9843A"  # orange
C_LS   = "#D62728"  # red (label smoothing winner)
C_DROP = "#FF8C00"  # orange
C_WD   = "#8B5CF6"  # purple
C_BASELINE = "#333333"


def main():
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    # --- Row 1: 10ep screens ---
    # (1,0) baseline 3 optimizers
    for name, color, label in [
        ("baseline_muon",  C_BASE, "Muon (Jordan)"),
        ("baseline_sgd",   C_SGD,  "SGD-Momentum"),
        ("baseline_adamw", C_ADAM, "AdamW"),
    ]:
        log = load(f"/home/fuqingxu/cc-workspace/muon/results/generalization_10ep/{name}.jsonl")
        ep = [r["epoch"] for r in log]
        va = [r["val_acc"] for r in log]
        axes[0, 0].plot(ep, va, label=label, color=color, lw=2)
        axes[0, 0].annotate(f"{va[-1]:.4f}", xy=(ep[-1], va[-1]),
                            xytext=(5, 0), textcoords="offset points", color=color, fontsize=8)
    axes[0, 0].set_title("10ep: optimizer baselines (val_acc)")
    axes[0, 0].set_xlabel("Epoch"); axes[0, 0].set_ylabel("Val acc")
    axes[0, 0].grid(alpha=0.3); axes[0, 0].legend(fontsize=9)
    axes[0, 0].set_ylim(0.83, 0.92)

    # (1,1) weight decay ablation
    wd_vals = ["wd_0", "wd_1e-4", "wd_5e-4", "wd_1e-3", "wd_2e-3", "wd_5e-3"]
    wd_lbl  = ["0", "1e-4", "5e-4", "1e-3", "2e-3", "5e-3"]
    for tag, lbl in zip(wd_vals, wd_lbl):
        log = load(f"/home/fuqingxu/cc-workspace/muon/results/generalization_10ep/{tag}.jsonl")
        ep = [r["epoch"] for r in log]
        va = [r["val_acc"] for r in log]
        axes[0, 1].plot(ep, va, label=f"wd={lbl}", lw=1.5)
    axes[0, 1].set_title("10ep: weight decay ablation (val_acc)")
    axes[0, 1].set_xlabel("Epoch"); axes[0, 1].set_ylabel("Val acc")
    axes[0, 1].grid(alpha=0.3); axes[0, 1].legend(fontsize=8, ncol=2)
    axes[0, 1].set_ylim(0.88, 0.915)

    # (1,2) dropout ablation
    drop_vals = ["drop_0.0", "drop_0.1", "drop_0.2", "drop_0.3"]
    drop_lbl  = ["0.0", "0.1", "0.2 (base)", "0.3"]
    for tag, lbl in zip(drop_vals, drop_lbl):
        log = load(f"/home/fuqingxu/cc-workspace/muon/results/generalization_10ep/{tag}.jsonl")
        ep = [r["epoch"] for r in log]
        va = [r["val_acc"] for r in log]
        axes[0, 2].plot(ep, va, label=f"drop={lbl}", lw=1.5)
    axes[0, 2].set_title("10ep: dropout ablation (val_acc)")
    axes[0, 2].set_xlabel("Epoch"); axes[0, 2].set_ylabel("Val acc")
    axes[0, 2].grid(alpha=0.3); axes[0, 2].legend(fontsize=8)
    axes[0, 2].set_ylim(0.88, 0.915)

    # --- Row 2: label smoothing + 30ep + gap analysis ---
    # (2,0) label smoothing (winner)
    ls_vals = ["baseline_muon", "ls_0.05", "ls_0.1"]
    ls_lbl  = ["ls=0.0 (base)", "ls=0.05", "ls=0.1"]
    ls_col  = [C_BASELINE, "#8B5CF6", C_LS]
    for tag, lbl, col in zip(ls_vals, ls_lbl, ls_col):
        if tag == "baseline_muon":
            log = load(f"/home/fuqingxu/cc-workspace/muon/results/generalization_10ep/{tag}.jsonl")
        else:
            log = load(f"/home/fuqingxu/cc-workspace/muon/results/generalization_10ep/{tag}.jsonl")
        ep = [r["epoch"] for r in log]
        va = [r["val_acc"] for r in log]
        axes[1, 0].plot(ep, va, label=lbl, color=col, lw=2.5)
        axes[1, 0].annotate(f"{va[-1]:.4f}", xy=(ep[-1], va[-1]),
                            xytext=(5, 0), textcoords="offset points",
                            color=col, fontsize=9, fontweight="bold")
    axes[1, 0].set_title("10ep: LABEL SMOOTHING ablation (winner)")
    axes[1, 0].set_xlabel("Epoch"); axes[1, 0].set_ylabel("Val acc")
    axes[1, 0].grid(alpha=0.3); axes[1, 0].legend(fontsize=9)
    axes[1, 0].set_ylim(0.88, 0.92)

    # (2,1) 30ep val_acc
    cfg_30 = [("baseline_muon", C_BASELINE, "baseline (ls=0, drop=0.2)"),
              ("drop_0.1",      C_DROP,     "drop=0.1"),
              ("drop_0.3",      "#E07B00",  "drop=0.3"),
              ("ls_0.05",       "#8B5CF6",  "ls=0.05"),
              ("ls_0.1",        C_LS,       "ls=0.1 (winner)")]
    for tag, col, lbl in cfg_30:
        log = load(f"/home/fuqingxu/cc-workspace/muon/results/generalization_30ep/{tag}.jsonl")
        ep = [r["epoch"] for r in log]
        va = [r["val_acc"] for r in log]
        lw = 3.0 if "winner" in lbl else 2.0
        axes[1, 1].plot(ep, va, label=lbl, color=col, lw=lw)
        axes[1, 1].annotate(f"{va[-1]:.4f}", xy=(ep[-1], va[-1]),
                            xytext=(5, 0), textcoords="offset points",
                            color=col, fontsize=9,
                            fontweight="bold" if "winner" in lbl else "normal")
    axes[1, 1].axvline(20, ls="--", color="gray", alpha=0.4)
    axes[1, 1].axvline(25, ls="--", color="gray", alpha=0.4)
    axes[1, 1].set_title("30ep follow-up: val accuracy (5 configs)")
    axes[1, 1].set_xlabel("Epoch"); axes[1, 1].set_ylabel("Val acc")
    axes[1, 1].grid(alpha=0.3); axes[1, 1].legend(fontsize=8, loc="lower right")
    axes[1, 1].set_ylim(0.86, 0.94)

    # (2,2) gap = val_loss - train_loss for 30ep configs
    gap_data = []
    for tag, col, lbl in cfg_30:
        log = load(f"/home/fuqingxu/cc-workspace/muon/results/generalization_30ep/{tag}.jsonl")
        fin_vl = log[-1]["val_loss"]
        fin_tl = log[-1]["train_loss"]
        gap = fin_vl - fin_tl
        gap_data.append((lbl, gap, col))
    gap_data.sort(key=lambda x: x[1])
    lbls  = [d[0] for d in gap_data]
    gaps  = [d[1] for d in gap_data]
    cols  = [d[2] for d in gap_data]
    bars = axes[1, 2].barh(range(len(lbls)), gaps, color=cols, edgecolor="black", linewidth=0.5)
    axes[1, 2].set_yticks(range(len(lbls)))
    axes[1, 2].set_yticklabels(lbls, fontsize=9)
    axes[1, 2].set_xlabel("gap = val_loss − train_loss  (lower = better)")
    axes[1, 2].set_title("30ep final gap: label smoothing halves it")
    axes[1, 2].grid(axis="x", alpha=0.3)
    axes[1, 2].invert_yaxis()
    for i, g in enumerate(gaps):
        axes[1, 2].text(g + 0.005, i, f"{g:+.3f}", va="center", fontsize=9)
    axes[1, 2].set_xlim(0, max(gaps) * 1.15)

    plt.suptitle("Muon generalization gap + regularization ablation · SmallCNN (1.26M) · CIFAR-10 · seed=42",
                 fontsize=13, fontweight="bold", y=1.00)
    plt.tight_layout()
    plt.savefig("figures/generalization.png", dpi=150, bbox_inches="tight")
    print("[done] -> figures/generalization.png")


if __name__ == "__main__":
    main()
