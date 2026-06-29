"""
Chord ring simulation: in-process Python implementation of Chord lookup.

- Nodes are objects (with id, finger table, predecessor).
- Routing table is data (finger table).
- Query is in-memory hop count.
- No real network/socket/Docker.

Implements the iterative Chord lookup as described in
Stoica et al., "Chord: A Scalable Peer-to-peer Lookup Service
for Internet Applications" (SIGCOMM 2001).
"""

import hashlib
import math
import random
import statistics
import time
from bisect import bisect_left


# ============================
# Fixed experiment parameters
# ============================
# m = identifier-space size in bits. We use SHA-1 (m=160) as the canonical
# Chord identifier function; identifier space is 2^160.
M = 160
M_MAX = 1 << M           # 2^160

QUERY_COUNT = 10_000     # queries per N
RANDOM_SEED = 42         # fixed seed for reproducibility
N_VALUES = [100, 200, 500, 1000, 2000]


# ============================
# Consistent hashing helpers
# ============================

def hash_id(text: str) -> int:
    """SHA-1 of text -> integer id in [0, 2^M)."""
    h = hashlib.sha1(text.encode("utf-8")).digest()
    return int.from_bytes(h, "big") % M_MAX


def in_interval(x: int, a: int, b: int, inclusive_left: bool = False) -> bool:
    """Is x in (a, b] (or [a, b] if inclusive_left) modulo 2^M?

    Standard Chord convention: successor(k) is the first node whose id is
    >= k on the circle, so we use (n, n.successor] for "predecessor-ness".
    """
    if a == b:
        return inclusive_left and x == a
    if a < b:
        return (a <= x <= b) if inclusive_left else (a < x <= b)
    # wrap-around
    return (x >= a) or (x <= b) if inclusive_left else (x > a) or (x <= b)


# ============================
# Chord node
# ============================

class ChordNode:
    __slots__ = ("id", "finger", "predecessor")

    def __init__(self, node_id: int):
        self.id = node_id
        self.finger = []            # list of (start, succ_id)
        self.predecessor = None

    def build_finger_table(self, sorted_ids):
        """Build finger table: finger[i] = (n + 2^i, succ(n + 2^i))."""
        n_ids = len(sorted_ids)
        self.finger = []
        for i in range(M):
            start = (self.id + (1 << i)) % M_MAX
            # First node with id >= start on the circle.
            j = bisect_left(sorted_ids, start)
            if j == n_ids:
                j = 0
            self.finger.append((start, sorted_ids[j]))

    def closest_preceding_finger(self, target: int) -> int:
        """Walk finger table from largest i to smallest, return the largest
        finger[i].node that is strictly in (self.id, target)."""
        for i in range(M - 1, -1, -1):
            succ_id = self.finger[i][1]
            if succ_id == self.id:
                continue
            # Strictly in (self.id, target] on the circle.
            # (Using (a, b] here matches the paper's `finger[i].node ∈ (n, id)`.)
            if in_interval(succ_id, self.id, target, inclusive_left=False):
                return succ_id
        return self.id

    def successor(self) -> int:
        return self.finger[0][1]


def find_successor_iterative(start_id: int, target: int, node_by_id):
    """Iterative Chord find_successor protocol.

    Returns (successor_id, hops) where hops = number of nodes OTHER than the
    start node that we contacted along the way (matching the paper's
    iterative-style path length, which counts one message per non-start hop).
    """
    current = start_id
    succ_id = node_by_id[current].successor()
    hops = 0

    # Direct hit: target is in [current, current.successor()] on the circle.
    # The start node resolves it in zero extra hops beyond itself, but to
    # follow the paper's path-length definition (every contacted node counts),
    # we still credit the request to the start node's successor as one hop
    # (it is the node that actually owns the key).
    if in_interval(target, current, succ_id, inclusive_left=True):
        return succ_id, 1

    # Otherwise, iteratively forward to closest preceding finger.
    hops = 1  # we've contacted current.successor() in the check above
    while True:
        nxt = node_by_id[current].closest_preceding_finger(target)
        if nxt == current:
            # Stuck: return current.successor().
            return succ_id, hops
        current = nxt
        succ_id = node_by_id[current].successor()
        hops += 1
        if in_interval(target, current, succ_id, inclusive_left=True):
            return succ_id, hops
        if hops > 10_000:
            raise RuntimeError(
                f"Lookup exceeded 10000 hops: target={target}, current={current}"
            )


# ============================
# Experiment driver
# ============================

def build_ring(N: int, rng: random.Random):
    """Create N unique Chord nodes and build their finger tables."""
    node_ids_set = set()
    while len(node_ids_set) < N:
        # Randomly named source -> SHA-1 -> 160-bit Chord id.
        src = f"node-{rng.randrange(1 << 64)}"
        node_ids_set.add(hash_id(src))
    node_ids = sorted(node_ids_set)
    node_by_id = {nid: ChordNode(nid) for nid in node_ids}

    # Wire up finger tables.
    for nid in node_ids:
        node_by_id[nid].build_finger_table(node_ids)

    # Predecessors (not used by lookup but kept for completeness).
    m = len(node_ids)
    for k, nid in enumerate(node_ids):
        node_by_id[nid].predecessor = node_ids[(k - 1) % m]

    return node_ids, node_by_id


def run_for_n(N: int, rng: random.Random):
    node_ids, node_by_id = build_ring(N, rng)

    # Generate random key IDs to query.
    keys = [rng.randrange(M_MAX) for _ in range(QUERY_COUNT)]
    start_nodes = [rng.choice(node_ids) for _ in range(QUERY_COUNT)]

    hops_list = [0] * QUERY_COUNT
    for i in range(QUERY_COUNT):
        _, h = find_successor_iterative(start_nodes[i], keys[i], node_by_id)
        hops_list[i] = h

    hops_sorted = sorted(hops_list)
    mean_h = statistics.fmean(hops_list)
    max_h = max(hops_list)
    median_h = statistics.median(hops_list)
    p99_h = hops_sorted[int(0.99 * QUERY_COUNT) - 1]

    return {
        "N": N,
        "mean": mean_h,
        "max": max_h,
        "median": median_h,
        "p99": p99_h,
        "log2_N": math.log2(N),
    }


def main():
    rng = random.Random(RANDOM_SEED)
    rows = []
    print(f"{'N':>5}  {'mean':>8}  {'max':>4}  {'median':>7}  {'p99':>4}  "
          f"{'log2(N)':>8}  {'mean/log2':>10}  {'time(s)':>8}")
    print("-" * 70)
    for N in N_VALUES:
        t0 = time.time()
        r = run_for_n(N, rng)
        elapsed = time.time() - t0
        ratio = r["mean"] / r["log2_N"]
        rows.append((r["mean"], r["max"], r["median"], r["p99"], r["log2_N"], ratio, elapsed))
        print(f"{N:>5d}  {r['mean']:>8.4f}  {r['max']:>4d}  {r['median']:>7.4f}  "
              f"{r['p99']:>4d}  {r['log2_N']:>8.4f}  {ratio:>10.4f}  {elapsed:>8.2f}")

    # Persist a CSV for later inspection.
    with open("results.csv", "w") as f:
        f.write("N,mean_hops,max_hops,median_hops,p99_hops,log2_N,mean_over_log2,time_seconds\n")
        for N, row in zip(N_VALUES, rows):
            mean_h, max_h, median_h, p99_h, log2N, ratio, elapsed = row
            f.write(f"{N},{mean_h:.6f},{max_h},{median_h:.6f},{p99_h},{log2N:.6f},"
                    f"{ratio:.6f},{elapsed:.3f}\n")
    print("\nResults written to results.csv")
    return rows


if __name__ == "__main__":
    main()
