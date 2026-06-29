"""Probe: how does precision change with N?"""

import numpy as np
from collections import Counter
import time


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


def measure(N, alpha, k=100, alphabet_size=500_000, seed=42):
    t0 = time.time()
    stream = generate_zipfian_stream(N, alpha, alphabet_size, seed)
    t1 = time.time()
    true_freq = Counter(stream.tolist())
    t2 = time.time()
    ss = space_saving(stream, k)
    t3 = time.time()
    truth_topk = set(e for e, _ in true_freq.most_common(k))
    ss_topk = set(e for e, _ in sorted(ss.items(), key=lambda x: -x[1][0])[:k])
    intersection = truth_topk & ss_topk
    precision = len(intersection) / k

    over_errors = []
    for e, (fhat, err) in ss.items():
        f_true = true_freq.get(e, 0)
        over_errors.append(fhat - f_true)
    mean_over = float(np.mean(over_errors))
    max_over = int(np.max(over_errors))

    return {
        "N": N,
        "alpha": alpha,
        "k": k,
        "distinct": len(true_freq),
        "precision@k": precision,
        "intersection": len(intersection),
        "mean_over": mean_over,
        "max_over": max_over,
        "top1_freq": true_freq.most_common(1)[0][1],
        "top100_freq": true_freq.most_common(k)[-1][1],
        "stream_gen_time": t1 - t0,
        "ss_time": t3 - t2,
    }


def main():
    print(f"{'N':>10} {'alpha':>5} {'k':>4} {'distinct':>10} {'prec':>6} {'inter':>5} {'mean_over':>10} {'max_over':>9} {'top1':>8} {'top100':>8}")
    for N, alpha in [(1_000_000, 1.0),
                     (1_000_000, 1.5),
                     (10_000_000, 1.0),
                     (10_000_000, 1.5),
                     (100_000_000, 1.0),
                     (100_000_000, 1.5)]:
        try:
            r = measure(N, alpha)
            print(f"{r['N']:>10} {r['alpha']:>5} {r['k']:>4} {r['distinct']:>10} {r['precision@k']:>6.3f} {r['intersection']:>5} {r['mean_over']:>10.1f} {r['max_over']:>9} {r['top1_freq']:>8} {r['top100_freq']:>8}")
        except MemoryError as e:
            print(f"N={N} alpha={alpha}: MemoryError")


if __name__ == "__main__":
    main()
