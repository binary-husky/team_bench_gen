# Summary: Bit-Vector (BV) Fixed-Width Arithmetic Property Verification with z3

## 1. Setup

| Item               | Value                                              |
| ------------------ | -------------------------------------------------- |
| SMT solver         | z3-solver 4.16.0 (Python API)                      |
| Bit width          | **8 bits** (fixed)                                 |
| Encoding           | Unsigned bit-vectors (`BitVec('x', 8)`)            |
| Tactics            | z3 default QF_BV (no per-property tuning)          |
| Timeout per query  | 30 000 ms                                          |
| z3 random seed     | `0xC0FFEE` (`smt.random_seed`)                     |
| Repeats            | 3 (timings averaged across the 3 runs)             |
| Source script      | `./verify.py`                                      |
| Raw measurements   | `./results.json`                                   |

For every "prove" property we follow the canonical z3 pattern required by the
task: assert the **negation** of the property, then call `Solver.check()`. If
the solver returns `unsat`, the negation is unsatisfiable, hence the original
property is **proved**. For "find counterexample" properties we just call
`Solver.check()` and ask for a model when the result is `sat`.

For all queries the wall-clock time of `check()` is the "solving time" we
report. (Each query is well below 1 ms except the SAT overflow searches which
are < 6 ms — far under the 30 s budget, so no timeouts occurred.)

---

## 2. Results — the three required properties

### (a) `SAT` — does there exist x, y such that unsigned `x + y` overflows?

* **Query (find counterexample):**  `∃ x, y ∈ BV(8):  y ≠ 0  ∧  ULT(x + y, x)`
  (overflow in unsigned 8-bit add iff the BV result is unsigned-less-than `x`,
  which can only happen when addition wrapped past 2⁸.)
* **Result:** **`sat`** — z3 found a witness.
* **Counterexample (one of three runs):** `x = 193, y = 67`
  * 193 + 67 = 260 in unbounded integer arithmetic
  * BV(8) result = 260 mod 256 = **4**
  * 4 < 193, i.e. `ULT(4, 193) = true`  ✓ wraparound confirmed
* **Solving time:** ≈ 0.5 – 5 ms (run-to-run variance from z3's own SAT search).

> **Conclusion for (a):** **counterexample found** — unsigned 8-bit addition
> can (and does) wrap.

### (b) `UNSAT` — is `(x + y) − y == x` for all x, y?

* **Query (prove):**  assert `¬((x + y) − y == x)`, then call `check()`.
  z3 returns `unsat` ⇒ the negation is unsatisfiable ⇒ the identity holds for
  all x, y ∈ BV(8).
* **Result:** **`unsat` (proved).**
* **Solving time:** ≈ 0.03 ms (z3 dispatches the identity in the bit-blasting
  pre-processing; no SAT search needed).

> **Conclusion for (b):** **proved** — the modular-arithmetic identity
> `(x + y) − y = x` holds for every 8-bit pair.

### (c) `SAT` — does there exist x, y such that unsigned `x * y` overflows?

* **Query (find counterexample):**  `∃ x, y ∈ BV(8):  y ≠ 0  ∧  ULT(x * y, x)`
  (multiplication wrap-around iff the BV product is unsigned-less-than `x`).
* **Result:** **`sat`** — z3 found a witness.
* **Counterexample (one of three runs):** `x = 127, y = 170`
  * 127 · 170 = 21 590 in unbounded integer arithmetic
  * BV(8) result = 21 590 mod 256 = **86**
  * 86 < 127, i.e. `ULT(86, 127) = true`  ✓ wraparound confirmed
* **Solving time:** ≈ 1 – 5 ms.

> **Conclusion for (c):** **counterexample found** — unsigned 8-bit
> multiplication can (and does) wrap. The wraparound condition is real, not
> vacuous.

---

## 3. Additional cross-check properties (same width, same z3 settings)

To show the experiment is not pathological we ran four more BV properties
using the same fixed configuration.

| #   | Property                                  | Query form (z3 input)                                                 | Result          | Solving time |
| --- | ----------------------------------------- | ---------------------------------------------------------------------- | --------------- | ------------ |
| d   | `x * y == y * x` (commutativity)          | assert `¬(x * y == y * x)`                                            | **unsat (proved)** | ≈ 0.03 ms    |
| e   | non-zero BV x, y with `x * y == 0`        | `x ≠ 0 ∧ y ≠ 0 ∧ x * y == 0`                                          | **sat**, cex `{x:2, y:128}` (2·128=256≡0 mod 256) | ≈ 4 ms |
| f   | `(x ^ x) == 0` for all x                   | assert `¬(x ^ x == 0)`                                                | **unsat (proved)** | ≈ 0.03 ms    |
| g   | `UGE(x | y, x)` (OR is monotone)          | assert `¬UGE(x | y, x)`                                               | **unsat (proved)** | ≈ 0.3 ms     |

(d, f, g) are exactly the kind of "obvious" identities one would expect a
bit-vector solver to discharge almost instantly. (e) is interesting: 8-bit
BV is **not** an integral domain — a non-zero element can multiply another
non-zero element to zero, and z3 finds such a pair in a few ms.

---

## 4. Per-property summary table

| id | name                       | kind                  | expected   | got              | verdict                  |
| -- | -------------------------- | --------------------- | ---------- | ---------------- | ------------------------ |
| a  | add overflow exists        | find counterexample   | sat        | sat (cex found)  | counterexample found     |
| b  | add inverse `(x+y)−y==x`   | prove (¬formula→UNSAT)| unsat      | unsat            | **proved**               |
| c  | mul overflow exists        | find counterexample   | sat        | sat (cex found)  | counterexample found     |
| d  | mul commutativity `x*y==y*x`| prove                | unsat      | unsat            | **proved**               |
| e  | BV zero divisor            | find counterexample   | sat        | sat (cex found)  | counterexample found     |
| f  | self-xor zero `(x^x)==0`   | prove                 | unsat      | unsat            | **proved**               |
| g  | OR monotonicity `UGE(x|y,x)`| prove                | unsat      | unsat            | **proved**               |

All seven properties behaved exactly as expected. There were no
`unknown`/timeouts, no inconsistent verdicts across the 3 repeated runs, and
all reported counterexamples re-check correctly against Python's
unbounded-integer arithmetic.

---

## 5. Conclusion (one paragraph)

For **8-bit unsigned bit-vectors**, z3's bit-vector theory confirms the
expected fixed-width behaviour of every property we tested:

* **Counterexamples were found** for the two overflow queries
  (a) unsigned addition overflow (e.g. `x=193, y=67` ⇒ 260 mod 256 = 4) and
  (c) unsigned multiplication overflow (e.g. `x=127, y=170` ⇒ 21 590 mod 256 = 86),
  as well as for the BV zero-divisor query (e) (`x=2, y=128`).
* **Identities were proved** for the four "for all" properties — (b)
  `(x + y) − y == x`, (d) `x * y == y * x`, (f) `(x ^ x) == 0`, and (g)
  `UGE(x | y, x)` — by asserting the negation and observing `unsat`.

The bit-vector theory's "equality is equality of bit-patterns, arithmetic is
modulo 2ⁿ" semantics therefore behaves exactly as a hardware engineer would
expect: wraparound exists and is observable, but the algebraic identities
that hold in `ℤ/2ⁿℤ` are still provable. Solving time for every query is
well under 10 ms on this machine, so the experiment is dominated by
script-IO, not by SMT search.
