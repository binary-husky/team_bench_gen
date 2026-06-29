"""Diagnose what's in SS's top-100 vs truth for alpha=1.5"""

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

    # Build sorted truth
    truth_sorted = true_freq.most_common()
    truth_ranks = {e: i+1 for i, (e, _) in enumerate(truth_sorted)}

    print(f"alpha={alpha}, N={N}, k={k}")
    print(f"Distinct elements: {len(true_freq)}")
    print(f"Top-1 freq: {truth_sorted[0][1]}")
    print(f"Top-100 freq: {truth_sorted[99][1]}")
    print(f"Top-200 freq: {truth_sorted[199][1]}")
    print(f"Top-500 freq: {truth_sorted[499][1]}")

    # SS top-100
    ss_topk = sorted(ss.items(), key=lambda x: (-x[1][0], x[0]))[:k]

    print(f"\nSS top-100 details:")
    not_in_top100 = 0
    for i, (e, (fhat, err)) in enumerate(ss_topk):
        f_true = true_freq.get(e, 0)
        rank = truth_ranks[e]
        in_top100 = "✓" if rank <= 100 else "✗"
        if rank > 100:
            not_in_top100 += 1
        if i < 30 or rank > 100:
            print(f"  SS-rank {i+1}: elem={e} fhat={fhat} err={err} ftrue={f_true} true-rank={rank} {in_top100}")

    print(f"\nTotal SS top-100 NOT in true top-100: {not_in_top100}")

    # Print truth top-30 to compare
    print(f"\nTruth top-30 (first 30):")
    for i in range(30):
        e, f = truth_sorted[i]
        in_ss = e in ss
        ss_count = ss.get(e, [0,0])[0]
        print(f"  truth-rank {i+1}: elem={e} f={f} in_ss={in_ss} ss_count={ss_count}")

    # Count how many true top-100 elements are MISSING from SS monitor set
    missing = sum(1 for e in truth_sorted[:100] if e not in ss)
    print(f"\nTrue top-100 elements MISSING from SS monitor set: {missing}")

    # Print the structure of SS monitor set: how many of them are in true top 100, 200, 500, 1000
    ranks_in_ss = []
    for e in ss:
        ranks_in_ss.append(truth_ranks[e])
    ranks_in_ss.sort()
    print(f"\nDistribution of true ranks of SS's 100 monitored elements:")
    print(f"  in true top-100: {sum(1 for r in ranks_in_ss if r <= 100)}")
    print(f"  in true top-200: {sum(1 for r in ranks_in_ss if r <= 200)}")
    print(f"  in true top-500: {sum(1 for r in ranks_in_ss if r <= 500)}")
    print(f"  in true top-1000: {sum(1 for r in ranks_in_ss if r <= 1000)}")
    print(f"  min rank: {min(ranks_in_ss)}, max rank: {max(ranks_in_ss)}")
    print(f"  median rank: {ranks_in_ss[50]}")


if __name__ == "__main__":
    main()
