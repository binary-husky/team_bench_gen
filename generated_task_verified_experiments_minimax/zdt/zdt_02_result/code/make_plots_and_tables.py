"""Generate plots and tables from raw_results.json."""

import os
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT_DIR = "/data/workspace/admin/happy_lake/.verify_judge_minimax/zdt/zdt_02"

with open(os.path.join(OUT_DIR, "raw_results.json"), "r") as f:
    data = json.load(f)


# ---------------------------------------------------------------------------------------------------------
# 1. Summary table
# ---------------------------------------------------------------------------------------------------------
print("=" * 70)
print(f"{'Problem':<8} {'Metric':<6} {'Mean':<14} {'Std (ddof=1)':<14} {'Min':<10} {'Max':<10}")
print("-" * 70)
for prob in ["ZDT1", "ZDT2"]:
    igds = np.array(data[prob]["igd_runs"])
    hvs = np.array(data[prob]["hv_runs"])
    print(f"{prob:<8} {'IGD':<6} {np.mean(igds):<14.6f} {np.std(igds, ddof=1):<14.6f} "
          f"{np.min(igds):<10.6f} {np.max(igds):<10.6f}")
    print(f"{prob:<8} {'HV':<6} {np.mean(hvs):<14.6f} {np.std(hvs, ddof=1):<14.6f} "
          f"{np.min(hvs):<10.6f} {np.max(hvs):<10.6f}")
    print("-" * 70)


# ---------------------------------------------------------------------------------------------------------
# 2. Convergence curve: mean IGD vs generation (with shaded std band)
# ---------------------------------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 5))

for prob, color, marker in [("ZDT1", "tab:blue", "o"), ("ZDT2", "tab:red", "s")]:
    curves = data[prob]["igd_curves"]
    # Each curve is a list of {"gen": g, "igd": v}
    gens = [pt["gen"] for pt in curves[0]]
    igd_matrix = np.array([[pt["igd"] for pt in c] for c in curves])  # shape (n_runs, n_gen_samples)
    mean_igd = np.mean(igd_matrix, axis=0)
    std_igd = np.std(igd_matrix, axis=0, ddof=1)
    ax.plot(gens, mean_igd, color=color, marker=marker, markevery=1,
            label=f"{prob} (mean)")
    ax.fill_between(gens, mean_igd - std_igd, mean_igd + std_igd,
                    color=color, alpha=0.20, label=f"{prob} (mean ± std)")

ax.set_xlabel("Generation")
ax.set_ylabel("IGD")
ax.set_title("NSGA-II convergence on ZDT1 / ZDT2 (n_var=30, N=100, 31 seeds)")
ax.set_yscale("log")
ax.grid(True, which="both", linestyle="--", alpha=0.5)
ax.legend(loc="best")
fig.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "igd_convergence.png"), dpi=150)
plt.close(fig)
print(f"Saved: igd_convergence.png")


# ---------------------------------------------------------------------------------------------------------
# 3. Box-plot of final IGD and HV (side by side)
# ---------------------------------------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(10, 4))

for ax_i, (metric, label) in enumerate(zip(["igd_runs", "hv_runs"], ["IGD", "HV"])):
    bp_data = [data["ZDT1"][metric], data["ZDT2"][metric]]
    bp = axes[ax_i].boxplot(bp_data, labels=["ZDT1", "ZDT2"], patch_artist=True, showmeans=True)
    colors = ["tab:blue", "tab:red"]
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.5)
    axes[ax_i].set_title(f"{label} across 31 runs")
    axes[ax_i].set_ylabel(label)
    axes[ax_i].grid(True, linestyle="--", alpha=0.5)

fig.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "boxplot_igd_hv.png"), dpi=150)
plt.close(fig)
print(f"Saved: boxplot_igd_hv.png")


# ---------------------------------------------------------------------------------------------------------
# 4. Mean convergence curves table
# ---------------------------------------------------------------------------------------------------------
print("\nMean ± std IGD across 31 runs by generation (sampled every 25 gens):")
gens_all = [pt["gen"] for pt in data["ZDT1"]["igd_curves"][0]]
print(f"{'Gen':<6}", end="")
for prob in ["ZDT1", "ZDT2"]:
    print(f"{prob + ' mean':<14}{prob + ' std':<14}", end="")
print()
for j, g in enumerate(gens_all):
    print(f"{g:<6}", end="")
    for prob in ["ZDT1", "ZDT2"]:
        col = np.array([data[prob]["igd_curves"][i][j]["igd"] for i in range(len(data[prob]["igd_curves"]))])
        print(f"{np.mean(col):<14.6f}{np.std(col, ddof=1):<14.6f}", end="")
    print()


# ---------------------------------------------------------------------------------------------------------
# 5. Per-run IGD/HV table
# ---------------------------------------------------------------------------------------------------------
print("\nPer-run results:")
print(f"{'seed':<6}{'ZDT1 IGD':<14}{'ZDT1 HV':<14}{'ZDT2 IGD':<14}{'ZDT2 HV':<14}")
for i in range(31):
    seed = data["ZDT1"]["seeds"][i]
    print(f"{seed:<6}"
          f"{data['ZDT1']['igd_runs'][i]:<14.6f}{data['ZDT1']['hv_runs'][i]:<14.6f}"
          f"{data['ZDT2']['igd_runs'][i]:<14.6f}{data['ZDT2']['hv_runs'][i]:<14.6f}")


# ---------------------------------------------------------------------------------------------------------
# 6. Save the stats dict as JSON for the summary writer
# ---------------------------------------------------------------------------------------------------------
stats = {}
for prob in ["ZDT1", "ZDT2"]:
    igds = np.array(data[prob]["igd_runs"])
    hvs = np.array(data[prob]["hv_runs"])
    stats[prob] = {
        "igd_mean": float(np.mean(igds)),
        "igd_std": float(np.std(igds, ddof=1)),
        "hv_mean": float(np.mean(hvs)),
        "hv_std": float(np.std(hvs, ddof=1)),
        "igd_min": float(np.min(igds)),
        "igd_max": float(np.max(igds)),
        "hv_min": float(np.min(hvs)),
        "hv_max": float(np.max(hvs)),
        "igd_median": float(np.median(igds)),
        "hv_median": float(np.median(hvs)),
    }

# Convergence table (mean ± std per gen)
gens_all = [pt["gen"] for pt in data["ZDT1"]["igd_curves"][0]]
conv_table = {"gens": gens_all}
for prob in ["ZDT1", "ZDT2"]:
    means, stds = [], []
    for j, g in enumerate(gens_all):
        col = np.array([data[prob]["igd_curves"][i][j]["igd"] for i in range(len(data[prob]["igd_curves"]))])
        means.append(float(np.mean(col)))
        stds.append(float(np.std(col, ddof=1)))
    conv_table[prob + "_mean"] = means
    conv_table[prob + "_std"] = stds

# Per-seed results
per_seed = {"seeds": data["ZDT1"]["seeds"]}
for prob in ["ZDT1", "ZDT2"]:
    per_seed[prob + "_igd"] = data[prob]["igd_runs"]
    per_seed[prob + "_hv"] = data[prob]["hv_runs"]

with open(os.path.join(OUT_DIR, "summary_stats.json"), "w") as f:
    json.dump({"stats": stats, "convergence": conv_table, "per_seed": per_seed}, f, indent=2)

print("\nSaved: summary_stats.json")