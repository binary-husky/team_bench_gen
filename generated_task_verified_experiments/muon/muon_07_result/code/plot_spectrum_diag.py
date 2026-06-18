"""Plot spectrum diagnostics across Muon / SGD / AdamW."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load(path):
    return [json.loads(l) for l in open(path)]


DIR = "/home/fuqingxu/cc-workspace/muon/results/spectrum"
LAYERS = ["stem", "block1.conv2", "block2.conv2", "block3.conv2", "fc1"]
OPTIMIZERS = ["muon", "sgd", "adamw"]
KINDS = ["grad", "moment", "update"]
LAYER_LABELS = {
    "stem":         "stem\n(64,27)",
    "block1.conv2": "block1.conv2\n(64,576)",
    "block2.conv2": "block2.conv2\n(128,576)",
    "block3.conv2": "block3.conv2\n(256,1152)",
    "fc1":          "fc1\n(128,256)",
}
OPT_COLOR = {"muon": "#1F4E89", "sgd": "#D62728", "adamw": "#D9843A"}
OPT_MARKER = {"muon": "o", "sgd": "s", "adamw": "^"}


def index_by(records):
    """Return dict[(epoch, layer)] = record."""
    out = {}
    for r in records:
        out[(r["epoch"], r["layer"])] = r
    return out


def main():
    by = {opt: index_by(load(f"{DIR}/{opt}.jsonl")) for opt in OPTIMIZERS}

    fig = plt.figure(figsize=(20, 12))
    gs = fig.add_gridspec(2, 3)

    # ---- (1) Effective rank of UPDATE across epochs (5 layers × 3 optim) ----
    ax = fig.add_subplot(gs[0, 0])
    for lay_i, lay in enumerate(LAYERS):
        for opt in OPTIMIZERS:
            ep_er = []
            for ep in range(1, 11):
                r = by[opt][(ep, lay)]
                ep_er.append(r["update"]["eff_rank"])
            label = f"{opt}/{lay.replace('.conv2','')}"
            ax.plot(range(1, 11), ep_er,
                    color=OPT_COLOR[opt], marker=OPT_MARKER[opt], markersize=3,
                    lw=1.3 if lay_i == 0 else 1.0,
                    alpha=0.9 if lay_i == 0 else 0.55,
                    label=label if lay_i == 0 else None)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Effective rank of update")
    ax.set_title("(1) Update effective rank over epochs (5 layers × 3 optim)", fontsize=10)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, loc="upper left", ncol=3)

    # ---- (2) Spectral norm of UPDATE across epochs ----
    ax = fig.add_subplot(gs[0, 1])
    for opt in OPTIMIZERS:
        ep_spec = []
        for ep in range(1, 11):
            # Average spectral norm across 5 layers
            specs = [by[opt][(ep, lay)]["update"]["spec"] for lay in LAYERS]
            ep_spec.append(np.mean(specs))
        ax.plot(range(1, 11), ep_spec, color=OPT_COLOR[opt], marker=OPT_MARKER[opt],
                lw=2.5, label=opt, markersize=5)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Mean spectral norm of update (5 layers)")
    ax.set_yscale("log")
    ax.set_title("(2) Update spectral norm (log scale)\nAdamW ≫ Muon ≫ SGD by orders of magnitude", fontsize=10)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=9)

    # ---- (3) Effective rank: grad vs moment vs update (epoch=10, Muon only) ----
    ax = fig.add_subplot(gs[0, 2])
    x = np.arange(len(LAYERS))
    width = 0.27
    for k_i, kind in enumerate(KINDS):
        vals = [by["muon"][(10, lay)][kind]["eff_rank"] for lay in LAYERS]
        ax.bar(x + (k_i - 1) * width, vals, width,
               label=kind, edgecolor="black", linewidth=0.5,
               color=["#A0A0A0", "#606060", "#1F4E89"][k_i])
        for i, v in enumerate(vals):
            ax.text(x[i] + (k_i - 1) * width, v + 3, f"{v:.0f}",
                    ha="center", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels([LAYER_LABELS[lay] for lay in LAYERS], fontsize=7)
    ax.set_ylabel("Effective rank (Muon, ep=10)")
    ax.set_title("(3) Muon: eff_rank of grad / moment / update\nupdate ≫ grad ≈ moment", fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(fontsize=8, loc="upper left")

    # ---- (4) Top-10 singular value of UPDATE at ep=10 (block3.conv2, 3 optim) ----
    ax = fig.add_subplot(gs[1, 0])
    lay = "block3.conv2"
    for opt in OPTIMIZERS:
        r = by[opt][(10, lay)]
        top = r["update"]["top_singular"][:10]
        ax.plot(range(1, 11), top, color=OPT_COLOR[opt], marker=OPT_MARKER[opt],
                lw=2.5, label=opt, markersize=5)
    ax.set_xlabel("Singular value rank (1 = largest)")
    ax.set_ylabel("Singular value")
    ax.set_yscale("log")
    ax.set_title(f"(4) Top-10 singular values of UPDATE\n({lay}, ep=10, log scale)", fontsize=10)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=9)
    # annotate decay ratio
    for opt in OPTIMIZERS:
        r = by[opt][(10, lay)]
        top = r["update"]["top_singular"][:10]
        ratio = top[0] / max(top[-1], 1e-6)
        ax.text(10.3, top[-1], f"{opt}: top1/top10 ≈ {ratio:.0f}×",
                color=OPT_COLOR[opt], fontsize=7, va="center")

    # ---- (5) Spectral norm: grad vs moment vs update (epoch=10, 3 optim × 5 layers) ----
    ax = fig.add_subplot(gs[1, 1])
    x = np.arange(len(LAYERS))
    width = 0.13
    for k_i, kind in enumerate(KINDS):
        for o_i, opt in enumerate(OPTIMIZERS):
            vals = [by[opt][(10, lay)][kind]["spec"] for lay in LAYERS]
            offset = (k_i * len(OPTIMIZERS) + o_i - 4) * width
            ax.bar(x + offset, vals, width,
                   color=OPT_COLOR[opt],
                   edgecolor="black", linewidth=0.3,
                   alpha=0.55 if kind != "update" else 1.0,
                   hatch="" if kind == "update" else ("//" if kind == "grad" else ".."))
    ax.set_xticks(x)
    ax.set_xticklabels([LAYER_LABELS[lay] for lay in LAYERS], fontsize=7)
    ax.set_ylabel("Spectral norm (ep=10, log scale)")
    ax.set_yscale("log")
    ax.set_title("(5) Spectral norm: grad / moment / update × 3 optim × 5 layers\n(solid=update, hatch=grad, dot=moment)", fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    # Custom legend
    from matplotlib.patches import Patch
    legend_handles = [
        Patch(facecolor="white", edgecolor="black", hatch="//", label="grad"),
        Patch(facecolor="white", edgecolor="black", hatch="..", label="moment"),
        Patch(facecolor="white", edgecolor="black", label="update"),
        Patch(facecolor=OPT_COLOR["muon"], label="muon"),
        Patch(facecolor=OPT_COLOR["sgd"], label="sgd"),
        Patch(facecolor=OPT_COLOR["adamw"], label="adamw"),
    ]
    ax.legend(handles=legend_handles, fontsize=7, loc="upper left", ncol=2)

    # ---- (6) Frobenius norm of UPDATE over epochs (3 optim × 5 layers, mean) ----
    ax = fig.add_subplot(gs[1, 2])
    for opt in OPTIMIZERS:
        # show block3.conv2 (largest) + fc1 (interesting shape)
        for lay, ls in [("block3.conv2", "-"), ("fc1", "--")]:
            ep_fro = [by[opt][(ep, lay)]["update"]["fro"] for ep in range(1, 11)]
            ax.plot(range(1, 11), ep_fro, color=OPT_COLOR[opt], linestyle=ls,
                    lw=1.8 if ls == "-" else 1.2,
                    marker=OPT_MARKER[opt] if ls == "-" else None,
                    markersize=4 if ls == "-" else 0,
                    label=f"{opt}/{lay}" if ls == "-" else None)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Frobenius norm of update (log scale)")
    ax.set_yscale("log")
    ax.set_title("(6) Frobenius norm of update over epochs\nMuon saturates, SGD shrinks w/ LR, AdamW explodes", fontsize=10)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, loc="lower left", ncol=3)

    plt.suptitle("Muon / SGD / AdamW spectrum diagnostics · SmallCNN (1.26M) · CIFAR-10 · seed=42 · 10ep",
                 fontsize=13, fontweight="bold", y=1.00)
    plt.tight_layout()
    plt.savefig("/home/fuqingxu/cc-workspace/muon/figures/spectrum_diagnostics.png",
                dpi=150, bbox_inches="tight")
    print("[done] -> figures/spectrum_diagnostics.png")


if __name__ == "__main__":
    main()