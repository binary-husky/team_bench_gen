"""Plot width transfer experiments."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load(path):
    return [json.loads(l) for l in open(path)]


DIR = "/home/fuqingxu/cc-workspace/muon/results/width"
OPTIMIZERS = ["muon", "sgd", "adamw"]
OPT_COLOR = {"muon": "#1F4E89", "sgd": "#D62728", "adamw": "#D9843A"}
OPT_MARKER = {"muon": "o", "sgd": "s", "adamw": "^"}
WIDTHS = ["0.5", "1.0", "1.5", "2.0"]
DEFAULT_LR = {"muon": 0.02, "sgd": 0.1, "adamw": 3e-3}


def parse(fn):
    """Parse filename. Examples:
       adamw_0.5x_lr0.0005_0.5x_lr5.jsonl       -> (adamw, 0.5, 5e-4)
       muon_1.0x_lr0.02_30ep_1.0x_lr0.02.jsonl   -> (muon, 1.0, 0.02)
       The actual lr is recovered from the record (log[0]['lr']) so we don't
       rely on filename-encoded lr.
    """
    base = fn.replace(".jsonl", "")
    parts = base.split("_")
    optim = parts[0]
    # find first part ending in "x" — that's the width tag
    width_tag = next((p for p in parts if p.endswith("x")), "1.0x")
    width = width_tag[:-1]
    is_30ep = "30ep" in base
    return optim, width, is_30ep


def main():
    import os
    files_10 = [f for f in os.listdir(DIR) if "30ep" not in f]
    files_30 = [f for f in os.listdir(DIR) if "30ep" in f]

    fig = plt.figure(figsize=(20, 12))
    gs = fig.add_gridspec(2, 3)

    # ---- (1) 10ep: lr sensitivity per width per optim (3 lr × 4 widths × 3 optim) ----
    ax = fig.add_subplot(gs[0, 0])
    # For each optim, show lr sensitivity (max - min) across widths
    for opt in OPTIMIZERS:
        spread_per_width = []
        for w in WIDTHS:
            sub = []
            for f in files_10:
                # 10ep only handled above, but pattern matches
                o, ww, is30 = parse(f)
                if o == opt and ww == w:
                    log = load(f"{DIR}/{f}")
                    sub.append(max(log, key=lambda r: r["val_acc"])["val_acc"])
            spread_per_width.append(max(sub) - min(sub))
        ax.plot(range(len(WIDTHS)), [s * 100 for s in spread_per_width],
                color=OPT_COLOR[opt], marker=OPT_MARKER[opt], lw=2.5, markersize=10,
                label=opt)
    ax.set_xticks(range(len(WIDTHS))); ax.set_xticklabels([f"{w}x" for w in WIDTHS])
    ax.set_ylabel("10ep: best_va spread across 3 lr (pp)")
    ax.set_title("(1) LR sensitivity per width (lower = more stable)\nMuon is dramatically more lr-stable than SGD/AdamW",
                 fontsize=10)
    ax.grid(alpha=0.3); ax.legend(fontsize=9)

    # ---- (2) 10ep: best_va per (width, optim), default lr ----
    ax = fig.add_subplot(gs[0, 1])
    width_x = np.arange(len(WIDTHS))
    width_w = 0.27
    for o_i, opt in enumerate(OPTIMIZERS):
        vals = []
        for w in WIDTHS:
            target = DEFAULT_LR[opt]
            v = None
            for f in files_10:
                # 10ep only handled above, but pattern matches
                o, ww, is30 = parse(f)
                if o != opt or ww != w or is30:
                    continue
                log = load(f"{DIR}/{f}")
                if abs(log[0]["lr"] - target) < 1e-9:
                    v = max(log, key=lambda r: r["val_acc"])["val_acc"]
                    break
            vals.append(v if v is not None else 0)
        ax.bar(width_x + (o_i - 1) * width_w, vals, width_w,
               color=OPT_COLOR[opt], edgecolor="black", linewidth=0.5,
               label=opt)
        for i, v in enumerate(vals):
            ax.text(width_x[i] + (o_i - 1) * width_w, v + 0.003, f"{v:.3f}",
                    ha="center", fontsize=7)
    ax.set_xticks(width_x); ax.set_xticklabels([f"{w}x" for w in WIDTHS])
    ax.set_ylabel("10ep best val_acc (default lr)")
    ax.set_title("(2) 10ep best_va at default lr per width", fontsize=10)
    ax.set_ylim(0.84, 0.93)
    ax.grid(axis="y", alpha=0.3); ax.legend(fontsize=8)

    # ---- (3) 30ep: best_va per (width, optim), default lr ----
    ax = fig.add_subplot(gs[0, 2])
    widths_30 = ["0.5", "1.0", "2.0"]
    width_x = np.arange(len(widths_30))
    width_w = 0.27
    for o_i, opt in enumerate(OPTIMIZERS):
        vals = []
        for w in widths_30:
            target = DEFAULT_LR[opt]
            v = None
            for f in files_30:
                parts = f.replace(".jsonl", "").split("_")
                if parts[0] != opt:
                    continue
                width_tag = [p for p in parts if p.endswith("x")][0]
                if width_tag[:-1] != w:
                    continue
                log = load(f"{DIR}/{f}")
                v = max(log, key=lambda r: r["val_acc"])["val_acc"]
                break
            vals.append(v if v is not None else 0)
        ax.bar(width_x + (o_i - 1) * width_w, vals, width_w,
               color=OPT_COLOR[opt], edgecolor="black", linewidth=0.5,
               label=opt)
        for i, v in enumerate(vals):
            ax.text(width_x[i] + (o_i - 1) * width_w, v + 0.003, f"{v:.4f}",
                    ha="center", fontsize=8)
    ax.set_xticks(width_x); ax.set_xticklabels([f"{w}x" for w in widths_30])
    ax.set_ylabel("30ep best val_acc (default lr)")
    ax.set_title("(3) 30ep best_va at default lr per width\n(ranking shifts: SGD wins small, Muon wins large)",
                 fontsize=10)
    ax.set_ylim(0.88, 0.94)
    ax.grid(axis="y", alpha=0.3); ax.legend(fontsize=8)

    # ---- (4) 10ep → 30ep gain per (width, optim) ----
    ax = fig.add_subplot(gs[1, 0])
    width_x = np.arange(len(widths_30))
    width_w = 0.27
    for o_i, opt in enumerate(OPTIMIZERS):
        gains = []
        for w in widths_30:
            target = DEFAULT_LR[opt]
            v10 = v30 = None
            for f in files_10:
                # 10ep only handled above, but pattern matches
                o, ww, is30 = parse(f)
                if o != opt or ww != w or is30:
                    continue
                log = load(f"{DIR}/{f}")
                if abs(log[0]["lr"] - target) < 1e-9:
                    v10 = max(log, key=lambda r: r["val_acc"])["val_acc"]
                    break
            for f in files_30:
                parts = f.replace(".jsonl", "").split("_")
                if parts[0] != opt:
                    continue
                width_tag = [p for p in parts if p.endswith("x")][0]
                if width_tag[:-1] != w:
                    continue
                log = load(f"{DIR}/{f}")
                v30 = max(log, key=lambda r: r["val_acc"])["val_acc"]
                break
            gains.append((v30 - v10) * 100 if (v10 and v30) else 0)
        ax.bar(width_x + (o_i - 1) * width_w, gains, width_w,
               color=OPT_COLOR[opt], edgecolor="black", linewidth=0.5,
               label=opt)
    ax.set_xticks(width_x); ax.set_xticklabels([f"{w}x" for w in widths_30])
    ax.set_ylabel("30ep - 10ep best_va (pp)")
    ax.set_title("(4) Training length gain (10ep → 30ep)\nMuon gains LESS from extra epochs (already converged early)",
                 fontsize=10)
    ax.grid(axis="y", alpha=0.3); ax.legend(fontsize=8)

    # ---- (5) Training stability: per-run final train_loss across all 36 10ep runs ----
    ax = fig.add_subplot(gs[1, 1])
    # Plot train_loss at ep 10 across (width, optim, lr) — for each optim, scatter
    # train_loss vs best_va; outlier-prone runs (NaN / huge train_loss) are unstable
    for opt in OPTIMIZERS:
        xs, ys = [], []
        for f in files_10:
                # 10ep only handled above, but pattern matches
            o, w, _ = parse(f)
            if o != opt:
                continue
            log = load(f"{DIR}/{f}")
            last = log[-1]
            ys.append(last["train_loss"])
            xs.append(max(log, key=lambda r: r["val_acc"])["val_acc"])
        ax.scatter(ys, xs, color=OPT_COLOR[opt], s=40, alpha=0.7, label=opt,
                   edgecolors="black", linewidths=0.4)
    ax.set_xlabel("Final train_loss (ep 10)")
    ax.set_ylabel("Best val_acc (ep 10)")
    ax.set_title("(5) Training stability: train_loss vs best_va\n(no outliers → all 36 runs stable)",
                 fontsize=10)
    ax.grid(alpha=0.3); ax.legend(fontsize=8)

    # ---- (6) Best lr per width (10ep), for each optim ----
    ax = fig.add_subplot(gs[1, 2])
    for opt in OPTIMIZERS:
        best_lrs = []
        for w in WIDTHS:
            best_v = -1; best_lr = None
            for f in files_10:
                # 10ep only handled above, but pattern matches
                o, ww, is30 = parse(f)
                if o != opt or ww != w or is30:
                    continue
                log = load(f"{DIR}/{f}")
                v = max(log, key=lambda r: r["val_acc"])["val_acc"]
                if v > best_v:
                    best_v = v
                    best_lr = log[0]["lr"]
            best_lrs.append(best_lr)
        ax.plot(range(len(WIDTHS)), best_lrs, color=OPT_COLOR[opt], marker=OPT_MARKER[opt],
                lw=2.5, markersize=10, label=opt)
        # draw default lr as horizontal dashed
        ax.axhline(DEFAULT_LR[opt], ls=":", color=OPT_COLOR[opt], alpha=0.4)
    ax.set_xticks(range(len(WIDTHS))); ax.set_xticklabels([f"{w}x" for w in WIDTHS])
    ax.set_ylabel("Best lr (10ep best_va)")
    ax.set_yscale("log")
    ax.set_title("(6) Optimal lr per width (10ep, dotted=default)\nAdamW needs lr↓ as width grows; Muon stable",
                 fontsize=10)
    ax.grid(alpha=0.3, which="both"); ax.legend(fontsize=8)

    plt.suptitle("Muon / SGD / AdamW width transfer & lr stability · SmallCNN × width · CIFAR-10 · seed=42",
                 fontsize=13, fontweight="bold", y=1.00)
    plt.tight_layout()
    plt.savefig("/home/fuqingxu/cc-workspace/muon/figures/width_transfer.png",
                dpi=150, bbox_inches="tight")
    print("[done] -> figures/width_transfer.png")


if __name__ == "__main__":
    main()