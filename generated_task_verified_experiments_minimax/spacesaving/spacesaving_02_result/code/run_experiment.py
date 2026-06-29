"""
Evaluate Space-Saving top-k identification accuracy on a synthetic Zipfian stream.

Settings (fixed):
  - Stream size N = 1e6
  - Zipfian parameter alpha = 1.0 (canonical Zipf)
  - Random seed = 42
  - Number of counters k = 100
"""

import numpy as np
from collections import Counter


def generate_zipfian_stream(N, alpha, alphabet_size, seed):
    """Generate a Zipfian stream of length N over an alphabet of size `alphabet_size`."""
    rng = np.random.default_rng(seed)
    # ranks are 1..alphabet_size
    ranks = np.arange(1, alphabet_size + 1, dtype=np.float64)
    weights = 1.0 / np.power(ranks, alpha)
    weights /= weights.sum()
    stream = rng.choice(ranks.astype(np.int64), size=N, p=weights)
    return stream


def space_saving(stream, k):
    """Run Space-Saving with `k` counters on the stream.

    Returns:
        counters: dict mapping element -> (estimated_count, over_estimation)
        The over_estimation is the min counter value at the time the element
        was first inserted into the monitor set.
    """
    counters = {}  # element -> [count, error]
    for e in stream:
        if e in counters:
            counters[e][0] += 1
        elif len(counters) < k:
            # empty slot: insert with count 1, error 0
            counters[e] = [1, 0]
        else:
            # all slots full: find element with minimum count
            min_e = min(counters, key=lambda x: counters[x][0])
            min_count = counters[min_e][0]
            # replace it with the new element
            del counters[min_e]
            counters[e] = [min_count + 1, min_count]
    return counters


def main():
    N = 1_000_000
    k = 100
    alpha = 1.0       # Zipfian skew parameter (canonical)
    seed = 42         # fixed random seed
    # Theoretically a Zipfian distribution has a long tail. Use a large alphabet
    # (5e5) to ensure rank-100 elements are reasonably frequent.
    alphabet_size = 500_000

    # 1. Generate stream
    stream = generate_zipfian_stream(N, alpha, alphabet_size, seed)
    print(f"Generated stream: N={N}, alpha={alpha}, alphabet={alphabet_size}, seed={seed}")

    # 2. True frequencies
    true_freq = Counter(stream.tolist())
    print(f"Distinct elements observed: {len(true_freq)}")

    # 3. Run Space-Saving
    ss = space_saving(stream, k)
    print(f"Space-Saving monitor set size: {len(ss)}")

    # 4. Top-k truth
    truth_topk = [e for e, _ in true_freq.most_common(k)]
    truth_topk_set = set(truth_topk)

    # 5. Space-Saving reported top-k
    ss_topk_sorted = sorted(ss.items(), key=lambda x: (-x[1][0], x[0]))
    ss_topk = [e for e, _ in ss_topk_sorted[:k]]
    ss_topk_set = set(ss_topk)

    # 6. precision@k, recall@k
    intersection = truth_topk_set & ss_topk_set
    precision_at_k = len(intersection) / k
    recall_at_k = len(intersection) / k   # both have size k so they coincide

    print(f"\nPrecision@100 = {precision_at_k:.4f}")
    print(f"Recall@100    = {recall_at_k:.4f}")
    print(f"Intersection size = {len(intersection)} / 100")

    # 7. Frequency estimation errors (over-estimation)
    # Compute over-estimation for every element that is in the SS monitor set.
    # By the Space-Saving analysis:
    #   f_hat >= f_true
    #   f_hat - f_true <= error (stored value, equal to the min counter at insertion)
    over_errors = []
    abs_errors = []
    for e, (fhat, err) in ss.items():
        f_true = true_freq.get(e, 0)
        delta = fhat - f_true
        over_errors.append(delta)
        abs_errors.append(abs(delta))

    mean_over = float(np.mean(over_errors))
    median_over = float(np.median(over_errors))
    max_over = int(np.max(over_errors))
    min_over = int(np.min(over_errors))
    p95_over = float(np.percentile(over_errors, 95))
    p99_over = float(np.percentile(over_errors, 99))
    n_under = int(np.sum(np.array(over_errors) < 0))
    n_zero = int(np.sum(np.array(over_errors) == 0))
    n_over = int(np.sum(np.array(over_errors) > 0))
    mean_abs = float(np.mean(abs_errors))

    # Frequency estimation errors specifically for the reported top-k
    over_errors_topk = []
    abs_errors_topk = []
    for e in ss_topk:
        fhat, err = ss[e]
        f_true = true_freq.get(e, 0)
        delta = fhat - f_true
        over_errors_topk.append(delta)
        abs_errors_topk.append(abs(delta))

    mean_over_topk = float(np.mean(over_errors_topk))
    median_over_topk = float(np.median(over_errors_topk))
    max_over_topk = int(np.max(over_errors_topk))
    min_over_topk = int(np.min(over_errors_topk))
    p95_over_topk = float(np.percentile(over_errors_topk, 95))
    p99_over_topk = float(np.percentile(over_errors_topk, 99))
    n_under_topk = int(np.sum(np.array(over_errors_topk) < 0))
    n_zero_topk = int(np.sum(np.array(over_errors_topk) == 0))
    n_over_topk = int(np.sum(np.array(over_errors_topk) > 0))
    mean_abs_topk = float(np.mean(abs_errors_topk))

    # Mean over-estimation among ONLY over-estimated elements
    over_only = [x for x in over_errors if x > 0]
    mean_over_only = float(np.mean(over_only)) if over_only else 0.0
    over_only_topk = [x for x in over_errors_topk if x > 0]
    mean_over_only_topk = float(np.mean(over_only_topk)) if over_only_topk else 0.0

    # Relative over-estimation (fhat / f_true - 1)
    rel_over = []
    rel_over_topk = []
    for e, (fhat, err) in ss.items():
        f_true = true_freq.get(e, 0)
        if f_true > 0:
            rel_over.append((fhat - f_true) / f_true)
    for e in ss_topk:
        fhat, err = ss[e]
        f_true = true_freq.get(e, 0)
        if f_true > 0:
            rel_over_topk.append((fhat - f_true) / f_true)

    mean_rel_over = float(np.mean(rel_over)) if rel_over else 0.0
    max_rel_over = float(np.max(rel_over)) if rel_over else 0.0
    mean_rel_over_topk = float(np.mean(rel_over_topk)) if rel_over_topk else 0.0
    max_rel_over_topk = float(np.max(rel_over_topk)) if rel_over_topk else 0.0

    # Per-rank comparison
    print(f"\nPer-element over-estimation (reported top-100):")
    print(f"  mean over-estimation = {mean_over_topk:.2f}")
    print(f"  median over-estimation = {median_over_topk}")
    print(f"  max over-estimation = {max_over_topk}")
    print(f"  p95 over-estimation = {p95_over_topk}")
    print(f"  p99 over-estimation = {p99_over_topk}")
    print(f"  #under-estimated = {n_under_topk} (should be 0 by theory)")
    print(f"  #exact = {n_zero_topk}")
    print(f"  #over-estimated = {n_over_topk}")
    print(f"  #over-estimated mean (only over) = {mean_over_only_topk:.2f}")
    print(f"  relative over-estimation mean = {mean_rel_over_topk:.4f}")
    print(f"  relative over-estimation max  = {max_rel_over_topk:.4f}")

    print(f"\nOver-estimation across all {len(ss)} monitored elements:")
    print(f"  mean over-estimation = {mean_over:.2f}")
    print(f"  median over-estimation = {median_over}")
    print(f"  max over-estimation = {max_over}")
    print(f"  #under-estimated = {n_under} (should be 0)")
    print(f"  #exact = {n_zero}")
    print(f"  #over-estimated = {n_over}")
    print(f"  relative over-estimation mean = {mean_rel_over:.4f}")
    print(f"  relative over-estimation max  = {max_rel_over:.4f}")

    # Print first 10 entries of the top-k list with truth comparison
    print(f"\nTop-10 comparison (rank: true_freq | ss_fhat | over-est):")
    for i in range(10):
        e = ss_topk[i]
        fhat, _ = ss[e]
        f_true = true_freq.get(e, 0)
        print(f"  rank {i+1}: elem={e}  f_true={f_true}  fhat={fhat}  delta={fhat - f_true}")

    # Truth top-10
    print(f"\nTruth top-10:")
    for i in range(10):
        e = truth_topk[i]
        f_true = true_freq.get(e, 0)
        fhat = ss.get(e, [0, 0])[0]
        print(f"  rank {i+1}: elem={e}  f_true={f_true}  in_ss={e in ss}")

    # Summary statistics on Zipf
    truth_top10_freqs = [true_freq[e] for e in truth_topk[:10]]
    truth_top100_freqs = [true_freq[e] for e in truth_topk]
    print(f"\nZipf shape check (truth):")
    print(f"  true top-1 freq = {truth_top10_freqs[0]}")
    print(f"  true top-10 freq = {truth_top10_freqs[-1]}")
    print(f"  true top-100 freq = {truth_top100_freqs[-1]}")
    print(f"  true top-100 / top-1 ratio = {truth_top100_freqs[-1] / truth_top10_freqs[0]:.4f}")

    # Save outputs for the markdown report
    metrics = {
        "N": N,
        "alpha": alpha,
        "alphabet_size": alphabet_size,
        "seed": seed,
        "k": k,
        "n_distinct_observed": len(true_freq),
        "ss_monitor_size": len(ss),
        "precision_at_k": precision_at_k,
        "recall_at_k": recall_at_k,
        "intersection_size": len(intersection),
        # Errors over reported top-k
        "topk_mean_over": mean_over_topk,
        "topk_median_over": median_over_topk,
        "topk_max_over": max_over_topk,
        "topk_min_over": min_over_topk,
        "topk_p95_over": p95_over_topk,
        "topk_p99_over": p99_over_topk,
        "topk_n_under": n_under_topk,
        "topk_n_exact": n_zero_topk,
        "topk_n_over": n_over_topk,
        "topk_mean_over_only_over": mean_over_only_topk,
        "topk_mean_rel_over": mean_rel_over_topk,
        "topk_max_rel_over": max_rel_over_topk,
        "topk_mean_abs": mean_abs_topk,
        # Errors over all monitored elements
        "all_mean_over": mean_over,
        "all_median_over": median_over,
        "all_max_over": max_over,
        "all_min_over": min_over,
        "all_p95_over": p95_over,
        "all_p99_over": p99_over,
        "all_n_under": n_under,
        "all_n_exact": n_zero,
        "all_n_over": n_over,
        "all_mean_over_only_over": mean_over_only,
        "all_mean_rel_over": mean_rel_over,
        "all_max_rel_over": max_rel_over,
        "all_mean_abs": mean_abs,
        # Zipf shape
        "truth_top1_freq": truth_top10_freqs[0],
        "truth_top10_freq": truth_top10_freqs[-1],
        "truth_top100_freq": truth_top100_freqs[-1],
    }
    return metrics


if __name__ == "__main__":
    main()
