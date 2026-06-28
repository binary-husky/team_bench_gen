#!/usr/bin/env python3
"""
Fixed-width (BitVec) arithmetic property verification with z3.

Bit-width: 8 bits (set below; also run 16-bit for the wraparound check
to confirm the finding is not an artifact of an 8-bit width).

Properties:
  (a) EXISTENCE: Do there exist x, y such that x + y (unsigned) overflows?
      -> Expect SAT; extract a model (counterexample/witness).
  (b) UNIVERSAL: Does (x + y) - y == x hold for ALL x, y (mod 2^n)?
      -> Prove by asserting the negation and checking UNSAT.
  (c) MULTIPLICATION WRAPAROUND CONDITION:
      "If x != 0 and y != 0 then x * y wraps (i.e. overflows) iff ... "
      We test a concrete wraparound claim:
        Claim C1: For all x,y: (x * y) / y == x   (unsigned division)
      This is FALSE in general because of wraparound (e.g. y=0, or wrap).
      We look for a counterexample (SAT) where the equality fails.
      We also characterize the wraparound condition by checking whether
        (x * y) mod 2^n == (true product mod 2^n)  -- trivially true,
      so instead we verify the *useful* property:
        Property C2 (universal, true): If x*y does NOT overflow (i.e.
        x*y < 2^n in unbounded arithmetic) then (x*y)/y == x for y!=0.
      We prove C2 by asserting its negation and checking UNSAT.

For each property we record: result (SAT/UNSAT), model (if SAT), time (s).
"""

import time
from z3 import (BitVec, BitVecVal, Solver, URem, UDiv, ULT, And, Not,
                sat, unsat, unknown)

WIDTH = 8          # primary bit-width
N = 1 << WIDTH     # 2^WIDTH


def timed_check(solver, label):
    t0 = time.perf_counter()
    r = solver.check()
    t1 = time.perf_counter()
    dt = t1 - t0
    if r == sat:
        status = "SAT"
    elif r == unsat:
        status = "UNSAT"
    else:
        status = f"UNKNOWN({r})"
    return status, dt, r


def header(w):
    print(f"\n{'='*60}\nBit-width = {w}  (domain size 2^{w} = {1<<w})\n{'='*60}")


def property_a(w):
    """(a) EXISTS x,y with unsigned overflow of x+y."""
    print(f"\n(a) Does there exist x,y such that x+y overflows (unsigned)?")
    print("    Encoding: s+t != ZeroExt-to-2w(x+y)  <=> low byte mismatch")
    x = BitVec('x', w)
    y = BitVec('y', w)
    s = BitVec('s', w)
    # s = x + y (mod 2^w); overflow in unsigned sense means
    # true sum (x+y) >= 2^w, i.e. s < x  (unsigned) and s < y.
    # Overflow condition (unsigned): s < x  (carry out of MSB).
    sol = Solver()
    sol.add(s == x + y)
    sol.add(ULT(s, x))   # unsigned: result < operand => overflow
    status, dt, r = timed_check(sol, "a")
    model = None
    if r == sat:
        m = sol.model()
        xv = m[x].as_long()
        yv = m[y].as_long()
        sv = m[s].as_long()
        model = {"x": xv, "y": yv, "x+y(mod 2^w)": sv,
                 "true_sum": xv + yv}
    print(f"    -> {status}  ({dt*1000:.3f} ms)")
    if model:
        print(f"    witness: {model}")
    return status, dt, model


def property_b(w):
    """(b) UNIVERSAL: (x+y)-y == x for all x,y. Prove via negation UNSAT."""
    print(f"\n(b) Does (x+y)-y == x hold for ALL x,y? (prove: assert negation, expect UNSAT)")
    x = BitVec('x', w)
    y = BitVec('y', w)
    lhs = (x + y) - y
    sol = Solver()
    sol.add(lhs != x)          # negation of the property
    status, dt, r = timed_check(sol, "b")
    model = None
    if r == sat:
        m = sol.model()
        model = {"x": m[x].as_long(), "y": m[y].as_long()}
    print(f"    -> {status}  ({dt*1000:.3f} ms)")
    verdict = "PROVED (property holds)" if r == unsat else "DISPROVED (counterexample)"
    print(f"    verdict: {verdict}")
    if model:
        print(f"    counterexample: {model}")
    return status, dt, model, verdict


def property_c1(w):
    """(c) COUNTEREXAMPLE: (x*y)/y == x is FALSE in general. Find SAT model."""
    print(f"\n(c1) Is (x*y)/y == x for all x,y with y!=0? (expect SAT counterexample)")
    x = BitVec('x', w)
    y = BitVec('y', w)
    sol = Solver()
    sol.add(y != 0)
    sol.add(UDiv(x * y, y) != x)   # negation -> find wraparound where div 'loses' info
    status, dt, r = timed_check(sol, "c1")
    model = None
    if r == sat:
        m = sol.model()
        xv = m[x].as_long()
        yv = m[y].as_long()
        prod = (xv * yv) % (1 << w)
        quo = (prod // yv) if yv != 0 else None
        model = {"x": xv, "y": yv, "x*y(mod 2^w)": prod,
                 "(x*y)/y(mod 2^w)": quo}
    print(f"    -> {status}  ({dt*1000:.3f} ms)")
    if model:
        print(f"    counterexample: {model}")
    return status, dt, model


def property_c2(w):
    """(c) PROVE: if x*y does not overflow (true product < 2^w) and y!=0,
       then (x*y)/y == x. Prove via negation UNSAT."""
    print(f"\n(c2) If x*y does NOT overflow (true product < 2^w) and y!=0, then (x*y)/y==x.")
    print("     (prove: assert negation, expect UNSAT)")
    x = BitVec('x', w)
    y = BitVec('y', w)
    # We need the *true* (unbounded) product to express the no-overflow guard.
    # Express via comparison of the modular product against operands using
    # the standard test: for unsigned, x*y overflows iff
    #   (x != 0) and ( (x*y) / x != y )   (using the modular product).
    # "No overflow" is the negation of that (with the x!=0 guard), plus y!=0.
    prod = x * y
    overflow = And(x != 0, UDiv(prod, x) != y)   # standard unsigned mul-overflow test
    sol = Solver()
    sol.add(y != 0)
    sol.add(Not(overflow))            # guard: no overflow
    sol.add(UDiv(prod, y) != x)       # negation of conclusion
    status, dt, r = timed_check(sol, "c2")
    model = None
    if r == sat:
        m = sol.model()
        model = {"x": m[x].as_long(), "y": m[y].as_long()}
    print(f"    -> {status}  ({dt*1000:.3f} ms)")
    verdict = "PROVED (property holds)" if r == unsat else "DISPROVED (counterexample)"
    print(f"    verdict: {verdict}")
    if model:
        print(f"    counterexample: {model}")
    return status, dt, model, verdict


def run_width(w):
    header(w)
    a = property_a(w)
    b = property_b(w)
    c1 = property_c1(w)
    c2 = property_c2(w)
    return {"width": w, "a": a, "b": b, "c1": c1, "c2": c2}


if __name__ == "__main__":
    results = [run_width(WIDTH), run_width(16)]
    # summary table
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    fmt = "{:<8} {:<6} {:<14} {:<14} {:<14} {:<14}"
    print(fmt.format("width", "prop", "(a) overflow", "(b) sub-add",
                     "(c1) mul-div CE", "(c2) noOF=>div"))
    for R in results:
        w = R["width"]
        print(fmt.format(
            w, "res",
            f"{R['a'][0]} {R['a'][1]*1000:.3f}ms",
            f"{R['b'][0]} {R['b'][1]*1000:.3f}ms",
            f"{R['c1'][0]} {R['c1'][1]*1000:.3f}ms",
            f"{R['c2'][0]} {R['c2'][1]*1000:.3f}ms",
        ))
    # persist machine-readable results for the summary writer
    import json
    out = []
    for R in results:
        out.append({
            "width": R["width"],
            "a": {"status": R["a"][0], "time_ms": R["a"][1] * 1000,
                  "model": R["a"][2]},
            "b": {"status": R["b"][0], "time_ms": R["b"][1] * 1000,
                  "model": R["b"][2], "verdict": R["b"][3]},
            "c1": {"status": R["c1"][0], "time_ms": R["c1"][1] * 1000,
                   "model": R["c1"][2]},
            "c2": {"status": R["c2"][0], "time_ms": R["c2"][1] * 1000,
                   "model": R["c2"][2], "verdict": R["c2"][3]},
        })
    with open("results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nWrote results.json")
