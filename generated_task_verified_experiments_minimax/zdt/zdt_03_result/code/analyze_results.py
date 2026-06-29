"""
Analyze the 31x4 NSGA-II benchmark results.
- IGD / HV summary table
- ZDT3 5-segment coverage
- ZDT6 f1-axis distribution bias
- Figures
"""

import os
import pickle
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_PATH = os.path.join(OUT_DIR, "benchmark_results.pkl")

PROBLEMS = ["ZDT1", "ZDT2", "ZDT3", "ZDT6"]

# Per task spec
ZDT3_SEGMENTS = [
    (0.0000, 0.0830),
    (0.1822, 0.2578),
    (0.4093, 0.4539),
    (0.6184, 0.6525),
    (0.8233, 0.8518),
]


def main():
    with open(RESULTS_PATH, "rb") as f:
        all_results = pickle.load(f)

    # ---------- 1. IGD/HV summary ----------
    summary_lines = ["# IGD / HV summary over 31 independent runs",
                    "",
                    "| Problem | IGD mean | IGD std | IGD median | IGD best | IGD worst | HV mean | HV std | HV median |",
                    "|---|---|---|---|---|---|---|---|---|"]
    summary = {}
    for pname in PROBLEMS:
        per = all_results[pname]
        igd = np.array([r["igd"] for r in per])
        hv = np.array([r["hv"] for r in per])
        summary[pname] = {"igd": igd, "hv": hv}
        summary_lines.append(
            f"| {pname} | {igd.mean():.4f} | {igd.std(ddof=1):.4f} | {np.median(igd):.4f} | "
            f"{igd.min():.4f} | {igd.max():.4f} | {hv.mean():.4f} | {hv.std(ddof=1):.4f} | {np.median(hv):.4f} |"
        )
    summary_lines.append("")
    print("\n".join(summary_lines))

    # ---------- 2. ZDT3 segment coverage ----------
    zdt3_runs = all_results["ZDT3"]
    n_runs = len(zdt3_runs)
    seg_counts = np.zeros((n_runs, len(ZDT3_SEGMENTS)), dtype=int)
    seg_hits = np.zeros(len(ZDT3_SEGMENTS), dtype=int)
    full_coverage_runs = 0
    for i, r in enumerate(zdt3_runs):
        F = r["F"]
        for j, (lo, hi) in enumerate(ZDT3_SEGMENTS):
            # Count solutions whose f1 lies in the segment.
            mask = (F[:, 0] >= lo) & (F[:, 0] <= hi)
            n_hits = int(mask.sum())
            seg_counts[i, j] = n_hits
            if n_hits > 0:
                seg_hits[j] += 1
        if (seg_counts[i] > 0).all():
            full_coverage_runs += 1

    zdt3_lines = []
    zdt3_lines.append("# ZDT3 5-segment coverage analysis")
    zdt3_lines.append("")
    zdt3_lines.append("| Segment | f1 range | # runs with ≥1 solution | success rate | mean # solutions per run |")
    zdt3_lines.append("|---|---|---|---|---|")
    for j, (lo, hi) in enumerate(ZDT3_SEGMENTS):
        zdt3_lines.append(
            f"| {j+1} | [{lo:.4f}, {hi:.4f}] | {seg_hits[j]} / {n_runs} | "
            f"{seg_hits[j]/n_runs:.1%} | {seg_counts[:, j].mean():.1f} |"
        )
    zdt3_lines.append("")
    zdt3_lines.append(f"**Runs that cover all 5 segments:** {full_coverage_runs} / {n_runs} "
                      f"({full_coverage_runs/n_runs:.1%})")
    zdt3_lines.append("")
    print("\n".join(zdt3_lines))

    # ---------- 3. ZDT6 f1 distribution bias ----------
    zdt6_runs = all_results["ZDT6"]
    all_f1_zdt6 = np.concatenate([r["F"][:, 0] for r in zdt6_runs])  # 31 * 100 = 3100 points
    # The Pareto front of ZDT6 is defined for f1 in [0.2807753191, 1.0]
    pf_f1_min, pf_f1_max = 0.2807753191, 1.0
    in_front = (all_f1_zdt6 >= pf_f1_min) & (all_f1_zdt6 <= pf_f1_max)
    print(f"ZDT6: {in_front.sum()} / {len(all_f1_zdt6)} solutions lie on/in PF range "
          f"[{pf_f1_min:.4f}, {pf_f1_max:.4f}]")

    # Mean f1 of solutions on the front
    on_front_f1 = all_f1_zdt6[in_front]
    mean_f1 = on_front_f1.mean()
    median_f1 = np.median(on_front_f1)
    # KS test against uniform distribution on [0.2807753191, 1.0]
    from scipy.stats import kstest, skew, kurtosis
    ks_stat, ks_p = kstest(on_front_f1, 'uniform', args=(pf_f1_min, pf_f1_max - pf_f1_min))
    # Compare to expected uniform mean
    exp_mean = (pf_f1_min + pf_f1_max) / 2
    print(f"ZDT6 f1: mean={mean_f1:.4f} (uniform expected {exp_mean:.4f}), "
          f"median={median_f1:.4f}, skew={skew(on_front_f1):.4f}, "
          f"kurtosis={kurtosis(on_front_f1):.4f}")
    print(f"KS test vs uniform: D={ks_stat:.4f}, p={ks_p:.3e}")
    # Quantify the bias as # of solutions in upper half / lower half
    mid = 0.5
    upper = (on_front_f1 > mid).sum()
    lower = (on_front_f1 <= mid).sum()
    print(f"ZDT6 f1 split: f1 > 0.5 → {upper} ({upper/(upper+lower):.1%}); f1 ≤ 0.5 → {lower} ({lower/(upper+lower):.1%})")

    zdt6_lines = []
    zdt6_lines.append("# ZDT6 non-uniform distribution analysis")
    zdt6_lines.append("")
    zdt6_lines.append("The ZDT6 Pareto front is the curve f₂ = 1 − f₁², but f₁ itself is defined over "
                      "[0.2808, 1.0] and the search space is mapped through "
                      "f₁ = 1 − exp(−4 x₁) sin⁶(6π x₁). The resulting *target* density on the "
                      "true front is intentionally non-uniform: solutions with large f₁ "
                      "(near 1) are exponentially easier to discover than solutions with small f₁.")
    zdt6_lines.append("")
    zdt6_lines.append(f"- Solutions kept on the front range: **{in_front.sum()} / {len(all_f1_zdt6)}** = "
                      f"**{in_front.sum()/len(all_f1_zdt6):.1%}** of the 31 × 100 = 3100 final-population points")
    zdt6_lines.append(f"- Mean f₁ of those solutions: **{mean_f1:.4f}** "
                      f"(uniform would give {exp_mean:.4f})")
    zdt3_lines  # noqa
    zdt6_lines.append(f"- Median f₁: **{median_f1:.4f}**")
    zdt6_lines.append(f"- Skewness: **{skew(on_front_f1):.4f}** (negative = bulk on the right)")
    zdt6_lines.append(f"- Excess kurtosis: **{kurtosis(on_front_f1):.4f}**")
    zdt6_lines.append(f"- KS test vs Uniform[{pf_f1_min:.4f}, 1.0]: **D = {ks_stat:.4f}, p = {ks_p:.2e}**")
    zdt6_lines.append(f"- Split at f₁ = 0.5: upper half **{upper} ({upper/(upper+lower):.1%})**, "
                      f"lower half **{lower} ({lower/(upper+lower):.1%})**")
    zdt6_lines.append("")
    print("\n".join(zdt6_lines))

    # ---------- 4. Figures ----------
    # Fig 1: PF vs final front on a representative run for each problem
    fig, axes = plt.subplots(1, 4, figsize=(20, 4.5))
    for ax, pname in zip(axes, PROBLEMS):
        from pymoo.problems import get_problem
        problem = get_problem(pname)
        pf = problem.pareto_front()
        # Take a representative run (median IGD)
        per = all_results[pname]
        igd = np.array([r["igd"] for r in per])
        med_idx = int(np.argsort(igd)[len(igd) // 2])
        F = per[med_idx]["F"]
        ax.scatter(F[:, 0], F[:, 1], s=14, color="C1", alpha=0.8, label=f"NSGA-II run #{med_idx} (IGD={igd[med_idx]:.4f})")
        ax.plot(pf[:, 0], pf[:, 1], color="C0", lw=1.5, label="True PF")
        ax.set_title(pname)
        ax.set_xlabel("f₁")
        ax.set_ylabel("f₂")
        ax.legend(loc="best", fontsize=8)
        ax.grid(alpha=0.3)
    plt.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "fig_pf_vs_final.png"), dpi=130)
    plt.close(fig)

    # Fig 2: ZDT3 segment coverage visualization
    fig, ax = plt.subplots(figsize=(9, 5.5))
    # Plot the true PF in light grey
    from pymoo.problems import get_problem
    pf3 = get_problem("ZDT3").pareto_front()
    ax.plot(pf3[:, 0], pf3[:, 1], color="grey", lw=1, alpha=0.6, label="True PF")
    # Overlay 5 runs at random
    rng = np.random.default_rng(0)
    pick = rng.choice(len(zdt3_runs), size=5, replace=False)
    for k, idx in enumerate(pick):
        F = zdt3_runs[int(idx)]["F"]
        ax.scatter(F[:, 0], F[:, 1], s=22, alpha=0.7, label=f"run {int(idx)}")
    # Draw segment bands
    for j, (lo, hi) in enumerate(ZDT3_SEGMENTS):
        ax.axvspan(lo, hi, color=f"C{j}", alpha=0.06)
        ax.text((lo + hi) / 2, 1.02, f"seg{j+1}", ha="center", va="bottom", fontsize=8,
                color=f"C{j}")
    ax.set_title("ZDT3 — 5 sample final populations vs 5-segment PF")
    ax.set_xlabel("f₁")
    ax.set_ylabel("f₂")
    ax.set_ylim(-0.05, 1.15)
    ax.legend(loc="lower left", fontsize=8)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "fig_zdt3_segments.png"), dpi=130)
    plt.close(fig)

    # Fig 3: ZDT6 f1 distribution
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    # (a) Histogram of f1
    bins = np.linspace(0, 1, 26)
    axes[0].hist(on_front_f1, bins=bins, density=True, color="C0", alpha=0.7, label="NSGA-II f₁ (final pop)")
    # Plot expected uniform
    axes[0].axhline(1.0 / (pf_f1_max - pf_f1_min), color="C3", ls="--",
                    label=f"Uniform density on [{pf_f1_min:.3f}, 1.0]")
    axes[0].set_xlabel("f₁")
    axes[0].set_ylabel("density")
    axes[0].set_title("ZDT6 — f₁ distribution over 31 runs (final populations)")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)
    # (b) Histogram of per-bin counts vs uniform
    counts, edges = np.histogram(on_front_f1, bins=10, range=(0, 1))
    centers = 0.5 * (edges[:-1] + edges[1:])
    expected = len(on_front_f1) * np.ones(10) * 0.1
    width = (edges[1] - edges[0]) * 0.4
    axes[1].bar(centers - width/2, counts, width=width, color="C0", label="NSGA-II count")
    axes[1].bar(centers + width/2, expected, width=width, color="C3", alpha=0.6, label="Uniform expected")
    axes[1].set_xlabel("f₁")
    axes[1].set_ylabel("count (over 31×100 = 3100 final points)")
    axes[1].set_title("ZDT6 — bias toward large f₁")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)
    plt.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "fig_zdt6_bias.png"), dpi=130)
    plt.close(fig)

    # Fig 4: Box plot of IGD per problem
    fig, ax = plt.subplots(figsize=(8, 4.5))
    data = [summary[p]["igd"] for p in PROBLEMS]
    ax.boxplot(data, labels=PROBLEMS, showmeans=True, meanline=True)
    ax.set_ylabel("IGD")
    ax.set_title("IGD distribution over 31 runs")
    ax.grid(alpha=0.3)
    plt.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "fig_igd_boxplot.png"), dpi=130)
    plt.close(fig)

    # Fig 5: Convergence of mean IGD over generations (we didn't track, skip)
    # Save all summary text for use by the report writer
    with open(os.path.join(OUT_DIR, "analysis_dump.txt"), "w") as f:
        f.write("\n".join(summary_lines) + "\n\n")
        f.write("\n".join(zdt3_lines) + "\n\n")
        f.write("\n".join(zdt6_lines) + "\n\n")
        f.write(f"ZDT6 raw metrics:\n")
        f.write(f"  n_on_front={in_front.sum()}/{len(all_f1_zdt6)}\n")
        f.write(f"  mean_f1={mean_f1:.6f}\n")
        f.write(f"  median_f1={median_f1:.6f}\n")
        f.write(f"  skew={skew(on_front_f1):.6f}\n")
        f.write(f"  kurt={kurtosis(on_front_f1):.6f}\n")
        f.write(f"  ks_D={ks_stat:.6f}, ks_p={ks_p:.6e}\n")
        f.write(f"  upper_half={upper}, lower_half={lower}\n")
    print("\nAnalysis written to analysis_dump.txt")


if __name__ == "__main__":
    main()
