"""
Virtual Chord ring simulation - measures lookup robustness under node failures.

This implements the Chord successor-list mechanism (Stoica et al., 2001,
Section 5.2) on a single-process virtual ring.

Setup
-----
* N = 1000 nodes, identifiers drawn uniformly from a 2^16 = 65536 circle.
* Each node's successor list of length r is built once, when every node is
  alive (i.e. at "join time"), pointing to its r nearest clockwise successors.
* Then a fraction f of nodes is killed at random.
* No stabilization / fix-up runs after the failure burst: the lookups run
  while the ring is in the same intermediate state the Chord paper describes
  in Section 6.5 - "lookups during stabilization, before fix-up has
  completed".  This is precisely the regime in which the successor-list
  mechanism is supposed to save us.

Lookup
------
A lookup for key K starts at a random live requester and walks the
successor list iteratively, exactly as in Section 5.2:
  1. From the current node, take its successor list in order and pick the
     first *alive* entry.  Call that node `next`.
  2. If K is in (current, next], return next (next owns K).
  3. Otherwise, advance current = next and repeat, capping at N+10 hops
     (a fully-broken ring with zero live entries would loop forever).
This is essentially the iterative Figure-4 walk with the finger table
replaced by the successor list.

For each (r, f) cell we measure lookup success rate over 1e4 random keys.
A lookup is a "success" iff it returns the live node that owns K in the
*current* (post-failure) ring.

The experiment is repeated across 5 seeds; we report mean and population
std-dev of the success rate.
"""

from __future__ import annotations

import bisect
import random
import statistics
from dataclasses import dataclass, field

M = 16
MOD = 1 << M  # 65536


def in_interval(x: int, start: int, end: int) -> bool:
    """x in (start, end] on the modular circle (start < end linear OR wraps)."""
    if start == end:
        return True
    if start < end:
        return start < x <= end
    return x > start or x <= end


# ---------------------------------------------------------------------------
@dataclass
class Node:
    nid: int
    successor_list: list[int] = field(default_factory=list)  # stale-ish
    predecessor: int | None = None
    alive: bool = True


class ChordRing:
    def __init__(self, n: int, r: int, seed: int):
        self.n = n
        self.r = r
        self.rng = random.Random(seed)
        ids = self.rng.sample(range(MOD), n)
        ids.sort()
        self.sorted_ids: list[int] = ids
        self.nodes: dict[int, Node] = {i: Node(nid=i) for i in ids}

    # --- failure ---------------------------------------------------------
    def mark_dead_fraction(self, f: float) -> None:
        if f <= 0:
            return
        ids = self.sorted_ids.copy()
        self.rng.shuffle(ids)
        k = int(round(f * len(ids)))
        for nid in ids[:k]:
            self.nodes[nid].alive = False

    def live_ids(self) -> list[int]:
        return [nid for nid in self.sorted_ids if self.nodes[nid].alive]

    # --- build successor lists from the FULL ring (all alive at "join") --
    def build_successor_lists(self) -> None:
        for nid in self.sorted_ids:
            node = self.nodes[nid]
            pos = bisect.bisect_left(self.sorted_ids, nid)
            succs: list[int] = []
            for j in range(1, self.r + 1):
                cand = self.sorted_ids[(pos + j) % len(self.sorted_ids)]
                if cand == nid:
                    break
                succs.append(cand)
            node.successor_list = succs
            # predecessor pointer: the live id immediately counter-clockwise
            pred_idx = (pos - 1) % len(self.sorted_ids)
            pred = self.sorted_ids[pred_idx]
            if pred != nid:
                node.predecessor = pred

    # --- ground truth ----------------------------------------------------
    def true_successor(self, key: int) -> int | None:
        """The live node that owns `key` in the current ring."""
        live = self.live_ids()
        if not live:
            return None
        idx = bisect.bisect_left(live, key)
        if idx == len(live):
            idx = 0
        return live[idx]

    # --- lookup ----------------------------------------------------------
    def find_successor(self, start_id: int, key: int,
                       max_hops: int = 5000) -> int | None:
        """Iterative lookup using ONLY the (possibly stale) successor list.

        Walk forward through the list, skipping dead successors.  At each
        step, if K is in (cur, next_alive_successor] on the ring, return it.
        Otherwise, advance to that successor.  If the entire successor list
        is dead we are stuck at `cur` and return None.
        """
        cur = start_id
        for _ in range(max_hops):
            node = self.nodes[cur]
            if not node.alive:
                return None
            # find first alive entry in this node's successor list
            next_alive = None
            for s in node.successor_list:
                if self.nodes[s].alive:
                    next_alive = s
                    break
            if next_alive is None:
                # all r successors are dead -> stuck
                return None
            # check ownership
            if in_interval(key, cur, next_alive):
                # next_alive covers the key.  Sanity: if key == cur (i.e. key
                # is exactly cur, which happens when cur owns the key),
                # then in_interval returns True via the wrap arm only if
                # cur > next_alive (wraps).  In that case key == cur means
                # key is the END of the interval (cur, next_alive] which
                # requires key <= next_alive or key > cur.  Key == cur > cur
                # is false; key == cur <= next_alive is true iff cur <=
                # next_alive.  In the wrap case cur > next_alive, so this
                # arm returns False.  In the linear case cur < next_alive,
                # in_interval(cur, cur, next_alive) -> True (since x <= end
                # when x == start is allowed... wait, our in_interval is
                # strict at start.  cur == start, so cur > start is False.
                # So we would NOT return cur here.  Good.)
                return next_alive
            # advance clockwise through the successor list (skip dead)
            cur = next_alive
        return None


def run_one(n: int, r: int, f: float, n_queries: int, seed: int) -> dict:
    ring = ChordRing(n=n, r=r, seed=seed)
    ring.build_successor_lists()      # lists built when all nodes alive
    ring.mark_dead_fraction(f)        # then some die

    rng = random.Random(seed + 1)
    queries = [rng.randrange(MOD) for _ in range(n_queries)]
    gt = [ring.true_successor(k) for k in queries]
    live = ring.live_ids()

    successes = none_lookup = wrong_lookup = none_gt = stuck_hops = 0
    if not live:
        return dict(success_rate=0.0, successes=0, decided=0, none_gt=n_queries,
                    none_lookup=0, wrong_lookup=0, live_count=0,
                    avg_hops_on_success=0.0)

    total_hops_on_success = 0
    n_success_with_hops = 0
    for key, true_node in zip(queries, gt):
        if true_node is None:
            none_gt += 1
            continue
        requester = live[rng.randrange(len(live))]
        # count hops for diagnostics
        cur = requester
        hops = 0
        node = ring.nodes[cur]
        for s in node.successor_list:
            if ring.nodes[s].alive:
                cur = s
                hops += 1
                break
        result = ring.find_successor(requester, key)
        if result == true_node:
            successes += 1
            total_hops_on_success += hops
            n_success_with_hops += 1
        elif result is None:
            none_lookup += 1
        else:
            wrong_lookup += 1

    decided = n_queries - none_gt
    return {
        'success_rate': successes / decided if decided else 0.0,
        'successes': successes,
        'decided': decided,
        'none_gt': none_gt,
        'none_lookup': none_lookup,
        'wrong_lookup': wrong_lookup,
        'live_count': len(live),
        'avg_hops_on_success': (total_hops_on_success / n_success_with_hops
                                if n_success_with_hops else 0.0),
    }


def main():
    import json
    N = 1000
    N_QUERIES = 10_000
    F_VALUES = [0.0, 0.1, 0.2, 0.3, 0.5]
    EXTENDED_F = [0.6, 0.7, 0.8, 0.9, 0.95]      # extra cells to find breakdown
    R_VALUES = [1, 16]
    SEEDS = [42, 43, 44, 45, 46]

    rows = []
    for r in R_VALUES:
        for f in F_VALUES + EXTENDED_F:
            rates, none_l, wrong_l, hops = [], [], [], []
            for seed in SEEDS:
                res = run_one(N, r, f, N_QUERIES, seed)
                rates.append(res['success_rate'])
                none_l.append(res['none_lookup'])
                wrong_l.append(res['wrong_lookup'])
                hops.append(res['avg_hops_on_success'])
            rows.append({
                'r': r,
                'f': f,
                'is_main': f in F_VALUES,
                'success_rate_mean': statistics.mean(rates),
                'success_rate_stdev': statistics.pstdev(rates),
                'success_rate_min': min(rates),
                'success_rate_max': max(rates),
                'none_lookup_mean': statistics.mean(none_l),
                'wrong_lookup_mean': statistics.mean(wrong_l),
                'avg_hops_on_success_mean': statistics.mean(hops),
                'live_count_mean': N * (1 - f),
            })

    print(json.dumps(rows, indent=2))
    with open('simulation_results.json', 'w') as fp:
        json.dump(rows, fp, indent=2)


if __name__ == '__main__':
    main()