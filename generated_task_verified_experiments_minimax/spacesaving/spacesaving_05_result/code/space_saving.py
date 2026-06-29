"""
Space-Saving implementation following Metwally, Agrawal, Abbadi (2005)
"Efficient Computation of Frequent and Top-k Elements in Data Streams"

This is a clean, from-scratch implementation of the counter-based algorithm
that uses a hash map of (element -> counter) plus a min-heap (or sorted
structure) to find the minimum count for the replacement step.
"""

from __future__ import annotations

import heapq
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple


class SpaceSaving:
    """Stream-Summary data structure for Space-Saving.

    Keeps at most `m` (element, count) counters.
    Each counter additionally stores an `error` value which is the
    over-estimation bound (the value of `min` at the time the element
    was inserted/replaced).  Lemma 3:  count_i - error_i <= f_i <= count_i.
    """

    def __init__(self, m: int) -> None:
        if m <= 0:
            raise ValueError("m must be > 0")
        self.m = m
        # element -> (count, error)
        self.counts: Dict[int, Tuple[int, int]] = {}
        # Min-heap of (count, error, element).  Using a tuple with a
        # unique element at the end is safe because Python's heapq
        # breaks ties deterministically and elements are unique ints.
        self._heap: List[Tuple[int, int, int]] = []

    def _push(self, e: int, c: int, err: int) -> None:
        heapq.heappush(self._heap, (c, err, e))

    def offer(self, e: int) -> None:
        """Process a single stream element."""
        if e in self.counts:
            c, err = self.counts[e]
            new_c = c + 1
            self.counts[e] = (new_c, err)
            # Push updated counter; old entry becomes stale in the heap
            self._push(e, new_c, err)
            return

        if len(self.counts) < self.m:
            # Fresh counter
            self.counts[e] = (1, 0)
            self._push(e, 1, 0)
            return

        # Replacement step: evict the current minimum counter
        c_min, err_min, e_min = heapq.heappop(self._heap)
        # Skip stale heap entries (element already replaced)
        while (e_min not in self.counts) or (self.counts[e_min] != (c_min, err_min)):
            c_min, err_min, e_min = heapq.heappop(self._heap)
        # Now (c_min, err_min, e_min) is the live minimum.
        del self.counts[e_min]
        # Insert e with count = c_min + 1 and error = c_min
        self.counts[e] = (c_min + 1, c_min)
        self._push(e, c_min + 1, c_min)

    def consume(self, stream: Iterable[int]) -> None:
        for e in stream:
            self.offer(e)

    def top_k(self, k: int) -> List[Tuple[int, int, int]]:
        """Return the top-k elements (by count, descending) as
        (count, error, element) triples."""
        rows = [(c, err, e) for e, (c, err) in self.counts.items()]
        rows.sort(key=lambda r: (-r[0], r[2]))
        return rows[:k]


def exact_top_k(stream: Iterable[int], k: int) -> List[Tuple[int, int]]:
    """Full exact counts (baseline) and top-k by count descending."""
    freq: Dict[int, int] = defaultdict(int)
    for e in stream:
        freq[e] += 1
    rows = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return rows[:k], freq


def precision_recall_at_k(
    reported: List[Tuple[int, int]],
    exact: List[Tuple[int, int]],
    k: int,
) -> Tuple[float, float]:
    """precision@k and recall@k for the top-k set comparison.

    reported/exact are lists of (element, count) of length >= k.
    """
    rep_set = {e for e, _ in reported[:k]}
    exa_set = {e for e, _ in exact[:k]}
    inter = rep_set & exa_set
    prec = len(inter) / k
    rec = len(inter) / k
    return prec, rec


def main() -> None:
    import time
    import numpy as np

    # -------- fixed experimental settings --------
    N = 1_000_000
    K = 100
    # Cardinality = alphabet size.  Set comfortably larger than k so that
    # neither distribution trivially saturates; Zipfian effectively only
    # activates the first O(N^1/alpha) ranks while uniform spreads mass
    # over all |A| items.
    ALPHABET = 100_000
    SEED = 12345

    rng = np.random.default_rng(SEED)

    # ----- Zipfian stream (strongly skewed, alpha=1.5) -----
    # numpy.random.Generator.zipf draws from {1, 2, ...} with P(X=k) ~ k^-alpha.
    # Subtract 1 to use 0-indexed alphabet of size ALPHABET.
    zipf_raw = rng.zipf(1.5, size=N)
    # numpy can return 0 when alpha is small; mask those out by resampling
    # until all values are within the alphabet (very rare for alpha=1.5).
    zipf_mask = zipf_raw <= ALPHABET
    while not zipf_mask.all():
        zipf_raw[~zipf_mask] = rng.zipf(1.5, size=(~zipf_mask).sum())
        zipf_mask = zipf_raw <= ALPHABET
    zipf_stream = (zipf_raw - 1).tolist()  # 0-indexed, deterministic

    # ----- Uniform stream over the same alphabet, same seed-derived RNG -----
    # We use a fresh Generator that derives from the same SEED, but the
    # task says "fixed seed"; we keep one rng and split the draw so the
    # call order is identical.  Easier: instantiate a separate RNG with
    # a derived seed so the streams are independently reproducible.
    rng2 = np.random.default_rng(SEED)
    uniform_stream = rng2.integers(0, ALPHABET, size=N, dtype=np.int64).tolist()

    # ----- Exact baselines -----
    zipf_top, zipf_freq = exact_top_k(zipf_stream, K)
    uniform_top, uniform_freq = exact_top_k(uniform_stream, K)

    # ----- Space-Saving (k = K) -----
    t0 = time.perf_counter()
    ss_zipf = SpaceSaving(K)
    ss_zipf.consume(zipf_stream)
    t_zipf = time.perf_counter() - t0

    t0 = time.perf_counter()
    ss_uni = SpaceSaving(K)
    ss_uni.consume(uniform_stream)
    t_uni = time.perf_counter() - t0

    zipf_reported = [(e, c) for (c, _err, e) in ss_zipf.top_k(K)]
    uni_reported = [(e, c) for (c, _err, e) in ss_uni.top_k(K)]

    # ----- Precision@k / Recall@k -----
    prec_z, rec_z = precision_recall_at_k(zipf_reported, zipf_top, K)
    prec_u, rec_u = precision_recall_at_k(uni_reported, uniform_top, K)

    # ----- Diagnostics -----
    # Sum of all counters should equal N (Lemma 1).
    sum_zipf = sum(c for c, _ in ss_zipf.counts.values())
    sum_uni = sum(c for c, _ in ss_uni.counts.values())

    # The minimum counter value at the end of the run:
    min_zipf = min(c for c, _ in ss_zipf.counts.values())
    min_uni = min(c for c, _ in ss_uni.counts.values())

    # How many of the true top-K are not even in the monitored set?
    miss_z = len({e for e, _ in zipf_top} - set(ss_zipf.counts))
    miss_u = len({e for e, _ in uniform_top} - set(ss_uni.counts))

    # Frequency of the K-th most frequent exact item (= the threshold
    # an ideal top-K must clear):
    thr_z = zipf_top[-1][1]
    thr_u = uniform_top[-1][1]

    # Cardinality actually observed in the stream:
    print("=" * 70)
    print("Space-Saving top-k (k=100) on two N=1e6 streams")
    print("=" * 70)
    print(f"Settings: N={N:,}  k={K}  alphabet={ALPHABET:,}  seed={SEED}")
    print()
    print("Zipfian (alpha=1.5, strongly skewed):")
    print(f"  run-time              : {t_zipf:.3f} s")
    print(f"  sum of counters       : {sum_zipf:,}  (== N? {sum_zipf == N})")
    print(f"  final min counter     : {min_zipf}")
    print(f"  exact top-K threshold : {thr_z}")
    print(f"  true-top-K items MISSED in SS: {miss_z}")
    print(f"  precision@k           : {prec_z:.4f}")
    print(f"  recall@k              : {rec_z:.4f}")
    print()
    print("Uniform over same alphabet:")
    print(f"  run-time              : {t_uni:.3f} s")
    print(f"  sum of counters       : {sum_uni:,}  (== N? {sum_uni == N})")
    print(f"  final min counter     : {min_uni}")
    print(f"  exact top-K threshold : {thr_u}")
    print(f"  true-top-K items MISSED in SS: {miss_u}")
    print(f"  precision@k           : {prec_u:.4f}")
    print(f"  recall@k              : {rec_u:.4f}")
    print()
    # Build element -> exact-rank lookup so the side-by-side prints
    # make sense regardless of where each reported item lives in the
    # exact ranking.
    zipf_exact_rank = {e: i + 1 for i, (e, _) in enumerate(zipf_top)}
    zipf_exact_count = dict(zipf_top)
    uni_exact_rank = {e: i + 1 for i, (e, _) in enumerate(uniform_top)}
    uni_exact_count = dict(uniform_top)

    print("Top-10 (reported by SS) — Zipfian:")
    for i, (e, c) in enumerate(zipf_reported[:10], 1):
        rank_exact = zipf_exact_rank.get(e, "—")
        cnt_exact = zipf_exact_count.get(e, "—")
        print(f"  rank {i:2d}: e={e:5d}  SS-count={c:7d}  "
              f"exact-rank={rank_exact}  exact-count={cnt_exact}")
    print()
    print("Top-10 (reported by SS) — Uniform:")
    for i, (e, c) in enumerate(uni_reported[:10], 1):
        rank_exact = uni_exact_rank.get(e, "—")
        cnt_exact = uni_exact_count.get(e, "—")
        print(f"  rank {i:2d}: e={e:5d}  SS-count={c:7d}  "
              f"exact-rank={rank_exact}  exact-count={cnt_exact}")
    print()
    # Print a few true top-K items that SS missed (uniform case) so we
    # can see how badly SS diverges from the true ranking.
    if miss_u > 0:
        print(f"Examples of true top-K items NOT in the SS monitored set (uniform):")
        miss_examples = [e for e, _ in uniform_top if e not in set(ss_uni.counts)][:10]
        for e in miss_examples:
            print(f"  e={e:5d}  exact-count={uniform_freq[e]}")
        print()

    # ----- Save the numbers for the summary write-up -----
    import json
    results = {
        "N": N, "K": K, "alphabet": ALPHABET, "seed": SEED,
        "zipf": {
            "alpha": 1.5,
            "time_s": t_zipf,
            "sum_counters": sum_zipf,
            "min_counter_final": min_zipf,
            "exact_top_k_threshold_count": thr_z,
            "true_top_k_missed": miss_z,
            "precision_at_k": prec_z,
            "recall_at_k": rec_z,
        },
        "uniform": {
            "time_s": t_uni,
            "sum_counters": sum_uni,
            "min_counter_final": min_uni,
            "exact_top_k_threshold_count": thr_u,
            "true_top_k_missed": miss_u,
            "precision_at_k": prec_u,
            "recall_at_k": rec_u,
        },
    }
    with open("/data/workspace/admin/happy_lake/.verify_judge_minimax/spacesaving/spacesaving_05/results.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
