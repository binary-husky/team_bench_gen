"""Plot momentum / Nesterov / aux AdamW lr ratio ablation.

Reads:
  results/momentum_10ep/{mom_0.0, mom_0.6, mom_0.8, mom_0.9, mom_0.95, mom_0.98,
                       nest_false, aux_0.01, aux_0.025, aux_0.05, aux_0.1, aux_0.2}.jsonl
  results/momentum_30ep/{mom30_aux_0.1, mom30_mom_0.95, mom30_aux_0.05,
                        mom30_nest_false, mom30_mom_0.0}.jsonl
"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load(path):
    return [json.loads(l) for l in open(path)]


MOMENTUMS = ["0.0", "0.6", "0.8", "0.9", "0.95", "0.98"]
AUX_RATIOS = ["0.01", "0.025", "0.05", "0.1", "0.2"]

# 颜色 — momentum 维度用渐变，aux 维度用另一色系
MOM_COLOR = {
    "0.0":  "#9CA3AF",  # gray (negative control)
    "0.6":  "#60A5FA",
    "0.8":  "#3B82F6",
    "0.9":  "#1D4ED8",
    "0.95": "#1E3A8A",  # paper default
    "0.98": "#1E40AF",
}
AUX_COLOR = {
    "0.01":  "#FCD34D",
    "0.025": "#FBBF24",
    "0.05":  "#F59E0B",  # paper default
    "0.1":   "#D97706",
    "0.2":   "#B45309",
}
NEST_COLOR = {"true": "#1E3A8A", "false": "#10B981"}


def get_acc_at(log, ep):
    for r in log:
        if r["epoch"] == ep:
            return r["val_acc"]
    return None


def main():
    fig = plt.figure(figsize=(20, 12))
    gs = fig.add_gridspec(2, 3)

    # ---- (1) momentum sweep — 10ep val_acc curve ----
    ax = fig.add_subplot(gs[0, 0])
    for m in MOMENTUMS:
        log = load(f"/home/fuqingxu/cc-workspace/muon/results/momentum_10ep/mom_{m}.jsonl")
        ep = [r["epoch"] for r in log]
        va = [r["val_acc"] for r in log]
        lw = 2.5 if m == "0.95" else 1.5
        ax.plot(ep, va, label=f"m={m}", color=MOM_COLOR[m], lw=lw)
    ax.set_title("10ep: momentum sweep (Nesterov on, aux=0.05)\nval_acc", fontsize=10)
    ax.set_xlabel("Epoch"); ax.set_ylabel("Val acc")
    ax.grid(alpha=0.3); ax.legend(fontsize=8, loc="lower right")
    ax.set_ylim(0.83, 0.92)

    # ---- (2) aux lr ratio sweep — 10ep val_acc curve ----
    ax = fig.add_subplot(gs[0, 1])
    for r in AUX_RATIOS:
        log = load(f"/home/fuqingxu/cc-workspace/muon/results/momentum_10ep/aux_{r}.jsonl")
        ep = [r["epoch"] for r in log]
        va = [r["val_acc"] for r in log]
        lw = 2.5 if r == "0.05" else 1.5
        ax.plot(ep, va, label=f"aux={r}", color=AUX_COLOR[r], lw=lw)
    ax.set_title("10ep: aux AdamW lr ratio sweep\n(mom=0.95, Nesterov on)", fontsize=10)
    ax.set_xlabel("Epoch"); ax.set_ylabel("Val acc")
    ax.grid(alpha=0.3); ax.legend(fontsize=8, loc="lower right")
    ax.set_ylim(0.83, 0.92)

    # ---- (3) 10ep best val_acc bars: all 12 configs ----
    ax = fig.add_subplot(gs[0, 2])
    all_cfgs = []
    for m in MOMENTUMS:
        all_cfgs.append((f"mom={m}", max(load(f"/home/fuqingxu/cc-workspace/muon/results/momentum_10ep/mom_{m}.jsonl"),
                                        key=lambda r: r["val_acc"])["val_acc"], MOM_COLOR[m], "mom"))
    all_cfgs.append(("nest=off", max(load("/home/fuqingxu/cc-workspace/muon/results/momentum_10ep/nest_false.jsonl"),
                                     key=lambda r: r["val_acc"])["val_acc"], NEST_COLOR["false"], "nest"))
    for r in AUX_RATIOS:
        all_cfgs.append((f"aux={r}", max(load(f"/home/fuqingxu/cc-workspace/muon/results/momentum_10ep/aux_{r}.jsonl"),
                                         key=lambda r: r["val_acc"])["val_acc"], AUX_COLOR[r], "aux"))
    labels = [c[0] for c in all_cfgs]
    vals = [c[1] for c in all_cfgs]
    colors = [c[2] for c in all_cfgs]
    bars = ax.barh(range(len(all_cfgs)), vals, color=colors, edgecolor="black", linewidth=0.5)
    ax.set_yticks(range(len(all_cfgs))); ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("10ep best val_acc")
    ax.set_title("10ep: best val_acc of all 12 configs\n(sorted ascending)", fontsize=10)
    ax.grid(axis="x", alpha=0.3); ax.invert_yaxis()
    # sort by val_acc ascending so highest on top after invert
    order = sorted(range(len(all_cfgs)), key=lambda i: all_cfgs[i][1])
    labels_o = [all_cfgs[i][0] for i in order]
    vals_o = [all_cfgs[i][1] for i in order]
    cols_o = [all_cfgs[i][2] for i in order]
    ax.clear()
    bars = ax.barh(range(len(all_cfgs)), vals_o, color=cols_o, edgecolor="black", linewidth=0.5)
    ax.set_yticks(range(len(all_cfgs))); ax.set_yticklabels(labels_o, fontsize=8)
    ax.set_xlabel("10ep best val_acc")
    ax.set_title("10ep: best val_acc — all 12 configs (lowest at bottom)", fontsize=10)
    ax.grid(axis="x", alpha=0.3)
    for i, v in enumerate(vals_o):
        ax.text(v + 0.0005, i, f"{v:.4f}", va="center", fontsize=7)
    ax.set_xlim(0.885, 0.910)

    # ---- (4) 30ep val_acc curves for 5 selected configs ----
    ax = fig.add_subplot(gs[1, 0])
    cfgs_30 = [
        ("mom30_aux_0.1",    "aux=0.1 (best)",            AUX_COLOR["0.1"],   3.0),
        ("mom30_mom_0.95",   "mom=0.95 (paper default)",   MOM_COLOR["0.95"],  2.0),
        ("mom30_aux_0.05",   "aux=0.05 (paper default)",   AUX_COLOR["0.05"],  2.0),
        ("mom30_nest_false", "Nesterov off",               NEST_COLOR["false"], 2.0),
        ("mom30_mom_0.0",    "mom=0.0 (negative control)", MOM_COLOR["0.0"],   1.5),
    ]
    for tag, lbl, col, lw in cfgs_30:
        log = load(f"/home/fuqingxu/cc-workspace/muon/results/momentum_30ep/{tag}.jsonl")
        ep = [r["epoch"] for r in log]
        va = [r["val_acc"] for r in log]
        ax.plot(ep, va, label=lbl, color=col, lw=lw)
        ax.annotate(f"{va[-1]:.4f}", xy=(ep[-1], va[-1]),
                    xytext=(5, 0), textcoords="offset points",
                    color=col, fontsize=8,
                    fontweight="bold" if "best" in lbl else "normal")
    ax.axvline(20, ls="--", color="gray", alpha=0.4)
    ax.axvline(25, ls="--", color="gray", alpha=0.4)
    ax.set_title("30ep: val_acc of 5 representative configs", fontsize=10)
    ax.set_xlabel("Epoch"); ax.set_ylabel("Val acc")
    ax.grid(alpha=0.3); ax.legend(fontsize=8, loc="lower right")
    ax.set_ylim(0.86, 0.93)

    # ---- (5) 30ep final gen gap bars ----
    ax = fig.add_subplot(gs[1, 1])
    gap_data = []
    for tag, lbl, col, _ in cfgs_30:
        log = load(f"/home/fuqingxu/cc-workspace/muon/results/momentum_30ep/{tag}.jsonl")
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
    ax.set_xlim(0.28, 0.34)

    # ---- (6) 30ep: @10ep, @20ep, @30ep grouped bars ----
    ax = fig.add_subplot(gs[1, 2])
    checkpts = [10, 20, 30]
    x = np.arange(len(cfgs_30))
    width = 0.27
    for i, ep in enumerate(checkpts):
        vals = [get_acc_at(load(f"/home/fuqingxu/cc-workspace/muon/results/momentum_30ep/{t}.jsonl"), ep) or 0
                for t, _, _, _ in cfgs_30]
        ax.bar(x + (i - 1) * width, vals, width, label=f"@{ep}ep",
               color=["#A0A0A0", "#606060", "#1F4E89"][i], edgecolor="black", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels([lbl for _, lbl, _, _ in cfgs_30], fontsize=8, rotation=15, ha="right")
    ax.set_ylabel("val_acc")
    ax.set_title("30ep: val_acc at 3 checkpoints", fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(fontsize=8, loc="lower right")
    ax.set_ylim(0.85, 0.94)
    # annotate bars
    for j, ep in enumerate(checkpts):
        for k, (t, lbl, _, _) in enumerate(cfgs_30):
            v = get_acc_at(load(f"/home/fuqingxu/cc-workspace/muon/results/momentum_30ep/{t}.jsonl"), ep) or 0
            ax.text(x[k] + (j - 1) * width, v + 0.0008, f"{v:.3f}",
                    ha="center", fontsize=6, rotation=90)

    plt.suptitle("Muon momentum / Nesterov / aux AdamW lr ratio · SmallCNN (1.26M) · CIFAR-10 · seed=42",
                 fontsize=13, fontweight="bold", y=1.00)
    plt.tight_layout()
    plt.savefig("figures/momentum_auxadam.png", dpi=150, bbox_inches="tight")
    print("[done] -> figures/momentum_auxadam.png")


if __name__ == "__main__":
    main()
