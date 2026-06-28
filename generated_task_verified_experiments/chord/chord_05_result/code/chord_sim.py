#!/usr/bin/env python3
"""
In-process virtual Chord ring: node join + stabilization study.

Faithfully implements the *stabilization scheme* of Stoica et al.,
"Chord: A Scalable Peer-to-peer Lookup Service" (SIGCOMM 2001),
Figures 4 (find_successor / find_predecessor / closest_preceding_finger)
and 7 (create / join / stabilize / notify / fix_fingers).

Experiment:
  - Start from an already-stabilized ring of N0 = 500 nodes (correct
    successor/predecessor/finger tables).
  - Batch-join Delta new nodes "all at once": each new node knows ONLY an
    access point into the original stable ring, so it computes its initial
    successor against the 500-node ring and does not see the other joiners.
    Its predecessor = nil and finger table = (uncorrected) all pointing to
    that successor. Existing nodes are NOT told about the joiners.
  - Each round: every node runs stabilize() once and fix_fingers() once
    (stabilize applied sequentially in a fresh seeded-random order, each
    call seeing the latest state; then fix_fingers once per node).
  - After each round: issue ~1e4 random key lookups from random origin
    nodes, count the fraction whose returned successor equals the TRUE
    immediate successor among ALL (N0+Delta) members.

Independent variables: Delta and round number.
Fixed: N0, Delta set, query count, random seed, stabilization routines.
"""

import bisect
import random
import sys
import time

# ---- ring parameters -------------------------------------------------------
M_BITS = 24                 # identifier length m; ring size = 2^m
M = 1 << M_BITS             # 2^24  (plenty sparse for <=700 nodes; m does not
                            #        affect *correctness* dynamics, only finger
                            #        routing speed -- correctness depends only
                            #        on successor-pointer convergence)
N0 = 500
DELTAS = [50, 100, 200]
QUERIES = 10000             # ~1e4 random key lookups per measurement
SEED = 20240601
MAX_ROUNDS = 25
EARLY_STOP_STABLE = 3       # stop after this many consecutive 100% rounds


# ---- interval helpers (all arithmetic modulo M, clockwise) -----------------
def in_oc(x, a, b):
    """x in (a, b] clockwise (left-open, right-closed)."""
    if a == b:
        return x != a
    if a < b:
        return a < x <= b
    return x > a or x <= b   # wraps

def in_oo(x, a, b):
    """x in (a, b) clockwise (open-open)."""
    if a == b:
        return False
    if a < b:
        return a < x < b
    return x > a or x < b    # wraps


class Node:
    __slots__ = ("id", "successor", "predecessor", "finger")
    def __init__(self, nid):
        self.id = nid
        self.successor = None       # explicit successor pointer (Fig. 7)
        self.predecessor = None     # None == nil
        self.finger = None          # list of length m; finger[0] kept == successor


class Chord:
    def __init__(self):
        self.nodes = {}             # id -> Node
        self.sorted_ids = []        # all member ids, ascending (ground truth)

    # -- ground-truth successor over ALL current members ---------------------
    def true_successor(self, key):
        ids = self.sorted_ids
        i = bisect.bisect_left(ids, key)
        if i == len(ids):
            i = 0
        return ids[i]

    # -- build a fully-correct (stable) ring ---------------------------------
    def build_stable(self, ids):
        ids = sorted(ids)
        self.sorted_ids = ids
        n = len(ids)
        for idx, nid in enumerate(ids):
            nd = Node(nid)
            nd.successor = ids[(idx + 1) % n]
            nd.predecessor = ids[(idx - 1) % n]
            nd.finger = [self.true_successor((nid + (1 << i)) % M)
                         for i in range(M_BITS)]
            self.nodes[nid] = nd

    # -- lookup primitives (Fig. 4), iterative -------------------------------
    def closest_preceding_finger(self, nid, key):
        nd = self.nodes[nid]
        fng = nd.finger
        for i in range(M_BITS - 1, -1, -1):
            f = fng[i]
            if in_oo(f, nid, key):
                return f
        # finger[0] == successor is always in (nid, key) when key not in
        # (nid, successor]; guarantees forward progress, no infinite loop.
        return nd.successor

    def find_predecessor(self, start_id, key):
        nodes = self.nodes
        n_id = start_id
        cap = 4 * len(self.sorted_ids) + 16
        hops = 0
        while not in_oc(key, n_id, nodes[n_id].successor):
            n_id = self.closest_preceding_finger(n_id, key)
            hops += 1
            if hops > cap:
                return None        # pathological / cannot resolve -> failure
        return n_id

    def find_successor(self, start_id, key):
        pred = self.find_predecessor(start_id, key)
        if pred is None:
            return None
        return self.nodes[pred].successor

    # -- stabilization scheme (Fig. 7) ---------------------------------------
    def stabilize(self, nid):
        nd = self.nodes[nid]
        succ = nd.successor
        succ_node = self.nodes[succ]
        x = succ_node.predecessor
        if x is not None and in_oo(x, nid, succ):
            nd.successor = x
            nd.finger[0] = x        # keep finger[0] in sync with successor
            succ = x
        self.notify(succ, nid)

    def notify(self, nid, prime):
        nd = self.nodes[nid]
        p = nd.predecessor
        if p is None or in_oo(prime, p, nid):
            nd.predecessor = prime

    def fix_fingers(self, nid, rng):
        nd = self.nodes[nid]
        i = rng.randint(1, M_BITS - 1)   # skip index 0 (== successor)
        start = (nid + (1 << i)) % M
        nd.finger[i] = self.find_successor(nid, start)

    # -- batch join of new nodes against the ORIGINAL stable ring -----------
    def batch_join(self, new_ids, old_sorted):
        for nid in new_ids:
            i = bisect.bisect_left(old_sorted, nid)
            if i == len(old_sorted):
                i = 0
            succ = old_sorted[i]         # successor among old nodes only
            nd = Node(nid)
            nd.successor = succ
            nd.predecessor = None
            nd.finger = [succ] * M_BITS  # uncorrected: only knows successor
            self.nodes[nid] = nd
        all_ids = sorted(self.nodes.keys())
        self.sorted_ids = all_ids

    # -- one stabilization round --------------------------------------------
    def round_stabilize_fix(self, rng):
        order = self.sorted_ids[:]
        rng.shuffle(order)
        for nid in order:
            self.stabilize(nid)
        rng.shuffle(order)
        for nid in order:
            self.fix_fingers(nid, rng)

    # -- measurement ---------------------------------------------------------
    def measure_lookup_correctness(self, n_queries, rng):
        ids = self.sorted_ids
        n = len(ids)
        rndr = rng.randrange
        correct = 0
        for _ in range(n_queries):
            key = rndr(M)
            origin = ids[rndr(n)]
            res = self.find_successor(origin, key)
            if res is not None and res == self.true_successor(key):
                correct += 1
        return correct / n_queries

    def successor_pointer_correctness(self):
        """Fraction of nodes whose `successor` field is the true immediate
        successor among all members. Cross-check: lookup correctness should
        track this (fingers affect speed, not correctness)."""
        ids = self.sorted_ids
        n = len(ids)
        ok = 0
        for idx, nid in enumerate(ids):
            true_succ = ids[(idx + 1) % n]
            if self.nodes[nid].successor == true_succ:
                ok += 1
        return ok / n


def sample_distinct_ids(k, rng):
    s = set()
    while len(s) < k:
        s.add(rng.randrange(M))
    return list(s)


def run_one(delta, seed):
    rng = random.Random(seed)
    ring = Chord()
    old_ids = sample_distinct_ids(N0, rng)
    ring.build_stable(old_ids)
    old_sorted = ring.sorted_ids[:]          # snapshot of stable ring

    new_ids = sample_distinct_ids(delta, rng)
    # ensure distinct from old (rejection already keeps them in [0,M), and
    # collision with old is possible but rare; drop any duplicates)
    new_ids = [x for x in new_ids if x not in ring.nodes]
    while len(new_ids) < delta:
        x = rng.randrange(M)
        if x not in ring.nodes:
            new_ids.append(x)

    ring.batch_join(new_ids, old_sorted)

    rows = []
    # round 0: immediately after batch join, before any stabilization
    rows.append((0,
                 ring.measure_lookup_correctness(QUERIES, rng),
                 ring.successor_pointer_correctness()))
    stable_streak = 0
    for r in range(1, MAX_ROUNDS + 1):
        ring.round_stabilize_fix(rng)
        rate = ring.measure_lookup_correctness(QUERIES, rng)
        sp = ring.successor_pointer_correctness()
        rows.append((r, rate, sp))
        if rate >= 0.9999:
            stable_streak += 1
            if stable_streak >= EARLY_STOP_STABLE:
                break
        else:
            stable_streak = 0
    return rows


def main():
    t0 = time.time()
    print(f"N0={N0}, m={M_BITS} (ring 2^{M_BITS}), queries/round={QUERIES}, "
          f"seed={SEED}")
    all_results = {}
    for delta in DELTAS:
        t = time.time()
        rows = run_one(delta, SEED + delta)   # per-delta offset, reproducible
        all_results[delta] = rows
        print(f"\n=== Delta = {delta}  (took {time.time()-t:.1f}s) ===")
        print("round  lookup_correct  succ_ptr_correct")
        for r, rate, sp in rows:
            print(f"  {r:3d}    {rate:7.4f}         {sp:7.4f}")
        # rounds to ~100%
        to_full = next((r for r, rate, _ in rows if rate >= 0.9999), None)
        to_999 = next((r for r, rate, _ in rows if rate >= 0.999), None)
        print(f"  -> first round >=0.9999 (≈100%): {to_full}")
        print(f"  -> first round >=0.999       : {to_999}")
    print(f"\nTotal time: {time.time()-t0:.1f}s")
    return all_results


if __name__ == "__main__":
    main()
