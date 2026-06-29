"""
Quick probe: vary Zipf alpha and see how precision@100 and over-estimation change.
This is just a diagnostic - the actual summary uses one fixed alpha.
"""

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
    seed = 42
    alphabet_size = 500_000

    for alpha in [1.0, 1.1, 1.2, 1.5, 2.0]:
        stream = generate_zipfian_stream(N, alpha, alphabet_size, seed)
        true_freq = Counter(stream.tolist())
        ss = space_saving(stream, k)
        truth_topk = [e for e, _ in true_freq.most_common(k)]
        truth_topk_set = set(truth_topk)
        ss_topk = [e for e, _ in sorted(ss.items(), key=lambda x: -x[1][0])[:k]]
        ss_topk_set = set(ss_topk)
        intersection = truth_topk_set & ss_topk_set
        precision_at_k = len(intersection) / k

        over_errors = []
        for e, (fhat, err) in ss.items():
            f_true = true_freq.get(e, 0)
            over_errors.append(fhat - f_true)
        mean_over = float(np.mean(over_errors))
        max_over = int(np.max(over_errors))
        n_under = int(np.sum(np.array(over_errors) < 0))

        # Truth rank of the last element in SS top-k
        truth_ranks_of_ss = []
        for e in ss_topk:
            cnt = true_freq.get(e, 0)
            # rank = position in sorted descending list
            rank = sum(1 for x in true_freq.values() if x > cnt)
            if any(x == cnt and x_id != e for x_id, x in true_freq.items() if x_id < e):
                rank += 1
            truth_ranks_of_ss.append(rank + 1)

        # truth ranks of SS elements that are NOT in true top-100
        not_in_truth = sum(1 for r in truth_ranks_of_ss if r > 100)
        in_truth = sum(1 for r in truth_ranks_of_ss if r <= 100)

        # Truth top-1, top-100 freqs
        top1 = true_freq.most_common(1)[0][1]
        top100 = true_freq.most_common(100)[-1][1]
        top200 = true_freq.most_common(200)[-1][1]

        print(f"\nalpha={alpha}:")
        print(f"  distinct elements observed: {len(true_freq)}")
        print(f"  precision@100 = {precision_at_k:.4f}  (intersection={len(intersection)})")
        print(f"  SS top-100 elements in true top-100: {in_truth}, not in: {not_in_truth}")
        print(f"  truth top-1 freq = {top1}, top-100 freq = {top100}, top-200 freq = {top200}")
        print(f"  mean over-estimation (all 100 monitors) = {mean_over:.1f}")
        print(f"  max over-estimation = {max_over}")
        print(f"  #under-estimated = {n_under}")
        # Worst true-rank of any element SS picked up
        worst_rank = max(truth_ranks_of_ss)
        print(f"  worst true-rank of any SS top-100 element: {worst_rank}")


if __name__ == "__main__":
    main()
