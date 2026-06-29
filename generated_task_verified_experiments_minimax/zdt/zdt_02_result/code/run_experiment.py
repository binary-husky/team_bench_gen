"""
Reproduce NSGA-II baseline performance on ZDT1 and ZDT2 (n_var=30).

Fixed experimental settings (do not change):
  Algorithm: standard NSGA-II (binary tournament + rank-and-crowding + elitism)
  Population size: N = 100
  Generations: 250  ->  250 x 100 = 25000 fitness evaluations
  Crossover: SBX with distribution index eta_c = 20, probability p_c = 0.9
  Mutation:  polynomial mutation, eta_m = 20, probability p_m = 1/n_var
  Independent runs: 31, with different random seeds
  Metrics:
    - Inverted Generational Distance (IGD)  -- reference front = 1000 analytical points
    - Hypervolume (HV) -- reference point (1.1, 1.1)
    - IGD-vs-generation convergence curve (sampled every 25 generations)
"""

import os
import time
import json
import numpy as np

from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.sampling.rnd import FloatRandomSampling
from pymoo.optimize import minimize
from pymoo.core.problem import Problem
from pymoo.indicators.igd import IGD
from pymoo.indicators.hv import HV


# ---------------------------------------------------------------------------------------------------------
# ZDT1 / ZDT2 problem definitions (n_var = 30)  -- analytical formulas
# ---------------------------------------------------------------------------------------------------------
class ZDT1(Problem):
    def __init__(self, n_var=30):
        super().__init__(n_var=n_var, n_obj=2, xl=0.0, xu=1.0)

    def _evaluate(self, X, out, *args, **kwargs):
        f1 = X[:, 0]
        g = 1.0 + 9.0 / (self.n_var - 1) * np.sum(X[:, 1:], axis=1)
        f2 = g * (1.0 - np.sqrt(f1 / g))
        out["F"] = np.column_stack([f1, f2])

    def _calc_pareto_front(self, n_points=1000):
        x = np.linspace(0.0, 1.0, n_points)
        return np.array([x, 1.0 - np.sqrt(x)]).T


class ZDT2(Problem):
    def __init__(self, n_var=30):
        super().__init__(n_var=n_var, n_obj=2, xl=0.0, xu=1.0)

    def _evaluate(self, X, out, *args, **kwargs):
        f1 = X[:, 0]
        g = 1.0 + 9.0 / (self.n_var - 1) * np.sum(X[:, 1:], axis=1)
        f2 = g * (1.0 - (f1 / g) ** 2)
        out["F"] = np.column_stack([f1, f2])

    def _calc_pareto_front(self, n_points=1000):
        x = np.linspace(0.0, 1.0, n_points)
        return np.array([x, 1.0 - x ** 2]).T


# ---------------------------------------------------------------------------------------------------------
# Build an NSGA-II instance with the *exact* settings required by the task
# ---------------------------------------------------------------------------------------------------------
def make_algorithm(seed, n_var):
    return NSGA2(
        pop_size=100,
        sampling=FloatRandomSampling(),
        crossover=SBX(eta=20, prob=0.9),
        mutation=PM(eta=20, prob=1.0 / n_var),  # p_m = 1/n_var
        eliminate_duplicates=True,
    )


# ---------------------------------------------------------------------------------------------------------
# Custom driver:  drive the algorithm generation-by-generation so we can record
# the IGD every 25 generations (and at generation 250, the final value).
# ---------------------------------------------------------------------------------------------------------
def run_one(problem_cls, seed, n_gen=250, record_every=25):
    problem = problem_cls(n_var=30)
    pf_ref = problem._calc_pareto_front(n_points=1000)
    igd_metric = IGD(pf=pf_ref)

    algorithm = make_algorithm(seed, problem.n_var)
    # Seed the algorithm -- pymoo uses numpy Generator API
    algorithm.setup(problem, seed=seed)

    # Initial population is already created by setup(); evaluate and assign rank/crowding
    igd_curve = []
    while algorithm.has_next():
        algorithm.next()
        # Record IGD every `record_every` generations
        gen = algorithm.n_gen - 1  # 0-indexed last completed generation
        if (gen + 1) % record_every == 0 or gen == n_gen - 1:
            # Get the non-dominated front (rank==0) from current population
            F = algorithm.pop.get("F")
            # Use the full algorithm population for IGD (standard NSGA-II
            # reporting uses the final non-dominated front)
            nd_mask = algorithm.pop.get("rank") == 0
            F_nd = F[nd_mask]
            if len(F_nd) == 0:
                igd_val = float("nan")
            else:
                igd_val = float(igd_metric(F_nd))
            igd_curve.append({"gen": gen + 1, "igd": igd_val})

        if gen + 1 >= n_gen:
            break

    # Final result
    F_final = algorithm.pop.get("F")[algorithm.pop.get("rank") == 0]
    igd_final = float(igd_metric(F_final)) if len(F_final) > 0 else float("nan")
    hv_metric = HV(ref_point=np.array([1.1, 1.1]))
    hv_final = float(hv_metric(F_final)) if len(F_final) > 0 else float("nan")

    return {
        "seed": seed,
        "igd": igd_final,
        "hv": hv_final,
        "igd_curve": igd_curve,
    }


# ---------------------------------------------------------------------------------------------------------
# Main experiment loop
# ---------------------------------------------------------------------------------------------------------
def main():
    n_runs = 31
    seeds = list(range(1, n_runs + 1))  # seeds 1..31
    n_gen = 250
    record_every = 25

    out_dir = "/data/workspace/admin/happy_lake/.verify_judge_minimax/zdt/zdt_02"
    os.makedirs(out_dir, exist_ok=True)

    summary = {}
    for prob_name, prob_cls in [("ZDT1", ZDT1), ("ZDT2", ZDT2)]:
        print(f"\n===== {prob_name} =====")
        runs = []
        t0 = time.time()
        for i, seed in enumerate(seeds):
            t_run0 = time.time()
            r = run_one(prob_cls, seed, n_gen=n_gen, record_every=record_every)
            dt = time.time() - t_run0
            runs.append(r)
            print(
                f"  seed={seed:2d}  IGD={r['igd']:.6f}  HV={r['hv']:.6f}  ({dt:.1f}s)"
            )
        print(f"  --- {prob_name} total: {time.time() - t0:.1f}s ---")

        igds = np.array([r["igd"] for r in runs])
        hvs = np.array([r["hv"] for r in runs])

        summary[prob_name] = {
            "n_runs": n_runs,
            "seeds": seeds,
            "igd_mean": float(np.mean(igds)),
            "igd_std": float(np.std(igds, ddof=1)),
            "hv_mean": float(np.mean(hvs)),
            "hv_std": float(np.std(hvs, ddof=1)),
            "igd_runs": igds.tolist(),
            "hv_runs": hvs.tolist(),
            "igd_curves": [r["igd_curve"] for r in runs],
        }

    # Save raw results
    with open(os.path.join(out_dir, "raw_results.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("\nResults saved to raw_results.json")


if __name__ == "__main__":
    main()