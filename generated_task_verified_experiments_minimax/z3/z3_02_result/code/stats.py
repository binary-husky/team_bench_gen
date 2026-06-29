"""
Run a smaller comparison capturing Z3's internal SAT solver statistics
to peek at what each encoding produces under the hood.
"""

import json
import time
from itertools import combinations

import z3

from experiment import (
    nqueens_native, nqueens_boolean,
    get_stats,
)


def main():
    out = {}
    for N in (4, 6, 8, 10, 12):
        s = z3.Solver()
        q = [z3.Int(f"q_{i}") for i in range(N)]
        s.add([z3.And(q[i] >= 0, q[i] < N) for i in range(N)])
        s.add(z3.Distinct(q))
        for i, j in combinations(range(N), 2):
            s.add(q[i] - q[j] != j - i)
            s.add(q[i] - q[j] != i - j)
        s.check()
        out[f"native-NQueens-{N}"] = get_stats(s)

        s = z3.Solver()
        x = [[z3.Bool(f"x_{i}_{j}") for j in range(N)] for i in range(N)]
        A = []
        for i in range(N):
            A.append(z3.Or(x[i]))
            for j1, j2 in combinations(range(N), 2):
                A.append(z3.Not(z3.And(x[i][j1], x[i][j2])))
        for j in range(N):
            col = [x[i][j] for i in range(N)]
            for i1, i2 in combinations(range(N), 2):
                A.append(z3.Not(z3.And(col[i1], col[i2])))
        for d in range(-(N - 1), N):
            d1 = [x[i][j] for i in range(N) for j in range(N) if i - j == d]
            for a, b in combinations(range(len(d1)), 2):
                A.append(z3.Not(z3.And(d1[a], d1[b])))
        for s_ in range(2 * N - 1):
            d2 = [x[i][j] for i in range(N) for j in range(N) if i + j == s_]
            for a, b in combinations(range(len(d2)), 2):
                A.append(z3.Not(z3.And(d2[a], d2[b])))
        s.add(A)
        s.check()
        out[f"bool-NQueens-{N}"] = get_stats(s)

    with open("results/stats.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
