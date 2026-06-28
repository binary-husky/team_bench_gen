import json, numpy as np
d = json.load(open("results.json"))
res = d["results"]
Ks = sorted(int(k) for k in res)
n = d["graph"]["n"]

print("=== 1/sqrt(K) regime fit (exclude near-saturation K=2000, which is 67% sampling) ===")
regime = [K for K in Ks if K <= 500]   # pure sampling regime K << n
ks = np.array(regime, float)
for metric in ["err_max_mean", "err_rmse_mean"]:
    y = np.array([res[str(K)][metric] for K in regime])
    slope, intercept = np.polyfit(np.log(ks), np.log(y), 1)
    pred = np.exp(intercept) * ks ** slope
    ss_res = np.sum((y - pred) ** 2); ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot
    print(f"  {metric:16s}: exponent={slope:+.3f} (expect -0.50), R^2={r2:.4f}")

print("\n=== Ratio checks: actual error ratio vs predicted 1/sqrt(K) (K_new/K_old -> err/sqrt) ===")
print(f"{'metric':16s} {'K_old->K_new':14s} {'Kratio':7s} {'pred':6s} {'actual':7s}")
pairs = [(10,50),(50,100),(100,500),(500,2000)]
for metric in ["err_max_mean", "err_rmse_mean"]:
    for a,b in pairs:
        ea = res[str(a)][metric]; eb = res[str(b)][metric]
        kratio = b/a
        pred = np.sqrt(kratio)
        actual = ea/eb
        print(f"  {metric:16s} {a:>4}->{b:<4}  {kratio:6.0f} {pred:6.2f} {actual:7.2f}")
