"""
Random 3-SAT phase transition experiment.

- Fix n = 50 variables.
- Sweep alpha = m/n in {3.0, 3.5, 4.0, 4.267, 4.5, 5.0, 6.0}.
- For each alpha, generate 15 random 3-SAT instances (seeds 0..14) in DIMACS CNF.
- Solve each instance with PySAT's Minisat22 solver.
- Record conflicts and wall-clock solve time.
- Compute per-alpha average conflicts, average time, and SAT ratio.
"""

import os
import time
import random
from pysat.solvers import Solver

N_VARS = 50
ALPHAS = [3.0, 3.5, 4.0, 4.267, 4.5, 5.0, 6.0]
N_SEEDS = 15
SEEDS = list(range(N_SEEDS))  # 0..14

OUT_DIR = "/data/workspace/admin/happy_lake/.verify_judge_minimax/minisat/minisat_02"
CNF_DIR = os.path.join(OUT_DIR, "cnf")
os.makedirs(CNF_DIR, exist_ok=True)


def gen_random_3sat(n_vars: int, m_clauses: int, seed: int) -> list[list[int]]:
    """Generate a random 3-CNF formula with `m_clauses` clauses of length 3."""
    rng = random.Random(seed)
    formula = []
    for _ in range(m_clauses):
        # sample 3 distinct variables, then random sign for each
        vars_ = rng.sample(range(1, n_vars + 1), 3)
        clause = [v if rng.random() < 0.5 else -v for v in vars_]
        formula.append(clause)
    return formula


def to_dimacs(formula: list[list[int]], n_vars: int) -> str:
    lines = [f"p cnf {n_vars} {len(formula)}"]
    for cl in formula:
        lines.append(" ".join(str(l) for l in cl) + " 0")
    return "\n".join(lines) + "\n"


def solve_instance(formula: list[list[int]], n_vars: int) -> dict:
    """Solve the formula with Minisat22; return stats dict."""
    with Solver(name="Minisat22", bootstrap_with=formula) as s:
        t0 = time.perf_counter()
        sat = s.solve()
        t1 = time.perf_counter()
        stats = s.accum_stats()
    return {
        "sat": bool(sat),
        "conflicts": int(stats.get("conflicts", 0)),
        "decisions": int(stats.get("decisions", 0)),
        "propagations": int(stats.get("propagations", 0)),
        "restarts": int(stats.get("restarts", 0)),
        "time_sec": t1 - t0,
        "solver_time": s.time(),
    }


def main():
    results = []
    for alpha in ALPHAS:
        m = int(round(alpha * N_VARS))
        per_alpha = []
        for seed in SEEDS:
            formula = gen_random_3sat(N_VARS, m, seed)
            # write the DIMACS file for reproducibility
            cnf_path = os.path.join(CNF_DIR, f"n{N_VARS}_a{alpha:.3f}_s{seed}.cnf")
            with open(cnf_path, "w") as f:
                f.write(to_dimacs(formula, N_VARS))
            res = solve_instance(formula, N_VARS)
            res.update({"alpha": alpha, "n": N_VARS, "m": m, "seed": seed})
            per_alpha.append(res)
            print(
                f"alpha={alpha:6.3f} m={m:4d} seed={seed:2d} "
                f"SAT={'T' if res['sat'] else 'F'} "
                f"conflicts={res['conflicts']:>8d} "
                f"propagations={res['propagations']:>10d} "
                f"time={res['time_sec']*1000:8.3f} ms"
            )
        # aggregates
        n_sat = sum(1 for r in per_alpha if r["sat"])
        avg_conf = sum(r["conflicts"] for r in per_alpha) / len(per_alpha)
        avg_time = sum(r["time_sec"] for r in per_alpha) / len(per_alpha)
        med_conf = sorted(r["conflicts"] for r in per_alpha)[len(per_alpha) // 2]
        med_time = sorted(r["time_sec"] for r in per_alpha)[len(per_alpha) // 2]
        max_conf = max(r["conflicts"] for r in per_alpha)
        max_time = max(r["time_sec"] for r in per_alpha)
        agg = {
            "alpha": alpha,
            "m": m,
            "n_sat": n_sat,
            "sat_ratio": n_sat / len(per_alpha),
            "avg_conflicts": avg_conf,
            "avg_time_sec": avg_time,
            "median_conflicts": med_conf,
            "median_time_sec": med_time,
            "max_conflicts": max_conf,
            "max_time_sec": max_time,
        }
        results.append({"per_instance": per_alpha, "aggregate": agg})
        print(
            f"  >> alpha={alpha:.3f}: SAT {n_sat}/{N_SEEDS} "
            f"avg_conf={avg_conf:.1f} avg_time={avg_time*1000:.3f}ms "
            f"med_conf={med_conf} med_time={med_time*1000:.3f}ms "
            f"max_conf={max_conf} max_time={max_time*1000:.3f}ms"
        )

    # save raw results
    import json
    with open(os.path.join(OUT_DIR, "results.json"), "w") as f:
        json.dump(results, f, indent=2)
    print("\nWrote", os.path.join(OUT_DIR, "results.json"))


if __name__ == "__main__":
    main()
