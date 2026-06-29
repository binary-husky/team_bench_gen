"""
NSGA-II benchmark on ZDT1, ZDT2, ZDT3, ZDT6.
Fixed configuration per task spec, 31 independent runs each.
"""

import os
import time
import pickle
import numpy as np

from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.sampling.rnd import FloatRandomSampling
from pymoo.optimize import minimize
from pymoo.problems import get_problem
from pymoo.indicators.igd import IGD
from pymoo.indicators.hv import HV


OUT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_PATH = os.path.join(OUT_DIR, "benchmark_results.pkl")
SEED_BASE = 12345

# (problem_name, n_var, n_gen)
PROBLEMS = [
    ("ZDT1", 30, 250),
    ("ZDT2", 30, 250),
    ("ZDT3", 30, 250),
    ("ZDT6", 10, 250),
]

N_RUNS = 31
POP_SIZE = 100


def run_one(problem_name, n_var, n_gen, seed):
    problem = get_problem(problem_name, n_var=n_var)
    pf = problem.pareto_front()

    algorithm = NSGA2(
        pop_size=POP_SIZE,
        sampling=FloatRandomSampling(),
        crossover=SBX(eta=20, prob=0.9),
        mutation=PM(eta=20, prob=1.0 / n_var),
        eliminate_duplicates=True,
    )

    res = minimize(
        problem,
        algorithm,
        ("n_gen", n_gen),
        seed=seed,
        verbose=False,
    )

    F = res.F
    return {
        "F": np.asarray(F),
        "X": np.asarray(res.X) if res.X is not None else None,
        "n_eval": int(res.algorithm.evaluator.n_eval) if hasattr(res.algorithm.evaluator, "n_eval") else None,
    }


def compute_igd_hv(problem_name, F):
    problem = get_problem(problem_name)
    pf = problem.pareto_front()
    # Filter to non-dominated points among F
    F = np.asarray(F)
    if F.ndim != 2 or F.shape[0] == 0:
        return np.nan, np.nan
    igd_val = IGD(pf)(F)

    # Use the canonical reference point for each problem.
    if problem_name in ("ZDT1", "ZDT2"):
        ref = np.array([1.1, 1.1])
    elif problem_name == "ZDT3":
        ref = np.array([1.1, 1.1])
    elif problem_name == "ZDT6":
        # f1 in roughly [0.28, 1.0]; f2 in roughly [0, 1]
        ref = np.array([1.1, 1.1])
    else:
        ref = np.array([1.1, 1.1])
    hv_val = HV(ref_point=ref)(F)
    return float(igd_val), float(hv_val)


def main():
    overall_start = time.time()
    all_results = {}
    for problem_name, n_var, n_gen in PROBLEMS:
        print(f"\n=== {problem_name} (n_var={n_var}, n_gen={n_gen}) ===")
        per_problem = []
        for run_idx in range(N_RUNS):
            seed = SEED_BASE + run_idx
            t0 = time.time()
            res = run_one(problem_name, n_var, n_gen, seed)
            igd, hv = compute_igd_hv(problem_name, res["F"])
            dt = time.time() - t0
            per_problem.append({
                "run": run_idx,
                "seed": seed,
                "F": res["F"],
                "X": res["X"],
                "igd": igd,
                "hv": hv,
                "time_s": dt,
            })
            print(f"  run {run_idx:02d} seed={seed} IGD={igd:.4f} HV={hv:.4f} ({dt:.1f}s)")
        all_results[problem_name] = per_problem
        elapsed = time.time() - overall_start
        print(f"  ... cumulative elapsed: {elapsed:.1f}s")

    with open(RESULTS_PATH, "wb") as f:
        pickle.dump(all_results, f)
    print(f"\nSaved results to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
