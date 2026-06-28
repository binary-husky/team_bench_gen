"""
Lightweight z3 symbolic / concolic execution framework.

Research goal: verify that a simple constraint / counter-example cache
drastically cuts the number of queries that actually hit z3 during symbolic
execution.  This mirrors KLEE's "no query is the fastest query" counter-example
cache optimization (Cadar et al. 2008).

CPU-only, Python + z3-solver, no KLEE binary.

Design
------
* Every "is this path condition SAT?" check goes through one countable
  `SolverInterface.check(constraints)` method.
* Two modes share the SAME interface / SAME exploration:
    (A) no cache  : every check calls z3.   z3_calls == total_queries.
    (B) simple cache: keyed by the (deduped) constraint set; a hit serves the
        cached SAT result + model without touching z3.  z3_calls == #distinct
        queries (the misses).
* The exploration is *concolic* (DSE).  For each executed path we issue, at every
  branch on the path, a "flip-query" = prefix_PC AND NOT(taken_branch).  Flip
  queries for shared prefixes recur across executions -> exact-key cache hits.
  A function with repeated sub-constraints makes whole sequences of queries
  collapse to one key.
* z3's smt.random_seed is fixed so model generation is deterministic; therefore
  mode (A) and mode (B) traverse exactly the same set of queries and are
  perfectly comparable.  The *exploration* seed (1..3) randomises the initial
  random inputs and worklist order, giving the >=3 seed repetitions requested.
"""

import random
import z3

# deterministic z3 model generation -> A and B explore identically
z3.set_param("smt.random_seed", 7)


# --------------------------------------------------------------------------- #
#  Symbolic value + primitive ops
# --------------------------------------------------------------------------- #
class Val:
    """A value carrying both a concrete int and a z3 expr."""
    __slots__ = ("conc", "z3")

    def __init__(self, conc, z3expr):
        self.conc = conc
        self.z3 = z3expr


def v_add(a, b):
    ca, za = (a.conc, a.z3) if isinstance(a, Val) else (a, a)
    cb, zb = (b.conc, b.z3) if isinstance(b, Val) else (b, b)
    return Val(ca + cb, za + zb)


def v_sub(a, b):
    ca, za = (a.conc, a.z3) if isinstance(a, Val) else (a, a)
    cb, zb = (b.conc, b.z3) if isinstance(b, Val) else (b, b)
    return Val(ca - cb, za - zb)


def v_lt(a, b):
    ca, za = (a.conc, a.z3) if isinstance(a, Val) else (a, a)
    cb, zb = (b.conc, b.z3) if isinstance(b, Val) else (b, b)
    return (za < zb, ca < cb)          # (z3_bool, concrete_bool)


def v_le(a, b):
    ca, za = (a.conc, a.z3) if isinstance(a, Val) else (a, a)
    cb, zb = (b.conc, b.z3) if isinstance(b, Val) else (b, b)
    return (za <= zb, ca <= cb)


def v_eq(a, b):
    ca, za = (a.conc, a.z3) if isinstance(a, Val) else (a, a)
    cb, zb = (b.conc, b.z3) if isinstance(b, Val) else (b, b)
    return (za == zb, ca == cb)


def v_gt(a, b):
    ca, za = (a.conc, a.z3) if isinstance(a, Val) else (a, a)
    cb, zb = (b.conc, b.z3) if isinstance(b, Val) else (b, b)
    return (za > zb, ca > cb)


def v_or(p, q):
    return (z3.Or(p[0], q[0]), p[1] or q[1])


def v_and(p, q):
    return (z3.And(p[0], q[0]), p[1] and q[1])


class Engine:
    """Concolic driver: runs toy functions, records branch paths, issues
    flip-queries through a SolverInterface."""

    def __init__(self, solver_if, rng):
        self.si = solver_if
        self.rng = rng

    # ---- branch primitive the toy functions call --------------------------- #
    def sym_if(self, cond_pair):
        """cond_pair = (z3_bool, concrete_bool). Record branch, return concrete."""
        z3expr, conc = cond_pair
        self._path.append((z3expr, conc))
        return conc

    # ---- run one concrete+symbolic execution ------------------------------- #
    def execute(self, fn, conc_input):
        """Run fn with concrete inputs; return the recorded branch path."""
        self._path = []
        syms = {n: Val(c, z3.Int(n)) for n, c in conc_input.items()}
        fn(syms, self.sym_if)
        return self._path

    # ---- main exploration -------------------------------------------------- #
    def explore(self, fn, var_names, n_random_starts=4, max_inputs=20000):
        covered_edges = set()
        inputs = []
        # a handful of random restarts so disjoint input regions (e.g. x>0 vs
        # x<=0 when the flip between them is infeasible) are both reached
        for _ in range(n_random_starts):
            inp = {n: self.rng.randint(-50, 50) for n in var_names}
            inputs.append(inp)

        n_exec = 0
        while inputs and n_exec < max_inputs:
            inp = inputs.pop(self.rng.randint(0, len(inputs) - 1) if inputs else 0)
            n_exec += 1
            path = self.execute(fn, inp)

            pc = []  # accumulated prefix constraints (z3 bools) along taken path
            for (pred, dec) in path:
                # the edge actually taken at this branch
                taken = pred if dec else z3.Not(pred)
                # the flip-query: feasibility of the *other* side
                flip = z3.Not(pred) if dec else pred
                qconstraints = pc + [flip]
                res, model = self.si.check(qconstraints)

                key = self.si.key_of(qconstraints)
                if key not in covered_edges:
                    covered_edges.add(key)
                    if res == z3.sat and model is not None:
                        new_inp = dict(inp)
                        for n in var_names:
                            ev = model.eval(z3.Int(n), model_completion=True)
                            try:
                                new_inp[n] = int(ev.as_string())
                            except Exception:
                                pass
                        inputs.append(new_inp)
                pc.append(taken)

        return n_exec


# --------------------------------------------------------------------------- #
#  Solver interface  --  the thing being measured
# --------------------------------------------------------------------------- #
class SolverInterface:
    def __init__(self, use_cache):
        self.use_cache = use_cache
        self.total_queries = 0
        self.z3_calls = 0
        self.cache_hits = 0
        self.cache = {}            # key -> (result, model_dict_or_None)
        self._solver = z3.Solver()

    @staticmethod
    def key_of(constraints):
        """Canonical, deduped key: frozenset of stringified constraints.

        Using a *set* means a predicate added twice collapses to one entry --
        this is exactly why repeated sub-constraints are so cacheable."""
        return frozenset(str(c) for c in constraints)

    def check(self, constraints):
        self.total_queries += 1
        key = self.key_of(constraints)
        if self.use_cache and key in self.cache:
            self.cache_hits += 1
            return self.cache[key]

        # real solver call
        self.z3_calls += 1
        s = self._solver
        s.push()
        s.add(*constraints)
        r = s.check()
        model = s.model() if r == z3.sat else None
        s.pop()
        out = (r, model)
        if self.use_cache:
            self.cache[key] = out
        return out


# --------------------------------------------------------------------------- #
#  Toy functions under test
# --------------------------------------------------------------------------- #
def f_get_sign(v, sym_if):
    x = v["x"]
    if sym_if(v_lt(x, 0)):
        return "neg"
    if sym_if(v_eq(x, 0)):
        return "zero"
    return "pos"


def f_classify_triangle(v, sym_if):
    a, b, c = v["a"], v["b"], v["c"]
    ab = v_add(a, b)
    ac = v_add(a, c)
    bc = v_add(b, c)
    valid = v_and(v_and(v_gt(ab, c), v_gt(ac, b)), v_gt(bc, a))
    if not sym_if(valid):
        return "not_a_triangle"
    eq_ab = v_eq(a, b)
    eq_bc = v_eq(b, c)
    eq_ac = v_eq(a, c)
    if sym_if(v_and(eq_ab, eq_bc)):
        return "equilateral"
    if sym_if(v_or(eq_ab, v_or(eq_bc, eq_ac))):
        return "isosceles"
    return "scalene"


def make_k_independent_ifs(k):
    def f(v, sym_if):
        acc = 0
        for i in range(k):
            xi = v[f"x{i}"]
            if sym_if(v_gt(xi, 0)):
                acc += 1
        return acc
    f.__name__ = f"k_independent_ifs(k={k})"
    return f, [f"x{i}" for i in range(k)]


def make_repeated_subconstraints(k):
    """The SAME predicate (x>0) re-checked k times in sequence -- models
    redundant guards / unrolled loops / re-checked invariants.  Deduping the
    constraint set makes every repeat a cache hit."""
    def f(v, sym_if):
        x = v["x"]
        guard = 0
        for _ in range(k):
            if sym_if(v_gt(x, 0)):
                guard += 1
        return guard
    f.__name__ = f"repeated_subconstraints(k={k})"
    return f, ["x"]


# --------------------------------------------------------------------------- #
#  Experiment runner
# --------------------------------------------------------------------------- #
def run_one(fn, var_names, use_cache, seed):
    si = SolverInterface(use_cache=use_cache)
    rng = random.Random(seed)
    eng = Engine(si, rng)
    n_exec = eng.explore(fn, var_names,
                         n_random_starts=4, max_inputs=20000)
    return {
        "fn": fn.__name__,
        "use_cache": use_cache,
        "seed": seed,
        "total_queries": si.total_queries,
        "z3_calls": si.z3_calls,
        "cache_hits": si.cache_hits,
        "n_executions": n_exec,
    }


FUNCTIONS = []


def setup_functions():
    fs = []
    fs.append((f_get_sign, ["x"]))
    fs.append((f_classify_triangle, ["a", "b", "c"]))
    f, vn = make_k_independent_ifs(4)
    fs.append((f, vn))
    f, vn = make_repeated_subconstraints(8)
    fs.append((f, vn))
    return fs


def main():
    funcs = setup_functions()
    seeds = [1, 2, 3, 7]
    rows = []
    for (fn, vn) in funcs:
        for seed in seeds:
            a = run_one(fn, vn, use_cache=False, seed=seed)
            b = run_one(fn, vn, use_cache=True, seed=seed)
            rows.append((a, b))
    # print machine-readable
    for (a, b) in rows:
        print("RES", a["fn"], "seed", a["seed"],
              "A_total", a["total_queries"], "A_z3", a["z3_calls"],
              "B_total", b["total_queries"], "B_z3", b["z3_calls"],
              "B_hits", b["cache_hits"], "exec", a["n_executions"])
    # sanity: A and B must have identical total_queries & executions
    for (a, b) in rows:
        assert a["total_queries"] == b["total_queries"], (a, b)
        assert a["n_executions"] == b["n_executions"], (a, b)
        assert a["z3_calls"] == a["total_queries"]   # mode A: every query -> z3
    print("SANITY_OK")


if __name__ == "__main__":
    main()
