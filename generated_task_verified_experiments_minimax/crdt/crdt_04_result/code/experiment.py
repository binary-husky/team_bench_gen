"""
Experiment: compare state-based (CvRDT) G-Counter vs op-based (CmRDT) Counter
in terms of total transmitted bytes and per-message bytes.

Setup (per task):
- N = 5 replicas.
- M in {1e3, 5e3, 1e4, 5e4} total increments, evenly split across replicas.
- state-based: each local increment broadcasts the full state vector to all other
  replicas; receivers take component-wise max.
- op-based: each local increment broadcasts a single increment op (replica i +1)
  to all other replicas via reliable causal broadcast; receivers add.
- 3 different seeds.
- Byte counts use the actual JSON-encoded length of each message.
"""

import json
import random
import statistics
from typing import List, Tuple

N = 5
M_GRID = [1_000, 5_000, 10_000, 50_000]
SEEDS = [1, 42, 2024]


def make_interleaving(seed: int, M: int) -> List[int]:
    """Return a length-M list of replica ids in the order increments occur.
    Operations are evenly split across replicas; the seed controls interleaving.
    """
    rng = random.Random(seed)
    # start from a balanced round-robin then permute within blocks to vary
    per_replica, rem = divmod(M, N)
    ops = []
    for r in range(N):
        ops.extend([r] * per_replica)
    ops.extend([0] * rem)  # any leftover goes to replica 0; rare
    rng.shuffle(ops)
    return ops


# ---------------------------------------------------------------------------
# State-based G-Counter (Spec 6)
# ---------------------------------------------------------------------------
def run_state_based(M: int, ops: List[int]) -> Tuple[int, int, List[int]]:
    """Return (total_bytes, num_messages, per_message_sizes_in_bytes)."""
    # vector[i] is replica i's local count
    vector = [0] * N
    total_bytes = 0
    sizes: List[int] = []
    for r in ops:
        vector[r] += 1
        # broadcast the FULL state to every other replica
        msg = {"v": vector}
        encoded = json.dumps(msg, separators=(",", ":"))
        size = len(encoded.encode("utf-8"))
        # one message per other replica
        for _ in range(N - 1):
            total_bytes += size
            sizes.append(size)
    return total_bytes, len(sizes), sizes


# ---------------------------------------------------------------------------
# Op-based CmRDT Counter (Spec 5 variant for increment only)
# ---------------------------------------------------------------------------
def run_op_based(M: int, ops: List[int]) -> Tuple[int, int, List[int]]:
    """Return (total_bytes, num_messages, per_message_sizes_in_bytes)."""
    total_bytes = 0
    sizes: List[int] = []
    for r in ops:
        # single increment op: "replica i +1"
        msg = {"i": r}
        encoded = json.dumps(msg, separators=(",", ":"))
        size = len(encoded.encode("utf-8"))
        for _ in range(N - 1):
            total_bytes += size
            sizes.append(size)
    return total_bytes, len(sizes), sizes


def summarize(sizes: List[int]) -> Tuple[float, float, float]:
    return (
        statistics.mean(sizes),
        min(sizes),
        max(sizes),
    )


def main() -> None:
    rows = []
    for M in M_GRID:
        sb_totals, sb_avg_msg = [], []
        op_totals, op_msg_size = [], []
        for seed in SEEDS:
            ops = make_interleaving(seed, M)

            sb_bytes, sb_n, sb_sizes = run_state_based(M, ops)
            op_bytes, op_n, op_sizes = run_op_based(M, ops)

            assert sb_n == M * (N - 1)
            assert op_n == M * (N - 1)

            sb_avg, _, _ = summarize(sb_sizes)
            op_avg, _, _ = summarize(op_sizes)

            sb_totals.append(sb_bytes)
            sb_avg_msg.append(sb_avg)
            op_totals.append(op_bytes)
            op_msg_size.append(op_avg)

            rows.append({
                "M": M, "seed": seed,
                "state_total": sb_bytes, "state_avg_msg": sb_avg,
                "op_total": op_bytes, "op_msg_size": op_avg,
            })

        print(f"\n=== M = {M:>6} ===")
        print(f"  state-based: total bytes (mean over seeds) = "
              f"{statistics.mean(sb_totals):>12,.0f}  "
              f"avg msg bytes = {statistics.mean(sb_avg_msg):>7.2f}")
        print(f"  op-based   : total bytes (mean over seeds) = "
              f"{statistics.mean(op_totals):>12,.0f}  "
              f"msg bytes (const) = {statistics.mean(op_msg_size):>7.2f}")
        print(f"  ratio (state/op total) = "
              f"{statistics.mean(sb_totals)/statistics.mean(op_totals):.2f}x")

    # save raw results
    with open("raw_results.json", "w") as f:
        json.dump(rows, f, indent=2)


if __name__ == "__main__":
    main()
