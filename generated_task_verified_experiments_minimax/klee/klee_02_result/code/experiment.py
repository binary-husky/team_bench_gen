"""Main experiment driver: symbolic execution vs. random testing.

Per the task brief:

  * Both methods are repeated for at least three different seeds.
  * Random testing uses at least 1 000 inputs per seed.
  * We report branch coverage (and whether the magic branch is hit) for
    every (method, seed) combination, plus an aggregate row that unions
    the edges hit across all seeds of the same method.

The driver writes a JSON dump of every per-seed measurement to
``results.json`` and prints a Markdown table on stdout -- the latter is
copied verbatim into the summary report.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import target
import symex
import random_test


# ---------------------------------------------------------------- constants
SEEDS = [42, 123, 9999]                       # >= 3 different seeds
NUM_RANDOM_INPUTS = 1000                       # >= 1000 per task brief
X_RANGE = (-1_000_000, 2_000_000)              # 3 000 001 values, magic=12345


# -------------------------------------------------------------- per-run data
@dataclass
class MethodRun:
    method: str          # "SymEx" or "Random"
    seed: int
    num_inputs: int
    coverage_pct: float
    hit_magic: bool
    edges_hit: list      # list[[branch_id, taken_bool]]
    edges_missed: list
    elapsed_ms: float
    extra: dict | None = None  # method-specific details


# --------------------------------------------------------------- measurement
def _edges(tracker: target.BranchTracker) -> tuple[list, list]:
    hit = sorted(list(tracker.edges_hit()))
    miss = sorted(list(tracker.edges_missed()))
    return [list(e) for e in hit], [list(e) for e in miss]


def run_symex(seed: int) -> MethodRun:
    t0 = time.perf_counter()
    inputs, tracker, paths = symex.run_and_measure(
        x_range=X_RANGE, seed=seed
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    hit, miss = _edges(tracker)
    return MethodRun(
        method="SymEx",
        seed=seed,
        num_inputs=len(inputs),
        coverage_pct=round(tracker.coverage_fraction() * 100, 2),
        hit_magic=tracker.hit_magic(),
        edges_hit=hit,
        edges_missed=miss,
        elapsed_ms=round(elapsed_ms, 2),
        extra={"paths_enumerated": len(paths)},
    )


def run_random(seed: int) -> MethodRun:
    t0 = time.perf_counter()
    rr = random_test.run(
        num_inputs=NUM_RANDOM_INPUTS, seed=seed, x_range=X_RANGE
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    hit, miss = _edges(rr.tracker)
    return MethodRun(
        method="Random",
        seed=seed,
        num_inputs=rr.num_inputs,
        coverage_pct=round(rr.tracker.coverage_fraction() * 100, 2),
        hit_magic=rr.tracker.hit_magic(),
        edges_hit=hit,
        edges_missed=miss,
        elapsed_ms=round(elapsed_ms, 2),
    )


def aggregate(method: str, runs: list[MethodRun]) -> MethodRun:
    """Union-coverage across all seeds of the same method."""
    union_hit: set[tuple[str, bool]] = set()
    total_inputs = 0
    hit_magic = False
    for r in runs:
        for branch_id, taken in r.edges_hit:
            union_hit.add((branch_id, taken))
        total_inputs += r.num_inputs
        hit_magic = hit_magic or r.hit_magic
    all_edges = {(b, t) for b in target.ALL_BRANCHES for t in (True, False)}
    coverage_pct = round(100 * len(union_hit) / len(all_edges), 2)
    return MethodRun(
        method=method,
        seed=-1,                                # sentinel for "aggregate"
        num_inputs=total_inputs,
        coverage_pct=coverage_pct,
        hit_magic=hit_magic,
        edges_hit=[list(e) for e in sorted(union_hit)],
        edges_missed=[list(e) for e in sorted(all_edges - union_hit)],
        elapsed_ms=round(sum(r.elapsed_ms for r in runs), 2),
        extra={"seeds": [r.seed for r in runs]},
    )


# ------------------------------------------------------------------ driver
def main() -> None:
    print("Running experiment with seeds:", SEEDS)
    print(f"Input range: {X_RANGE}, random inputs per seed: {NUM_RANDOM_INPUTS}\n")

    sym_runs: list[MethodRun] = []
    rand_runs: list[MethodRun] = []

    print("--- Symbolic execution ---")
    for s in SEEDS:
        r = run_symex(s)
        sym_runs.append(r)
        print(
            f"  seed={s:<6} paths={r.extra['paths_enumerated']:<3} "
            f"inputs={r.num_inputs:<3} coverage={r.coverage_pct:>6.2f}% "
            f"magic={'Y' if r.hit_magic else 'N'}  t={r.elapsed_ms:.2f}ms"
        )

    print("\n--- Random testing ---")
    for s in SEEDS:
        r = run_random(s)
        rand_runs.append(r)
        print(
            f"  seed={s:<6} inputs={r.num_inputs:<5} "
            f"coverage={r.coverage_pct:>6.2f}% "
            f"magic={'Y' if r.hit_magic else 'N'}  t={r.elapsed_ms:.2f}ms"
        )

    # aggregate
    sym_agg = aggregate("SymEx", sym_runs)
    rand_agg = aggregate("Random", rand_runs)

    print("\n--- Aggregate across all seeds ---")
    print(
        f"  SymEx  (3 seeds) -> {sym_agg.num_inputs} inputs total, "
        f"coverage={sym_agg.coverage_pct:>6.2f}%, magic={sym_agg.hit_magic}"
    )
    print(
        f"  Random (3 seeds) -> {rand_agg.num_inputs} inputs total, "
        f"coverage={rand_agg.coverage_pct:>6.2f}%, magic={rand_agg.hit_magic}"
    )

    # Markdown table -- this is the table that goes into the summary.
    md_table = build_markdown_table(sym_runs, rand_runs, sym_agg, rand_agg)
    print("\n" + md_table)

    # Persist raw results for later analysis.
    payload = {
        "config": {
            "seeds": SEEDS,
            "num_random_inputs": NUM_RANDOM_INPUTS,
            "x_range": list(X_RANGE),
            "all_branches": target.ALL_BRANCHES,
            "magic_branch": target.MAGIC_BRANCH,
            "magic_value": 12345,
        },
        "symex": [asdict(r) for r in sym_runs] + [asdict(sym_agg)],
        "random": [asdict(r) for r in rand_runs] + [asdict(rand_agg)],
    }
    Path("results.json").write_text(json.dumps(payload, indent=2))
    print("\nWrote results.json")
    return md_table, payload


def build_markdown_table(
    sym_runs: list[MethodRun],
    rand_runs: list[MethodRun],
    sym_agg: MethodRun,
    rand_agg: MethodRun,
) -> str:
    lines = []
    lines.append("| Method | Seed | #Inputs | Branch coverage | Hit magic branch (B0-true) |")
    lines.append("|--------|------|---------|-----------------|---------------------------|")
    for r in sym_runs:
        lines.append(
            f"| SymEx  | {r.seed} | {r.num_inputs} | {r.coverage_pct:.2f}% "
            f"| {'**Yes**' if r.hit_magic else 'No'} |"
        )
    for r in rand_runs:
        lines.append(
            f"| Random | {r.seed} | {r.num_inputs} | {r.coverage_pct:.2f}% "
            f"| {'**Yes**' if r.hit_magic else 'No'} |"
        )
    lines.append(
        f"| **SymEx (agg.)**  | – | {sym_agg.num_inputs} | "
        f"**{sym_agg.coverage_pct:.2f}%** "
        f"| {'**Yes**' if sym_agg.hit_magic else 'No'} |"
    )
    lines.append(
        f"| **Random (agg.)** | – | {rand_agg.num_inputs} | "
        f"**{rand_agg.coverage_pct:.2f}%** "
        f"| {'**Yes**' if rand_agg.hit_magic else 'No'} |"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
