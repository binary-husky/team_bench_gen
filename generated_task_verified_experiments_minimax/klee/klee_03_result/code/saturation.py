"""
Saturation experiment: how branch coverage grows as we explore more paths.

This complements the main experiment.  It shows that branch coverage
saturates to 100% as we keep enumerating paths.  For each function we
process paths in order and record the branch coverage after each
additional path.
"""
import json
import z3
import random
from typing import List, Dict, Tuple, Set

from symex import (SymbolicState, make_inputs, explore_get_sign,
                   explore_classify_triangle, explore_k_independent_ifs,
                   solve_state, get_sign_concrete, classify_triangle_concrete,
                   k_independent_ifs_concrete)


def partial_branch_coverage(paths_chosen, total_branches):
    covered = set()
    for p in paths_chosen:
        covered.update(p)
    return len(covered) / (total_branches * 2) * 100


def explore_with_order(initial, explore_func, order_seed):
    """Explore all paths but return them in a randomized order."""
    all_states = []

    def dfs(state):
        for nxt in explore_func(state):
            if nxt.terminated:
                all_states.append(nxt)
            else:
                dfs(nxt)

    dfs(initial)
    random.Random(order_seed).shuffle(all_states)
    return all_states


def main():
    rows = []
    runs = [
        ("get_sign", explore_get_sign, ["x"], (-1000, 1000), 2),
        ("classify_triangle", explore_classify_triangle, ["a", "b", "c"],
         (-100, 100), 4),
        ("k_independent_ifs_k4",
         lambda st: explore_k_independent_ifs(st, 4),
         [f"x{i+1}" for i in range(4)], (-1000, 1000), 4),
        ("k_independent_ifs_k5",
         lambda st: explore_k_independent_ifs(st, 5),
         [f"x{i+1}" for i in range(5)], (-1000, 1000), 5),
    ]

    for name, exp, inames, dom, nb in runs:
        ivars, idoms = make_inputs(inames, dom)
        for s in [42, 123, 7]:
            states = explore_with_order(SymbolicState(ivars, idoms), exp, s)
            chosen = []
            for st in states:
                chosen.append(st.path)
                cov = partial_branch_coverage(chosen, nb)
                rows.append({
                    "function": name,
                    "seed": s,
                    "paths_explored": len(chosen),
                    "total_paths": len(states),
                    "branch_coverage_pct": cov,
                })

    with open("saturation.json", "w") as f:
        json.dump(rows, f, indent=2)

    # Print the saturation curve.
    print("Branch-coverage saturation:")
    print(f"{'function':<26} {'seed':>4} {'paths':>6}/{'total':<6} {'branch_cov':>10}")
    for r in rows:
        print(f"{r['function']:<26} {r['seed']:>4} "
              f"{r['paths_explored']:>6}/{r['total_paths']:<6} "
              f"{r['branch_coverage_pct']:>9.2f}%")
    return rows


if __name__ == "__main__":
    main()
