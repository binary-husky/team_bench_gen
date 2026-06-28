"""Analyze results.json: fit power-law slopes, compute speedups, draw log-log plot."""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

res = json.load(open("results.json"))

B = {int(k): v for k, v in res["brandes"].items()}
N = {int(k): v for k, v in res["naive"].items()}

# measured naive points (exclude extrapolated)
naive_meas = sorted(n for n, v in N.items() if not v.get("extrapolated", False))


def slope(xs, ys):
    xs, ys = np.array(xs, float), np.array(ys, float)
    return np.polyfit(np.log(xs), np.log(ys), 1)[0]


# ---- slopes ----
bn = sorted(B)
b_t = [B[n]["median"] for n in bn]
b_nm = [n * B[n]["m_median"] for n in bn]
brandes_slope_n = slope(bn, b_t)
brandes_slope_nm = slope(b_nm, b_t)

n_t = [N[n]["median"] for n in naive_meas]
naive_slope_n = slope(naive_meas, n_t)

print("=== power-law fits (log t vs log x) ===")
print(f"Brandes  slope vs n   = {brandes_slope_n:.3f}   (theory ~2, since nm~n^2)")
print(f"Brandes  slope vs nm  = {brandes_slope_nm:.3f}   (theory ~1 : near-linear in nm)")
print(f"Naive    slope vs n   = {naive_slope_n:.3f}   (theory ~3)")
print()

print("=== table ===")
print(f"{'n':>6} {'m':>7} {'nm':>10} {'Brandes(s)':>11} {'Naive(s)':>11} {'speedup':>9}")
alln = sorted(set(B) | set(N))
for n in alln:
    bt = B[n]["median"] if n in B else None
    nt = N[n]["median"]
    tag = " (extrap)" if N[n].get("extrapolated") else ""
    m = (B[n]["m_median"] if n in B else N[n]["m_median"])
    bts = f"{bt:.4f}" if bt is not None else "  --"
    sps = f"{nt / bt:.1f}x" if bt is not None else "  --"
    print(f"{n:>6} {m:>7} {n*m:>10} {bts:>11} {nt:>11.4f}{tag:>9} {sps:>9}")
print()

print("=== speedups ===")
for n in [1000, 2000]:
    sp = N[n]["median"] / B[n]["median"]
    print(f"n={n}: Brandes={B[n]['median']:.3f}s  Naive={N[n]['median']:.2f}s  "
          f"speedup={sp:.1f}x  ({'measured' if not N[n].get('extrapolated') else 'extrapolated'})")

# ---- plot ----
fig, ax = plt.subplots(figsize=(7.5, 5.2))
bn_sorted = sorted(B)
ax.loglog(bn_sorted, [B[n]["median"] for n in bn_sorted], "o-", lw=2, ms=7,
          color="#1f77b4", label=f"Brandes O(nm)  [slope {brandes_slope_nm:.2f} vs nm]")
ax.loglog(naive_meas, [N[n]["median"] for n in naive_meas], "s-", lw=2, ms=7,
          color="#d62728", label=f"Naive O(n$^3$)  [slope {naive_slope_n:.2f} vs n]")

# reference guide lines anchored at n=200
n0 = 200
ref = np.array(bn_sorted, float)
ax.loglog(bn_sorted, B[n0]["median"] * (ref / n0) ** 2, ":", color="#1f77b4",
          alpha=0.5, label=r"reference $\propto n^2$")
ax.loglog(bn_sorted, N[n0]["median"] * (ref / n0) ** 3, ":", color="#d62728",
          alpha=0.5, label=r"reference $\propto n^3$")

ax.set_xlabel("graph size n  (avg degree ~ 8,  m = Θ(n))")
ax.set_ylabel("median runtime  (seconds, 3 seeds)")
ax.set_title("Betweenness centrality: Brandes vs naive scaling")
ax.grid(True, which="both", ls="-", alpha=0.25)
ax.legend(fontsize=8.5, loc="upper left")
fig.tight_layout()
fig.savefig("plot_runtime.png", dpi=130)
print("\n[saved] plot_runtime.png")

# stash derived numbers for the markdown writer
out = {
    "brandes_slope_n": brandes_slope_n,
    "brandes_slope_nm": brandes_slope_nm,
    "naive_slope_n": naive_slope_n,
    "speedups": {str(n): N[n]["median"] / B[n]["median"] for n in [1000, 2000]},
}
json.dump(out, open("derived.json", "w"), indent=2)
print("[saved] derived.json")
