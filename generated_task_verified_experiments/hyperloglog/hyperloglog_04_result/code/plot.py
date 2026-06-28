import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

d = np.load("hll04_results.npz")
n = d["n_grid"]; rm = d["raw_mean"]*100; rs = d["raw_std"]*100
cm = d["cor_mean"]*100; cs = d["cor_std"]*100
m = int(d["m"]); thr = float(d["threshold"])

fig, ax = plt.subplots(figsize=(8,5))
ax.errorbar(n, rm, yerr=rs, marker="o", label="(A) raw (no correction)", color="#c0392b", capsize=3)
ax.errorbar(n, cm, yerr=cs, marker="s", label="(B) corrected (linear counting)", color="#27ae60", capsize=3)
ax.axvline(thr, color="gray", ls="--", lw=1, label=f"2.5·m = {int(thr)}")
ax.axhline(0, color="black", lw=0.8)
ax.set_xscale("log")
ax.set_xlabel("true cardinality n")
ax.set_ylabel("signed relative error  (Ê − n)/n  [%]")
ax.set_title(f"HyperLogLog bias: raw vs linear-counting corrected  (p=10, m={m}, 8 seeds)")
ax.legend(loc="upper right")
ax.grid(True, which="both", ls=":", alpha=0.5)
fig.tight_layout()
fig.savefig("hll04_bias.png", dpi=130)
print("saved hll04_bias.png")
