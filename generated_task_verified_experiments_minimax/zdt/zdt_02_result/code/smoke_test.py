"""Smoke test: 2 seeds x 2 problems to verify pipeline correctness."""

import sys, os
sys.path.insert(0, "/data/workspace/admin/happy_lake/.verify_judge_minimax/zdt/zdt_02")
from run_experiment import run_one, ZDT1, ZDT2
import time

t0 = time.time()
for prob_name, prob_cls in [("ZDT1", ZDT1), ("ZDT2", ZDT2)]:
    for seed in [1, 2]:
        r = run_one(prob_cls, seed, n_gen=250, record_every=25)
        print(f"{prob_name} seed={seed}  IGD={r['igd']:.6f}  HV={r['hv']:.6f}")
        print(f"  IGD curve: {r['igd_curve']}")
print(f"Total: {time.time() - t0:.1f}s")