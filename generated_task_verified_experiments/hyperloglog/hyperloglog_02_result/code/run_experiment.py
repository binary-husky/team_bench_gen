"""Final experiment: more seeds, signed + |relative| errors, plot + table."""
import time, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from hll import run_one, M_REG

SEEDS = [1, 2, 3, 4, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61]
NS = [1000, 5000, 10000, 50000, 100000, 500000, 1000000]
THEO_SE = 1.04 / math.sqrt(M_REG) * 100   # percent

t0 = time.time()
records = []  # (n, seed, est, signed_rel, abs_rel)
for n in NS:
    for s in SEEDS:
        est = run_one(s, n)
        signed = (est - n) / n * 100
        abse = abs(signed)
        records.append((n, s, est, signed, abse))
print("elapsed", round(time.time()-t0, 1), "s")

rec = np.array(records, dtype=float)
ns = rec[:, 0]; est = rec[:, 2]; sgn = rec[:, 3]; abse = rec[:, 4]

# aggregate
summary = []
for n in NS:
    mask = rec[:, 0] == n
    summary.append((n, abse[mask].mean(), abse[mask].std(),
                    sgn[mask].mean(), sgn[mask].std(), mask.sum()))
print(f"{'n':>9} {'|rel|mean%':>10} {'|rel|std%':>9} {'bias%':>9} {'sgn_std%':>9} {'seeds':>5}")
for n, am, asd, bm, bsd, k in summary:
    print(f"{int(n):>9d} {am:10.3f} {asd:9.3f} {bm:9.3f} {bsd:9.3f} {int(k):>5d}")
print(f"theoretical SE = {THEO_SE:.3f}%")

# plot: |rel| mean +/- std vs n, with theoretical SE line
xs = np.array([s[0] for s in summary], dtype=float)
means = np.array([s[1] for s in summary])
stds = np.array([s[2] for s in summary])

fig, ax = plt.subplots(figsize=(7, 4.5))
ax.errorbar(xs, means, yerr=stds, fmt='o-', capsize=4, label='mean |rel. error| ± std')
ax.axhline(THEO_SE, color='r', ls='--', label=f'theoretical SE ≈ {THEO_SE:.2f}%')
ax.set_xscale('log')
ax.set_xlabel('true cardinality n')
ax.set_ylabel('relative error (%)')
ax.set_title(f'HyperLogLog (p={int(round(math.log2(M_REG)))}, m={M_REG}) accuracy vs true cardinality')
ax.legend()
ax.grid(True, which='both', alpha=0.3)
fig.tight_layout()
fig.savefig("hll_accuracy_vs_n.png", dpi=130)
print("plot saved")

# also dump raw per-seed table for the summary
np.savetxt("raw_records.csv", rec, delimiter=",",
           header="n,seed,est,signed_rel_pct,abs_rel_pct", comments="", fmt=["%d","%d","%.3f","%.4f","%.4f"])
print("raw records saved")
