"""
Concolic / symbolic-execution experiment: query-cache hit-rate.

A miniature clone of the relevant slice of KLEE's solver interface:
  * Each path-branch decision goes through a single ``Solver.check_sat(PC)``
    function that counts how many times it actually invokes z3.
  * Mode (A) -- NoCache: every branch decision calls z3.
  * Mode (B) -- Cache:   the result/model of ``check_sat`` is keyed by the
    path-condition (frozen set of z3 BoolRefs) and reused on subsequent
    identical PCs (mirroring KLEE's "counter-example cache").

The toy programs are deliberately written to mimic realistic redundancy:
  - defensive re-checks of an entry condition
  - input validation re-asserted before any side-effecting call
  - a hot loop that tests the same compound predicate every iteration
  - a function called from two sites with the same caller-state

These are exactly the patterns in real code that KLEE's counter-example
cache was designed to amortize.

Per (program, seed) we record:
  - total_queries      (every check_sat() the engine emitted)
  - z3_calls           (actual z3 invocations)
  - cache_hits         (queries served from cache)
  - hit_rate
  - paths_explored, dead_ends

Run: ``python se_cache_experiment.py``
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Tuple

import z3


# ---------------------------------------------------------------------------
#  Counting solver interface
# ---------------------------------------------------------------------------

class CountingSolver:
    """The Query Logger: wraps z3 and records every real z3 invocation.

    In mode (A) -- no cache -- every check_sat ends in a z3 call.
    In mode (B) -- cache -- the PC key is the frozenset of z3 BoolRefs;
    an identical PC (a hit) returns the cached (result, model) and does
    not call z3.
    """

    def __init__(self, use_cache: bool):
        self.use_cache = use_cache
        self.z3_calls = 0
        self.total_queries = 0
        self.cache_hits = 0
        # bookkeeping for the report
        self.sat_queries = 0
        self.unsat_queries = 0
        self._cache: Dict[frozenset, Tuple[str, z3.ModelRef | None]] = {}

    def check_sat(self, constraints: Iterable[z3.BoolRef]
                  ) -> Tuple[str, z3.ModelRef | None]:
        constraints = tuple(constraints)
        self.total_queries += 1
        key = frozenset(constraints)   # BoolRefs hash by AST; frozenset dedupes

        if self.use_cache and key in self._cache:
            self.cache_hits += 1
            return self._cache[key]

        s = z3.Solver()
        for c in constraints:
            s.add(c)
        self.z3_calls += 1
        result = s.check()
        if result == z3.sat:
            cached: Tuple[str, z3.ModelRef | None] = ("sat", s.model())
            self.sat_queries += 1
        else:
            cached = ("unsat", None)
            self.unsat_queries += 1

        if self.use_cache:
            self._cache[key] = cached
        return cached


# ---------------------------------------------------------------------------
#  Symbolic-execution engine
# ---------------------------------------------------------------------------

@dataclass
class SymState:
    pc: List[z3.BoolRef] = field(default_factory=list)
    symbolic: Dict[str, z3.ExprRef] = field(default_factory=dict)


class SymbolicExecutor:
    def __init__(self, solver: CountingSolver, max_depth: int = 64):
        self.solver = solver
        self.max_depth = max_depth
        self.paths_explored = 0
        self.dead_ends = 0

    def run(self, fn: Callable, initial: SymState) -> None:
        self._explore(fn, initial, depth=0)

    def _fork(self, fn, state: SymState, extra: z3.BoolRef) -> None:
        child = SymState(pc=state.pc + [extra], symbolic=state.symbolic)
        self._explore(fn, child, depth=len(child.pc))

    def _explore(self, fn, state: SymState, depth: int) -> None:
        if depth > self.max_depth:
            return
        status, _ = self.solver.check_sat(state.pc)
        if status == "unsat":
            self.dead_ends += 1
            return
        self.paths_explored += 1
        fn(self, state)

    def branch(self, fn, state: SymState, cond: z3.BoolRef) -> None:
        self._fork(fn, state, cond)
        self._fork(fn, state, z3.Not(cond))


# ---------------------------------------------------------------------------
#  Toy programs
# ---------------------------------------------------------------------------

def _leaf(_e, _s): pass


# -- Program 1: get_sign ---------------------------------------------------
# A simple "is the integer positive/zero/negative" routine, with the entry
# condition re-checked four times.  This mimics a guarded function whose
# author was unsure whether the caller had already validated the input.
def prog_get_sign(exec_: SymbolicExecutor, state: SymState) -> None:
    x = state.symbolic["x"]
    guard = x > 0           # the BoolRef we will re-assert at every site
    for _ in range(4):
        exec_.branch(_leaf, state, guard)
    exec_.branch(_leaf, state, x == 0)


# -- Program 2: classify_triangle -----------------------------------------
# A more interesting program: validity is checked both up-front and again
# before any classification decision (a common defensive idiom in C code).
def prog_classify_triangle(exec_: SymbolicExecutor, state: SymState) -> None:
    a, b, c = state.symbolic["a"], state.symbolic["b"], state.symbolic["c"]
    valid = z3.And(a + b > c, a + c > b, b + c > a)
    exec_.branch(prog_classify_triangle_inner, state, valid)


def prog_classify_triangle_inner(exec_: SymbolicExecutor, state: SymState) -> None:
    a, b, c = state.symbolic["a"], state.symbolic["b"], state.symbolic["c"]
    valid = z3.And(a + b > c, a + c > b, b + c > a)   # same BoolRef again
    # Re-assert the guard 3 times before doing anything substantive
    for _ in range(3):
        exec_.branch(_leaf, state, valid)
    exec_.branch(_leaf, state, z3.And(a == b, b == c))            # equil.
    exec_.branch(_leaf, state, z3.And(a == b, z3.Not(b == c)))   # iso ab
    exec_.branch(_leaf, state, z3.And(b == c, z3.Not(a == c)))   # iso bc
    exec_.branch(_leaf, state, z3.And(a == c, z3.Not(a == b)))   # iso ac
    exec_.branch(_leaf, state, z3.Not(z3.Or(a == b, b == c, a == c)))


# -- Program 3: k_independent_ifs(k=4) ------------------------------------
# Four independent branches followed by a defensive re-check of two of them.
def prog_k_independent_ifs(exec_: SymbolicExecutor, state: SymState) -> None:
    ks = [state.symbolic[f"k{i}"] for i in range(4)]
    for k in ks:
        exec_.branch(_leaf, state, k > 0)
    # re-assert the first two: same BoolRefs from the loop above
    exec_.branch(_leaf, state, ks[0] > 0)
    exec_.branch(_leaf, state, ks[1] > 0)
    # and a 3rd re-assertion of ks[0] -- the engineer got paranoid
    exec_.branch(_leaf, state, ks[0] > 0)


# -- Program 4: dup_subconstraints -----------------------------------------
# A tight inner loop that re-uses the *same* compound BoolRef; this is the
# cleanest demonstration of "many queries, one PC key".
def prog_dup_subconstraints(exec_: SymbolicExecutor, state: SymState) -> None:
    x, y = state.symbolic["x"], state.symbolic["y"]
    big   = x * x + y * y < 100
    small = x + y > -5
    small_not = z3.Not(small)
    for _ in range(8):
        exec_.branch(_leaf, state, big)
        exec_.branch(_leaf, state, small_not)


# -- Program 5: function_called_from_two_sites ----------------------------
# A function that asks the same precondition both at the call-site
# (mimicking a wrapper) and inside the function itself.
def prog_func_reentry(exec_: SymbolicExecutor, state: SymState) -> None:
    x = state.symbolic["x"]
    pre = z3.And(x >= 0, x <= 100)   # one BoolRef shared by both call-sites
    # caller #1: assert the precondition, then call the body
    exec_.branch(_func_body, state, pre)
    # caller #2: same precondition, called from a different "site"
    exec_.branch(_func_body, state, pre)


def _func_body(exec_: SymbolicExecutor, state: SymState) -> None:
    x = state.symbolic["x"]
    pre = z3.And(x >= 0, x <= 100)
    # inside the function we re-assert the precondition (defensive)
    exec_.branch(_leaf, state, pre)
    exec_.branch(_leaf, state, x % 2 == 0)
    exec_.branch(_leaf, state, x < 50)


# -- Program 6: many_guards -----------------------------------------------
# A single hot path guarded by the same predicate, re-checked 20 times in
# sequence (a common pattern: input validation in a tight loop, or many
# call-sites for a helper that all do the same assert).
def prog_many_guards(exec_: SymbolicExecutor, state: SymState) -> None:
    x = state.symbolic["x"]
    cond = x > 0
    for _ in range(20):
        exec_.branch(_leaf, state, cond)


# ---------------------------------------------------------------------------
#  Driver
# ---------------------------------------------------------------------------

PROGRAMS: Dict[str, Tuple[Callable, Dict[str, z3.ExprRef]]] = {
    "get_sign":           (prog_get_sign,           {"x": z3.Int("x")}),
    "classify_triangle":  (prog_classify_triangle,  {"a": z3.Int("a"),
                                                    "b": z3.Int("b"),
                                                    "c": z3.Int("c")}),
    "k_independent_ifs_4":(prog_k_independent_ifs,
                           {f"k{i}": z3.Int(f"k{i}") for i in range(4)}),
    "dup_subconstraints": (prog_dup_subconstraints, {"x": z3.Int("x"),
                                                    "y": z3.Int("y")}),
    "func_reentry":       (prog_func_reentry,       {"x": z3.Int("x")}),
    "many_guards":        (prog_many_guards,        {"x": z3.Int("x")}),
}


def make_initial_state(spec: Dict[str, z3.ExprRef],
                       lo: int, hi: int) -> SymState:
    pc, symbolic = [], {}
    for name, var in spec.items():
        pc.append(var >= lo)
        pc.append(var <= hi)
        symbolic[name] = var
    return SymState(pc=pc, symbolic=symbolic)


def run_one(program_name: str, seed: int) -> Dict:
    fn, sym = PROGRAMS[program_name]
    rng = random.Random(seed)
    lo, hi = rng.randint(-16, -4), rng.randint(4, 16)
    init = make_initial_state(sym, lo, hi)
    out: Dict = {"program": program_name, "seed": seed, "lo": lo, "hi": hi,
                 "A": {}, "B": {}}
    for label, use_cache in (("A", False), ("B", True)):
        solver = CountingSolver(use_cache=use_cache)
        engine = SymbolicExecutor(solver)
        random.seed(seed)
        engine.run(fn, init)
        n_q = solver.total_queries
        n_z3 = solver.z3_calls
        hit_rate = (solver.cache_hits / n_q) if n_q else 0.0
        out[label] = {
            "total_queries": n_q,
            "z3_calls":      n_z3,
            "cache_hits":    solver.cache_hits,
            "sat_queries":   solver.sat_queries,
            "unsat_queries": solver.unsat_queries,
            "hit_rate":      hit_rate,
            "paths":         engine.paths_explored,
            "dead_ends":     engine.dead_ends,
        }
    return out


def fmt_row(r: Dict) -> str:
    a, b = r["A"], r["B"]
    red = a["z3_calls"] / max(b["z3_calls"], 1)
    return (f"| {r['program']:<22} | seed={r['seed']} "
            f"({r['lo']:>3},{r['hi']:<3}) | "
            f"{a['total_queries']:>5} | {a['z3_calls']:>5} | "
            f"{b['total_queries']:>5} | {b['z3_calls']:>5} | "
            f"{b['cache_hits']:>5} | {b['hit_rate']*100:>6.2f}% | "
            f"{red:>6.2f}x |")


def main() -> None:
    seeds = [0, 1, 2, 3, 4]
    print("=" * 118)
    print(" KLEE-style counter-example cache experiment  (z3-solver 4.x, CPU only)")
    print("=" * 118)

    rows: List[Dict] = []
    for prog in PROGRAMS:
        for s in seeds:
            rows.append(run_one(prog, s))

    header = ("| program                | seed (lo,hi)        | "
              "Q(A)  | z3(A) | Q(B)  | z3(B) | hits  | hit-rate | A/B   |")
    sep = ("|" + "-" * 24 + "|" + "-" * 22 + "|" +
           "-" * 7 + "|" + "-" * 7 + "|" + "-" * 7 + "|" +
           "-" * 7 + "|" + "-" * 7 + "|" + "-" * 10 + "|" + "-" * 7 + "|")
    print(header)
    print(sep)
    for r in rows:
        print(fmt_row(r))

    print()
    print("Per-program aggregates (mean over seeds):")
    agg_header = ("| program                | Q(A) avg | z3(A) avg | "
                  "z3(B) avg | hit-rate avg | A/B avg |")
    print(agg_header)
    print("|" + "-" * 24 + "|" + "-" * 10 + "|" + "-" * 10 + "|" +
          "-" * 10 + "|" + "-" * 13 + "|" + "-" * 8 + "|")
    for prog in PROGRAMS:
        per = [r for r in rows if r["program"] == prog]
        avg_q_a = sum(r["A"]["total_queries"] for r in per) / len(per)
        avg_z_a = sum(r["A"]["z3_calls"]      for r in per) / len(per)
        avg_z_b = sum(r["B"]["z3_calls"]      for r in per) / len(per)
        avg_hr  = sum(r["B"]["hit_rate"]      for r in per) / len(per)
        avg_red = avg_z_a / max(avg_z_b, 1)
        print(f"| {prog:<22} | {avg_q_a:>8.1f} | {avg_z_a:>8.1f} | "
              f"{avg_z_b:>8.1f} | {avg_hr*100:>10.2f}% | "
              f"{avg_red:>5.2f}x |")

    with open("results.json", "w") as f:
        json.dump(rows, f, indent=2)
    print()
    print("Wrote raw results -> results.json")


if __name__ == "__main__":
    main()
