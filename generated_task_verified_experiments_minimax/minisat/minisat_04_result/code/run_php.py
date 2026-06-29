"""Pigeonhole Principle (PHP_n) hard-case experiment for MiniSAT.

Encoding (standard):
  Variables x_{i,j}: pigeon i is in hole j.
  Number of pigeons = n+1, number of holes = n.

  Clauses:
    (a) "Each pigeon must go into at least one hole" (positive clause):
        For each pigeon i: (x_{i,1} ∨ x_{i,2} ∨ ... ∨ x_{i,n})
    (b) "Each hole holds at most one pigeon" (pairwise mutual exclusion):
        For each hole j, for each pair i<k: (¬x_{i,j} ∨ ¬x_{k,j})

The CNF is unsatisfiable for every n ≥ 1.
"""
import time
import signal
from pysat.solvers import Minisat22


def build_php(n: int):
    """Build PHP_n: n+1 pigeons into n holes.

    Returns (clauses, nvars).
    Variable numbering in PySAT starts at 1.
    Variable id (i, j) -> (i-1) * n + j, where i in [1, n+1], j in [1, n].
    """
    n_pigeons = n + 1
    n_holes = n

    def var_id(i, j):
        # i in [1, n_pigeons], j in [1, n_holes]
        return (i - 1) * n_holes + j

    clauses = []

    # (a) Each pigeon must be in at least one hole (positive clause of length n)
    for i in range(1, n_pigeons + 1):
        clause = [var_id(i, j) for j in range(1, n_holes + 1)]
        clauses.append(clause)

    # (b) Each hole has at most one pigeon (pairwise mutual exclusion)
    for j in range(1, n_holes + 1):
        for i in range(1, n_pigeons + 1):
            for k in range(i + 1, n_pigeons + 1):
                clause = [-var_id(i, j), -var_id(k, j)]
                clauses.append(clause)

    nvars = n_pigeons * n_holes
    return clauses, nvars


def measure_conflicts(n: int, timeout_s: float = 240.0):
    """Run MiniSAT on PHP_n and measure conflicts + wall time.

    Returns dict with:
      n, nvars, nclauses, time_s, conflicts, status, timed_out
    """
    clauses, nvars = build_php(n)

    solver = Minisat22()

    # Use signal-based soft timeout that survives Python; we also rely on
    # wall-clock below.
    timed_out = {"flag": False}

    def _on_timeout(signum, frame):
        timed_out["flag"] = True
        raise TimeoutError("timeout")

    old_handler = signal.signal(signal.SIGALRM, _on_timeout)
    signal.setitimer(signal.ITIMER_REAL, timeout_s)

    t0 = time.perf_counter()
    status = None
    conflicts = None
    try:
        for cl in clauses:
            solver.add_clause(cl)
        # solve() returns True/False/None (None = undecided / interrupted)
        result = solver.solve()
        t1 = time.perf_counter()
        status = "SAT" if result is True else ("UNSAT" if result is False else "UNKNOWN")
        # PySAT exposes solver stats via accum_stats()
        stats = solver.accum_stats() if hasattr(solver, "accum_stats") else {}
        conflicts = int(stats.get("conflicts", 0)) if stats else None
        decisions = int(stats.get("decisions", 0)) if stats else None
        propagations = int(stats.get("propagations", 0)) if stats else None
        restarts = int(stats.get("restarts", 0)) if stats else None
    except TimeoutError:
        t1 = time.perf_counter()
        status = "TIMEOUT"
        try:
            stats = solver.accum_stats() if hasattr(solver, "accum_stats") else {}
            conflicts = int(stats.get("conflicts", 0)) if stats else None
            decisions = int(stats.get("decisions", 0)) if stats else None
            propagations = int(stats.get("propagations", 0)) if stats else None
            restarts = int(stats.get("restarts", 0)) if stats else None
        except Exception:
            conflicts = decisions = propagations = restarts = None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        solver.delete()

    return {
        "n": n,
        "nvars": nvars,
        "nclauses": len(clauses),
        "time_s": t1 - t0,
        "conflicts": conflicts,
        "decisions": decisions,
        "propagations": propagations,
        "restarts": restarts,
        "status": status,
        "timed_out": timed_out["flag"],
    }


def main():
    results = []
    # Per task: n in {3, 4, 5, 6, 7}; may be slow near n=7
    for n in [3, 4, 5, 6, 7]:
        # Per-instance timeout so total stays well under 30 min
        per_timeout = 480.0 if n <= 6 else 900.0
        r = measure_conflicts(n, timeout_s=per_timeout)
        results.append(r)
        print(
            f"n={n}: status={r['status']} time={r['time_s']:.4f}s "
            f"conflicts={r['conflicts']} decisions={r['decisions']} "
            f"propagations={r['propagations']} restarts={r['restarts']} "
            f"nvars={r['nvars']} nclauses={r['nclauses']} "
            f"timed_out={r['timed_out']}"
        )

    # Save a JSON for reference
    import json
    with open("php_results.json", "w") as f:
        json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    main()
