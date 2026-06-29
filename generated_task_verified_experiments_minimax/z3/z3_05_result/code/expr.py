"""
Compare Z3 satisfaction solving vs optimization solving on a small
job-shop scheduling problem with integer variables and linear constraints.

Fixed problem instance (same across runs):
  - 5 jobs, 3 machines, 3 operations per job.
  - Each operation (j, k) has fixed machine routing and duration.
  - Operations must respect job precedence and machine no-overlap.
  - All start times are non-negative integers.

Independent variable: solver mode (sat vs optimize).

Metrics:
  - wall-clock seconds for each solver invocation,
  - feasibility status (sat/unsat),
  - feasible / optimal objective value (makespan),
  - the variable assignment.

Run several repeats to get a stable estimate.
"""
from __future__ import annotations

import json
import time
import statistics
from itertools import combinations
from z3 import (
    Solver,
    Optimize,
    Int,
    sat,
    And,
    Or,
    If,
    Implies,
    Not,
    PbEq,
)


# --------------------------------------------------------------------------- #
# Fixed problem instance                                                       #
# --------------------------------------------------------------------------- #

# job -> ordered list of (machine, duration) operations.
JOBS: dict[int, list[tuple[int, int]]] = {
    1: [(1, 2), (2, 3), (3, 1)],
    2: [(2, 1), (3, 2), (1, 3)],
    3: [(3, 3), (1, 2), (2, 2)],
    4: [(1, 1), (3, 2), (2, 3)],
    5: [(2, 2), (1, 1), (3, 2)],
}

NUM_JOBS = len(JOBS)  # 5
MACHINES = [1, 2, 3]
HORIZON = 30  # an a-priori upper bound on any makespan


# --------------------------------------------------------------------------- #
# Build model                                                                 #
# --------------------------------------------------------------------------- #

def build():
    """Return (start_vars, makespan_var) for the fixed instance.

    start_vars[(j, k)] is the integer start time of the k-th operation
    of job j (k = 0,1,2). makespan_var is an integer upper bound on the
    completion time of every operation.
    """
    start_vars: dict[tuple[int, int], object] = {}
    completion_vars: list[object] = []

    # Create a start variable for each (job, operation_index).
    for j, ops in JOBS.items():
        for k, (machine, duration) in enumerate(ops):
            v = Int(f"s_{j}_{k}")
            start_vars[(j, k)] = v
            completion_vars.append(v + duration)

    # Makespan = max completion time.
    makespan = Int("makespan")
    return start_vars, completion_vars, makespan


def add_core_constraints(solver, start_vars, completion_vars, makespan):
    """Add the job-shop constraints that BOTH the sat and optimize
    solver must respect."""
    # Non-negative start times.
    for v in start_vars.values():
        solver.add(v >= 0)

    # Upper bound on makespan.
    for c in completion_vars:
        solver.add(c <= makespan)
    solver.add(makespan >= 0)
    solver.add(makespan <= HORIZON)

    # Job precedence.
    for j, ops in JOBS.items():
        for k in range(len(ops) - 1):
            _, d_k = ops[k]
            solver.add(start_vars[(j, k + 1)] >= start_vars[(j, k)] + d_k)

    # Machine no-overlap via pairwise disjunctions.
    # Group all operations by machine.
    ops_by_machine: dict[int, list[tuple[int, int]]] = {m: [] for m in MACHINES}
    for j, ops in JOBS.items():
        for k, (machine, duration) in enumerate(ops):
            ops_by_machine[machine].append((j, k, duration))

    for m, items in ops_by_machine.items():
        for (j1, k1, d1), (j2, k2, d2) in combinations(items, 2):
            a = start_vars[(j1, k1)]
            b = start_vars[(j2, k2)]
            # Either a finishes before b starts, or b finishes before a starts.
            solver.add(Or(a + d1 <= b, b + d2 <= a))


# --------------------------------------------------------------------------- #
# Mode A: just find a feasible solution (sat).                                #
# --------------------------------------------------------------------------- #

def run_sat_mode(start_vars, completion_vars, makespan):
    """Return dict with status, makespan value, timing, and assignment."""
    s = Solver()
    add_core_constraints(s, start_vars, completion_vars, makespan)

    t0 = time.perf_counter()
    res = s.check()
    elapsed = time.perf_counter() - t0

    out: dict = {"status": str(res), "elapsed_sec": elapsed}
    if res == sat:
        model = s.model()
        out["makespan"] = int(model.eval(makespan).as_long())
        out["assignment"] = {
            f"s_{j}_{k}": int(model.eval(v).as_long())
            for (j, k), v in start_vars.items()
        }
    return out


# --------------------------------------------------------------------------- #
# Mode B: optimize — minimize makespan.                                       #
# --------------------------------------------------------------------------- #

def run_optimize_mode(start_vars, completion_vars, makespan):
    opt = Optimize()
    add_core_constraints(opt, start_vars, completion_vars, makespan)
    opt.minimize(makespan)

    t0 = time.perf_counter()
    res = opt.check()
    elapsed = time.perf_counter() - t0

    out: dict = {"status": str(res), "elapsed_sec": elapsed}
    if res == sat:
        model = opt.model()
        out["makespan"] = int(model.eval(makespan).as_long())
        out["assignment"] = {
            f"s_{j}_{k}": int(model.eval(v).as_long())
            for (j, k), v in start_vars.items()
        }
    return out


# --------------------------------------------------------------------------- #
# Driver                                                                      #
# --------------------------------------------------------------------------- #

def main(repeats: int = 5):
    # Warm up the import / library once.
    start_vars, completion_vars, makespan = build()

    sat_results = []
    opt_results = []
    for _ in range(repeats):
        sat_results.append(run_sat_mode(start_vars, completion_vars, makespan))
        opt_results.append(run_optimize_mode(start_vars, completion_vars, makespan))

    summary = {
        "problem": {
            "jobs": NUM_JOBS,
            "machines": MACHINES,
            "operations_per_job": 3,
            "horizon_upper_bound": HORIZON,
            "routing": {f"J{j}": JOBS[j] for j in JOBS},
        },
        "sat_mode": {
            "runs": sat_results,
            "mean_elapsed_sec": statistics.mean(r["elapsed_sec"] for r in sat_results),
            "min_elapsed_sec": min(r["elapsed_sec"] for r in sat_results),
            "median_elapsed_sec": statistics.median(r["elapsed_sec"] for r in sat_results),
            "objective_values": [r["makespan"] for r in sat_results],
            "first_objective": sat_results[0]["makespan"],
            "first_assignment": sat_results[0]["assignment"],
        },
        "optimize_mode": {
            "runs": opt_results,
            "mean_elapsed_sec": statistics.mean(r["elapsed_sec"] for r in opt_results),
            "min_elapsed_sec": min(r["elapsed_sec"] for r in opt_results),
            "median_elapsed_sec": statistics.median(r["elapsed_sec"] for r in opt_results),
            "optimal_makespan": opt_results[0]["makespan"],
            "optimal_assignment": opt_results[0]["assignment"],
        },
        "repeats": repeats,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    with open("/data/workspace/admin/happy_lake/.verify_judge_minimax/z3/z3_05/results.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main(repeats=5)