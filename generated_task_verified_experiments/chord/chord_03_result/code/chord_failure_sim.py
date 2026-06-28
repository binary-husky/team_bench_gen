#!/usr/bin/env python3
"""
In-process Chord ring failure-tolerance experiment.

Faithful to Stoica et al., "Chord: A Scalable Peer-to-peer Lookup Service
for Internet Applications", SIGCOMM 2001, especially Section 5.2
(Failures and Replication) and Theorems 7 & 8.

Goal (from task.md):
  - Fix N = 1000 nodes on a virtual Chord ring (no real network).
  - Each node keeps a successor list of length r.
  - For r in {1, 16}:
      randomly fail a fraction f in {0, 0.1, 0.2, 0.3, 0.5} of nodes,
      then issue ~1e4 random key lookups from *surviving* nodes using
      (stale) finger tables + successor lists,
      measure the lookup success rate = fraction of lookups that return the
      correct *surviving* node responsible for the key.
  - Compare success rate vs f for r = 1 vs r = 16.

Failure-handling model (per paper Sec 5.2):
  * Finger tables are built on the full pre-failure ring and are NOT rebuilt
    after the failure burst (transient / pre-stabilization state). A failed
    finger is simply skipped during routing (paper: "a list of alternate
    nodes, easily found in the finger table entries preceding that of the
    failed node").
  * Each node's effective successor = the FIRST LIVE entry of its successor
    list (paper: "If node n notices that its successor has failed, it
    replaces it with the first live entry in its successor list"). With r=1
    this is just the immediate successor; if it died there is no fallback.
  * A lookup "succeeds" iff find_successor returns responsible(key), where
    responsible(key) is the first *surviving* node with id >= key (cyclically)
    -- the closest living successor to the key.
"""

import json
import time
import numpy as np

# ----------------------------- configuration --------------------------------
M = 20                      # identifier bits; RING = 2^M >> N (avoids id collisions)
RING = 1 << M
N = 1000                    # number of Chord nodes (fixed)
R_VALUES = [1, 16]          # successor-list lengths (independent var)
F_VALUES = [0.0, 0.1, 0.2, 0.3, 0.5]   # failure fractions (independent var)
N_QUERIES = 10_000          # ~1e4 random key lookups per (r, f, seed)
SEEDS = [0, 1, 2, 3, 4]     # fixed seeds for reproducibility
MAX_STEPS = 2 * N           # generous cap on routing hops (lookup is monotonic)


# ----------------------------- ring arithmetic ------------------------------
def ccw(a, b):
    """Clockwise distance from a to b on the ring, in [0, RING)."""
    return (b - a) % RING


def build_ring(n_nodes, rng):
    """n_nodes random distinct node identifiers, sorted ascending."""
    ids = np.sort(rng.choice(RING, size=n_nodes, replace=False))
    return ids


def build_fingers(ids):
    """Finger tables on the FULL (pre-failure) ring.

    fingers[n, k] = ring-index of successor( ids[n] + 2^k ),  k = 0..M-1.
    (These are kept stale after failures -- we skip failed entries at route time.)
    """
    n_nodes = len(ids)
    fingers = np.zeros((n_nodes, M), dtype=np.int64)
    for n in range(n_nodes):
        nid = int(ids[n])
        for k in range(M):
            start = (nid + (1 << k)) % RING
            i = int(np.searchsorted(ids, start, side='left'))
            if i == n_nodes:
                i = 0
            fingers[n, k] = i
    return fingers


def build_succ_lists(n_nodes, r):
    """successor list of node n = its r nearest successors = indices n+1..n+r (mod N)."""
    sl = np.zeros((n_nodes, r), dtype=np.int64)
    idxs = (np.arange(1, r + 1) % n_nodes)
    for n in range(n_nodes):
        sl[n] = (n + idxs) % n_nodes
    return sl


def effective_successor(n, succ_lists, alive, r):
    """First *live* entry of n's successor list, or -1 if all r have failed."""
    row = succ_lists[n]
    for j in range(r):
        s = row[j]
        if alive[s]:
            return s
    return -1


def closest_preceding_finger(n, nid, d_nk, ids, fingers, alive, succ_lists, r):
    """Largest-index live finger strictly in (n, key); else live successor-list
    head in (n, key); else -1 (stuck).  d_nk = ccw(nid, key)."""
    fn = fingers[n]
    for k in range(M - 1, -1, -1):
        fi = fn[k]
        if alive[fi]:
            d_nf = (int(ids[fi]) - nid) % RING
            if 0 < d_nf < d_nk:
                return fi
    es = effective_successor(n, succ_lists, alive, r)
    if es != -1:
        d_ne = (int(ids[es]) - nid) % RING
        if 0 < d_ne < d_nk:
            return es
    return -1


def find_successor(start_idx, key, ids, fingers, alive, succ_lists, r):
    """Iterative Chord find_successor with failure handling.
    Returns the responsible id, or None if routing gets stuck / times out."""
    n = start_idx
    nid = int(ids[n])
    for _ in range(MAX_STEPS):
        es = effective_successor(n, succ_lists, alive, r)
        d_nk = (key - nid) % RING
        if es != -1 and d_nk > 0:
            d_ns = (int(ids[es]) - nid) % RING
            if d_nk <= d_ns:               # key in (n, succ] -> landed on predecessor
                return int(ids[es])
        nxt = closest_preceding_finger(n, nid, d_nk, ids, fingers, alive, succ_lists, r)
        if nxt == -1 or nxt == n:          # cannot make progress -> fail
            return None
        n = int(nxt)
        nid = int(ids[n])
    return None


def compute_truths(keys, alive_ids):
    """Ground-truth responsible node for each key = first alive id >= key (cyclic)."""
    idx = np.searchsorted(alive_ids, keys, side='left')
    idx = np.where(idx == len(alive_ids), 0, idx)
    return alive_ids[idx]


# ----------------------------- experiment -----------------------------------
def main():
    t0 = time.time()
    # results[(r, f)] = list of per-seed success rates
    results = {(r, f): [] for r in R_VALUES for f in F_VALUES}

    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        ids = build_ring(N, rng)
        fingers = build_fingers(ids)

        for f in F_VALUES:
            alive = np.ones(N, dtype=bool)
            if f > 0:
                n_fail = int(round(f * N))
                fail_idx = rng.choice(N, size=n_fail, replace=False)
                alive[fail_idx] = False
            alive_ids = ids[alive]
            start_cand = np.where(alive)[0]

            # fixed query set for this (seed, f) -> paired comparison across r
            keys = rng.integers(0, RING, size=N_QUERIES)
            starts = start_cand[rng.integers(0, len(start_cand), size=N_QUERIES)]
            truths = compute_truths(keys, alive_ids)

            for r in R_VALUES:
                succ_lists = build_succ_lists(N, r)
                n_succ = 0
                for q in range(N_QUERIES):
                    res = find_successor(int(starts[q]), int(keys[q]),
                                         ids, fingers, alive, succ_lists, r)
                    if res is not None and res == int(truths[q]):
                        n_succ += 1
                rate = n_succ / N_QUERIES
                results[(r, f)].append(rate)
                print(f"  seed={seed} f={f:.1f} r={r:>2}  success={rate:.4f}  "
                      f"({n_succ}/{N_QUERIES})  alive={alive.sum()}")

    # aggregate
    summary = {}
    for r in R_VALUES:
        for f in F_VALUES:
            arr = np.array(results[(r, f)])
            summary[(r, f)] = (float(arr.mean()), float(arr.std()))

    print("\n===== MEAN SUCCESS RATE (mean +/- std over seeds) =====")
    print(f"{'f':>5} | {'r=1':>16} | {'r=16':>16}")
    for f in F_VALUES:
        m1, s1 = summary[(1, f)]
        m16, s16 = summary[(16, f)]
        print(f"{f:>5.1f} | {m1:.4f} +/- {s1:.4f} | {m16:.4f} +/- {s16:.4f}")
    print(f"\nelapsed: {time.time()-t0:.1f}s")

    # persist raw + summary
    out = {
        "config": {"M": M, "N": N, "R_VALUES": R_VALUES, "F_VALUES": F_VALUES,
                   "N_QUERIES": N_QUERIES, "SEEDS": SEEDS, "MAX_STEPS": MAX_STEPS},
        "per_seed": {f"{r},{f}": results[(r, f)] for r in R_VALUES for f in F_VALUES},
        "summary": {f"{r},{f}": list(summary[(r, f)]) for r in R_VALUES for f in F_VALUES},
    }
    with open("results.json", "w") as fh:
        json.dump(out, fh, indent=2)
    print("wrote results.json")
    return summary, results


if __name__ == "__main__":
    main()
