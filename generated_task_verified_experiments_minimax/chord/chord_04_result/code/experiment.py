"""
Experiment: consistent hashing key load balance on an in-process virtual Chord ring.

Setup:
  - N = 200 physical nodes.
  - K = 1e5 random keys.
  - v in {1, 2, 5, 10, 20} virtual nodes per physical node.
  - Hash function: SHA-1, full 160-bit digest (as in Chord paper).
  - Keys and virtual-node ids are hashed onto a 2^160 modular ring.
  - Each key is assigned to the successor virtual node; load is aggregated by physical node.

For each v, report:
  - max/mean load ratio across physical nodes
  - coefficient of variation (std/mean) of per-physical-node load

Fixed: N, K, random seed for key strings, hash function, identifier space.
Variable: v (number of virtual nodes per physical node).
"""

import hashlib
import statistics
import random
import time

# ---------------- parameters ----------------
N = 200                       # physical nodes
K = 100_000                   # keys
VS = [1, 2, 5, 10, 20]        # virtual nodes per physical node
RANDOM_SEED = 20260628        # fixed seed for reproducibility
M_BITS = 160                  # identifier space (SHA-1 digest size, per the paper)
M_MOD = 1 << M_BITS           # 2^160

# ---------------- helpers ----------------
def sha1_int(s: str) -> int:
    """Hash a string with SHA-1 and return the digest as a 160-bit integer."""
    return int.from_bytes(hashlib.sha1(s.encode("utf-8")).digest(), "big")


def make_virtual_node_ids(v: int):
    """
    Generate N*v virtual node ids on the ring.
    Each virtual node carries its physical node index.
    Returns: list of (hash_id, physical_node_index) sorted ascending by hash_id.
    """
    vnodes = []
    for pid in range(N):
        for j in range(v):
            h = sha1_int(f"node-{pid}-vnode-{j}")
            vnodes.append((h, pid))
    vnodes.sort(key=lambda x: x[0])
    return vnodes


def assign_keys(vnodes_sorted, key_hashes):
    """
    For each key hash, find its successor virtual node (first vnode whose id >= key hash,
    wrapping around at the end). Aggregate loads into per-physical-node counters.

    Uses bisect for O(log(N*v)) per key.
    """
    ring = [h for (h, _) in vnodes_sorted]
    pids = [pid for (_, pid) in vnodes_sorted]
    L = len(ring)

    loads = [0] * N
    # Linear scan in batches with bisect for the rest:
    import bisect
    for kh in key_hashes:
        idx = bisect.bisect_left(ring, kh)
        if idx == L:
            idx = 0  # wrap around
        loads[pids[idx]] += 1
    return loads


def imbalance_stats(loads):
    mean = sum(loads) / len(loads)
    mx = max(loads)
    std = statistics.pstdev(loads)   # population std; balanced with mean
    return mx, mean, std, mx / mean, std / mean


# ---------------- main ----------------
def main():
    rng = random.Random(RANDOM_SEED)
    # Pre-generate K random key strings with the fixed seed (so the key stream
    # is identical across runs of v).
    key_strs = [f"key-{rng.randrange(1 << 31)}-{rng.randrange(1 << 31)}"
                for _ in range(K)]
    print(f"Pre-hashing {K} keys with SHA-1...", flush=True)
    t0 = time.time()
    key_hashes = [sha1_int(ks) for ks in key_strs]
    print(f"  done in {time.time() - t0:.2f}s", flush=True)

    results = []
    for v in VS:
        print(f"\n=== v = {v} ===", flush=True)
        t0 = time.time()
        vnodes = make_virtual_node_ids(v)
        loads = assign_keys(vnodes, key_hashes)
        mx, mean, std, max_over_mean, cv = imbalance_stats(loads)
        elapsed = time.time() - t0
        print(f"  physical nodes      : {N}")
        print(f"  virtual node count  : {N * v}")
        print(f"  total assigned keys : {sum(loads)}")
        print(f"  min load            : {min(loads)}")
        print(f"  max load            : {mx}")
        print(f"  mean load           : {mean:.4f}")
        print(f"  std load (pop.)     : {std:.4f}")
        print(f"  max/mean            : {max_over_mean:.6f}")
        print(f"  std/mean (CV)       : {cv:.6f}")
        print(f"  elapsed             : {elapsed:.2f}s")
        results.append({
            "v": v,
            "max": mx,
            "mean": mean,
            "std": std,
            "max_over_mean": max_over_mean,
            "cv": cv,
            "min": min(loads),
            "vnodes": N * v,
        })

    return results


if __name__ == "__main__":
    main()
