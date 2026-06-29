"""
Compare naive DPLL (no learning, no VSIDS, no restarts) vs PySAT's MiniSAT (CDCL)
on small random 3-SAT instances.

Implements:
  * random_ksat(n, m, k, seed): k-SAT instance generator.
  * dpll_solve(clauses, n_vars, time_limit): naive DPLL solver with unit
    propagation and chronological backtracking. NO clause learning, NO
    VSIDS, NO restarts.
  * minisat_solve(clauses, n_vars, deadline): PySAT Minisat22 wrapper.
"""

import argparse
import csv
import os
import random
import signal
import time
from contextlib import contextmanager

from pysat.solvers import Minisat22


# ---------------------------------------------------------------------------
# Random 3-SAT generator
# ---------------------------------------------------------------------------

def random_ksat(n, m, k, seed):
    """Return (clauses, n_vars).  Each clause has k distinct, non-trivial
    literals, no duplicates, no tautologies."""
    rng = random.Random(seed)
    clauses = []
    seen = set()
    while len(clauses) < m:
        vars_ = rng.sample(range(1, n + 1), k)
        pols = [rng.choice((True, False)) for _ in range(k)]
        lits = tuple(v if p else -v for v, p in zip(vars_, pols))
        if any(-l in lits for l in lits):  # tautology
            continue
        if lits in seen:
            continue
        seen.add(lits)
        clauses.append(list(lits))
    return clauses, n


# ---------------------------------------------------------------------------
# Timeout helper
# ---------------------------------------------------------------------------

class TimeoutError(Exception):
    pass


@contextmanager
def time_limit(seconds):
    """POSIX-only deadline enforced with SIGALRM."""
    def _handler(signum, frame):
        raise TimeoutError("deadline reached")
    old = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


# ---------------------------------------------------------------------------
# Naive DPLL (clean recursive implementation)
# ---------------------------------------------------------------------------

class NaiveDPLL:
    """Naive DPLL with unit propagation and chronological backtracking.

    ABSENT: clause learning, VSIDS, restarts.

    Decision heuristic: pick the lowest-indexed unassigned variable, try
    True then False.

    Statistics tracked: decisions (only explicit choice points, NOT unit
    propagations), propagations, conflicts, max decision depth.
    """

    def __init__(self, clauses, n_vars):
        self.clauses = [tuple(c) for c in clauses]
        self.n_vars = n_vars
        self.assignment = [None] * (n_vars + 1)  # 1-indexed
        self.trail = []      # stack of (var, value) — used for backtracking
        self.decisions = 0
        self.propagations = 0
        self.conflicts = 0
        self.max_depth = 0
        self._depth = 0

    # --- helpers ---------------------------------------------------------

    def _eval(self, lit):
        v = abs(lit)
        a = self.assignment[v]
        if a is None:
            return 0
        if lit > 0:
            return 1 if a == 1 else -1
        else:
            return 1 if a == 0 else -1

    def _unit_propagate(self):
        """Apply unit propagation until fixpoint.  Returns True on success,
        False on conflict (also counts as a conflict)."""
        changed = True
        while changed:
            changed = False
            for cl in self.clauses:
                unassigned = None
                n_unassigned = 0
                satisfied = False
                for l in cl:
                    ev = self._eval(l)
                    if ev == 1:
                        satisfied = True
                        break
                    if ev == 0:
                        n_unassigned += 1
                        unassigned = l
                if satisfied:
                    continue
                if n_unassigned == 0:
                    # all literals false -> conflict
                    self.conflicts += 1
                    return False
                if n_unassigned == 1:
                    # unit clause: assign the remaining literal
                    v = abs(unassigned)
                    val = 1 if unassigned > 0 else 0
                    self.assignment[v] = val
                    self.trail.append((v, val))
                    self.propagations += 1
                    changed = True
                # else: still 2+ unassigned, no info yet
        return True

    def _is_all_sat(self):
        for cl in self.clauses:
            if not any(self._eval(l) == 1 for l in cl):
                return False
        return True

    def _pick_var(self):
        for v in range(1, self.n_vars + 1):
            if self.assignment[v] is None:
                return v
        return None

    def _pop_to(self, target_size):
        while len(self.trail) > target_size:
            v, _ = self.trail.pop()
            self.assignment[v] = None

    # --- entry point -----------------------------------------------------

    def solve(self, deadline=None):
        t0 = time.time()
        try:
            if deadline is not None:
                with time_limit(deadline):
                    res = self._solve_inner()
            else:
                res = self._solve_inner()
        except TimeoutError:
            return {
                "status": "timeout",
                "decisions": self.decisions,
                "propagations": self.propagations,
                "conflicts": self.conflicts,
                "max_depth": self.max_depth,
                "time": time.time() - t0,
            }
        res["time"] = time.time() - t0
        return res

    def _solve_inner(self):
        # initial unit propagation
        if not self._unit_propagate():
            return {"status": "unsat",
                    "decisions": self.decisions,
                    "propagations": self.propagations,
                    "conflicts": self.conflicts,
                    "max_depth": self.max_depth}
        return self._dpll()

    def _dpll(self):
        """Recursive DPLL.  Always operates on current self.assignment state."""
        if self._is_all_sat():
            return {"status": "sat",
                    "decisions": self.decisions,
                    "propagations": self.propagations,
                    "conflicts": self.conflicts,
                    "max_depth": self.max_depth}
        v = self._pick_var()
        if v is None:
            # all assigned but not all-sat should be impossible
            return {"status": "unsat",
                    "decisions": self.decisions,
                    "propagations": self.propagations,
                    "conflicts": self.conflicts,
                    "max_depth": self.max_depth}

        # try v = True
        self.decisions += 1
        self._depth += 1
        if self._depth > self.max_depth:
            self.max_depth = self._depth
        mark = len(self.trail)
        self.assignment[v] = 1
        self.trail.append((v, 1))
        if self._unit_propagate():
            res = self._dpll()
            if res["status"] == "sat":
                self._depth -= 1
                return res
        # backtrack
        self._pop_to(mark)
        if not self._is_all_sat() and not self._all_assigned():
            # try v = False
            self.decisions += 1
            self.assignment[v] = 0
            self.trail.append((v, 0))
            if self._unit_propagate():
                res = self._dpll()
                if res["status"] == "sat":
                    self._depth -= 1
                    return res
            self._pop_to(mark)
        else:
            # all clauses already satisfied or all assigned
            if self._is_all_sat():
                self._depth -= 1
                return {"status": "sat",
                        "decisions": self.decisions,
                        "propagations": self.propagations,
                        "conflicts": self.conflicts,
                        "max_depth": self.max_depth}

        self._depth -= 1
        return {"status": "unsat",
                "decisions": self.decisions,
                "propagations": self.propagations,
                "conflicts": self.conflicts,
                "max_depth": self.max_depth}

    def _all_assigned(self):
        return all(self.assignment[v] is not None for v in range(1, self.n_vars + 1))


def dpll_solve(clauses, n_vars, time_limit=None):
    s = NaiveDPLL(clauses, n_vars)
    return s.solve(deadline=time_limit)


# ---------------------------------------------------------------------------
# PySAT's MiniSAT (CDCL)
# ---------------------------------------------------------------------------

def minisat_solve(clauses, n_vars, deadline=None):
    t0 = time.time()
    solver = Minisat22()
    for c in clauses:
        solver.add_clause(c)
    try:
        if deadline is not None:
            with time_limit(deadline):
                sat = solver.solve()
        else:
            sat = solver.solve()
    except TimeoutError:
        solver.delete()
        return {
            "status": "timeout",
            "decisions": 0,
            "conflicts": 0,
            "propagations": 0,
            "restarts": 0,
            "time": time.time() - t0,
        }
    stats = solver.accum_stats()
    res = {
        "status": "sat" if sat else "unsat",
        "decisions": stats.get("decisions", 0),
        "conflicts": stats.get("conflicts", 0),
        "propagations": stats.get("propagations", 0),
        "restarts": stats.get("restarts", 0),
        "time": time.time() - t0,
    }
    solver.delete()
    return res


# ---------------------------------------------------------------------------
# Experiment driver
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-list", nargs="+", type=int, default=[15, 20, 25])
    parser.add_argument("--alpha", type=float, default=4.2)
    parser.add_argument("--seeds", nargs="+", type=int, default=[1, 2, 3, 4, 5])
    parser.add_argument("--time-limit", type=float, default=60.0)
    parser.add_argument("--out-csv", default="results.csv")
    args = parser.parse_args()

    rows = []
    print(f"{'n':>3} {'m':>4} {'seed':>5}  {'DPLL time':>10} {'DPLL dec':>9} {'DPLL confl':>11}  "
          f"{'CDCL time':>10} {'CDCL dec':>9} {'CDCL confl':>11}  "
          f"{'DPLL':>8} {'CDCL':>8}")
    for n in args.n_list:
        m = int(round(args.alpha * n))
        for seed in args.seeds:
            clauses, nv = random_ksat(n, m, k=3, seed=seed)
            d = dpll_solve(clauses, nv, time_limit=args.time_limit)
            c = minisat_solve(clauses, nv, deadline=args.time_limit)
            row = {
                "n": n,
                "m": m,
                "seed": seed,
                "dpll_status": d["status"],
                "dpll_time": d["time"],
                "dpll_decisions": d["decisions"],
                "dpll_propagations": d.get("propagations", 0),
                "dpll_conflicts": d["conflicts"],
                "dpll_max_depth": d.get("max_depth", 0),
                "cdcl_status": c["status"],
                "cdcl_time": c["time"],
                "cdcl_decisions": c["decisions"],
                "cdcl_propagations": c.get("propagations", 0),
                "cdcl_conflicts": c["conflicts"],
                "cdcl_restarts": c.get("restarts", 0),
            }
            rows.append(row)
            print(f"{n:>3} {m:>4} {seed:>5}  {d['time']:>10.4f} {d['decisions']:>9d} {d['conflicts']:>11d}  "
                  f"{c['time']:>10.4f} {c['decisions']:>9d} {c['conflicts']:>11d}  "
                  f"{d['status']:>8} {c['status']:>8}", flush=True)

    with open(args.out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print(f"wrote {args.out_csv}")


if __name__ == "__main__":
    main()
