#!/usr/bin/env python3
"""
Compare pure-Boolean SAT encoding vs native SMT theory encoding on a fixed
small integer constraint puzzle: the 3x3 magic square.

Puzzle instance (fixed):
  - 9 integer variables x0..x8 arranged in a 3x3 grid.
  - Each variable takes a value in {1,...,9}.
  - All-different (a permutation of 1..9).
  - 8 linear sum constraints, each == 15:
        3 rows + 3 columns + 2 main diagonals.

Two encodings, both solved with z3-solver (pip z3-solver):
  (a) Pure Boolean / SAT (direct + table encoding):
        - one Bool per (variable, value) pair.
        - exactly-one per variable (ALO big-OR + AMO pairwise).
        - all-different: pairwise mutual-exclusion (x_i=v  =>  x_j!=v).
        - each sum==15 constraint: table encoding (Tseitin auxiliary per
          allowed value-tuple + one "at-least-one-tuple" clause).
  (b) Native SMT: z3 Int variables, And/Or/arith/relations, Distinct.

We record: #variables, #constraints(clauses/assertions), solve time, sat/unsat,
and validate that both encodings return a genuine magic square.
"""

import time
import z3

# ----------------------------------------------------------------------------
# Fixed puzzle instance
# ----------------------------------------------------------------------------
N = 9                     # 9 cells
LO, HI = 1, 9             # domain {1..9}
VALUES = list(range(LO, HI + 1))

# grid index mapping (row, col) -> var index
def idx(r, c):
    return r * 3 + c

# 8 sum==15 constraints as lists of variable indices (each length 3)
SUM_TRIPLES = []
# rows
for r in range(3):
    SUM_TRIPLES.append([idx(r, 0), idx(r, 1), idx(r, 2)])
# cols
for c in range(3):
    SUM_TRIPLES.append([idx(0, c), idx(1, c), idx(2, c)])
# diagonals
SUM_TRIPLES.append([idx(0, 0), idx(1, 1), idx(2, 2)])
SUM_TRIPLES.append([idx(0, 2), idx(1, 1), idx(2, 0)])
TARGET = 15

print(f"z3 version: {z3.get_version_string()}")
print(f"Puzzle: 3x3 magic square, {N} vars, domain {LO}..{HI}, "
      f"{len(SUM_TRIPLES)} sum=={TARGET} constraints + all-different")
print("=" * 70)


def valid_magic_square(assign):
    """assign: list of 9 ints. Check it is a real magic square."""
    vals = [assign[i] for i in range(N)]
    if sorted(vals) != list(range(LO, HI + 1)):
        return False, "not a permutation of 1..9"
    for t in SUM_TRIPLES:
        if sum(assign[i] for i in t) != TARGET:
            return False, f"sum {t} != {TARGET}"
    return True, "ok"


# ----------------------------------------------------------------------------
# (a) Pure Boolean / SAT encoding
# ----------------------------------------------------------------------------
def build_sat():
    """Return (solver, stats_dict, extract_fn)."""
    s = z3.Solver()
    # Bool var b[i][vi] meaning "variable i takes VALUES[vi]".
    # Index b by position vi (0..len(VALUES)-1); VALUES[vi] is the value.
    b = [[z3.Bool(f"b_{i}_{VALUES[vi]}") for vi in range(len(VALUES))]
         for i in range(N)]

    n_bool_vars = N * len(VALUES)
    n_clauses = 0

    def add_clause(cl):
        nonlocal n_clauses
        s.add(cl)
        n_clauses += 1

    def vi_of(value):
        return value - LO  # value -> position (since VALUES = LO..HI contiguous)

    # (1) exactly-one per variable: ALO (at-least-one) + AMO (at-most-one)
    for i in range(N):
        # ALO: at least one value
        add_clause(z3.Or(b[i]))
        # AMO: at most one value -> pairwise mutual exclusion
        for p in range(len(VALUES)):
            for q in range(p + 1, len(VALUES)):
                add_clause(z3.Or(z3.Not(b[i][p]), z3.Not(b[i][q])))

    # (2) all-different: for each pair of distinct variables and each value,
    #     they cannot both take that value.
    for i in range(N):
        for j in range(i + 1, N):
            for v in VALUES:
                vi = vi_of(v)
                add_clause(z3.Or(z3.Not(b[i][vi]), z3.Not(b[j][vi])))

    # (3) each sum==TARGET constraint via TABLE encoding (Tseitin)
    # enumerate allowed ordered value-tuples (a,b,c) in VALUES with a+b+c=TARGET
    allowed = [(a, c, d) for a in VALUES for c in VALUES for d in VALUES
               if a + c + d == TARGET]
    n_aux_tuplevars = 0
    n_table_clauses = 0
    for triple in SUM_TRIPLES:
        i1, i2, i3 = triple
        tuple_vars = []
        for (a, c, d) in allowed:
            t = z3.Bool(f"t_{i1}_{i2}_{i3}_{a}_{c}_{d}")
            n_aux_tuplevars += 1
            tuple_vars.append(t)
            # t => b[i1][a] and b[i2][c] and b[i3][d]  (3 clauses)
            add_clause(z3.Or(z3.Not(t), b[i1][vi_of(a)]))
            add_clause(z3.Or(z3.Not(t), b[i2][vi_of(c)]))
            add_clause(z3.Or(z3.Not(t), b[i3][vi_of(d)]))
            n_table_clauses += 3
        # at least one allowed tuple holds
        add_clause(z3.Or(tuple_vars))
        n_table_clauses += 1

    def extract(model):
        out = []
        for i in range(N):
            for vi in range(len(VALUES)):
                if z3.is_true(model.eval(b[i][vi])):
                    out.append(VALUES[vi])
                    break
        return out

    stats = dict(
        encoding="pure-Boolean SAT (direct + table)",
        bool_vars=n_bool_vars,
        aux_tuple_vars=n_aux_tuplevars,
        total_bool_vars=n_bool_vars + n_aux_tuplevars,
        clauses=n_clauses,
        table_clauses=n_table_clauses,
        allowed_tuples_per_constraint=len(allowed),
    )
    return s, stats, extract


# ----------------------------------------------------------------------------
# (b) Native SMT encoding
# ----------------------------------------------------------------------------
def build_smt():
    s = z3.Solver()
    x = [z3.Int(f"x_{i}") for i in range(N)]

    n_assertions = 0

    def add(c):
        nonlocal n_assertions
        s.add(c)
        n_assertions += 1

    # domain bounds
    for i in range(N):
        add(z3.And(x[i] >= LO, x[i] <= HI))

    # all-different
    add(z3.Distinct(x))

    # sum constraints
    for t in SUM_TRIPLES:
        add(x[t[0]] + x[t[1]] + x[t[2]] == TARGET)

    def extract(model):
        return [model.eval(x[i]).as_long() for i in range(N)]

    stats = dict(
        encoding="native SMT (Int + Distinct + arithmetic)",
        int_vars=N,
        assertions=n_assertions,
        domain_constraints=N,
        alldiff_assertions=1,
        sum_constraints=len(SUM_TRIPLES),
    )
    return s, stats, extract


# ----------------------------------------------------------------------------
# Run + time
# ----------------------------------------------------------------------------
def run(build_fn, trials=5):
    times = []
    result = None
    stats = extract_model = None
    for _ in range(trials):
        s, stats, extract = build_fn()
        t0 = time.perf_counter()
        res = s.check()
        t1 = time.perf_counter()
        times.append(t1 - t0)
        if result is None:
            result = res
            extract_model = (extract, s)
    return result, times, stats, extract_model


def main():
    encodings = [("SAT", build_sat), ("SMT", build_smt)]
    summary = {}
    for name, fn in encodings:
        res, times, stats, (extract, solver) = run(fn, trials=7)
        assign = None
        if res == z3.sat:
            assign = extract(solver.model())
            ok, msg = valid_magic_square(assign)
        else:
            ok, msg = None, "n/a"
        summary[name] = dict(stats=stats, res=str(res), times=times,
                             assign=assign, valid=(ok, msg))
        print(f"\n[{name}] {stats['encoding']}")
        print(f"  result      : {res}")
        print(f"  times (s)   : {[f'{t:.6f}' for t in times]}")
        print(f"  min/med/max : {min(times):.6f} / "
              f"{sorted(times)[len(times)//2]:.6f} / {max(times):.6f}")
        for k, v in stats.items():
            if k != "encoding":
                print(f"  {k:<28}: {v}")
        if assign is not None:
            g = [assign[idx(r, c)] for r in range(3) for c in range(3)]
            print(f"  grid        : [{assign[0]},{assign[1]},{assign[2]}] "
                  f"[{assign[3]},{assign[4]},{assign[5]}] "
                  f"[{assign[6]},{assign[7]},{assign[8]}]")
            print(f"  valid?      : {ok} ({msg})")

    # write a machine-readable json for the summary writer
    import json
    out = {
        "z3_version": z3.get_version_string(),
        "puzzle": "3x3 magic square",
        "N": N, "domain": [LO, HI],
        "n_sum_constraints": len(SUM_TRIPLES),
        "SAT": {k: (v if not isinstance(v, list) or (v and not isinstance(v[0], float))
                    else [round(t, 6) for t in v])
                for k, v in summary["SAT"].items()},
        "SMT": {k: (v if not isinstance(v, list) or (v and not isinstance(v[0], float))
                    else [round(t, 6) for t in v])
                for k, v in summary["SMT"].items()},
    }
    with open("results.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("\nWrote results.json")


if __name__ == "__main__":
    main()
