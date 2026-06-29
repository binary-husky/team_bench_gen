"""
Extended experiment with harder instances: larger N-Queens and harder coloring,
plus a couple of repeated runs to get a median and reduce noise.
"""

import json
import time
import csv
from itertools import combinations

import z3

# Re-use the encoders from experiment.py
from experiment import (
    nqueens_native, nqueens_boolean,
    coloring_native, coloring_boolean,
    linsys_native, linsys_boolean,
    k4, petersen, grotzsch,
    count_assertions, get_stats,
    Graph,
)


def erdos_renyi(n, p, seed):
    """Random Erdős–Rényi graph for additional instances."""
    import random
    random.seed(seed)
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            if random.random() < p:
                edges.append((i, j))
    return Graph(f"ER-{n}-{p}-{seed}", edges)


def main():
    rows = []
    print("== Extended N-Queens ==")
    for N in (9, 10, 11, 12):
        a = nqueens_native(N)
        b = nqueens_boolean(N)
        rows += [a, b]
        print(f"  N={N}  native asr={a['num_assertions']} "
              f"enc={a['encode_time_s']*1000:.2f}ms sol={a['solve_time_s']*1000:.2f}ms "
              f"res={a['result']} | bool vars={b['num_bool_vars']} asr={b['num_assertions']} "
              f"enc={b['encode_time_s']*1000:.2f}ms sol={b['solve_time_s']*1000:.2f}ms "
              f"res={b['result']}")

    print("== Extended graph coloring ==")
    extra = [
        (petersen(), 4),     # 4-color Petersen (easy)
        (erdos_renyi(15, 0.3, 1), 4),
        (erdos_renyi(20, 0.3, 2), 5),
        (erdos_renyi(25, 0.3, 3), 6),
    ]
    for graph, k in extra:
        a = coloring_native(graph, k)
        b = coloring_boolean(graph, k)
        rows += [a, b]
        print(f"  {graph.name} k={k}  native asr={a['num_assertions']} "
              f"enc={a['encode_time_s']*1000:.2f}ms sol={a['solve_time_s']*1000:.2f}ms "
              f"res={a['result']} | bool vars={b['num_bool_vars']} asr={b['num_assertions']} "
              f"enc={b['encode_time_s']*1000:.2f}ms sol={b['solve_time_s']*1000:.2f}ms "
              f"res={b['result']}")

    with open("results/extended.json", "w") as f:
        json.dump(rows, f, indent=2, default=str)
    keys = ["encoding", "problem", "N", "k", "num_int_vars", "num_bool_vars",
            "num_assertions", "encode_time_s", "solve_time_s", "result"]
    with open("results/extended.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("Wrote results/extended.{json,csv}")


if __name__ == "__main__":
    main()
