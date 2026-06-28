"""Run the symbolic-execution experiment described in task.md.

For each toy function and >=3 seeds, record:
  (a) number of generated test inputs,
  (b) number of distinct feasible execution paths,
  (c) branch coverage.
"""
import json
import sys
import statistics

from symexec import enumerate_paths, branch_coverage

# ---------------------------------------------------------------------------
# Toy functions (path complexity increases). Plain Python using only the AST
# subset the engine understands (arithmetic, comparisons, bool ops, if/elif/else,
# return).
# ---------------------------------------------------------------------------

GET_SIGN_SRC = """
def get_sign(x):
    if x < 0:
        return -1
    if x == 0:
        return 0
    return 1
"""

# get_sign written as elif chain is equivalent in path count; use nested ifs
# above so the engine sees 2 If nodes (x<0) and (x==0). Feasible paths: 3
# (x<0 ; x>=0 & x==0 ; x>=0 & x!=0).

CLASSIFY_SRC = """
def classify_triangle(a, b, c):
    if a + b <= c or a + c <= b or b + c <= a:
        return 0
    if a == b and b == c:
        return 3
    if a == b or b == c or a == c:
        return 2
    return 1
"""

def k_indep_src(k):
    """k mutually independent ifs over independent symbolic inputs x1..xk.
    Each if is satisfiable both ways independently -> 2^k feasible paths."""
    args = ", ".join(f"x{i}" for i in range(1, k + 1))
    body_lines = [f"    r = 0"]
    for i in range(1, k + 1):
        body_lines.append(f"    if x{i} > 0:")
        body_lines.append(f"        r = r + {2**(i-1)}")
    body_lines.append(f"    return r")
    return f"def k_independent_ifs_{k}({args}):\n" + "\n".join(body_lines) + "\n"


FUNCTIONS = [
    ("get_sign", GET_SIGN_SRC, ["x"]),
    ("classify_triangle", CLASSIFY_SRC, ["a", "b", "c"]),
]
for k in (2, 3, 4, 5):
    name = f"k_independent_ifs_{k}"
    FUNCTIONS.append((name, k_indep_src(k), [f"x{i}" for i in range(1, k + 1)]))


def run_one(name, src, args, seed):
    se = enumerate_paths(src, name, args, seed=seed)
    n_tests = len(se.tests)
    n_paths = len(se.paths)
    covered, total, cov = branch_coverage(se)
    return {
        "function": name,
        "seed": seed,
        "n_tests": n_tests,
        "n_paths": n_paths,
        "branches_covered": covered,
        "branches_total": total,
        "branch_coverage": cov,
        "tests": se.tests,
    }


def main():
    seeds = [1, 7, 42]
    rows = []
    for name, src, args in FUNCTIONS:
        for seed in seeds:
            r = run_one(name, src, args, seed)
            r["source"] = src
            rows.append(r)
            print(f"{name:22s} seed={seed:<3d} tests={r['n_tests']:>3d} "
                  f"paths={r['n_paths']:>3d} "
                  f"br={r['branches_covered']}/{r['branches_total']} "
                  f"cov={r['branch_coverage']*100:.1f}%")
        # aggregate across seeds
        tests_vals = [r["n_tests"] for r in rows if r["function"] == name]
        path_vals = [r["n_paths"] for r in rows if r["function"] == name]
        cov_vals = [r["branch_coverage"] for r in rows if r["function"] == name]
        agg = {
            "function": name,
            "tests_mean": statistics.mean(tests_vals),
            "tests_all": tests_vals,
            "paths_mean": statistics.mean(path_vals),
            "paths_all": path_vals,
            "cov_mean": statistics.mean(cov_vals),
            "cov_all": cov_vals,
        }
        # attach aggregate to last row of this function for convenience
        rows = [r if r["function"] != name else dict(r, **({}) if r["seed"] != seeds[-1] else agg) for r in rows]

    out = {
        "seeds": seeds,
        "functions": [{"name": n, "args": a, "source": s} for n, s, a in FUNCTIONS],
        "runs": rows,
    }
    with open("experiment_results.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("\nWrote experiment_results.json")


if __name__ == "__main__":
    main()
