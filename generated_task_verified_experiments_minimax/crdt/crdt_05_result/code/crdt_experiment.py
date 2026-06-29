"""
crdt_experiment.py — In-process verification of state-based CRDTs:
  * OR-Set  (Observed-Remove Set, add-wins)
  * PN-Counter (Positive-Negative Counter, supports decrement)

References:
  Shapiro, Preguiça, Baquero, Zawirski (2011)
  "A comprehensive study of Convergent and Commutative Replicated Data Types"
  INRIA RR-7506.
    §3.1.3 (Spec 7)  — State-based PN-Counter
    §3.3.5 (Spec 15) — Observed-Remove Set (op-based; we give state-based
                       payload = set of (element, unique-tag) pairs, with
                       merge = union of token sets, per the task spec).

The experiments are in-process, deterministic (seeded), and verify:
  (A) OR-Set add-wins: after concurrent add(x)/remove(x) at different
      replicas and merge, x MUST remain in the set (since add-wins).
  (B) PN-Counter: after concurrent increments/decrements and merge,
      value = P - N MUST equal the exact serial replay of the same op
      sequence.

All work is done in this single process; no threads.
"""

import random
import copy
import json
from dataclasses import dataclass, field
from typing import Any, List, Tuple, Dict


# ---------------------------------------------------------------------------
# OR-Set (state-based), payload = set of (element, unique-tag) pairs
# ---------------------------------------------------------------------------

class ORSet:
    """
    State-based OR-Set.

    Payload: a set S of (element, unique-tag) pairs.
      - add(e)        : generate a fresh unique tag, S := S ∪ {(e, tag)}
      - remove(e)     : R := {(e, u) in S}; S := S \\ R  (removes only
                        currently-observed tokens at the source)
      - lookup(e)     : ∃u : (e, u) ∈ S
      - merge(S, T)   : S := S ∪ T                    (union of token sets)
      - value()       : {e : ∃u. (e, u) ∈ S}

    Crucially, when add(x) and remove(x) are concurrent:
      - remove(x) can only delete the tokens it has observed at its source.
      - The concurrent add(x) introduced a fresh token that the remove
        has NOT observed.  After merge, that fresh token survives in the
        union, so x remains in the set → add-wins.
    """

    def __init__(self, replica_id: str, tag_counter: int = 0):
        self.replica_id = replica_id
        self.S: set = set()                       # set of (element, tag) tuples
        self._tag_counter = tag_counter

    # --- local helpers -----------------------------------------------------
    def _new_tag(self) -> Tuple[Any, int]:
        self._tag_counter += 1
        return (self.replica_id, self._tag_counter)

    def _tokens_of(self, e):
        return {pair for pair in self.S if pair[0] == e}

    # --- interface ---------------------------------------------------------
    def add(self, e):
        tag = self._new_tag()
        self.S.add((e, tag))

    def remove(self, e):
        # observed-remove: only remove tokens this replica currently sees
        self.S -= self._tokens_of(e)

    def lookup(self, e) -> bool:
        return any(pair[0] == e for pair in self.S)

    def value(self) -> set:
        return {e for (e, _) in self.S}

    def merge(self, other: "ORSet"):
        # state-based merge: union of token sets
        # (also pull in tag counter so locally-generated tags stay unique)
        self.S |= other.S
        # tag counter is per-replica; keep it monotonic
        if other._tag_counter > self._tag_counter:
            self._tag_counter = other._tag_counter

    # clone for parallelism within a scenario
    def snapshot(self) -> "ORSet":
        c = ORSet(self.replica_id, self._tag_counter)
        c.S = set(self.S)
        return c


# A naive "remove-wins" comparison CRDT (FIFO-set / 2P-Set flavour):
#   add(x) puts x in a set; remove(x) puts x in a tombstone set.
# When both happen concurrently, x ends up absent — "remove wins".
class NaiveRemoveWinsSet:
    def __init__(self):
        self.A = set()
        self.R = set()

    def add(self, e):
        self.A.add(e)

    def remove(self, e):
        self.R.add(e)

    def lookup(self, e) -> bool:
        return e in self.A and e not in self.R

    def value(self):
        return {e for e in self.A if e not in self.R}

    def merge(self, other: "NaiveRemoveWinsSet"):
        self.A |= other.A
        self.R |= other.R


# ---------------------------------------------------------------------------
# PN-Counter (state-based, two G-Counters P and N)
# ---------------------------------------------------------------------------

class PNCounter:
    """
    State-based PN-Counter.

    Payload: two integer vectors P[0..n-1], N[0..n-1], one slot per replica.
      - increment(g)        : P[g] += 1
      - decrement(g)        : N[g] += 1
      - value()             : Σ P[i] - Σ N[i]
      - merge((P,N), (P',N')): P[i] = max(P[i], P'[i]); N[i] = max(N[i], N'[i])
      - compare             : P ≤ P' ∧ N ≤ N'  (product partial order)

    Crucially, P and N are themselves G-Counters (each monotonic under
    merge = max).  Decrement is mapped to "increment of N", so the
    state vector never has to decrease, and merge = max over each
    component is still a LUB.
    """

    def __init__(self, n: int, replica_id: int):
        self.n = n
        self.g = replica_id
        self.P = [0] * n
        self.N = [0] * n

    def increment(self):
        self.P[self.g] += 1

    def decrement(self):
        self.N[self.g] += 1

    def value(self) -> int:
        return sum(self.P) - sum(self.N)

    def merge(self, other: "PNCounter"):
        assert other.n == self.n
        for i in range(self.n):
            if other.P[i] > self.P[i]:
                self.P[i] = other.P[i]
            if other.N[i] > self.N[i]:
                self.N[i] = other.N[i]

    def snapshot(self) -> "PNCounter":
        c = PNCounter(self.n, self.g)
        c.P = list(self.P)
        c.N = list(self.N)
        return c


# ---------------------------------------------------------------------------
# Experiment (A) — OR-Set add-wins
# ---------------------------------------------------------------------------

@dataclass
class AResult:
    seed: int
    n_pairs: int
    concurrent_pairs: int
    add_wins_correct: int
    add_wins_rate: float
    naive_remove_wins_wrong: int
    naive_remove_wins_rate: float


def run_add_wins_experiment(seed: int, n_pairs: int = 1200) -> AResult:
    """
    For a given seed, generate >= n_pairs concurrent add(x)/remove(x)
    pairs distributed across three replicas (N=3).  Each pair has
    one replica doing add(x) and a DIFFERENT replica doing remove(x)
    concurrently — i.e., neither replica sees the other's effect
    before it executes its own op.  Then we merge all three replicas
    and check whether x is still present (add-wins ⇒ yes).

    A "pair" here is one shared element x with two concurrent ops
    (add on replica A, remove on replica B).  After merge, x must
    remain in the OR-Set (add-wins), but a naive remove-wins
    comparator would erroneously drop it.
    """
    rng = random.Random(seed)
    replicas = [ORSet(replica_id=f"r{i}") for i in range(3)]

    # We keep track of how many pairs we *actually* got (rng may collapse
    # some pairs if e.g. both replicas happen to be the same one, but
    # we ensure pairings are between distinct replicas).
    actual_concurrent = 0
    seen_pairs = set()

    # To enforce *concurrent* semantics, we process ops as a batch:
    # each replica records its own intended ops but never merges
    # until after the whole batch is dispatched.  This is exactly
    # what "concurrent across replicas" means in a state-based CRDT
    # experiment: at the source, no one has observed the other.
    staged = [[] for _ in range(3)]   # list of (op, x) per replica

    # Build n_pairs candidate (add_replica, remove_replica, x) triples
    # with x unique within the scenario so we don't conflate pairs.
    for k in range(n_pairs):
        # x is unique per candidate to isolate add/remove semantics
        x = (seed, k)                   # hashable, globally unique element
        # choose two distinct replicas
        a, b = rng.sample(range(3), 2)
        # add at a, remove at b
        staged[a].append(("add", x))
        staged[b].append(("remove", x))
        seen_pairs.add((a, b, x))
        actual_concurrent += 1

    # Apply staged ops to each replica in isolation — neither replica
    # sees the others' ops yet, so add(x) and remove(x) are truly
    # concurrent as far as this scenario is concerned.
    for r_idx, ops in enumerate(staged):
        for op, x in ops:
            if op == "add":
                replicas[r_idx].add(x)
            else:
                replicas[r_idx].remove(x)

    # Verify the source replica doing remove(x) DID observe x
    # (otherwise remove would be a no-op and we wouldn't be testing
    # add-wins under genuine concurrency).  We force x to be present
    # at the remover via a preliminary add at every replica — but
    # *only at the source*, not propagated.  This models the OR-Set
    # requirement "remove only removes observed tokens".
    # Since each replica is independent, we ensure that before the
    # concurrent remove, every replica already had at least one token
    # for x.  We simulate this by re-issuing the add on the remover
    # side just before remove (this is what an OR-Set user does when
    # they say "I want to remove x I see here").

    # Simpler & cleaner: pre-seed each replica with x (so remove is a
    # genuine removal attempt), then apply the concurrent add on
    # replica A and concurrent remove on replica B.
    replicas = [ORSet(replica_id=f"r{i}") for i in range(3)]
    naive_replicas = [NaiveRemoveWinsSet() for _ in range(3)]

    # pre-seed x at all replicas (state that exists before the batch)
    for r in replicas:
        r.add(x)  # x is from the *last* iteration — wrong, we need per-pair
    # Actually we need per-pair pre-seed.  Let me redo this cleanly.

    # --- redo cleanly ----------------------------------------------------
    replicas = [ORSet(replica_id=f"r{i}") for i in range(3)]
    naive_replicas = [NaiveRemoveWinsSet() for _ in range(3)]

    # Re-derive the same (a, b, x) schedule
    rng2 = random.Random(seed)
    staged = [[] for _ in range(3)]
    schedule = []     # list of (a, b, x)
    for k in range(n_pairs):
        x = (seed, k)
        a, b = rng2.sample(range(3), 2)
        staged[a].append(("add", x))
        staged[b].append(("remove", x))
        schedule.append((a, b, x))

    # Phase 1: pre-seed EVERY replica with x (so the remover actually
    # has an observed token to remove — the OR-Set precondition).
    for k in range(n_pairs):
        x = (seed, k)
        for r in replicas:
            r.add(x)
        for nr in naive_replicas:
            nr.add(x)

    # Phase 2: apply the concurrent batch.  Each replica operates on
    # its own snapshot, so add(x) on replica A and remove(x) on
    # replica B never see each other before they execute.
    for r_idx, ops in enumerate(staged):
        for op, x in ops:
            if op == "add":
                replicas[r_idx].add(x)
            else:
                replicas[r_idx].remove(x)
        # naive replica
        for op, x in ops:
            if op == "add":
                naive_replicas[r_idx].add(x)
            else:
                naive_replicas[r_idx].remove(x)

    # Phase 3: merge all replicas into one (full Gossip / merge-everything)
    merged = replicas[0].snapshot()
    for r in replicas[1:]:
        merged.merge(r)

    merged_naive = naive_replicas[0]
    for nr in naive_replicas[1:]:
        merged_naive.merge(nr)

    # Phase 4: count add-wins correctness — for every pair, x MUST be
    # in the merged OR-Set (because the add happened *concurrently*
    # with remove, on a different replica, and remove can only drop
    # observed tokens).
    add_wins_correct = 0
    for (a, b, x) in schedule:
        if merged.lookup(x):
            add_wins_correct += 1

    # Phase 5: compare against the naive remove-wins set, which would
    # erase x whenever remove(x) appears anywhere in the merge.
    naive_wrong = 0
    for (a, b, x) in schedule:
        if not merged_naive.lookup(x):
            # The naive comparator wrongly removed x
            naive_wrong += 1

    return AResult(
        seed=seed,
        n_pairs=n_pairs,
        concurrent_pairs=actual_concurrent,
        add_wins_correct=add_wins_correct,
        add_wins_rate=add_wins_correct / n_pairs,
        naive_remove_wins_wrong=naive_wrong,
        naive_remove_wins_rate=naive_wrong / n_pairs,
    )


# ---------------------------------------------------------------------------
# Experiment (B) — PN-Counter decrement correctness
# ---------------------------------------------------------------------------

@dataclass
class BResult:
    seed: int
    n_ops: int
    n_inc: int
    n_dec: int
    merged_value: int
    serial_value: int
    error: int
    abs_error: int


def run_pn_counter_experiment(seed: int, n_ops: int = 5000) -> BResult:
    """
    Three replicas execute an interleaved sequence of increment/decrement
    ops (interleaved across replicas using a seeded RNG).  Each replica
    applies its ops to its OWN local state without seeing the others'
    ops, i.e. the ops are concurrent / not exchanged until the end.

    After all ops are dispatched, we merge the three replicas and read
    the value = ΣP - ΣN.

    Ground truth: replay the SAME op sequence sequentially in a single
    integer counter (the natural sequential semantics for "how many
    more increments than decrements were issued").  The PN-Counter's
    merged value MUST equal this serial value (because PN-Counter is
    SEC over the same op set).
    """
    rng = random.Random(seed)

    replicas = [PNCounter(n=3, replica_id=i) for i in range(3)]

    # Schedule: list of (replica_id, op)
    schedule = []
    for _ in range(n_ops):
        r = rng.randrange(3)
        op = "inc" if rng.random() < 0.5 else "dec"
        schedule.append((r, op))

    # Apply concurrently to each replica's local snapshot
    for r_idx, op in schedule:
        if op == "inc":
            replicas[r_idx].increment()
        else:
            replicas[r_idx].decrement()

    # Merge all replicas
    merged = replicas[0].snapshot()
    for r in replicas[1:]:
        merged.merge(r)
    merged_value = merged.value()

    # Serial ground truth: same sequence in a single counter
    serial = 0
    for _, op in schedule:
        if op == "inc":
            serial += 1
        else:
            serial -= 1

    n_inc = sum(1 for _, op in schedule if op == "inc")
    n_dec = sum(1 for _, op in schedule if op == "dec")

    return BResult(
        seed=seed,
        n_ops=n_ops,
        n_inc=n_inc,
        n_dec=n_dec,
        merged_value=merged_value,
        serial_value=serial,
        error=merged_value - serial,
        abs_error=abs(merged_value - serial),
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main():
    seeds = [1, 2, 3, 4, 5]            # ≥ 5 seeds
    n_pairs_addwins = 1200             # ≥ 1000
    n_ops_counter = 5000              # 1e3 .. 1e4

    print("=" * 78)
    print("(A) OR-Set add-wins experiment")
    print("=" * 78)
    a_results = []
    for s in seeds:
        r = run_add_wins_experiment(seed=s, n_pairs=n_pairs_addwins)
        a_results.append(r)
        print(f"seed={s}  pairs={r.n_pairs:5d}  "
              f"add-wins_correct={r.add_wins_correct:5d}  "
              f"rate={r.add_wins_rate*100:6.2f}%  "
              f"naive-remove-wins_wrong={r.naive_remove_wins_wrong:5d}  "
              f"({r.naive_remove_wins_rate*100:5.2f}%)")

    overall_correct = sum(r.add_wins_correct for r in a_results)
    overall_total = sum(r.n_pairs for r in a_results)
    print(f"\nOverall add-wins: {overall_correct}/{overall_total}  "
          f"= {overall_correct/overall_total*100:.4f}%")

    print()
    print("=" * 78)
    print("(B) PN-Counter decrement experiment")
    print("=" * 78)
    b_results = []
    for s in seeds:
        r = run_pn_counter_experiment(seed=s, n_ops=n_ops_counter)
        b_results.append(r)
        print(f"seed={s}  ops={r.n_ops:5d}  "
              f"inc={r.n_inc:5d}  dec={r.n_dec:5d}  "
              f"merged={r.merged_value:6d}  "
              f"serial={r.serial_value:6d}  "
              f"error={r.error:+d}")

    overall_abs_err = sum(r.abs_error for r in b_results)
    print(f"\nOverall |error| across all seeds = {overall_abs_err}  "
          f"(should be 0)")

    # Dump JSON summary for the markdown summary
    summary = {
        "experiment_A_or_set_addwins": [
            {
                "seed": r.seed,
                "n_pairs": r.n_pairs,
                "add_wins_correct": r.add_wins_correct,
                "add_wins_rate": r.add_wins_rate,
                "naive_remove_wins_wrong": r.naive_remove_wins_wrong,
                "naive_remove_wins_rate": r.naive_remove_wins_rate,
            }
            for r in a_results
        ],
        "experiment_B_pn_counter": [
            {
                "seed": r.seed,
                "n_ops": r.n_ops,
                "n_inc": r.n_inc,
                "n_dec": r.n_dec,
                "merged_value": r.merged_value,
                "serial_value": r.serial_value,
                "error": r.error,
                "abs_error": r.abs_error,
            }
            for r in b_results
        ],
    }
    with open("experiment_results.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("\nWrote experiment_results.json")


if __name__ == "__main__":
    main()