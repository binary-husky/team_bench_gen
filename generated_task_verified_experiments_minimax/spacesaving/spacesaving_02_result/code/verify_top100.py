"""More detailed diagnosis: where are elements 50-150 of truth in SS monitor set?"""

import numpy as np
from collections import Counter


def generate_zipfian_stream(N, alpha, alphabet_size, seed):
    rng = np.random.default_rng(seed)
    ranks = np.arange(1, alphabet_size + 1, dtype=np.float64)
    weights = 1.0 / np.power(ranks, alpha)
    weights /= weights.sum()
    stream = rng.choice(ranks.astype(np.int64), size=N, p=weights)
    return stream


def space_saving(stream, k):
    counters = {}
    for e in stream:
        if e in counters:
            counters[e][0] += 1
        elif len(counters) < k:
            counters[e] = [1, 0]
        else:
            min_e = min(counters, key=lambda x: counters[x][0])
            min_count = counters[min_e][0]
            del counters[min_e]
            counters[e] = [min_count + 1, min_count]
    return counters


def main():
    N = 1_000_000
    k = 100
    alpha = 1.5
    seed = 42
    alphabet_size = 500_000

    stream = generate_zipfian_stream(N, alpha, alphabet_size, seed)
    true_freq = Counter(stream.tolist())
    ss = space_saving(stream, k)

    truth_sorted = true_freq.most_common()
    truth_ranks = {e: i+1 for i, (e, _) in enumerate(truth_sorted)}

    # Check: are elements at truth ranks 80-150 present in SS monitor set?
    print(f"alpha={alpha}, N={N}, k={k}")
    print(f"Top 130 truth elements vs SS monitor set:")
    for i in range(80, 130):
        e, f = truth_sorted[i]
        in_ss = e in ss
        ss_count = ss.get(e, [0,0])[0]
        marker = "✓" if in_ss else "✗"
        print(f"  rank {i+1}: elem={e} f_true={f} in_ss={marker} ss_count={ss_count}")

    # Count truth top-100 in SS
    top100_in_ss = sum(1 for e, _ in truth_sorted[:100] if e in ss)
    print(f"\nTruth top-100 elements present in SS monitor set: {top100_in_ss}")

    # How does the min count in SS evolve over time? Track it.
    counters = {}
    min_count_history = []
    sample_points = [1000, 10000, 50000, 100000, 500000, 750000, 1000000]
    for i, e in enumerate(stream):
        if e in counters:
            counters[e][0] += 1
        elif len(counters) < k:
            counters[e] = [1, 0]
        else:
            min_e = min(counters, key=lambda x: counters[x][0])
            min_count = counters[min_e][0]
            del counters[min_e]
            counters[e] = [min_count + 1, min_count]
        if (i+1) in sample_points:
            current_min = min(c[0] for c in counters.values()) if counters else 0
            distinct = len(true_freq)
            current_min_rank = sum(1 for e2, f in truth_sorted if f > current_min) + 1
            print(f"\nAt position {i+1}: SS monitor size = {len(counters)}, current min count = {current_min}")
            print(f"  Count >= current_min: how many true elements have f > {current_min}? {current_min_rank - 1}")

    # Final state: distribution of SS counters
    ss_counts = sorted([c[0] for c in counters.values()], reverse=True)
    print(f"\nFinal SS counter values (sorted descending), first 30:")
    for i, c in enumerate(ss_counts[:30]):
        print(f"  SS-rank {i+1}: count={c}")
    print(f"  ...")
    for i, c in enumerate(ss_counts[-10:]):
        print(f"  SS-rank {90+i+1}: count={c}")


if __name__ == "__main__":
    main()
