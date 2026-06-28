"""Run RCMAES on the official CEC2022 suite, D=20, budget=200000, 51 runs.
Parallelized over CPU cores. Saves per-run best fitness to rcmaes_results.npz.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool

import cec22
from rcmaes import rcmaes_minimize, make_rcmaes_objective

D = 20
NMAX = 200000
NRUNS = 51
NFUNCS = 12

def _worker(args):
    func_num, run = args
    obj = make_rcmaes_objective(cec22.evaluate_batch, func_num)
    # seed = run index (paper convention)
    try:
        bx, bf, bxn, ne = rcmaes_minimize(obj, D, NMAX, seed=run)
    except Exception as e:
        return (func_num, run, np.inf, 0, str(e))
    return (func_num, run, float(bf), int(ne), None)


def main():
    tasks = [(f, r) for f in range(1, NFUNCS + 1) for r in range(NRUNS)]
    print(f"Running {len(tasks)} RCMAES runs (D={D}, Nmax={NMAX}, {NRUNS} runs x {NFUNCS} funcs) ...")
    t0 = time.time()
    # build problem objects once to warm C data load per func in main process (not required)
    nproc = min(64, os.cpu_count() or 8)
    with Pool(processes=nproc) as pool:
        results = []
        for i, res in enumerate(pool.imap_unordered(_worker, tasks, chunksize=4)):
            results.append(res)
            if (i + 1) % 50 == 0 or (i + 1) == len(tasks):
                print(f"  {i+1}/{len(tasks)} done ({time.time()-t0:.1f}s)")
    dt = time.time() - t0
    print(f"All runs finished in {dt:.1f}s")

    # assemble (NFUNCS, NRUNS) matrix of best fitness
    best = np.full((NFUNCS, NRUNS), np.nan)
    nevals = np.full((NFUNCS, NRUNS), np.nan)
    for func_num, run, bf, ne, err in results:
        best[func_num - 1, run] = bf
        nevals[func_num - 1, run] = ne
        if err:
            print(f"  ERROR func {func_num} run {run}: {err}")

    np.savez("rcmaes_results.npz", best=best, nevals=nevals,
             optima=np.array([cec22.OPTIMA[f] for f in range(1, NFUNCS + 1)]))
    print("Saved rcmaes_results.npz")
    # quick summary
    optima = np.array([cec22.OPTIMA[f] for f in range(1, NFUNCS + 1)])
    relerr = (best - optima[:, None]) / optima[:, None]
    eps = relerr.mean(axis=1)
    E_j = eps / (1.0 + eps)
    E = E_j.mean()
    print(f"\nRCMAES accuracy metric E (D=20) = {E:.4f}")
    for f in range(NFUNCS):
        print(f"  F{f+1:2d}: mean err={best[f].mean()-optima[f]:.4g}  relerr={eps[f]:.3e}  E_j={E_j[f]:.4f}  f*={optima[f]}")


if __name__ == "__main__":
    main()
