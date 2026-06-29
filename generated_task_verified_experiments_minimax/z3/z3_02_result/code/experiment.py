"""
Experiment: SAT (pure Boolean table encoding) vs. native SMT (Int + arithmetic)
encoding for the same integer constraint puzzle.

Puzzle families (fixed instances):

  * N-Queens for N in {4, 5, 6, 7, 8}.
      Variables q_0 .. q_{N-1}, each q_i in {0, ..., N-1}.
      Constraints:
         - all-different across rows
         - no two queens share a diagonal: q_i - q_j != j - i  and
                                            q_i - q_j != i - j
           for all i < j

  * Graph coloring for fixed graphs:
      - K4 (4 vertices, 6 edges)            with k=3 colors  (3-colorable)
      - Petersen (10 v, 15 e)               with k=3 colors  (3-colorable)
      - Grotzsch (11 v, 20 e)               with k=3 colors  (3-uncolorable)
      - Grotzsch (11 v, 20 e)               with k=4 colors  (4-colorable)

  * Small linear integer system: ABC + DEF = GHIJ in base 10, all digits
    distinct, A,D,G non-zero. (A classic "cryptarithmetic" puzzle.)

For each instance we build two encodings:

  (a) Boolean / SAT-style "table encoding":
        For every (variable, value) pair introduce a Bool x[i][v].
        "Variable i = v" is encoded by x[i][v].
        at-least-one: Or(x[i][v] for v) for each i
        at-most-one:  pairwise Not(And(x[i][v1], x[i][v2])) for v1<v2
        plus per-constraint clauses written as conjunctions of those booleans.

  (b) Native SMT encoding:
        Int variables v[i] with v[i] in [lo, hi] and Distinct(...) / Diseq(...)
        and arithmetic constraints written directly.

We solve each instance, recording variable/constraint counts, encoding
time, and solver time. We also assert the two encodings produce
equivalent (satisifiability / model) results on the same instance.
"""

import json
import time
import csv
import statistics
from itertools import combinations

import z3


# ----------------------------------------------------------------------
# Statistics helpers
# ----------------------------------------------------------------------

def get_stats(solver):
    """Return a dict of Z3 internal statistics. Parses the S-expression repr
    because direct `stats[k]` access is broken for some z3py builds."""
    s = solver.statistics()
    out = {}
    text = repr(s)
    for tok in text.split(":"):
        tok = tok.strip()
        if not tok:
            continue
        # First whitespace-separated word is the key
        parts = tok.split(None, 1)
        if not parts:
            continue
        key = parts[0]
        val = parts[1] if len(parts) > 1 else ""
        try:
            out[key] = int(val)
            continue
        except (TypeError, ValueError):
            pass
        try:
            out[key] = float(val)
            continue
        except (TypeError, ValueError):
            pass
        out[key] = val.strip()
    return out


def count_assertions(solver):
    return len(solver.assertions())


def count_cnf_clauses(solver):
    """Best-effort: get the number of clauses from the SAT solver statistics."""
    st = get_stats(solver)
    return st.get("sat clauses", st.get("clauses", None))


# ----------------------------------------------------------------------
# N-Queens
# ----------------------------------------------------------------------

def nqueens_native(N):
    t0 = time.perf_counter()
    s = z3.Solver()
    q = [z3.Int(f"q_{i}") for i in range(N)]
    s.add([z3.And(q[i] >= 0, q[i] < N) for i in range(N)])
    s.add(z3.Distinct(q))
    for i, j in combinations(range(N), 2):
        s.add(q[i] - q[j] != j - i)
        s.add(q[i] - q[j] != i - j)
    enc_t = time.perf_counter() - t0

    t1 = time.perf_counter()
    res = s.check()
    sol_t = time.perf_counter() - t1
    model = s.model() if res == z3.sat else None
    return {
        "encoding": "native-Int",
        "problem": f"NQueens-{N}",
        "N": N,
        "num_int_vars": N,
        "num_bool_vars": 0,
        "num_assertions": count_assertions(s),
        "encode_time_s": enc_t,
        "solve_time_s": sol_t,
        "result": str(res),
        "model": [model.eval(q[i]).as_long() for i in range(N)] if model else None,
    }


def nqueens_boolean(N):
    """Boolean table encoding for N-Queens.

    x[i][j] = "queen i is in column j", for i, j in 0..N-1.
    At-least-one per row, at-most-one per row, per column, per diagonal.
    """
    t0 = time.perf_counter()
    s = z3.Solver()
    x = [[z3.Bool(f"x_{i}_{j}") for j in range(N)] for i in range(N)]

    A = []
    # Exactly-one per row.
    for i in range(N):
        A.append(z3.Or(x[i]))
        for j1, j2 in combinations(range(N), 2):
            A.append(z3.Not(z3.And(x[i][j1], x[i][j2])))
    # At most one per column.
    for j in range(N):
        col = [x[i][j] for i in range(N)]
        for i1, i2 in combinations(range(N), 2):
            A.append(z3.Not(z3.And(col[i1], col[i2])))
    # At most one per (i-j) and (i+j) diagonals.
    for d in range(-(N - 1), N):
        d1 = [x[i][j] for i in range(N) for j in range(N) if i - j == d]
        for a, b in combinations(range(len(d1)), 2):
            A.append(z3.Not(z3.And(d1[a], d1[b])))
    for s_ in range(2 * N - 1):
        d2 = [x[i][j] for i in range(N) for j in range(N) if i + j == s_]
        for a, b in combinations(range(len(d2)), 2):
            A.append(z3.Not(z3.And(d2[a], d2[b])))

    s.add(A)
    enc_t = time.perf_counter() - t0

    t1 = time.perf_counter()
    res = s.check()
    sol_t = time.perf_counter() - t1
    model = s.model() if res == z3.sat else None
    if model:
        sol = []
        for i in range(N):
            row = [j for j in range(N) if model.evaluate(x[i][j], model_completion=True)]
            sol.append(row[0])
    else:
        sol = None
    return {
        "encoding": "bool-table",
        "problem": f"NQueens-{N}",
        "N": N,
        "num_int_vars": 0,
        "num_bool_vars": N * N,
        "num_assertions": count_assertions(s),
        "encode_time_s": enc_t,
        "solve_time_s": sol_t,
        "result": str(res),
        "model": sol,
    }


# ----------------------------------------------------------------------
# Graph coloring
# ----------------------------------------------------------------------

class Graph:
    def __init__(self, name, edges):
        self.name = name
        self.edges = edges


def k4():
    return Graph("K4", list(combinations(range(4), 2)))


def petersen():
    outer = [(i, (i + 1) % 5) for i in range(5)]
    spokes = [(i, i + 5) for i in range(5)]
    inner = [(5 + i, 5 + (i + 2) % 5) for i in range(5)]
    return Graph("Petersen", outer + spokes + inner)


def grotzsch():
    edges = []
    for i in range(5):
        edges.append((i, (i + 1) % 5))            # outer 5-cycle
    for i in range(5):
        edges.append((5 + i, 5 + (i + 1) % 5))    # inner 5-cycle
    for i in range(5):
        edges.append((10, 5 + i))                 # vertex 10 -> all inner
    for i in range(5):
        edges.append((i, 5 + i))                  # spokes
    return Graph("Grotzsch", edges)


def coloring_native(graph, k):
    n = max(max(i, j) for (i, j) in graph.edges) + 1
    t0 = time.perf_counter()
    s = z3.Solver()
    v = [z3.Int(f"v_{i}") for i in range(n)]
    s.add([z3.And(v[i] >= 0, v[i] < k) for i in range(n)])
    s.add([v[i] != v[j] for (i, j) in graph.edges])
    enc_t = time.perf_counter() - t0

    t1 = time.perf_counter()
    res = s.check()
    sol_t = time.perf_counter() - t1
    model = s.model() if res == z3.sat else None
    return {
        "encoding": "native-Int",
        "problem": f"Coloring-{graph.name}-k{k}",
        "N": n,
        "k": k,
        "num_int_vars": n,
        "num_bool_vars": 0,
        "num_assertions": count_assertions(s),
        "encode_time_s": enc_t,
        "solve_time_s": sol_t,
        "result": str(res),
        "model": [model.eval(v[i]).as_long() for i in range(n)] if model else None,
    }


def coloring_boolean(graph, k):
    n = max(max(i, j) for (i, j) in graph.edges) + 1
    t0 = time.perf_counter()
    s = z3.Solver()
    x = [[z3.Bool(f"x_{i}_{c}") for c in range(k)] for i in range(n)]

    A = []
    for i in range(n):
        A.append(z3.Or(x[i]))
        for c1, c2 in combinations(range(k), 2):
            A.append(z3.Not(z3.And(x[i][c1], x[i][c2])))
    for (i, j) in graph.edges:
        for c in range(k):
            A.append(z3.Not(z3.And(x[i][c], x[j][c])))

    s.add(A)
    enc_t = time.perf_counter() - t0

    t1 = time.perf_counter()
    res = s.check()
    sol_t = time.perf_counter() - t1
    model = s.model() if res == z3.sat else None
    sol = None
    if model:
        sol = []
        for i in range(n):
            row = [c for c in range(k) if model.evaluate(x[i][c], model_completion=True)]
            sol.append(row[0])
    return {
        "encoding": "bool-table",
        "problem": f"Coloring-{graph.name}-k{k}",
        "N": n,
        "k": k,
        "num_int_vars": 0,
        "num_bool_vars": n * k,
        "num_assertions": count_assertions(s),
        "encode_time_s": enc_t,
        "solve_time_s": sol_t,
        "result": str(res),
        "model": sol,
    }


# ----------------------------------------------------------------------
# Cryptarithmetic / linear integer system:  ABC + DEF = GHIJ  (base 10)
# ----------------------------------------------------------------------

def linsys_native():
    A, B, C, D, E, F, G, H, I, J = z3.Ints("A B C D E F G H I J")
    t0 = time.perf_counter()
    s = z3.Solver()
    s.add([z3.And(v >= 0, v <= 9) for v in (A, B, C, D, E, F, G, H, I, J)])
    s.add(A != 0, D != 0, G != 0)
    s.add(z3.Distinct(A, B, C, D, E, F, G, H, I, J))
    s.add(100 * A + 10 * B + C + 100 * D + 10 * E + F ==
          1000 * G + 100 * H + 10 * I + J)
    enc_t = time.perf_counter() - t0

    t1 = time.perf_counter()
    res = s.check()
    sol_t = time.perf_counter() - t1
    model = s.model() if res == z3.sat else None
    return {
        "encoding": "native-Int",
        "problem": "ABC+DEF=GHIJ",
        "num_int_vars": 10,
        "num_bool_vars": 0,
        "num_assertions": count_assertions(s),
        "encode_time_s": enc_t,
        "solve_time_s": sol_t,
        "result": str(res),
        "model": {str(v): model.eval(v).as_long() for v in
                  (A, B, C, D, E, F, G, H, I, J)} if model else None,
    }


def linsys_boolean():
    """Boolean table encoding of ABC + DEF = GHIJ, all-different digits.

    For every (letter, digit) we make a Bool x[n][d]. The linear relation is
    encoded as a single pseudo-Boolean equality: sum over the contributions
    equals 0. This is a standard SAT-style encoding of linear integer
    constraints (sometimes called "bit/enumeration" or "table+PbEq" encoding).
    """
    t0 = time.perf_counter()
    s = z3.Solver()
    names = "ABCDEFGHIJ"
    x = {n: [z3.Bool(f"x_{n}_{d}") for d in range(10)] for n in names}
    A = []
    # Exactly-one digit per letter.
    for n in names:
        A.append(z3.Or(x[n]))
        for d1, d2 in combinations(range(10), 2):
            A.append(z3.Not(z3.And(x[n][d1], x[n][d2])))
    # All-different across letters.
    for d in range(10):
        for n1, n2 in combinations(names, 2):
            A.append(z3.Not(z3.And(x[n1][d], x[n2][d])))
    # A, D, G != 0.
    for n in ("A", "D", "G"):
        A.append(z3.Or([x[n][d] for d in range(1, 10)]))
    # Linear relation: ABC + DEF == GHIJ  i.e.
    # 100A + 10B + C + 100D + 10E + F - 1000G - 100H - 10I - J == 0
    def pos(n, k):
        return [(x[n][d], d * (10 ** k)) for d in range(10)]

    def neg(n, k):
        return [(x[n][d], -d * (10 ** k)) for d in range(10)]

    coeffs = (pos("A", 2) + pos("B", 1) + pos("C", 0) +
              pos("D", 2) + pos("E", 1) + pos("F", 0) +
              neg("G", 3) + neg("H", 2) + neg("I", 1) + neg("J", 0))
    A.append(z3.PbEq(coeffs, 0))
    s.add(A)
    enc_t = time.perf_counter() - t0

    t1 = time.perf_counter()
    res = s.check()
    sol_t = time.perf_counter() - t1
    model = s.model() if res == z3.sat else None
    sol = None
    if model:
        sol = {}
        for n in names:
            for d in range(10):
                if model.evaluate(x[n][d], model_completion=True):
                    sol[n] = d
                    break
    return {
        "encoding": "bool-table",
        "problem": "ABC+DEF=GHIJ",
        "num_int_vars": 0,
        "num_bool_vars": 10 * 10,
        "num_assertions": count_assertions(s),
        "encode_time_s": enc_t,
        "solve_time_s": sol_t,
        "result": str(res),
        "model": sol,
    }


# ----------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------

def cross_check(nat_row, bool_row):
    if nat_row["result"] != bool_row["result"]:
        return False, f"status mismatch: native={nat_row['result']} bool={bool_row['result']}"
    if nat_row["result"] != "sat":
        return True, "both unsat/unknown"
    nm, bm = nat_row["model"], bool_row["model"]
    if isinstance(nm, list) and isinstance(bm, list) and nm != bm:
        return False, f"models differ: native={nm} bool={bm}"
    if isinstance(nm, dict) and isinstance(bm, dict) and nm != bm:
        return False, f"models differ: native={nm} bool={bm}"
    return True, "models agree"


def main():
    rows = []
    print("== N-Queens ==")
    for N in (4, 5, 6, 7, 8):
        a = nqueens_native(N)
        b = nqueens_boolean(N)
        ok, msg = cross_check(a, b)
        rows += [a, b]
        print(f"  N={N}  native int={a['num_int_vars']} asr={a['num_assertions']} "
              f"enc={a['encode_time_s']*1000:.2f}ms sol={a['solve_time_s']*1000:.2f}ms "
              f"res={a['result']} | bool vars={b['num_bool_vars']} asr={b['num_assertions']} "
              f"enc={b['encode_time_s']*1000:.2f}ms sol={b['solve_time_s']*1000:.2f}ms "
              f"res={b['result']} | {msg}")

    print("== Graph coloring ==")
    instances = [
        (k4(), 3),
        (petersen(), 3),
        (grotzsch(), 3),
        (grotzsch(), 4),
    ]
    for graph, k in instances:
        a = coloring_native(graph, k)
        b = coloring_boolean(graph, k)
        ok, msg = cross_check(a, b)
        rows += [a, b]
        print(f"  {graph.name} k={k}  native n={a['num_int_vars']} asr={a['num_assertions']} "
              f"enc={a['encode_time_s']*1000:.2f}ms sol={a['solve_time_s']*1000:.2f}ms "
              f"res={a['result']} | bool vars={b['num_bool_vars']} asr={b['num_assertions']} "
              f"enc={b['encode_time_s']*1000:.2f}ms sol={b['solve_time_s']*1000:.2f}ms "
              f"res={b['result']} | {msg}")

    print("== ABC+DEF=GHIJ ==")
    a = linsys_native()
    b = linsys_boolean()
    ok, msg = cross_check(a, b)
    rows += [a, b]
    print(f"  native int={a['num_int_vars']} asr={a['num_assertions']} "
          f"enc={a['encode_time_s']*1000:.2f}ms sol={a['solve_time_s']*1000:.2f}ms "
          f"res={a['result']} model={a['model']} | bool vars={b['num_bool_vars']} "
          f"asr={b['num_assertions']} enc={b['encode_time_s']*1000:.2f}ms "
          f"sol={b['solve_time_s']*1000:.2f}ms res={b['result']} model={b['model']} | {msg}")

    # Persist
    with open("results/raw.json", "w") as f:
        json.dump(rows, f, indent=2, default=str)
    keys = ["encoding", "problem", "N", "k", "num_int_vars", "num_bool_vars",
            "num_assertions", "encode_time_s", "solve_time_s", "result"]
    with open("results/summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("\nWrote results/raw.json and results/summary.csv")


if __name__ == "__main__":
    main()
