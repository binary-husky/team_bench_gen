"""Target function with several branches, including a hard-to-reach "magic" branch.

We deliberately keep the function small and obviously instrumented so that
both the symbolic executor and the random tester see *the same* control-flow
graph.  The list ALL_BRANCHES is the canonical branch-id ordering, and is
shared by the symbolic engine, the random tester, and the experiment runner.

Branches
--------
B0 : x == 12345          -> "magic / rare"  (the hard-to-reach branch)
B1 : x < 0               -> "negative"      (vs. non-negative)
B2 : x % 2 == 0          -> "even"          (vs. odd)
B3 : x > 1000            -> "large"         (vs. small/medium)
B4 : x % 3 == 0          -> "multiple of 3" (vs. not a multiple of 3)

Total: 5 branches, 10 (branch, taken_bool) edges.

The "rare" branch (B0-true) is satisfied by exactly one value in the chosen
input range (-1_000_000..2_000_000): x = 12345.  Random sampling has only
~3.3e-7 chance per draw of producing that value, so it is essentially
invisible to random testing in 1 000 or even 3 000 draws.
"""

ALL_BRANCHES = ["B0", "B1", "B2", "B3", "B4"]
MAGIC_BRANCH = "B0"


class BranchTracker:
    """Records which (branch_id, taken_bool) edges were exercised."""

    def __init__(self) -> None:
        self.hits: set[tuple[str, bool]] = set()

    # ------------------------------------------------------------------ record
    def record(self, branch_id: str, taken: bool) -> None:
        self.hits.add((branch_id, taken))

    # ------------------------------------------------------------------ query
    def coverage_fraction(self) -> float:
        return len(self.hits) / (2 * len(ALL_BRANCHES))

    def hit_magic(self) -> bool:
        return (MAGIC_BRANCH, True) in self.hits

    def edges_hit(self) -> set[tuple[str, bool]]:
        return set(self.hits)

    def edges_missed(self) -> set[tuple[str, bool]]:
        all_edges = {(b, t) for b in ALL_BRANCHES for t in (True, False)}
        return all_edges - self.hits

    def reset(self) -> None:
        self.hits.clear()


# ----------------------------------------------------------------------- target
def f(x: int, tracker: BranchTracker | None = None) -> str:
    """The function-under-test.

    When *tracker* is supplied, every (branch, taken) is recorded for later
    coverage analysis.  The tracker is purely observational; the function's
    observable behaviour is identical with or without it.
    """
    # B0 -- the magic / rare branch
    if x == 12345:
        if tracker is not None:
            tracker.record("B0", True)
        return "rare_magic"
    if tracker is not None:
        tracker.record("B0", False)

    # B1 -- sign
    if x < 0:
        if tracker is not None:
            tracker.record("B1", True)
        sign = "negative"
    else:
        if tracker is not None:
            tracker.record("B1", False)
        sign = "non_negative"

    # B2 -- parity
    if x % 2 == 0:
        if tracker is not None:
            tracker.record("B2", True)
        parity = "even"
    else:
        if tracker is not None:
            tracker.record("B2", False)
        parity = "odd"

    # B3 -- magnitude
    if x > 1000:
        if tracker is not None:
            tracker.record("B3", True)
        size = "large"
    else:
        if tracker is not None:
            tracker.record("B3", False)
        size = "small"

    # B4 -- multiple of 3
    if x % 3 == 0:
        if tracker is not None:
            tracker.record("B4", True)
        mod3 = "mult3"
    else:
        if tracker is not None:
            tracker.record("B4", False)
        mod3 = "nonmult3"

    return f"{sign}_{parity}_{size}_{mod3}"


if __name__ == "__main__":  # quick sanity check
    for v in [12345, -7, 0, 4, 1500, 9, 1001]:
        t = BranchTracker()
        ret = f(v, t)
        print(f"f({v}) = {ret!r}  edges = {sorted(t.hits)}")
