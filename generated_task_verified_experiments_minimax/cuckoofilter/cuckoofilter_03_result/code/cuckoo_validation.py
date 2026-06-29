"""Additional validation: vary fingerprint size and seed to confirm trends."""

import json
import time
from cuckoo_experiment import CuckooFilter, run_experiment

M = 1 << 14
MAX_KICKS = 500
FP_BITS = 16

print("=== Primary run (the run reported in the summary) ===")
results = []
for b in (2, 4, 8):
    r = run_experiment(M, b, MAX_KICKS, seed=42, fingerprint_bits=FP_BITS)
    results.append(r)
    print(f"b={b}  load={r['load_factor']:.4f}  avg_kicks={r['avg_kicks']:.4f}  ({r['elapsed_s']:.2f}s)")

print()
print("=== Multi-seed validation (3 seeds, 16-bit fingerprint) ===")
multi = {b: [] for b in (2, 4, 8)}
for seed in (1, 7, 42, 123, 2024):
    for b in (2, 4, 8):
        r = run_experiment(M, b, MAX_KICKS, seed=seed, fingerprint_bits=FP_BITS)
        multi[b].append(r)

for b in (2, 4, 8):
    lfs = [r["load_factor"] for r in multi[b]]
    aks = [r["avg_kicks"] for r in multi[b]]
    mean_lf = sum(lfs) / len(lfs)
    mean_ak = sum(aks) / len(aks)
    min_lf, max_lf = min(lfs), max(lfs)
    min_ak, max_ak = min(aks), max(aks)
    print(
        f"b={b}  load_factor mean={mean_lf:.4f}  range=[{min_lf:.4f}, {max_lf:.4f}]  "
        f"avg_kicks mean={mean_ak:.4f}  range=[{min_ak:.4f}, {max_ak:.4f}]"
    )

print()
print("=== Smaller-fingerprint check (12-bit, paper uses this for m=2^15..2^30) ===")
for b in (2, 4, 8):
    r = run_experiment(M, b, MAX_KICKS, seed=42, fingerprint_bits=12)
    print(f"b={b}  load={r['load_factor']:.4f}  avg_kicks={r['avg_kicks']:.4f}")

# Persist the multi-seed + 12-bit numbers alongside the primary run
out = {
    "primary": results,
    "multi_seed_16bit": {str(b): multi[b] for b in multi},
    "fp12_seed42": [
        run_experiment(M, b, MAX_KICKS, seed=42, fingerprint_bits=12)
        for b in (2, 4, 8)
    ],
}
with open("validation_results.json", "w") as f:
    json.dump(out, f, indent=2)
print("\nWrote validation_results.json")