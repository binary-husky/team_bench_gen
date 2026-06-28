#!/usr/bin/env python3
"""
In-process virtual Chord ring simulation (no network / socket / docker).

Implements the Chord finger-table routing protocol exactly as in
Stoica et al., "Chord: A Scalable Peer-to-peer Lookup Service",
SIGCOMM 2001:

  find_successor(id):
      if id in (n, successor]:  return successor
      else:                     n' = closest_preceding_node(id)
                                 return n'.find_successor(id)

  closest_preceding_node(id):
      for i = m downto 1:
          if finger[i] in (n, id):  return finger[i]
      return n

  finger[i] = successor( (n + 2^(i-1)) mod 2^m )        # i = 1..m

Goal: measure how the lookup path length (number of routing hops per
find_successor) varies with the number of nodes N, and compare against
log2(N).  Only N varies; m, #queries, seed and routing protocol are fixed.
"""

import bisect
import hashlib
import math
import random
import statistics
import sys

# ----------------------------- fixed settings ------------------------------
M = 160                      # identifier length in bits (SHA-1)  -- FIXED
RING = 1 << M                # ring size 2^m
NUM_QUERIES = 10_000         # ~1e4 random-key lookups per N    -- FIXED
SEED = 1_234_567             # fixed RNG seed                    -- FIXED
NS = [100, 200, 500, 1000, 2000]
MAX_HOPS_CAP = M + 10        # safety guard against pathological loops


# ----------------------------- ring arithmetic -----------------------------
def sha1_id(label: bytes) -> int:
    """Map a byte label onto an m-bit identifier via SHA-1 (paper spec)."""
    return int.from_bytes(hashlib.sha1(label).digest(), "big") % RING


def in_open(x, a, b):
    """True if x lies in the open circular interval (a, b)."""
    if a == b:
        return False
    if a < b:
        return a < x < b
    return x > a or x < b        # wrap-around


def in_open_closed(x, a, b):
    """True if x lies in the half-open circular interval (a, b]."""
    if a == b:
        return x != a            # whole ring minus a (never hit in practice)
    if a < b:
        return a < x <= b
    return x > a or x <= b       # wrap-around


# ----------------------------- ring / nodes --------------------------------
class Node:
    __slots__ = ("id", "finger", "successor")

    def __init__(self, node_id):
        self.id = node_id
        self.finger = []          # length-M list of node ids; finger[0] == succ
        self.successor = None     # immediate clockwise neighbour (== finger[0])


def build_ring(sorted_ids):
    """Create every node with a *complete* m-entry finger table."""
    n = len(sorted_ids)
    nodes = {nid: Node(nid) for nid in sorted_ids}

    def ring_succ(key):
        """successor(key): smallest node id >= key, wrapping around."""
        idx = bisect.bisect_left(sorted_ids, key)
        if idx == n:
            idx = 0
        return sorted_ids[idx]

    for nid in sorted_ids:
        finger = [ring_succ((nid + (1 << i)) % RING) for i in range(M)]
        node = nodes[nid]
        node.finger = finger
        node.successor = finger[0]
    return nodes


# ----------------------------- routing -------------------------------------
def closest_preceding(node, key):
    """closest_preceding_node(key): scan finger table top-down (paper)."""
    nid = node.id
    for f in reversed(node.finger):
        if in_open(f, nid, key):
            return f
    return nid


def find_successor_hops(nodes, start_id, key):
    """
    Hop-by-hop find_successor following the finger-table routing protocol.
    Returns (successor_id, hops).  A 'hop' is one inter-node forward
    (closest_preceding -> find_successor at the next node); the node where
    the answer is resolved locally contributes 0 extra hops.
    """
    node = nodes[start_id]
    hops = 0
    while True:
        if in_open_closed(key, node.id, node.successor):
            return node.successor, hops
        nxt = closest_preceding(node, key)
        if nxt == node.id or hops >= MAX_HOPS_CAP:   # safety (degenerate key==id)
            return node.successor, hops
        node = nodes[nxt]
        hops += 1


# ----------------------------- experiment driver ---------------------------
def run(N, seed):
    rng = random.Random(seed)

    # N node identifiers: hash distinct random labels -> m-bit ids.
    node_ids = list({sha1_id(b"node|%d|%d" % (N, rng.getrandbits(64)))
                     for _ in range(N)})
    # guard against (astronomically unlikely) hash collisions shrinking the set
    while len(node_ids) < N:
        node_ids.append(sha1_id(b"node|%d|%d" % (N, rng.getrandbits(64))))
    node_ids = sorted(set(node_ids))[:N]

    nodes = build_ring(node_ids)
    sorted_ids = node_ids
    n_nodes = len(sorted_ids)

    def true_successor(key):
        idx = bisect.bisect_left(sorted_ids, key)
        if idx == n_nodes:
            idx = 0
        return sorted_ids[idx]

    hops_list = []
    mismatches = 0
    for q in range(NUM_QUERIES):
        key = sha1_id(b"key|%d|%d" % (q, rng.getrandbits(64)))
        start = rng.choice(sorted_ids)            # random initiating node
        succ, h = find_successor_hops(nodes, start, key)
        hops_list.append(h)
        if succ != true_successor(key):           # correctness self-check
            mismatches += 1

    return {
        "N": N,
        "avg": statistics.fmean(hops_list),
        "max": max(hops_list),
        "min": min(hops_list),
        "stdev": statistics.pstdev(hops_list),
        "log2_N": math.log2(N),
        "half_log2_N": 0.5 * math.log2(N),
        "mismatches": mismatches,
    }


def main():
    print(f"m={M}, queries={NUM_QUERIES}, seed={SEED}\n")
    results = []
    for N in NS:
        r = run(N, SEED + N)        # per-N offset so node sets differ, still fixed
        results.append(r)
        print("N=%5d  avg=%.4f  max=%2d  min=%d  stdev=%.3f  "
              "log2(N)=%.3f  0.5*log2(N)=%.3f  mismatches=%d"
              % (r["N"], r["avg"], r["max"], r["min"], r["stdev"],
                 r["log2_N"], r["half_log2_N"], r["mismatches"]))
    # stash for the summary writer
    import json
    with open("results.json", "w") as fh:
        json.dump(results, fh, indent=2)
    return results


if __name__ == "__main__":
    main()
