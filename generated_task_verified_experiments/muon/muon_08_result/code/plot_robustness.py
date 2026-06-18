"""Plot robustness experiments: small-data / label-noise / long-tail."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load(path):
    return [json.loads(l) for l in open(path)]


DIR = "/home/fuqingxu/cc-workspace/muon/results/robustness"
OPTIMIZERS = ["muon", "sgd", "adamw"]
OPT_COLOR = {"muon": "#1F4E89", "sgd": "#D62728", "adamw": "#D9843A"}
OPT_MARKER = {"muon": "o", "sgd": "s", "adamw": "^"}


def parse(fn):
    base = fn.replace(".jsonl", "")
    parts = base.split("_")
    optim = parts[0]
    if "smalldata" in base:
        kind, val = "smalldata", parts[2]
    elif "noise" in base:
        kind, val = "noise", parts[2]
    elif "longtail" in base:
        kind, val = "longtail", parts[2]
    else:
        kind, val = "?", "?"
    return optim, kind, val


def main():
    import os
    files = sorted(os.listdir(DIR))
    data = {}
    for f in files:
        o, k, v = parse(f)
        data[(o, k, v)] = load(f"{DIR}/{f}")

    fig = plt.figure(figsize=(20, 12))
    gs = fig.add_gridspec(2, 3)

    # ---- (1) Small-data: best val_acc vs N (3 optim) ----
    ax = fig.add_subplot(gs[0, 0])
    Ns = ["5000", "10000", "25000", "50000"]
    x = np.arange(len(Ns))
    width = 0.27
    for o_i, opt in enumerate(OPTIMIZERS):
        vals = [max(data[(opt, "smalldata", n)], key=lambda r: r["val_acc"])["val_acc"] for n in Ns]
        ax.bar(x + (o_i - 1) * width, vals, width,
               color=OPT_COLOR[opt], edgecolor="black", linewidth=0.5,
               label=opt)
        for i, v in enumerate(vals):
            ax.text(x[i] + (o_i - 1) * width, v + 0.005, f"{v:.3f}",
                    ha="center", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels([f"N={n}" for n in Ns])
    ax.set_ylabel("10ep best val_acc")
    ax.set_title("(1) Small-data: 10ep best val_acc\nMuon dominates at all sizes", fontsize=10)
    ax.set_ylim(0.55, 0.94)
    ax.grid(axis="y", alpha=0.3); ax.legend(fontsize=9)

    # ---- (2) Small-data: train/val gap (overfit indicator) ----
    ax = fig.add_subplot(gs[0, 1])
    for opt in OPTIMIZERS:
        gaps = []
        for n in Ns:
            log = data[(opt, "smalldata", n)]
            last = log[-1]
            gaps.append(last["val_loss"] - last["train_loss"])
        ax.plot(range(len(Ns)), gaps, color=OPT_COLOR[opt], marker=OPT_MARKER[opt],
                lw=2.5, markersize=8, label=opt)
    ax.set_xticks(range(len(Ns))); ax.set_xticklabels([f"N={n}" for n in Ns])
    ax.set_ylabel("gap = val_loss - train_loss")
    ax.set_title("(2) Small-data: train/val gap (final epoch)\nMuon has largest gap but highest val_acc", fontsize=10)
    ax.grid(alpha=0.3); ax.legend(fontsize=9)

    # ---- (3) Label noise: best val_acc vs noise level ----
    ax = fig.add_subplot(gs[0, 2])
    noises = ["0.0", "0.1", "0.2", "0.4"]
    x = np.arange(len(noises))
    for o_i, opt in enumerate(OPTIMIZERS):
        vals = [max(data[(opt, "noise", n)], key=lambda r: r["val_acc"])["val_acc"] for n in noises]
        ax.bar(x + (o_i - 1) * width, vals, width,
               color=OPT_COLOR[opt], edgecolor="black", linewidth=0.5,
               label=opt)
        for i, v in enumerate(vals):
            ax.text(x[i] + (o_i - 1) * width, v + 0.003, f"{v:.3f}",
                    ha="center", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels([f"p={n}" for n in noises])
    ax.set_ylabel("10ep best val_acc")
    ax.set_title("(3) Label noise: 10ep best val_acc\nMuon retains accuracy at all noise levels", fontsize=10)
    ax.set_ylim(0.75, 0.93)
    ax.grid(axis="y", alpha=0.3); ax.legend(fontsize=9)

    # ---- (4) Long-tail: overall acc + tail acc + head acc (3 optim × 2 ratio) ----
    ax = fig.add_subplot(gs[1, 0])
    ratios = ["10.0", "50.0"]
    x = np.arange(len(ratios))
    width = 0.13
    metric_color = {"overall": "#1F4E89", "head": "#5B8E7D", "tail": "#D62728"}
    for o_i, opt in enumerate(OPTIMIZERS):
        for m_i, (metric, col) in enumerate(metric_color.items()):
            vals = []
            for r in ratios:
                log = data[(opt, "longtail", r)]
                last = log[-1]
                if metric == "overall":
                    vals.append(max(log, key=lambda r: r["val_acc"])["val_acc"])
                elif metric == "head":
                    vals.append(last.get("head_mean_acc", 0))
                elif metric == "tail":
                    vals.append(last.get("tail_mean_acc", 0))
            offset = (o_i * 3 + m_i - 4) * width
            ax.bar(x + offset, vals, width,
                   color=col,
                   edgecolor="black", linewidth=0.3,
                   alpha=0.7 if metric != "overall" else 1.0,
                   label=f"{opt}/{metric}" if (o_i == 0 and metric == "overall") else None)
    ax.set_xticks(x); ax.set_xticklabels([f"ratio={r}" for r in ratios])
    ax.set_ylabel("val_acc (overall/head/tail)")
    ax.set_title("(4) Long-tail: overall / head / tail accuracy\nMuon tail acc ≫ SGD/AdamW", fontsize=10)
    ax.set_ylim(0.2, 0.85)
    ax.grid(axis="y", alpha=0.3)
    from matplotlib.patches import Patch
    legend_handles = [
        Patch(facecolor=metric_color["overall"], label="overall"),
        Patch(facecolor=metric_color["head"], label="head"),
        Patch(facecolor=metric_color["tail"], label="tail"),
        Patch(facecolor="white", edgecolor="black", label="—"),
        Patch(facecolor=OPT_COLOR["muon"], label="muon"),
        Patch(facecolor=OPT_COLOR["sgd"], label="sgd"),
        Patch(facecolor=OPT_COLOR["adamw"], label="adamw"),
    ]
    ax.legend(handles=legend_handles, fontsize=7, loc="upper left", ncol=2)

    # ---- (5) 30ep-ish summary: best val_acc across all 10 variants × 3 optim ----
    ax = fig.add_subplot(gs[1, 1])
    variants_short = ["5k", "10k", "25k", "50k", "n=0", "n=.1", "n=.2", "n=.4", "lt10", "lt50"]
    var_keys = [("smalldata", "5000"), ("smalldata", "10000"), ("smalldata", "25000"), ("smalldata", "50000"),
                ("noise", "0.0"), ("noise", "0.1"), ("noise", "0.2"), ("noise", "0.4"),
                ("longtail", "10.0"), ("longtail", "50.0")]
    x = np.arange(len(var_keys))
    width = 0.27
    for o_i, opt in enumerate(OPTIMIZERS):
        vals = [max(data[(opt, k, v)], key=lambda r: r["val_acc"])["val_acc"] for k, v in var_keys]
        ax.bar(x + (o_i - 1) * width, vals, width,
               color=OPT_COLOR[opt], edgecolor="black", linewidth=0.5,
               label=opt)
    ax.set_xticks(x); ax.set_xticklabels(variants_short, rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("10ep best val_acc")
    ax.set_title("(5) Summary: 10 variants × 3 optims (10ep)", fontsize=10)
    ax.set_ylim(0.5, 0.95)
    ax.grid(axis="y", alpha=0.3); ax.legend(fontsize=8, loc="lower right")

    # ---- (6) Muon's relative gain over SGD/AdamW across all 10 variants ----
    ax = fig.add_subplot(gs[1, 2])
    muon_vs_sgd = []
    muon_vs_adamw = []
    for k, v in var_keys:
        m = max(data[("muon", k, v)], key=lambda r: r["val_acc"])["val_acc"]
        s = max(data[("sgd", k, v)], key=lambda r: r["val_acc"])["val_acc"]
        a = max(data[("adamw", k, v)], key=lambda r: r["val_acc"])["val_acc"]
        muon_vs_sgd.append((m - s) * 100)
        muon_vs_adamw.append((m - a) * 100)
    x = np.arange(len(var_keys))
    width = 0.4
    ax.bar(x - width/2, muon_vs_sgd, width, color=OPT_COLOR["sgd"], alpha=0.6,
           edgecolor="black", linewidth=0.5, label="Muon - SGD (pp)")
    ax.bar(x + width/2, muon_vs_adamw, width, color=OPT_COLOR["adamw"], alpha=0.6,
           edgecolor="black", linewidth=0.5, label="Muon - AdamW (pp)")
    ax.axhline(0, color="black", lw=0.5)
    ax.set_xticks(x); ax.set_xticklabels(variants_short, rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("val_acc gap (percentage points)")
    ax.set_title("(6) Muon's advantage across all 10 variants\n(robustness ranking consistency)", fontsize=10)
    ax.grid(axis="y", alpha=0.3); ax.legend(fontsize=8)
    ax.set_ylim(-3, 18)

    plt.suptitle("Muon / SGD / AdamW robustness · SmallCNN (1.26M) · CIFAR-10 · seed=42 · 10ep",
                 fontsize=13, fontweight="bold", y=1.00)
    plt.tight_layout()
    plt.savefig("/home/fuqingxu/cc-workspace/muon/figures/robustness.png",
                dpi=150, bbox_inches="tight")
    print("[done] -> figures/robustness.png")


if __name__ == "__main__":
    main()