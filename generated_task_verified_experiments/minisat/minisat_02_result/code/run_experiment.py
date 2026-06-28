#!/usr/bin/env python3
"""Random 3-SAT phase-transition experiment with PySAT MiniSAT.

Fixed: n=50 variables, seeds 0..14, solver Minisat22.
Independent variable: clause/variable ratio alpha.
Measured: conflicts, solve time, SAT fraction.
"""
import random
import json
import time
from pysat.solvers import Solver

N = 50
ALPHAS = [3.0, 3.5, 4.0, 4.267, 4.5, 5.0, 6.0]
SEEDS = list(range(15))  # 0..14


def gen_instance(n, m, seed):
    """Generate a random 3-SAT instance with n vars, m clauses.

    Each clause: 3 distinct variables, each literal sign chosen uniformly at random.
    Returns a list of clauses (each a list of 3 nonzero ints)."""
    rng = random.Random(seed)
    clauses = []
    for _ in range(m):
        vars_sel = rng.sample(range(1, n + 1), 3)
        clause = []
        for v in vars_sel:
            sign = 1 if rng.random() < 0.5 else -1
            clause.append(sign * v)
        clauses.append(clause)
    return clauses


def solve_instance(clauses):
    """Solve with Minisat22, return (sat, conflicts, internal_time, wall_time)."""
    t0 = time.perf_counter()
    with Solver(name='Minisat22', bootstrap_with=clauses, use_timer=True) as s:
        sat = s.solve()
        stats = s.accum_stats()
        conflicts = stats.get('conflicts', 0)
        t_internal = s.time()
    t_wall = time.perf_counter() - t0
    return sat, conflicts, t_internal, t_wall


def main():
    results = {}
    for alpha in ALPHAS:
        m = round(alpha * N)
        per = []
        for seed in SEEDS:
            clauses = gen_instance(N, m, seed)
            sat, conflicts, t_internal, t_wall = solve_instance(clauses)
            per.append({
                'alpha': alpha,
                'm': m,
                'seed': seed,
                'sat': bool(sat),
                'conflicts': conflicts,
                'time_internal': t_internal,
                'time_wall': t_wall,
            })
        results[alpha] = per
        sat_count = sum(1 for r in per if r['sat'])
        avg_conf = sum(r['conflicts'] for r in per) / len(per)
        avg_time_i = sum(r['time_internal'] for r in per) / len(per)
        avg_time_w = sum(r['time_wall'] for r in per) / len(per)
        print(f"alpha={alpha:.3f} m={m} sat={sat_count}/{len(per)} "
              f"avg_conf={avg_conf:.1f} avg_time(int)={avg_time_i:.6f}s "
              f"avg_time(wall)={avg_time_w:.6f}s")

    with open('results.json', 'w') as f:
        json.dump({'n': N, 'alphas': ALPHAS, 'seeds': SEEDS, 'results': {str(k): v for k, v in results.items()}}, f, indent=2)
    print("Saved results.json")


if __name__ == '__main__':
    main()
