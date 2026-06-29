"""Random (fuzz-style) testing of the function-under-test.

For every seed we sample ``num_inputs`` integers uniformly from
``x_range`` and run the host function on each.  All (branch, taken_bool)
edges observed are accumulated in a :class:`target.BranchTracker`; the
tracker is the single source of truth for coverage.

This deliberately uses Python's stdlib :mod:`random` (Mersenne Twister)
so the result is fully reproducible from the seed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import target


@dataclass
class RandomRun:
    seed: int
    num_inputs: int
    inputs: list
    tracker: target.BranchTracker


def run(num_inputs: int, seed: int, x_range: tuple[int, int]) -> RandomRun:
    """Sample ``num_inputs`` integers from ``x_range`` and run ``target.f``."""
    rng = random.Random(seed)
    tracker = target.BranchTracker()
    inputs: list[int] = []
    for _ in range(num_inputs):
        x = rng.randint(x_range[0], x_range[1])
        target.f(x, tracker)
        inputs.append(x)
    return RandomRun(seed=seed, num_inputs=num_inputs, inputs=inputs, tracker=tracker)
