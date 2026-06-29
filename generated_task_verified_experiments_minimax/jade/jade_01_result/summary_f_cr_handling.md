# Why JADE must *regenerate* `F ≤ 0` rather than *truncate* it to 0

## Setup — the two operators and their domains

- **Equation (7)** — DE/current-to-pbest/1 mutation with archive:

  `v_{i,g} = x_{i,g} + F_i · (x^p_best,g − x_{i,g}) + F_i · (x_{r1,g} − x̃_{r2,g})`

- **Equation (4)** — binomial crossover:

  `u_{j,i,g} = v_{j,i,g}` if `rand_j(0,1) ≤ CR_i` **or** `j = j_rand`, else `u_{j,i,g} = x_{j,i,g}`

- **Equation (8)** — `CR_i = randn_i(μ_CR, 0.1)`, truncated to `[0, 1]` (clamp both ends).
- **Equation (10)** — `F_i = randc_i(μ_F, 0.1)`, truncated to `1` if `F_i ≥ 1`, **regenerated** if `F_i ≤ 0`.

The asymmetry of the paper's rules — symmetric clamp for CR, asymmetric "reject-and-resample" for F — is dictated by the role each parameter plays in the mutation-then-crossover pipeline. Below I walk through it step by step.

---

## 1. What happens if `F_i = 0` (the mutation vector collapses)

Substitute `F_i = 0` into equation (7):

`v_{i,g} = x_{i,g} + 0·(x^p_best,g − x_{i,g}) + 0·(x_{r1,g} − x̃_{r2,g}) = x_{i,g}`

So the **mutation vector is a clone of the parent**. Both the greedy `x^p_best` and the diversity `x_{r1} − x̃_{r2}` difference terms are multiplied by zero.

Now feed this into the crossover (4). For every dimension `j`:

- if `rand_j ≤ CR_i` or `j = j_rand`: `u_{j,i,g} = v_{j,i,g} = x_{j,i,g}`
- otherwise: `u_{j,i,g} = x_{j,i,g}`

Either way, `u_{j,i,g} = x_{j,i,g}`. Therefore **the trial vector equals the parent vector exactly**:

`u_{i,g} = x_{i,g}`  ⇒  `f(u_{i,g}) = f(x_{i,g})`.

This is qualitatively different from any other value of `F_i` in `(0, 1]`, which produces a non-trivial donor `v_{i,g} ≠ x_{i,g}` and therefore a trial `u_{i,g}` that can differ from `x_{i,g}` in at least the forced crossover coordinate `j_rand`. With `F_i = 0`, the crossover cannot even inject the single forced difference, because the donor it would copy from is already identical to the parent.

---

## 2. Cascading failure in the Table I pseudocode (lines 20–23 and 26–28)

Now follow such a "dead" trial through the rest of the generation.

**Selection (lines 20–23).** The rule is `if f(u_{i,g}) ≤ f(x_{i,g}) then x_{i,g+1} = u_{i,g}`. With equality, the parent survives unchanged — formally a "win", but a vacuous one. Crucially, the **else-branch never fires**:

- The parent is **not** added to archive `A` (line 22 — `x_{i,g} → A` is skipped).
- `F_i` is **not** appended to `S_F`.
- `CR_i` is **not** appended to `S_CR`.

**Generation-end updates (lines 26–28 and eqs. 9, 11, 12).** Both

  `μ_CR ← (1−c)·μ_CR + c · mean_A(S_CR)`

  `μ_F  ← (1−c)·μ_F  + c · mean_L(S_F)`

require `S_CR` and `S_F` to be non-empty. If, in a given generation, a *large* fraction of the `NP` individuals drew an `F_i = 0` (which is not unlikely, see §4), `S_F` and `S_CR` either stay empty or get only a few entries; the adaptation terms then evaluate to a tiny arithmetic / Lehmer mean dominated by sampling noise, or are skipped entirely. So:

- **Archive `A` stops growing.** Diversity in the mutation donors (`x̃_{r2,g}` is drawn from `P ∪ A`) collapses to the current population — JADE degenerates into a non-archive algorithm.
- **`S_F` does not get filled with successful F values.** The Lehmer-mean update of `μ_F` (eq. 11) cannot bias itself toward the large-F values that actually produced progress — i.e. the mechanism that "encourages large `F_i` for diversity" (paper §IV.C) is silently disabled.
- **`S_CR` does not get filled with successful CR values.** Adaptation of `μ_CR` is starved.
- **Function evaluations are wasted**, because every "trial" is just the parent re-evaluated at the same fitness — `NP` evals per generation producing zero information.

The trap is self-reinforcing. Because the Cauchy location parameter `μ_F` starts at 0.5 and adapts via Lehmer mean (which is more sensitive to the denominator than arithmetic mean), any generation in which few or no `F_i > 0` trials succeed leaves `μ_F` essentially unchanged; meanwhile many `F_i` are still being sampled ≤ 0.0 from a Cauchy whose CDF at 0 is large (≈ 0.5 when `μ_F = 0`), so the next generation is just as likely — possibly more likely, since `μ_F` was never nudged upward — to draw a flood of near-zero `F_i`. The adaptation loop stalls.

In contrast, *regenerating* `F_i ≤ 0` (the paper's rule) preserves `F_i > 0` strictly, so every trial is at least a non-trivial mutation and every successful trial can populate `S_F` and `A`.

---

## 3. Why `CR_i = 0` truncation is harmless — the contrast with F

Substitute `CR_i = 0` into equation (4):

- `rand_j(0,1) ≤ 0` is never true, so the first branch never fires.
- `j = j_rand` *still* forces the second branch exactly once (at the single index `j_rand ∈ {1,…,D}` chosen uniformly at random per individual).

So `u_{j,i,g} = x_{j,i,g}` for `j ≠ j_rand`, and `u_{j_rand,i,g} = v_{j_rand,i,g}` (≠ `x_{j_rand,i,g}` in general, because `v` came from a non-trivial mutation in eq. 7). Concretely:

`u_{i,g}` differs from `x_{i,g}` in **exactly one coordinate**, `j_rand`.

Hence `f(u_{i,g})` can be strictly less than `f(x_{i,g})` — exploration is still possible, the trial is not a clone, and the else-branch (success) in lines 20–23 can fire and feed `S_F` and `S_CR`.

This is the structural reason CR truncation to `[0, 1]` is benign while F truncation to `[0, 1]` is not:

| value | what does the trial look like vs the parent? | does the trial carry any new information? |
|---|---|---|
| `F_i = 0` | `u = x` everywhere (mutation vector itself is a clone; crossover's `j_rand` copies a clone) | **No** — pure stagnation |
| `CR_i = 0` | `u` differs from `x` in exactly one forced coordinate `j_rand` | **Yes** — single-dimension exploration |

Truncating `CR_i = 0` does mean "do almost nothing new", but it does not freeze the trial to the parent. Truncating `F_i = 0` *does* freeze the trial to the parent, because F multiplies the **mutation vector itself**, whereas CR only gates which dimensions of an already-non-trivial mutation vector get copied. F operates one level earlier in the pipeline and so its zero has a strictly stronger annihilating effect.

There is also a symmetric argument on the upper bound: clamping `F_i ≥ 1` to `1` is fine because `F_i = 1` still produces a meaningful mutation (a full-length donor step); clamping `CR_i ≥ 1` to `1` is fine because `CR_i = 1` means "inherit all donor dimensions", a valid extreme of crossover, not a destructive one. Both upper bounds are saturation, the only difference is the lower bound — and F's lower bound is the catastrophic one.

---

## 4. Why this asymmetry actually matters in practice (probabilistic amplification)

The Cauchy location parameter `μ_F` in eq. (10) tends to be small — empirically in the 0.3–0.5 range from the paper's numerical results. The Cauchy distribution has undefined mean and a very heavy left tail; even when its location is 0.3–0.5, a non-negligible fraction of samples (tens of percent) fall ≤ 0. So the `F ≤ 0` event is not a theoretical corner case but a frequent one that the paper explicitly accounts for.

With the paper's regenerate rule, those samples are simply thrown away and resampled — the Cauchy `F_i > 0` half keeps its heavy-tailed shape (which is the whole reason Cauchy was chosen over Normal for F, per §IV.C: "encourage large F values for diversity"). With a clamp-to-zero rule, that heavy left tail becomes a tall spike of exactly-zero F values, and §2's cascade triggers.

The Gaussian for `CR_i` in eq. (8) has a thin tail (0.1 standard deviation) and `μ_CR` is typically in `[0.3, 0.9]`; samples outside `[0, 1]` are rare, and when they occur the trial is still non-trivial (per §3), so clamping is harmless.

---

## Conclusion

**JADE must regenerate `F ≤ 0` rather than truncate to 0, because `F` multiplies the mutation vector itself: `F_i = 0` makes `v_{i,g} = x_{i,g}` and, via the binomial crossover's `j_rand` clause, makes `u_{i,g} = x_{i,g}` as well, so the trial is a literal clone of the parent.** A generation in which many individuals draw `F_i = 0` therefore wastes every function evaluation, refuses to grow the archive, refuses to fill `S_F` and `S_CR`, and starves the Lehmer-mean update of `μ_F` and the arithmetic-mean update of `μ_CR` — producing a self-reinforcing adaptation stall. Clamping `CR_i = 0` is safe precisely because `CR` only gates which dimensions of an already-non-trivial mutation get copied: the forced coordinate `j_rand` keeps the trial non-identical to the parent, so the selection / archive / adaptation machinery keeps working. The asymmetry in the paper's rules — symmetric `[0,1]` clamp for CR, asymmetric "reject `F ≤ 0`, clamp `F ≥ 1` to 1" for F — is not a stylistic choice; it is forced by the fact that `F = 0` annihilates the mutation vector while `CR = 0` does not.