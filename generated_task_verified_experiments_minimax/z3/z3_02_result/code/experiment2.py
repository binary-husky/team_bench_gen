"""
More instances: N-Queens N=13..16, harder coloring, and capture
Z3's internal SAT solver statistics so we can see what the encodings
produce internally.
"""

import json
import time
import csv
import statistics
from itertools import combinations

import z3

from experiment import (
    nqueens_native, nqueens_boolean,
    coloring_native, coloring_boolean,
    linsys_native, linsys_boolean,
    k4, petersen, grotzsch,
    count_assertions, get_stats,
    Graph,
)

import random


def erdos_renyi(n, p, seed):
    random.seed(seed)
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            if random.random() < p:
                edges.append((i, j))
    return Graph(f"ER-{n}-{p}-{seed}", edges)


def main():
    rows = []
    print("== N-Queens N=13..16 ==")
    for N in (13, 14, 15, 16):
        a = nqueens_native(N)
        b = nqueens_boolean(N)
        rows += [a, b]
        print(f"  N={N}  native asr={a['num_assertions']} "
              f"enc={a['encode_time_s']*1000:.2f}ms sol={a['solve_time_s']*1000:.2f}ms "
              f"res={a['result']} | bool vars={b['num_bool_vars']} asr={b['num_assertions']} "
              f"enc={b['encode_time_s']*1000:.2f}ms sol={b['solve_time_s']*1000:.2f}ms "
              f"res={b['result']}")

    print("== Heavier graph coloring ==")
    extra = [
        (erdos_renyi(30, 0.3, 1), 5),
        (erdos_renyi(40, 0.2, 4), 5),
        (erdos_renyi(40, 0.2, 4), 4),  # likely unsat
        (erdos_renyi(50, 0.2, 5), 6),
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

    # Median over 5 runs to reduce noise on a small N-Queens instance.
    print("== Median over 5 runs (N=10) ==")
    nat_solves = []
    bool_solves = []
    nat_encs = []
    bool_encs = []
    for _ in range(5):
        a = nqueens_native(10)
        b = nqueens_boolean(10)
        nat_solves.append(a["solve_time_s"])
        bool_solves.append(b["solve_time_s"])
        nat_encs.append(a["encode_time_s"])
        bool_encs.append(b["encode_time_s"])
    print(f"  native  encode median: {statistics.median(nat_encs)*1000:.2f}ms  "
          f"solve median: {statistics.median(nat_solves)*1000:.2f}ms")
    print(f"  boolean encode median: {statistics.median(bool_encs)*1000:.2f}ms  "
          f"solve median: {statistics.median(bool_solves)*1000:.2f}ms")
    medians = {
        "problem": "NQueens-10 (median over 5 runs)",
        "native_encode_ms": statistics.median(nat_encs) * 1000,
        "native_solve_ms": statistics.median(nat_solves) * 1000,
        "bool_encode_ms": statistics.median(bool_encs) * 1000,
        "bool_solve_ms": statistics.median(bool_solves) * 1000,
    }
    with open("results/medians.json", "w") as f:
        json.dump(medians, f, indent=2)

    with open("results/extended2.json", "w") as f:
        json.dump(rows, f, indent=2, default=str)
    keys = ["encoding", "problem", "N", "k", "num_int_vars", "num_bool_vars",
            "num_assertions", "encode_time_s", "solve_time_s", "result"]
    with open("results/extended2.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("Wrote results/extended2.{json,csv}")


if __name__ == "__main__":
    main()
