import json
import numpy as np

with open('/data/workspace/admin/happy_lake/.verify_judge_minimax/kmeanspp/kmeanspp_02/results.json') as f:
    r = json.load(f)

pp = np.array(r['kmeanspp']['values'])
rd = np.array(r['random']['values'])

# Quantiles
print("k-means++ quantiles:", [round(float(np.quantile(pp, q)), 2) for q in [0, 0.25, 0.5, 0.75, 0.9, 1.0]])
print("random    quantiles:", [round(float(np.quantile(rd, q)), 2) for q in [0, 0.25, 0.5, 0.75, 0.9, 1.0]])

# Percentile comparisons
print(f"\nmin(k-means++)      = {pp.min():.4f}")
print(f"median(k-means++)   = {np.median(pp):.4f}")
print(f"max(k-means++)      = {pp.max():.4f}")
print(f"min(random)         = {rd.min():.4f}")
print(f"median(random)      = {np.median(rd):.4f}")
print(f"max(random)         = {rd.max():.4f}")

# Fraction of random runs that beat best k-means++?
n_random_beats_best_pp = int((rd < pp.min()).sum())
print(f"\n#random runs beating best k-means++: {n_random_beats_best_pp}/{len(rd)}")

# Fraction of k-means++ runs that are worse than worst random?
n_pp_worse_than_worst_rd = int((pp > rd.max()).sum())
print(f"#k-means++ runs worse than worst random: {n_pp_worse_than_worst_rd}/{len(pp)}")

# Fraction of random runs that are worse than worst k-means++
n_random_worse_than_worst_pp = int((rd > pp.max()).sum())
print(f"#random runs worse than worst k-means++: {n_random_worse_than_worst_pp}/{len(rd)}")

# Wilcoxon / Mann-Whitney U
from scipy.stats import mannwhitneyu
u, p = mannwhitneyu(pp, rd, alternative='two-sided')
print(f"\nMann-Whitney U={u:.1f}, p-value={p:.4e}")

# Paired diff: per trial
print("\nper-trial difference (random - kmeans++):")
diffs = rd - pp
print(f"  mean diff = {diffs.mean():.4f}")
print(f"  min diff  = {diffs.min():.4f}  (random slightly under kmeans++)")
print(f"  max diff  = {diffs.max():.4f}  (random >> kmeans++)")
print(f"  #random < kmeans++ (per trial): {int((diffs<0).sum())}/{len(diffs)}")

# Save extra stats
r['quantiles_pp'] = [float(np.quantile(pp, q)) for q in [0, 0.25, 0.5, 0.75, 0.9, 1.0]]
r['quantiles_rd'] = [float(np.quantile(rd, q)) for q in [0, 0.25, 0.5, 0.75, 0.9, 1.0]]
r['n_random_beats_best_pp'] = n_random_beats_best_pp
r['n_random_worse_than_worst_pp'] = n_random_worse_than_worst_pp
r['mannwhitneyu_u'] = float(u)
r['mannwhitneyu_p'] = float(p)
r['mean_paired_diff'] = float(diffs.mean())
r['n_random_smaller_pp_per_trial'] = int((diffs<0).sum())

with open('/data/workspace/admin/happy_lake/.verify_judge_minimax/kmeanspp/kmeanspp_02/results.json', 'w') as f:
    json.dump(r, f, indent=2)
print("\nUpdated results.json")
