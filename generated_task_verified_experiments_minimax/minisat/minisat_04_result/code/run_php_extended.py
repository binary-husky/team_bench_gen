"""Extended PHP_n experiment: more values of n, with repeated measurements
to reduce timing noise."""
import time
import signal
import json
import statistics
from pysat.solvers import Minisat22
from run_php import build_php


def measure_once(n: int, timeout_s: float = 240.0):
    """Run MiniSAT on PHP_n once. Returns dict."""
    clauses, nvars = build_php(n)
    solver = Minisat22()

    timed_out = {"flag": False}

    def _on_timeout(signum, frame):
        timed_out["flag"] = True
        raise TimeoutError("timeout")

    old_handler = signal.signal(signal.SIGALRM, _on_timeout)
    signal.setitimer(signal.ITIMER_REAL, timeout_s)
    t0 = time.perf_counter()
    status = None
    stats = {}
    try:
        for cl in clauses:
            solver.add_clause(cl)
        result = solver.solve()
        t1 = time.perf_counter()
        status = "SAT" if result is True else ("UNSAT" if result is False else "UNKNOWN")
        stats = solver.accum_stats() if hasattr(solver, "accum_stats") else {}
    except TimeoutError:
        t1 = time.perf_counter()
        status = "TIMEOUT"
        try:
            stats = solver.accum_stats() if hasattr(solver, "accum_stats") else {}
        except Exception:
            stats = {}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        solver.delete()

    return {
        "n": n,
        "nvars": nvars,
        "nclauses": len(clauses),
        "time_s": t1 - t0,
        "conflicts": int(stats.get("conflicts", 0)) if stats else None,
        "decisions": int(stats.get("decisions", 0)) if stats else None,
        "propagations": int(stats.get("propagations", 0)) if stats else None,
        "restarts": int(stats.get("restarts", 0)) if stats else None,
        "status": status,
        "timed_out": timed_out["flag"],
    }


def measure_repeated(n: int, repeats: int, timeout_s: float):
    rows = []
    for _ in range(repeats):
        rows.append(measure_once(n, timeout_s=timeout_s))
        if rows[-1]["status"] != "UNSAT":
            break
    times = [r["time_s"] for r in rows if r["status"] == "UNSAT"]
    return {
        "n": n,
        "nvars": rows[0]["nvars"],
        "nclauses": rows[0]["nclauses"],
        "conflicts": rows[0]["conflicts"],
        "decisions": rows[0]["decisions"],
        "propagations": rows[0]["propagations"],
        "restarts": rows[0]["restarts"],
        "time_min_s": min(times) if times else None,
        "time_max_s": max(times) if times else None,
        "time_median_s": statistics.median(times) if times else None,
        "repeats_done": len(times),
        "status": rows[0]["status"],
    }


def main():
    # Required range: 3..7. Plus extend to 8..10 to characterise growth
    # before it gets too slow. Cap per-instance timeout so the full script
    # stays well under 30 min.
    plan = [
        (3, 11, 60.0),
        (4, 11, 60.0),
        (5, 11, 120.0),
        (6, 7, 240.0),
        (7, 5, 480.0),
        (8, 3, 900.0),
        (9, 3, 1200.0),
    ]
    summary = []
    for n, reps, to in plan:
        r = measure_repeated(n, reps, timeout_s=to)
        summary.append(r)
        print(
            f"n={n}: status={r['status']} "
            f"conflicts={r['conflicts']} decisions={r['decisions']} "
            f"propagations={r['propagations']} restarts={r['restarts']} "
            f"t_min={r['time_min_s']:.5f}s t_med={r['time_median_s']:.5f}s "
            f"t_max={r['time_max_s']:.5f}s (reps={r['repeats_done']}) "
            f"nvars={r['nvars']} nclauses={r['nclauses']}"
        )
    with open("php_results_extended.json", "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
