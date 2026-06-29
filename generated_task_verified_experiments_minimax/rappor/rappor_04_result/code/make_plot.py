"""
Analysis + plots for the RAPPOR accuracy-vs-N experiment.

Reads rappor_04_results.json (raw per-seed measurements) and:
  1. Aggregates per N (mean +/- std of L1, max-abs errors)
  2. Fits log(error) ~ a + b * log(N) by least squares to recover the
     empirical scaling exponent
  3. Saves:
        - rappor_04_accuracy_vs_N.png   (log-log scatter with fit lines
                                        and the theoretical 1/sqrt(N) line)
        - rappor_04_N_for_target_L1.txt (N needed to reach L1 <= 0.1)
"""

from __future__ import annotations

import json

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    with open("rappor_04_results.json") as f:
        raw = json.load(f)

    # Per-N aggregation
    Ns = sorted({r["N"] for r in raw})
    Ns_arr = np.asarray(Ns, dtype=float)
    l1_means, l1_stds, mx_means, mx_stds = [], [], [], []
    for N in Ns:
        l1 = np.array([r["l1_err"] for r in raw if r["N"] == N])
        mx = np.array([r["max_err"] for r in raw if r["N"] == N])
        l1_means.append(l1.mean())
        l1_stds.append(l1.std(ddof=0))
        mx_means.append(mx.mean())
        mx_stds.append(mx.std(ddof=0))
    l1_means = np.array(l1_means); l1_stds = np.array(l1_stds)
    mx_means = np.array(mx_means); mx_stds = np.array(mx_stds)

    # ------------------------------------------------------------------
    # Log-log fit: log(err) = a + b log(N)   =>  err ~ N^b
    # ------------------------------------------------------------------
    logN = np.log10(Ns_arr)
    logL1 = np.log10(l1_means)
    logMx = np.log10(mx_means)

    def linfit(x, y):
        b, a = np.polyfit(x, y, 1)
        return a, b

    a_L1, b_L1 = linfit(logN, logL1)
    a_Mx, b_Mx = linfit(logN, logMx)
    print(f"log-log fit L1 : log10(L1) = {a_L1:.3f} + {b_L1:.3f} * log10(N)")
    print(f"log-log fit Max: log10(Max) = {a_Mx:.3f} + {b_Mx:.3f} * log10(N)")

    # Constant c in  err = c * N^{-1/2}  -- separate fit
    c_L1 = np.median(l1_means * np.sqrt(Ns_arr))
    c_Mx = np.median(mx_means * np.sqrt(Ns_arr))
    print(f"\n1/sqrt(N) fit: L1 ~ {c_L1:.2f}/sqrt(N),  Max ~ {c_Mx:.2f}/sqrt(N)")

    # ------------------------------------------------------------------
    # Plot
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    Ns_dense = np.logspace(np.log10(1.5e3), np.log10(1.5e5), 200)

    # Theoretical 1/sqrt(N) anchored at the N=10,000 point
    N_anchor = 10_000
    l1_anchor = float(l1_means[Ns.index(N_anchor)])
    mx_anchor = float(mx_means[Ns.index(N_anchor)])
    ax.plot(Ns_dense, l1_anchor * np.sqrt(N_anchor) / np.sqrt(Ns_dense),
            "--", color="tab:blue",  alpha=0.55,
            label=r"theoretical $1/\sqrt{N}$ (anchored at $N=10^4$)")
    ax.plot(Ns_dense, mx_anchor * np.sqrt(N_anchor) / np.sqrt(Ns_dense),
            "--", color="tab:orange", alpha=0.55)

    # Empirical points with error bars (std across seeds)
    ax.errorbar(Ns_arr, l1_means, yerr=l1_stds, fmt="o", capsize=4,
                color="tab:blue",  label=r"$L_1$ error (mean $\pm$ std)")
    ax.errorbar(Ns_arr, mx_means, yerr=mx_stds, fmt="s", capsize=4,
                color="tab:orange", label=r"max-absolute error (mean $\pm$ std)")

    # Fits
    ax.plot(Ns_dense, 10 ** (a_L1 + b_L1 * np.log10(Ns_dense)),
            "-",  color="tab:blue",   alpha=0.7,
            label=fr"fit $L_1 \propto N^{{{b_L1:.2f}}}$")
    ax.plot(Ns_dense, 10 ** (a_Mx + b_Mx * np.log10(Ns_dense)),
            "-",  color="tab:orange", alpha=0.7,
            label=fr"fit max $\propto N^{{{b_Mx:.2f}}}$")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"Number of clients $N$")
    ax.set_ylabel(r"Frequency estimation error")
    ax.set_title(r"RAPPOR estimation error vs.\ client cohort size "
                 r"(M=20, k=128, h=4, $f=0.5$, $p=0.5$, $q=0.75$)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig("rappor_04_accuracy_vs_N.png", dpi=140)
    print("wrote rappor_04_accuracy_vs_N.png")

    # ------------------------------------------------------------------
    # N required to reach target L1
    # ------------------------------------------------------------------
    target = 0.1
    N_for_target = (c_L1 / target) ** 2          # from L1 ~ c/sqrt(N)
    N_for_target_empirical = 10 ** ((a_L1 - np.log10(target)) / -b_L1)
    out = (
        f"Target L1 error <= {target}\n"
        f"  1/sqrt(N) fit (c = {c_L1:.3f}):  N >= {N_for_target:,.0f}\n"
        f"  empirical log-log fit  (slope = {b_L1:.3f}): N >= {N_for_target_empirical:,.0f}\n"
        f"Observed at N = 100,000:  L1 = {l1_means[-1]:.4f}\n"
    )
    with open("rappor_04_N_for_target_L1.txt", "w") as f:
        f.write(out)
    print(out)


if __name__ == "__main__":
    main()
