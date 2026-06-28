"""Run BIPOP-aCMAES on CEC2022 D=20 (51 runs x 12 funcs), then compare to the
already-saved RCMAES results: accuracy E, Friedman rank, W/T/L (Mann-Whitney U).
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from multiprocessing import Pool
import cec22
from bipop import bipop_minimize

D, NMAX, NRUNS, NFUNCS = 20, 200000, 51, 12


def _worker(args):
    func_num, run = args
    try:
        bx, bf, ne = bipop_minimize(lambda X: cec22.evaluate_batch(X, func_num), D, NMAX, seed=run)
    except Exception as e:
        return (func_num, run, np.inf, 0, str(e))
    return (func_num, run, float(bf), int(ne), None)


def accuracy_E(best, optima):
    relerr = (best - optima[:, None]) / optima[:, None]
    eps = relerr.mean(axis=1)
    Ej = eps / (1.0 + eps)
    return Ej.mean(), Ej, eps


def friedman_rank_2(best_a, best_b):
    """Mean Friedman rank over all (func, run); lower=better. Ties -> 1.5/1.5."""
    a = best_a; b = best_b
    ra = np.where(a < b, 1.0, np.where(a > b, 2.0, 1.5))
    rb = 3.0 - ra
    return ra.mean(), rb.mean()


def main():
    # ---- run BIPOP ----
    tasks = [(f, r) for f in range(1, NFUNCS + 1) for r in range(NRUNS)]
    print(f"Running {len(tasks)} BIPOP runs ...")
    t0 = time.time()
    nproc = min(64, os.cpu_count() or 8)
    with Pool(processes=nproc) as pool:
        results = []
        for i, res in enumerate(pool.imap_unordered(_worker, tasks, chunksize=4)):
            results.append(res)
            if (i + 1) % 100 == 0 or (i + 1) == len(tasks):
                print(f"  {i+1}/{len(tasks)} ({time.time()-t0:.1f}s)")
    print(f"BIPOP done in {time.time()-t0:.1f}s")

    bipop_best = np.full((NFUNCS, NRUNS), np.nan)
    for func_num, run, bf, ne, err in results:
        bipop_best[func_num - 1, run] = bf
        if err:
            print(f"  ERROR func {func_num} run {run}: {err}")
    np.savez("bipop_results.npz", best=bipop_best)

    # ---- load RCMAES ----
    rc = np.load("rcmaes_results.npz")
    rcmaes_best = rc["best"]
    optima = np.array([cec22.OPTIMA[f] for f in range(1, NFUNCS + 1)])

    E_rc, Ej_rc, eps_rc = accuracy_E(rcmaes_best, optima)
    E_bp, Ej_bp, eps_bp = accuracy_E(bipop_best, optima)
    R_rc, R_bp = friedman_rank_2(rcmaes_best, bipop_best)

    # ---- W/T/L via Mann-Whitney U (RCMAES vs BIPOP), per function ----
    try:
        from scipy.stats import mannwhitneyu
        W = T = L = 0
        sig_info = []
        for f in range(NFUNCS):
            a = rcmaes_best[f]; b = bipop_best[f]
            stat, p = mannwhitneyu(a, b, alternative="less")
            if p < 0.05:
                W += 1; res = "W"
            else:
                # check reverse
                stat2, p2 = mannwhitneyu(b, a, alternative="less")
                if p2 < 0.05:
                    L += 1; res = "L"
                else:
                    T += 1; res = "T"
            sig_info.append((f + 1, p, res))
        scipy_ok = True
    except Exception as e:
        W = T = L = -1; sig_info = []; scipy_ok = False
        print(f"[scipy unavailable: {e}]")

    print("\n================ CEC2022 D=20: RCMAES vs BIPOP-aCMAES ================")
    print(f"{'Fn':>3} {'f*':>7} {'RCMAES err':>12} {'BIPOP err':>12} {'RC relerr':>10} {'BP relerr':>10} {'sig':>4}")
    for f in range(NFUNCS):
        sig = sig_info[f][2] if sig_info else "-"
        print(f"{f+1:>3} {optima[f]:>7.0f} {rcmaes_best[f].mean()-optima[f]:>12.4g} "
              f"{bipop_best[f].mean()-optima[f]:>12.4g} {eps_rc[f]:>10.3e} {eps_bp[f]:>10.3e} {sig:>4}")
    print("---------------------------------------------------------------------")
    print(f"Accuracy E   : RCMAES = {E_rc:.4f}   BIPOP = {E_bp:.4f}")
    print(f"Friedman R   : RCMAES = {R_rc:.3f}   BIPOP = {R_bp:.3f}  (lower better)")
    print(f"W/T/L (RCMAES vs BIPOP, Mann-Whitney a=0.05): {W}/{T}/{L}")

    np.savez("comparison_summary.npz", E_rc=E_rc, E_bp=E_bp, R_rc=R_rc, R_bp=R_bp,
             W=W, T=T, L=L, eps_rc=eps_rc, eps_bp=eps_bp,
             rcmaes_best=rcmaes_best, bipop_best=bipop_best, optima=optima)


if __name__ == "__main__":
    main()
