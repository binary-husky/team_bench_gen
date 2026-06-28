"""Fine sweep over p=8..14 plus a log-log fit to verify the -1/2 power law
of relative error vs m (memory). Supplements the required {8,10,12,14} grid."""
import math, json
import numpy as np
from hll_exp import make_stream, run_hll, N

SEEDS = list(range(2001, 2031))   # 30 seeds
PS = list(range(8, 15))           # 8,9,10,11,12,13,14
N = 100_000

rows = []
for p in PS:
    m = 1 << p
    errs = []
    for s in SEEDS:
        est = run_hll(p, make_stream(N, s), s)
        errs.append((est - N) / N)
    errs = np.array(errs)
    rows.append({
        "p": p, "m": m,
        "std": float(errs.std(ddof=1)),
        "mae": float(np.abs(errs).mean()),
        "mean": float(errs.mean()),
    })

ms = np.array([r["m"] for r in rows], dtype=float)
stds = np.array([r["std"] for r in rows])
maes = np.array([r["mae"] for r in rows])

# log-log linear fit: log(err) = a + b*log(m), expect b ~ -0.5
def fit(errs):
    b, a = np.polyfit(np.log(ms), np.log(errs), 1)
    return a, b

a_std, b_std = fit(stds)
a_mae, b_mae = fit(maes)

print("p   m      std%     MAE%     theory_SE%")
for r in rows:
    th = 1.04/math.sqrt(r["m"])*100
    print(f"{r['p']:2d}  {r['m']:6d}  {r['std']*100:7.3f}  {r['mae']*100:7.3f}  {th:7.3f}")

print(f"\nlog-log slope (std)  = {b_std:.4f}  (theory -0.5)")
print(f"log-log slope (MAE)  = {b_mae:.4f}  (theory -0.5)")

# doubling test: consecutive p (m x2) -> error should x 1/sqrt(2)=0.707
print("\ndoubling steps (m -> 2m), error ratio (cur/prev), expect ~0.707:")
for i in range(1, len(rows)):
    rs = rows[i]["std"]/rows[i-1]["std"]
    rm = rows[i]["mae"]/rows[i-1]["mae"]
    print(f"  p{rows[i-1]['p']}->p{rows[i]['p']} (m {rows[i-1]['m']}->{rows[i]['m']}): std_ratio={rs:.3f} mae_ratio={rm:.3f}")

# 4x steps (the required grid)
print("\n4x steps (the required grid {8,10,12,14}), error ratio, expect ~0.5:")
grid = [r for r in rows if r["p"] in (8,10,12,14)]
for i in range(1,len(grid)):
    rs = grid[i]["std"]/grid[i-1]["std"]
    rm = grid[i]["mae"]/grid[i-1]["mae"]
    print(f"  p{grid[i-1]['p']}->p{grid[i]['p']} (m x4): std_ratio={rs:.3f} mae_ratio={rm:.3f} (expect 0.5)")
rs64 = grid[0]["std"]/grid[-1]["std"]; rm64 = grid[0]["mae"]/grid[-1]["mae"]
print(f"  p8->p14 (m x64): std_ratio={rs64:.3f} mae_ratio={rm64:.3f} (expect 1/8=0.125, i.e. error/8)")

json.dump({"rows":rows,"b_std":b_std,"b_mae":b_mae}, open("hll_sweep.json","w"), indent=2, default=float)
