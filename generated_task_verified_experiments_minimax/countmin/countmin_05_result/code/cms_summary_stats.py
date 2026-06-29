"""Final analysis: comprehensive metrics for the summary."""
import numpy as np
from cms_experiment import run_one_seed

# Aggregate metrics across seeds
print("=" * 80)
print("FINAL EXPERIMENT RESULTS - Zipfian(s=1.0), w=2048, d=8")
print("=" * 80)

point_errs_all = []
point_errs_pos = []
point_errs_freq_weighted = []
F2_errs = []
F2_errs_per_row_mean = []
abs_point_errs = []

for s in range(12):
    seed = 1009 + s * 37
    pe, fe, extras = run_one_seed(seed, return_arrays=True)
    point_errs_all.append(pe)
    point_errs_pos.append(extras["point_err_pos"])
    F2_errs.append(fe)

    # Also compute freq-weighted relative error (only items with a[i]>0, weighted by a[i])
    point_errs_freq_weighted.append(None)  # placeholder
    F2_errs_per_row_mean.append(np.mean(extras["F2_err_per_row"]))
    abs_point_errs.append(None)

# Save the absolute noise distribution
print(f"\nNumber of seeds: 12")
print(f"\n--- Point Query Metrics ---")
print(f"Mean over all items (literal metric):     {np.mean(point_errs_all):.4e} "
      f"± {np.std(point_errs_all, ddof=1):.3e}")
print(f"Mean over items with a[i]>0:              {np.mean(point_errs_pos):.4e} "
      f"± {np.std(point_errs_pos, ddof=1):.3e}")

print(f"\n--- F2 Self-Join Metrics ---")
print(f"F2 relative error (min over rows):        {np.mean(F2_errs):.4e} "
      f"± {np.std(F2_errs, ddof=1):.3e}")
print(f"Mean per-row F2 relative error:           {np.mean(F2_errs_per_row_mean):.4e}")
print(f"\nNote: point_err values are mean over 1e5 items of (â[i]-a[i])/max(a[i],1)")
print(f"      F2_err values are (F̂₂-F₂)/F₂ where F̂₂=min_j Σ_l C[j,l]²")
