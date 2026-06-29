"""
Final canonical Space-Saving top-k accuracy measurement.

Configuration (fixed):
  - Stream size N = 1e6
  - Zipfian skew parameter alpha = 1.0 (canonical Zipf, A = 5e5 alphabet)
  - Random seed = 42
  - Number of counters k = 100

Metrics:
  - precision@100 and recall@100 vs. true top-100 (exact counting)
  - Over-estimation of f_hat relative to f_true for each reported top-k element
"""

import numpy as np
from collections import Counter
import json
import time


def generate_zipfian_stream(N, alpha, alphabet_size, seed):
    rng = np.random.default_rng(seed)
    ranks = np.arange(1, alphabet_size + 1, dtype=np.float64)
    weights = 1.0 / np.power(ranks, alpha)
    weights /= weights.sum()
    stream = rng.choice(ranks.astype(np.int64), size=N, p=weights)
    return stream


def space_saving(stream, k):
    """Standard Space-Saving with k counters (Metwally et al. 2005)."""
    counters = {}  # element -> [count, error=min-at-insertion]
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
    alpha = 1.0
    seed = 42
    alphabet_size = 500_000

    # 1. Generate stream
    t0 = time.time()
    stream = generate_zipfian_stream(N, alpha, alphabet_size, seed)
    t_gen = time.time() - t0

    # 2. True frequencies (ground truth) via full exact counting
    t0 = time.time()
    true_freq = Counter(stream)
    t_count = time.time() - t0

    # 3. Run Space-Saving with k=100 counters
    t0 = time.time()
    ss = space_saving(stream, k)
    t_ss = time.time() - t0

    # 4. Truth top-k and SS reported top-k
    truth_topk_sorted = true_freq.most_common(k)
    truth_topk = [e for e, _ in truth_topk_sorted]
    truth_topk_set = set(truth_topk)

    ss_topk_sorted = sorted(ss.items(), key=lambda x: (-x[1][0], x[0]))[:k]
    ss_topk = [e for e, _ in ss_topk_sorted]
    ss_topk_set = set(ss_topk)

    intersection = truth_topk_set & ss_topk_set
    precision_at_k = len(intersection) / k
    recall_at_k = len(intersection) / k   # both have size k

    # 5. Frequency estimation errors
    # For the reported top-k
    topk_errors = []
    topk_f_true = []
    topk_f_hat = []
    for e in ss_topk:
        fhat, _ = ss[e]
        ft = true_freq.get(e, 0)
        topk_f_true.append(ft)
        topk_f_hat.append(fhat)
        topk_errors.append(fhat - ft)

    topk_errors = np.array(topk_errors)
    topk_f_true = np.array(topk_f_true)
    topk_f_hat = np.array(topk_f_hat)

    # Relative over-estimation (fhat/ftrue - 1) - only for ftrue > 0
    mask = topk_f_true > 0
    rel_over_topk = (topk_f_hat[mask] - topk_f_true[mask]) / topk_f_true[mask]

    # Across all monitored elements
    all_errors = []
    all_f_true = []
    all_f_hat = []
    for e, (fhat, _) in ss.items():
        ft = true_freq.get(e, 0)
        all_f_true.append(ft)
        all_f_hat.append(fhat)
        all_errors.append(fhat - ft)

    all_errors = np.array(all_errors)
    all_f_true = np.array(all_f_true)
    all_f_hat = np.array(all_f_hat)

    # Theoretical min bound check (Lemma 2: min <= N/m)
    sum_counts = sum(c[0] for c in ss.values())
    min_count = min(c[0] for c in ss.values())
    max_count = max(c[0] for c in ss.values())

    # Summary stats
    metrics = {
        "config": {
            "N": N, "alpha": alpha, "alphabet_size": alphabet_size,
            "seed": seed, "k": k,
        },
        "runtime_seconds": {
            "stream_gen": t_gen, "true_count": t_count, "space_saving": t_ss,
            "total": t_gen + t_count + t_ss,
        },
        "data_stats": {
            "n_distinct_observed": len(true_freq),
            "true_top1_freq": truth_topk_sorted[0][1],
            "true_top10_freq": truth_topk_sorted[9][1],
            "true_top100_freq": truth_topk_sorted[99][1],
            "true_top500_freq": truth_topk_sorted[499][1] if len(truth_topk_sorted) >= 500 else None,
            "true_top1000_freq": truth_topk_sorted[999][1] if len(truth_topk_sorted) >= 1000 else None,
        },
        "ss_monitor_set_stats": {
            "size": len(ss),
            "sum_of_counts": int(sum_counts),
            "min_count_in_monitor": int(min_count),
            "max_count_in_monitor": int(max_count),
            "avg_count": float(sum_counts / len(ss)),
            "theoretical_min_upper_bound_N_over_k": N // k,
        },
        "topk_accuracy": {
            "precision_at_k": precision_at_k,
            "recall_at_k": recall_at_k,
            "intersection_size": len(intersection),
        },
        "frequency_estimation_error_reported_topk": {
            "n_elements": int(len(topk_errors)),
            "n_under_estimated": int(np.sum(topk_errors < 0)),
            "n_exact": int(np.sum(topk_errors == 0)),
            "n_over_estimated": int(np.sum(topk_errors > 0)),
            "mean_over_estimation": float(np.mean(topk_errors)),
            "median_over_estimation": float(np.median(topk_errors)),
            "max_over_estimation": int(np.max(topk_errors)),
            "min_over_estimation": int(np.min(topk_errors)),
            "p95_over_estimation": float(np.percentile(topk_errors, 95)),
            "p99_over_estimation": float(np.percentile(topk_errors, 99)),
            "mean_over_estimation_only_over": float(np.mean(topk_errors[topk_errors > 0])) if np.any(topk_errors > 0) else 0.0,
            "mean_relative_over_estimation": float(np.mean(rel_over_topk)) if rel_over_topk.size > 0 else 0.0,
            "max_relative_over_estimation": float(np.max(rel_over_topk)) if rel_over_topk.size > 0 else 0.0,
            "mean_absolute_error": float(np.mean(np.abs(topk_errors))),
        },
        "frequency_estimation_error_all_monitored": {
            "n_elements": int(len(all_errors)),
            "n_under_estimated": int(np.sum(all_errors < 0)),
            "n_exact": int(np.sum(all_errors == 0)),
            "n_over_estimated": int(np.sum(all_errors > 0)),
            "mean_over_estimation": float(np.mean(all_errors)),
            "median_over_estimation": float(np.median(all_errors)),
            "max_over_estimation": int(np.max(all_errors)),
            "min_over_estimation": int(np.min(all_errors)),
            "p95_over_estimation": float(np.percentile(all_errors, 95)),
            "p99_over_estimation": float(np.percentile(all_errors, 99)),
            "mean_over_estimation_only_over": float(np.mean(all_errors[all_errors > 0])) if np.any(all_errors > 0) else 0.0,
            "mean_absolute_error": float(np.mean(np.abs(all_errors))),
        },
    }

    print(json.dumps(metrics, indent=2, default=str))

    # Save metrics
    with open("metrics.json", "w") as f:
        json.dump(metrics, f, indent=2, default=str)

    # Per-rank detail
    detail = []
    for i, e in enumerate(ss_topk):
        fhat, err_bound = ss[e]
        ft = true_freq.get(e, 0)
        rank_in_truth = sum(1 for x in true_freq.values() if x > ft) + 1
        in_truth_topk = rank_in_truth <= k
        detail.append({
            "ss_rank": i + 1,
            "element": int(e),
            "f_true": int(ft),
            "f_hat": int(fhat),
            "delta_f": int(fhat - ft),
            "true_rank": int(rank_in_truth),
            "in_truth_topk": bool(in_truth_topk),
        })
    with open("topk_detail.json", "w") as f:
        json.dump(detail, f, indent=2)

    return metrics


if __name__ == "__main__":
    main()
