"""
Lightweight symbolic execution / concolic framework using z3 (Python only).

Key idea: KLEE-style execution.
  - The program is described by a Python "explore" function that uses z3
    symbolic variables for inputs and a small API to fork on branches.
  - At each symbolic branch, the framework forks the current state into
    two: one that takes the True direction (constraint + branch id),
    one that takes the False direction.
  - DFS explores all reachable states; whenever a state terminates
    (i.e. the program "returns"), the framework asks z3 for a model
    of the path constraints, producing one concrete test case per
    feasible path.
  - The framework also records every (branch_id, direction) it has
    seen so branch coverage can be measured.

This is intentionally a *toy* engine, on the same conceptual lines as
the KLEE paper (Cadar, Dunbar, Engler, OSDI 2008) - symbolic input,
path condition accumulation, fork at each branch, solve at termination
to get a test case - but written in < 200 lines of pure Python on top
of z3, with no LLVM, no Clang, no KLEE, and no C compilation.
"""

from __future__ import annotations
import z3
import random
from typing import List, Dict, Tuple, Set, Optional, Any, Callable, Iterable


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------

class SymbolicState:
    """A single symbolic execution state: one (path, constraints) pair."""

    def __init__(self, input_vars: Dict[str, z3.ArithRef],
                 input_domains: Dict[str, Tuple[int, int]]):
        self.input_vars = input_vars
        self.input_domains = input_domains
        # Path constraints accumulated along the way.
        self.constraints: List[z3.BoolRef] = []
        # Sequence of (branch_id, taken_direction) decisions along this path.
        self.path: List[Tuple[int, bool]] = []
        # Set by the explore function when this state reaches a return.
        self.outcome: Optional[str] = None
        self.terminated: bool = False

    def copy(self) -> "SymbolicState":
        new = SymbolicState(self.input_vars, self.input_domains)
        new.constraints = self.constraints.copy()
        new.path = self.path.copy()
        new.outcome = self.outcome
        new.terminated = self.terminated
        return new


# ---------------------------------------------------------------------------
# Exploration engine
# ---------------------------------------------------------------------------

def explore_all(initial: SymbolicState,
                explore_func: Callable[[SymbolicState], Iterable[SymbolicState]]
                ) -> List[SymbolicState]:
    """DFS through every reachable state; return only the terminal ones."""
    completed: List[SymbolicState] = []

    def dfs(state: SymbolicState) -> None:
        for nxt in explore_func(state):
            if nxt.terminated:
                completed.append(nxt)
            else:
                dfs(nxt)

    dfs(initial)
    return completed


def solve_state(state: SymbolicState,
                seed: int = 0) -> Optional[Dict[str, int]]:
    """Ask z3 for a concrete model of the path constraints."""
    s = z3.Solver()
    # Use the seed to vary z3's strategy so different seeds *try* different
    # solving strategies. (The path enumeration does not depend on this.)
    s.set("random_seed", seed)
    s.set("smt.phase_selection", seed % 6)
    s.set("smt.arith.random_initial_value", True)
    for c in state.constraints:
        s.add(c)
    for name, (lo, hi) in state.input_domains.items():
        s.add(state.input_vars[name] >= lo)
        s.add(state.input_vars[name] <= hi)
    if s.check() != z3.sat:
        return None
    m = s.model()
    return {name: m.eval(state.input_vars[name],
                          model_completion=True).as_long()
            for name in state.input_vars}


# ---------------------------------------------------------------------------
# Concrete reference implementations (for verification)
# ---------------------------------------------------------------------------

def get_sign_concrete(x: int) -> str:
    if x < 0:
        return "negative"
    elif x == 0:
        return "zero"
    else:
        return "positive"


def classify_triangle_concrete(a: int, b: int, c: int) -> str:
    if a <= 0 or b <= 0 or c <= 0:
        return "invalid"
    if a + b <= c or a + c <= b or b + c <= a:
        return "invalid"
    if a == b and b == c:
        return "equilateral"
    if a == b or a == c or b == c:
        return "isosceles"
    return "scalene"


def k_independent_ifs_concrete(xs: List[int]) -> str:
    return "".join(str(i + 1) for i, v in enumerate(xs) if v > 0)


# ---------------------------------------------------------------------------
# Symbolic descriptions of the toy functions
# ---------------------------------------------------------------------------

def explore_get_sign(state: SymbolicState):
    x = state.input_vars["x"]

    # Branch 0: x < 0 ?
    s_neg = state.copy()
    s_neg.constraints.append(x < 0)
    s_neg.path.append((0, True))
    s_neg.outcome = "negative"
    s_neg.terminated = True
    yield s_neg

    s_nonneg = state.copy()
    s_nonneg.constraints.append(x >= 0)
    s_nonneg.path.append((0, False))

    # Branch 1: x == 0 ?
    s_zero = s_nonneg.copy()
    s_zero.constraints.append(x == 0)
    s_zero.path.append((1, True))
    s_zero.outcome = "zero"
    s_zero.terminated = True
    yield s_zero

    s_pos = s_nonneg.copy()
    s_pos.constraints.append(x != 0)
    s_pos.path.append((1, False))
    s_pos.outcome = "positive"
    s_pos.terminated = True
    yield s_pos


def explore_classify_triangle(state: SymbolicState):
    a, b, c = state.input_vars["a"], state.input_vars["b"], state.input_vars["c"]

    # Branch 0: a <= 0 or b <= 0 or c <= 0  (sides must be positive)
    b0 = z3.Or(a <= 0, b <= 0, c <= 0)
    s_inv0 = state.copy()
    s_inv0.constraints.append(b0)
    s_inv0.path.append((0, True))
    s_inv0.outcome = "invalid"
    s_inv0.terminated = True
    yield s_inv0

    s_ok0 = state.copy()
    s_ok0.constraints.append(z3.Not(b0))
    s_ok0.path.append((0, False))

    # Branch 1: triangle inequality violated?
    b1 = z3.Or(a + b <= c, a + c <= b, b + c <= a)
    s_inv1 = s_ok0.copy()
    s_inv1.constraints.append(b1)
    s_inv1.path.append((1, True))
    s_inv1.outcome = "invalid"
    s_inv1.terminated = True
    yield s_inv1

    s_ok1 = s_ok0.copy()
    s_ok1.constraints.append(z3.Not(b1))
    s_ok1.path.append((1, False))

    # Branch 2: equilateral?  (a == b and b == c)
    b2 = z3.And(a == b, b == c)
    s_eq = s_ok1.copy()
    s_eq.constraints.append(b2)
    s_eq.path.append((2, True))
    s_eq.outcome = "equilateral"
    s_eq.terminated = True
    yield s_eq

    s_ok2 = s_ok1.copy()
    s_ok2.constraints.append(z3.Not(b2))
    s_ok2.path.append((2, False))

    # Branch 3: isosceles?  (a == b or a == c or b == c)
    b3 = z3.Or(a == b, a == c, b == c)
    s_iso = s_ok2.copy()
    s_iso.constraints.append(b3)
    s_iso.path.append((3, True))
    s_iso.outcome = "isosceles"
    s_iso.terminated = True
    yield s_iso

    s_sca = s_ok2.copy()
    s_sca.constraints.append(z3.Not(b3))
    s_sca.path.append((3, False))
    s_sca.outcome = "scalene"
    s_sca.terminated = True
    yield s_sca


def explore_k_independent_ifs(state: SymbolicState, k: int):
    """Recursively explore k independent `if x_i > 0` branches."""
    yield from _recurse_kifs(state, 0, k)


def _recurse_kifs(state: SymbolicState, i: int, k: int):
    if i == k:
        s = state.copy()
        # Match concrete function: indices (1-indexed) of branches that took True.
        s.outcome = "".join(str(idx + 1) for idx, (_, d) in enumerate(state.path) if d)
        s.terminated = True
        yield s
        return
    xi = state.input_vars[f"x{i+1}"]
    cond = xi > 0

    s_t = state.copy()
    s_t.constraints.append(cond)
    s_t.path.append((i, True))
    yield from _recurse_kifs(s_t, i + 1, k)

    s_f = state.copy()
    s_f.constraints.append(z3.Not(cond))
    s_f.path.append((i, False))
    yield from _recurse_kifs(s_f, i + 1, k)


# ---------------------------------------------------------------------------
# Experiment driver
# ---------------------------------------------------------------------------

def make_inputs(names: List[str], domain: Tuple[int, int]):
    return ({n: z3.Int(n) for n in names},
            {n: domain for n in names})


def run_one(function_name: str, explore_func, input_names: List[str],
            domain: Tuple[int, int], total_branches: int,
            concrete_func, seed: int):
    random.seed(seed)
    z3.set_param("smt.random_seed", seed)

    input_vars, input_domains = make_inputs(input_names, domain)
    initial = SymbolicState(input_vars, input_domains)
    terminal_states = explore_all(initial, explore_func)

    # Deduplicate paths by their decision sequence.
    unique_paths: Dict[Tuple, SymbolicState] = {}
    for st in terminal_states:
        key = tuple(st.path)
        # Keep the first one we see; they are equivalent.
        unique_paths.setdefault(key, st)
    path_list = list(unique_paths.values())

    # For each unique path, solve the path condition to obtain a test.
    tests: List[Dict[str, int]] = []
    for st in path_list:
        test = solve_state(st, seed=seed)
        if test is None:
            # Infeasible path; skip (shouldn't happen for these well-formed toys).
            continue
        # Sanity-check the concrete execution matches the symbolic outcome.
        if input_names == ["x"]:
            concrete_out = concrete_func(test["x"])
        elif input_names == ["a", "b", "c"]:
            concrete_out = concrete_func(test["a"], test["b"], test["c"])
        else:
            xs = [test[n] for n in input_names]
            concrete_out = concrete_func(xs)
        assert concrete_out == st.outcome, (
            f"Mismatch! test={test} expected={st.outcome} got={concrete_out}")
        tests.append(test)

    # Deduplicate tests.
    seen = set()
    unique_tests = []
    for t in tests:
        key = tuple(sorted(t.items()))
        if key not in seen:
            seen.add(key)
            unique_tests.append(t)

    # Branch coverage: every (branch_id, direction) we visited.
    covered: Set[Tuple[int, bool]] = set()
    for st in path_list:
        covered.update(st.path)
    branch_coverage = len(covered) / (total_branches * 2) * 100.0

    return {
        "function": function_name,
        "seed": seed,
        "num_tests": len(unique_tests),
        "num_paths": len(path_list),
        "branch_coverage_pct": branch_coverage,
        "covered_branch_directions": len(covered),
        "total_branch_directions": total_branches * 2,
        "outcomes": sorted(st.outcome for st in path_list),
    }


def main():
    results = []

    # ---- get_sign(x) -------------------------------------------------------
    # 2 branches (x<0, x==0) => 4 branch-directions.
    # 3 feasible paths: negative, zero, positive.
    for seed in [42, 123, 7]:
        r = run_one("get_sign", explore_get_sign, ["x"], (-1000, 1000),
                    total_branches=2, concrete_func=get_sign_concrete, seed=seed)
        results.append(r)

    # ---- classify_triangle(a, b, c) ---------------------------------------
    # 4 branches => 8 branch-directions; 5 feasible paths:
    #   invalid(sides), invalid(ineq), equilateral, isosceles, scalene
    # Domain must include non-positive ints so the "invalid (sides)" path
    # is feasible.
    for seed in [42, 123, 7]:
        r = run_one("classify_triangle", explore_classify_triangle,
                    ["a", "b", "c"], (-100, 100),
                    total_branches=4, concrete_func=classify_triangle_concrete,
                    seed=seed)
        results.append(r)

    # ---- k_independent_ifs -------------------------------------------------
    # k branches => 2k branch-directions; 2^k feasible paths.
    for k in [2, 3, 4, 5]:
        for seed in [42, 123, 7]:
            r = run_one(f"k_independent_ifs_k{k}",
                        lambda st, kk=k: explore_k_independent_ifs(st, kk),
                        [f"x{i+1}" for i in range(k)], (-1000, 1000),
                        total_branches=k,
                        concrete_func=k_independent_ifs_concrete,
                        seed=seed)
            results.append(r)

    # ---------------------------------------------------------------------
    print("=" * 78)
    print(f"{'function':<26} {'seed':>5} {'#tests':>7} {'#paths':>7} {'branch_cov':>11}")
    print("-" * 78)
    for r in results:
        print(f"{r['function']:<26} {r['seed']:>5} "
              f"{r['num_tests']:>7} {r['num_paths']:>7} "
              f"{r['branch_coverage_pct']:>10.2f}%")
    print("=" * 78)

    # Save results to JSON for the report.
    import json
    with open("results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to results.json ({len(results)} runs).")
    return results


if __name__ == "__main__":
    main()
