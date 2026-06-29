"""
Bit-Vector (BV) fixed-width arithmetic property verification with z3.

We test a fixed set of BV properties on n-bit (default: 8) unsigned bit-vectors:

  Core properties (the three the task explicitly asks for):
    (a) SAT — exists x, y s.t. unsigned x + y causes wrap-around overflow
                (ULT(x + y, x) ∧ y ≠ 0)
    (b) UNSAT (proved) — for all x, y: (x + y) − y == x
                (assert the negation  ¬((x + y) − y == x)  →  expect UNSAT)
    (c) SAT — exists x, y s.t. unsigned x * y causes wrap-around overflow
                (ULT(x * y, x) ∧ y ≠ 0)

  Extra cross-checks (same fixed width, same z3 settings) so the summary has
  something to talk about beyond the bare minimum:
    (d) UNSAT (proved) — for all x, y: (x * y) == (y * x)            (commutativity)
    (e) SAT — exists x, y: (x * y) == 0  with  x ≠ 0  ∧  y ≠ 0
    (f) UNSAT (proved) — for all x: (x ^ x) == 0                       (self-XOR is 0)
    (g) UNSAT (proved) — for all x, y: (x | y) >= x                   (OR-monotonicity)

z3 settings (kept fixed for every query — no per-property tuning):
  - timeout  : 30 000 ms
  - seed     : 0xC0FFEE
  - tactics  : z3's default QF_BV tactics
  - parallel : off (single-threaded, reproducible)
"""

import json
import time
from z3 import (
    BitVec, Solver, ULT, UGE, Not, sat, unsat,
    set_param,
)

# --- fixed configuration ---------------------------------------------------
WIDTH = 8                    # fixed bit-width for the experiment
TIMEOUT_MS = 30_000          # per-query wall-clock budget
REPEAT = 3                   # repeated runs to make timing less noisy
SEED = 0xC0FFEE              # fixed z3 seed
LOG_PATH = "results.json"

# Use the same fixed settings for every query (no per-property tuning).
set_param("timeout", TIMEOUT_MS)
set_param("smt.random_seed", SEED)


def timed_check(solver: Solver, label: str):
    """Run solver.check() under a wall-clock timer; return (result, model, secs)."""
    t0 = time.perf_counter()
    res = solver.check()
    elapsed = time.perf_counter() - t0
    model = None
    if res == sat:
        model = solver.model()
    print(f"  [{label}] check() -> {res}  in {elapsed*1000:.3f} ms")
    return res, model, elapsed


def model_bv(m, v):
    val = m.eval(v, model_completion=True)
    return None if val is None else val.as_long()


def make_solver():
    s = Solver()
    s.set("timeout", TIMEOUT_MS)
    return s


# --- the seven BV properties ---------------------------------------------

def property_a_add_overflow(width: int) -> dict:
    """(a) Find x, y BV(n) s.t. unsigned x + y wraps around 2^width."""
    x = BitVec("x", width)
    y = BitVec("y", width)
    s = make_solver()
    # ULT(x + y, x)  ↔  y > 0 and addition wrapped past 2^width
    s.add(ULT(x + y, x))
    s.add(y != 0)
    res, m, secs = timed_check(s, "a: add overflow")
    out = {
        "id": "a",
        "name": "add overflow exists",
        "formula": "∃x,y: y ≠ 0 ∧ ULT(x + y, x)",
        "interpretation": "Find x,y s.t. unsigned x+y wraps (counterexample search).",
        "kind": "find_counterexample",
        "width": width,
        "result": str(res),
        "expected": "sat",
        "counterexample": None,
        "elapsed_sec": secs,
    }
    if res == sat and m is not None:
        xv, yv = model_bv(m, x), model_bv(m, y)
        out["counterexample"] = {"x": xv, "y": yv}
        out["verifies"] = (xv + yv) % (1 << width) == (xv + yv) & ((1 << width) - 1) and \
                          ((xv + yv) >= (1 << width))  # mathematical check
    return out


def property_b_add_inverse(width: int) -> dict:
    """(b) Prove for all x, y: (x + y) − y == x.  Negate, expect UNSAT."""
    x = BitVec("x", width)
    y = BitVec("y", width)
    s = make_solver()
    # assert the negation  ¬((x + y) − y == x)  — expect UNSAT (proved)
    s.add(Not((x + y) - y == x))
    res, m, secs = timed_check(s, "b: add inverse (negation)")
    out = {
        "id": "b",
        "name": "add inverse identity",
        "formula": "∀x,y: (x + y) − y == x   (verified by ¬formula → UNSAT)",
        "interpretation": "Prove the modular-arithmetic identity (x+y)−y = x for all x,y.",
        "kind": "prove",
        "width": width,
        "result": str(res),
        "expected": "unsat (proved)",
        "elapsed_sec": secs,
    }
    return out


def property_c_mul_overflow(width: int) -> dict:
    """(c) Find x, y BV(n) s.t. unsigned x * y wraps around 2^width."""
    x = BitVec("x", width)
    y = BitVec("y", width)
    s = make_solver()
    # Multiplication overflow when ULT(x * y, x) with y ≥ 1.
    s.add(ULT(x * y, x))
    s.add(y != 0)
    res, m, secs = timed_check(s, "c: mul overflow")
    out = {
        "id": "c",
        "name": "mul overflow exists",
        "formula": "∃x,y: y ≠ 0 ∧ ULT(x * y, x)",
        "interpretation": "Find x,y s.t. unsigned x*y wraps (multiplication wraparound).",
        "kind": "find_counterexample",
        "width": width,
        "result": str(res),
        "expected": "sat",
        "counterexample": None,
        "elapsed_sec": secs,
    }
    if res == sat and m is not None:
        xv, yv = model_bv(m, x), model_bv(m, y)
        out["counterexample"] = {"x": xv, "y": yv}
    return out


def property_d_mul_commutativity(width: int) -> dict:
    """(d) Prove x * y == y * x (commutativity of multiplication)."""
    x = BitVec("x", width)
    y = BitVec("y", width)
    s = make_solver()
    s.add(Not(x * y == y * x))
    res, m, secs = timed_check(s, "d: mul commutativity (negation)")
    return {
        "id": "d",
        "name": "mul commutativity",
        "formula": "∀x,y: x * y == y * x   (verified by ¬formula → UNSAT)",
        "interpretation": "Prove that BV multiplication is commutative.",
        "kind": "prove",
        "width": width,
        "result": str(res),
        "expected": "unsat (proved)",
        "elapsed_sec": secs,
    }


def property_e_mul_zero(width: int) -> dict:
    """(e) Find x, y with x ≠ 0 ∧ y ≠ 0 ∧ x * y == 0 (BV zero-divisor)."""
    x = BitVec("x", width)
    y = BitVec("y", width)
    s = make_solver()
    s.add(x != 0)
    s.add(y != 0)
    s.add(x * y == 0)
    res, m, secs = timed_check(s, "e: BV zero divisor")
    out = {
        "id": "e",
        "name": "BV zero divisor",
        "formula": "∃x,y: x ≠ 0 ∧ y ≠ 0 ∧ x * y == 0",
        "interpretation": "Find non-zero BV x,y with x*y = 0 (BV is not an integral domain).",
        "kind": "find_counterexample",
        "width": width,
        "result": str(res),
        "expected": "sat",
        "counterexample": None,
        "elapsed_sec": secs,
    }
    if res == sat and m is not None:
        out["counterexample"] = {"x": model_bv(m, x), "y": model_bv(m, y)}
    return out


def property_f_self_xor(width: int) -> dict:
    """(f) Prove (x ^ x) == 0 for all x."""
    x = BitVec("x", width)
    s = make_solver()
    s.add(Not(x ^ x == 0))
    res, m, secs = timed_check(s, "f: self-xor zero (negation)")
    return {
        "id": "f",
        "name": "self-xor zero",
        "formula": "∀x: (x ^ x) == 0   (verified by ¬formula → UNSAT)",
        "interpretation": "Prove that every BV XORed with itself is zero.",
        "kind": "prove",
        "width": width,
        "result": str(res),
        "expected": "unsat (proved)",
        "elapsed_sec": secs,
    }


def property_g_or_monotone(width: int) -> dict:
    """(g) Prove for all x, y: (x | y) >= x  (OR is monotone in each arg, unsigned)."""
    x = BitVec("x", width)
    y = BitVec("y", width)
    s = make_solver()
    s.add(Not(UGE(x | y, x)))
    res, m, secs = timed_check(s, "g: OR-monotone (negation)")
    return {
        "id": "g",
        "name": "OR monotonicity",
        "formula": "∀x,y: UGE(x | y, x)   (verified by ¬formula → UNSAT)",
        "interpretation": "Prove that bitwise OR is monotone in each argument (unsigned).",
        "kind": "prove",
        "width": width,
        "result": str(res),
        "expected": "unsat (proved)",
        "elapsed_sec": secs,
    }


# --- driver ---------------------------------------------------------------

def main():
    properties = [
        property_a_add_overflow,
        property_b_add_inverse,
        property_c_mul_overflow,
        property_d_mul_commutativity,
        property_e_mul_zero,
        property_f_self_xor,
        property_g_or_monotone,
    ]

    results = {
        "config": {
            "width": WIDTH,
            "timeout_ms": TIMEOUT_MS,
            "repeat": REPEAT,
            "z3_version": __import__("z3").get_version_string(),
            "seed": SEED,
        },
        "runs": [],
    }

    for run_idx in range(REPEAT):
        print(f"\n=== run {run_idx + 1}/{REPEAT} (width={WIDTH}) ===")
        run = []
        for f in properties:
            print(f"\n[f] {f.__name__}  width={WIDTH}")
            run.append(f(WIDTH))
        results["runs"].append(run)

    with open(LOG_PATH, "w") as fp:
        json.dump(results, fp, indent=2, default=str)
    print(f"\nWrote raw JSON to {LOG_PATH}")

    print("\n=== final run summary ===")
    for r in results["runs"][-1]:
        line = f"  ({r['id']}) {r['name']:<22}  result={r['result']:<6}  t={r['elapsed_sec']*1000:.3f} ms"
        if r.get("counterexample"):
            line += f"  cex={r['counterexample']}"
        print(line)


if __name__ == "__main__":
    main()
