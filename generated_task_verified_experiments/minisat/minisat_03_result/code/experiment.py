#!/usr/bin/env python3
"""
Experiment: CDCL (MiniSAT) vs naive DPLL (no learning) on random 3-SAT.

Naive DPLL: unit propagation + chronological backtracking, static variable
ordering (lowest-index first), try polarity + then -, NO clause learning,
NO VSIDS, NO restarts. Decisions = number of branching guesses (one per
polarity attempt).

MiniSAT (CDCL) via PySAT (minisat22): records conflicts, decisions,
propagations, restarts and wall time. 60s per-instance timeout.
"""
import os, sys, time, json, threading, random

sys.setrecursionlimit(100000)

HERE = os.path.dirname(os.path.abspath(__file__))
INST_DIR = os.path.join(HERE, "instances")
os.makedirs(INST_DIR, exist_ok=True)

ALPHA = 4.2
NS = [15, 20, 25]
SEEDS = [0, 1, 2, 3, 4]
TIMEOUT = 60.0


# ---------------- instance generation ----------------
def gen_instance(n, m, seed):
    rng = random.Random(seed)
    clauses = []
    seen = set()
    while len(clauses) < m:
        vars_ = rng.sample(range(1, n + 1), 3)
        lits = [v if rng.random() < 0.5 else -v for v in vars_]
        key = tuple(sorted(lits))
        if key in seen:
            continue
        seen.add(key)
        clauses.append(lits)
    return clauses


def write_dimacs(path, n, clauses):
    with open(path, "w") as f:
        f.write(f"p cnf {n} {len(clauses)}\n")
        for c in clauses:
            f.write(" ".join(str(l) for l in c) + " 0\n")


# ---------------- naive DPLL ----------------
def naive_dpll(n, clauses, deadline):
    """Return dict: sat(bool), decisions(int), timed_out(bool), time(float)."""
    assign = [0] * (n + 1)  # 0 unassigned, 1 true, -1 false
    trail = []
    decisions = [0]
    timeouts = [False]

    # precompute clause tuples for speed
    Claus = [tuple(c) for c in clauses]

    def undo_to(mark):
        for i in range(len(trail) - 1, mark - 1, -1):
            v = trail[i]
            assign[v] = 0
        del trail[mark:]

    def propagate():
        """Unit propagation. Appends forced vars to trail. False on conflict."""
        changed = True
        while changed:
            changed = False
            for c in Claus:
                sat = False
                un_count = 0
                un_lit = 0
                for lit in c:
                    v = abs(lit)
                    av = assign[v]
                    if av == 0:
                        un_count += 1
                        un_lit = lit
                        if un_count > 1:
                            break
                    else:
                        val = 1 if av > 0 else -1
                        if (lit > 0 and val == 1) or (lit < 0 and val == -1):
                            sat = True
                            break
                if sat:
                    continue
                if un_count == 0:
                    return False  # conflict: all assigned, none true
                if un_count == 1:
                    v = abs(un_lit)
                    assign[v] = 1 if un_lit > 0 else -1
                    trail.append(v)
                    changed = True
        return True

    def next_unassigned():
        for v in range(1, n + 1):
            if assign[v] == 0:
                return v
        return None

    def check_time():
        if time.time() > deadline:
            timeouts[0] = True
            return True
        return False

    def solve():
        if check_time():
            return False
        mark = len(trail)
        if not propagate():
            undo_to(mark)
            return False
        var = next_unassigned()
        if var is None:
            return True  # SAT
        for val in (1, -1):
            decisions[0] += 1
            assign[var] = val
            trail.append(var)
            if solve():
                return True
            if timeouts[0]:
                assign[var] = 0
                trail.pop()
                return False
            # child undid its propagation back to just-after var; reset var
            assign[var] = 0
            trail.pop()
        undo_to(mark)
        return False

    t0 = time.time()
    try:
        sat = solve()
    except RecursionError:
        sat = False
        timeouts[0] = True
    dt = time.time() - t0
    if timeouts[0]:
        return {"sat": None, "decisions": decisions[0], "timed_out": True,
                "time": dt}
    return {"sat": bool(sat), "decisions": decisions[0],
            "timed_out": False, "time": dt}


# ---------------- MiniSAT (CDCL) ----------------
def minisat_solve(n, clauses):
    from pysat.solvers import Solver
    s = Solver(name="minisat22", bootstrap_with=clauses, use_timer=True)
    done = threading.Event()

    def watchdog():
        if not done.wait(TIMEOUT):
            s.interrupt()

    th = threading.Thread(target=watchdog, daemon=True)
    th.start()
    t0 = time.time()
    try:
        res = s.solve()
    finally:
        done.set()
    dt = time.time() - t0
    th.join(2.0)
    stats = s.accum_stats()
    status = s.get_status()
    s.delete()
    # status: None=unknown(interrupted), True/False
    if status is None:
        return {"sat": None, "conflicts": stats.get("conflicts", 0),
                "decisions": stats.get("decisions", 0),
                "propagations": stats.get("propagations", 0),
                "restarts": stats.get("restarts", 0),
                "timed_out": True, "time": dt}
    return {"sat": bool(status), "conflicts": stats.get("conflicts", 0),
            "decisions": stats.get("decisions", 0),
            "propagations": stats.get("propagations", 0),
            "restarts": stats.get("restarts", 0),
            "timed_out": False, "time": dt}


# ---------------- driver ----------------
def main():
    results = []
    for n in NS:
        m = round(ALPHA * n)
        for seed in SEEDS:
            clauses = gen_instance(n, m, seed)
            tag = f"n{n}_m{m}_s{seed}"
            dimacs = os.path.join(INST_DIR, f"{tag}.cnf")
            write_dimacs(dimacs, n, clauses)

            deadline = time.time() + TIMEOUT
            d_res = naive_dpll(n, clauses, deadline)
            m_res = minisat_solve(n, clauses)

            rec = {"tag": tag, "n": n, "m": m, "seed": seed,
                   "dpll": d_res, "minisat": m_res}
            results.append(rec)
            print(f"[{tag}] DPLL: dec={d_res['decisions']} "
                  f"t={d_res['time']:.2f}s sat={d_res['sat']} "
                  f"TO={d_res['timed_out']} | "
                  f"MiniSAT: conf={m_res['conflicts']} "
                  f"dec={m_res['decisions']} t={m_res['time']:.3f}s "
                  f"sat={m_res['sat']} TO={m_res['timed_out']}",
                  flush=True)

    with open(os.path.join(HERE, "results.json"), "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved results.json")


if __name__ == "__main__":
    main()
