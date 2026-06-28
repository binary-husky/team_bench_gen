#!/usr/bin/env python3
"""Supplementary scaling sweep: larger n to reveal the CDCL vs DPLL gap.
Labeled supplementary (not part of the fixed n in {15,20,25} spec)."""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from experiment import gen_instance, write_dimacs, naive_dpll, minisat_solve, INST_DIR, ALPHA

HERE = os.path.dirname(os.path.abspath(__file__))
NS = [30, 40, 50, 60]
SEEDS = [0, 1, 2]
TIMEOUT = 30.0  # shorter to bound total wall time

# monkeypatch TIMEOUT used by minisat watchdog via re-import isn't trivial;
# minisat_solve uses module-global TIMEOUT from experiment. Override it.
import experiment as E
E.TIMEOUT = TIMEOUT


def main():
    results = []
    for n in NS:
        m = round(ALPHA * n)
        for seed in SEEDS:
            clauses = gen_instance(n, m, seed)
            tag = f"n{n}_m{m}_s{seed}"
            write_dimacs(os.path.join(INST_DIR, f"{tag}.cnf"), n, clauses)
            deadline = time.time() + TIMEOUT
            d = naive_dpll(n, clauses, deadline)
            # minisat with 30s budget
            mr = minisat_solve(n, clauses)
            rec = {"tag": tag, "n": n, "m": m, "seed": seed,
                   "dpll": d, "minisat": mr}
            results.append(rec)
            print(f"[{tag}] DPLL: dec={d['decisions']} t={d['time']:.2f}s "
                  f"sat={d['sat']} TO={d['timed_out']} | "
                  f"MiniSAT: conf={mr['conflicts']} dec={mr['decisions']} "
                  f"t={mr['time']:.3f}s sat={mr['sat']} TO={mr['timed_out']}",
                  flush=True)
    with open(os.path.join(HERE, "results_supp.json"), "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved results_supp.json")


if __name__ == "__main__":
    main()
