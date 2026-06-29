"""
Space-Saving experiment: study effect of counter slot count k on
precision, recall, max over-estimation error, and memory usage.

Setup (fixed):
- Zipfian stream of length N = 1_000_000
- Zipf parameter alpha = 1.5  (realistic skew, per Metwally et al. Sec. 5)
- Random seed = 42
- Alphabet size = 10_000
- Variable: k in {50, 100, 200, 500}

For each k we run the Stream-Summary / Space-Saving algorithm of
Metwally, Agrawal, El Abbadi (2005) and report, vs. exact counts:
- precision@k
- recall@k
- max over-estimation error on top-k candidates
- number of occupied slots (memory proxy)
"""

import math
import sys
import os
import json
import resource
import numpy as np
from collections import Counter


# ----------------------------- Stream generation -----------------------------

def zipf_stream(N: int, alpha: float, alphabet_size: int, seed: int):
    """Generate a Zipfian stream using numpy's generator (deterministic)."""
    rng = np.random.default_rng(seed)
    # numpy's Zipf is 1-indexed: P(X=k) ~ 1/k^alpha, k in 1..alphabet_size
    # We want items in 0..alphabet_size-1.
    sample = rng.zipf(a=alpha, size=N)
    # Map 1-indexed to 0-indexed, and clip anything > alphabet_size-1
    sample = np.where(sample <= alphabet_size, sample - 1, -1)
    # Some samples may exceed alphabet_size; those are very rare for alpha>=1.
    # We re-sample those deterministically by replacing with a uniform random
    # choice from the alphabet (still deterministic under the same seed).
    if np.any(sample < 0):
        mask = sample < 0
        n_bad = int(mask.sum())
        # Use the same RNG (still deterministic) to draw uniform replacements.
        repl = rng.integers(0, alphabet_size, size=n_bad)
        sample[mask] = repl
    return sample.astype(np.int64, copy=False)


# ----------------------------- Space-Saving impl -----------------------------

class SpaceSaving:
    """
    Stream-Summary / Space-Saving (Metwally et al. 2005).

    Maintains at most `capacity` counters (item, count, error).  The
    estimate `count` satisfies:
        true_freq - error <= count <= true_freq
    The counter-list is kept sorted by count ascending so the min-count
    counter can be evicted in O(capacity) worst case (or O(1) with a
    hand-rolled min-pointer).  For this experiment k is small (<=500)
    so a linear scan is fine.

    `occupied` is the number of non-empty slots (memory proxy).
    """

    __slots__ = ("capacity", "item", "count", "error", "size", "N_seen")

    def __init__(self, capacity: int):
        self.capacity = capacity
        # Parallel arrays: the per-slot (item, count, error).
        # Unused slots have item == -1.
        self.item = np.full(capacity, -1, dtype=np.int64)
        self.count = np.zeros(capacity, dtype=np.int64)
        self.error = np.zeros(capacity, dtype=np.int64)
        self.size = 0
        self.N_seen = 0

    def update(self, e: int):
        """Single-element update (e is already an int)."""
        self.N_seen += 1
        # Look for e in the table
        # We expect most updates to be hits, so use np.where first.
        match = np.where(self.item == e)[0]
        if match.size > 0:
            idx = int(match[0])
            self.count[idx] += 1
            return
        # Not present: replace the min counter
        if self.size < self.capacity:
            idx = self.size
            self.size += 1
            self.item[idx] = e
            # error = 0 on fresh insert
            self.count[idx] = 1
            self.error[idx] = 0
            return
        # Find the slot with minimum count; ties broken by first occurrence.
        # np.argmin returns the first occurrence of the minimum.
        idx = int(np.argmin(self.count))
        # New element e could have actually occurred between
        # min + 1 times since insertion.  So we set:
        #   count_m = min + 1, error_m = min
        m = int(self.count[idx])
        self.item[idx] = e
        self.count[idx] = m + 1
        self.error[idx] = m

    def update_batch(self, stream):
        """Process a 1-D numpy array of items."""
        # Loop in Python — k is tiny, but N is 1e6 so vectorizing matters.
        for e in stream:
            self.update(int(e))

    def top_k(self, k: int):
        """Return top-k by count (descending).  Each entry is (item, count, error)."""
        # Get the live slots
        live_idx = np.where(self.item >= 0)[0]
        if live_idx.size == 0:
            return []
        cnts = self.count[live_idx]
        # Sort descending by count
        order = np.argsort(-cnts, kind="stable")
        out = []
        for j in order[:k]:
            i = int(live_idx[int(j)])
            out.append((int(self.item[i]), int(self.count[i]), int(self.error[i])))
        return out


# ----------------------------- Evaluation -------------------------------------

def evaluate(estimated_top, exact_top, exact_counter, k):
    """
    estimated_top: list of (item, count, error), length k.
    exact_top:     list of (item, true_freq), length k (the true top-k by freq).
    exact_counter: Counter[int -> true_freq] of all items seen.

    Returns a dict with precision, recall, max_overest.
    """
    est_items = [t[0] for t in estimated_top]
    true_items = [t[0] for t in exact_top]

    # Intersections
    est_set = set(est_items)
    true_set = set(true_items)
    tp = len(est_set & true_set)

    precision = tp / len(est_set) if est_set else 0.0
    recall = tp / len(true_set) if true_set else 0.0

    # Maximum over-estimation error on items that appear in either top-k.
    # Over-estimation error = estimated_count - true_freq
    max_over = 0
    for (it, ec, _err) in estimated_top:
        true_f = exact_counter.get(it, 0)
        over = ec - true_f
        if over > max_over:
            max_over = over
    # Also consider that a true top-k item may have been mis-estimated as
    # being outside our top-k.  Since we're only given estimated_top here,
    # the above is sufficient for the slots we report.

    return {
        "precision_at_k": precision,
        "recall_at_k": recall,
        "max_overest": int(max_over),
    }


def memory_bytes(ss: SpaceSaving) -> int:
    """
    Approximate the working-memory footprint of the Stream-Summary.

    The paper stores one counter per slot: item id, count, error.
    Plus the overhead of the per-slot list nodes for the bucket
    structure (Stream-Summary).  For a fair comparison across k we
    just count the live counter footprint, which is the primary
    memory cost that scales with k.  Each counter is 3 * int64.
    """
    return 3 * 8 * int(ss.size)


def peak_rss_bytes() -> int:
    """Peak resident set size in bytes (process-level).  Linux-specific."""
    ru = resource.getrusage(resource.RUSAGE_SELF)
    # On Linux ru_maxrss is in kilobytes.
    return int(ru.ru_maxrss) * 1024


def main():
    out_dir = "/data/workspace/admin/happy_lake/.verify_judge_minimax/spacesaving/spacesaving_03"
    # Fixed settings
    N = 1_000_000
    ALPHA = 1.5           # realistic skew (paper used 1.5 in many runs)
    ALPHABET = 10_000     # reasonable alphabet size
    SEED = 42
    K_VALUES = [50, 100, 200, 500]

    print(f"Generating Zipfian stream: N={N}, alpha={ALPHA}, alphabet={ALPHABET}, seed={SEED}")
    stream = zipf_stream(N, ALPHA, ALPHABET, SEED)
    print(f"  stream dtype={stream.dtype}, n={stream.size}")
    print(f"  unique items in stream: {len(np.unique(stream))}")

    # Ground-truth exact counts
    exact_counter = Counter(stream.tolist())
    # Top-k by frequency, with deterministic tie-break by item id ascending.
    # Get top 500 — that covers all K_VALUES we test.
    TOP_RANK = max(K_VALUES)
    sorted_items = sorted(exact_counter.items(), key=lambda x: (-x[1], x[0]))
    true_top = sorted_items[:TOP_RANK]

    print(f"\nExact top-{TOP_RANK}:")
    for i, (it, f) in enumerate(true_top[:10]):
        print(f"  rank {i+1}: item={it} freq={f}")

    results = {}

    for k in K_VALUES:
        print(f"\n=== k = {k} ===")
        ss = SpaceSaving(k)
        ss.update_batch(stream)
        est = ss.top_k(k)
        true_topk = true_top[:k]
        m = evaluate(est, true_topk, exact_counter, k)

        occupied = int(ss.size)
        mem = memory_bytes(ss)

        results[k] = {
            "k": k,
            "occupied_slots": occupied,
            "memory_bytes_per_slot": 24,
            "memory_bytes_total": mem,
            "precision_at_k": m["precision_at_k"],
            "recall_at_k": m["recall_at_k"],
            "max_overest": m["max_overest"],
            "N": ss.N_seen,
            "sum_of_counts": int(ss.count.sum()),  # should equal N
            "min_count": int(ss.count[:occupied].min()) if occupied else 0,
            "max_count": int(ss.count[:occupied].max()) if occupied else 0,
            "first_few_top": [
                {"item": int(it), "est_count": int(c), "err": int(e),
                 "true_freq": int(exact_counter.get(it, 0))}
                for (it, c, e) in est[:10]
            ],
        }
        print(f"  occupied={occupied}  sum_counts={results[k]['sum_of_counts']}")
        print(f"  precision@k = {m['precision_at_k']:.4f}")
        print(f"  recall@k    = {m['recall_at_k']:.4f}")
        print(f"  max over-est error = {m['max_overest']}")
        print(f"  memory_bytes = {mem}")

    # Process-level peak RSS for context
    peak = peak_rss_bytes()
    results["_meta"] = {
        "N": N, "alpha": ALPHA, "alphabet_size": ALPHABET, "seed": SEED,
        "n_unique_in_stream": int(len(np.unique(stream))),
        "peak_rss_bytes": peak,
    }

    # Save raw JSON for inspection
    with open(os.path.join(out_dir, "results.json"), "w") as f:
        json.dump(results, f, indent=2)

    print("\nSaved results.json")
    return results


if __name__ == "__main__":
    main()