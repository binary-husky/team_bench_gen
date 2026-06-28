"""
Experiment: effect of data distribution on Space-Saving accuracy.

Two streams of N=1e6 items, same cardinality, fixed seed:
  - Zipfian (strongly skewed)
  - Uniform
Run Space-Saving with k=100 on each. Compare top-k precision@k and recall@k
against exact full counting.
"""

import numpy as np
import heapq
import collections

# ---- fixed settings ----
N = 1_000_000          # stream length
K = 100                # number of counters / top-k
CARD = 100_000         # domain cardinality (number of distinct possible items)
SEED = 42              # fixed random seed


def gen_zipfian(n, card, seed, a=2.0):
    """Strongly skewed Zipfian (s=2.0) over `card` distinct items."""
    rng = np.random.default_rng(seed)
    # probabilities ∝ 1/r^a, r=1..card
    r = np.arange(1, card + 1, dtype=np.float64)
    w = 1.0 / np.power(r, a)
    p = w / w.sum()
    # sample n items
    items = rng.choice(card, size=n, p=p)
    return items.astype(np.int64)


def gen_uniform(n, card, seed):
    """Uniform distribution over `card` distinct items."""
    rng = np.random.default_rng(seed)
    items = rng.integers(0, card, size=n)
    return items.astype(np.int64)


class SpaceSaving:
    """Metwally et al. 2005 Space-Saving summary with k counters."""

    def __init__(self, k):
        self.k = k
        # item -> [count, error]  kept in a dict; plus a min-heap of (count, item)
        self.count = {}
        self.heap = []  # min-heap of (count, item)

    def add(self, item):
        if item in self.count:
            c = self.count[item][0] + 1
            self.count[item][0] = c
            # push a new heap entry (lazy deletion)
            heapq.heappush(self.heap, (c, item))
        else:
            if len(self.count) < self.k:
                self.count[item] = [1, 0]
                heapq.heappush(self.heap, (1, item))
            else:
                # evict min-count entry
                # lazily pop stale heap tops
                while self.heap:
                    c, it = self.heap[0]
                    if it in self.count and self.count[it][0] == c:
                        break
                    heapq.heappop(self.heap)
                c_min, it_min = self.heap[0]
                # remove evicted item
                del self.count[it_min]
                heapq.heappop(self.heap)
                new_c = c_min + 1
                self.count[item] = [new_c, c_min]
                heapq.heappush(self.heap, (new_c, item))

    def estimate(self):
        """Return dict item -> estimated count."""
        return {it: v[0] for it, v in self.count.items()}

    def errors(self):
        return {it: v[1] for it, v in self.count.items()}


def topk_from_counts(counts, k):
    """Return set of top-k items by count (ties broken arbitrarily by item id)."""
    # sort by count desc, then item asc for determinism
    ordered = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return [it for it, _ in ordered[:k]]


def run(items, k):
    ss = SpaceSaving(k)
    for it in items:
        ss.add(int(it))
    est = ss.estimate()
    exact = collections.Counter(int(x) for x in items)

    true_topk = topk_from_counts(exact, k)               # set of true top-k items
    est_topk = topk_from_counts(est, k)                   # estimated top-k items

    true_set = set(true_topk)
    est_set = set(est_topk)

    tp = len(true_set & est_set)
    precision = tp / len(est_set) if est_set else 1.0
    recall = tp / len(true_set) if true_set else 1.0

    # also report frequency-share metrics and error stats
    total = sum(exact.values())
    true_share = sum(exact[i] for i in true_topk) / total
    est_share = sum(est.get(i, 0) for i in est_topk) / total

    # per-item estimation error on monitored items
    errs = []
    for it, c in est.items():
        true_c = exact.get(it, 0)
        errs.append(c - true_c)

    return {
        "precision@k": precision,
        "recall@k": recall,
        "true_topk_freq_share": true_share,
        "est_topk_freq_share": est_share,
        "distinct_in_stream": len(exact),
        "monitored_items": len(est),
        "max_est_count": max(est.values()),
        "max_true_count": max(exact.values()),
        "mean_abs_est_error": float(np.mean(errs)) if errs else 0.0,
        "max_abs_est_error": float(max(errs)) if errs else 0.0,
        "true_topk": true_topk,
        "est_topk": est_topk,
        "overlap": true_set & est_set,
    }


def main():
    print(f"N={N}, K={K}, cardinality={CARD}, seed={SEED}")
    print("=" * 60)

    # Zipfian
    z = gen_zipfian(N, CARD, SEED, a=2.0)
    rz = run(z, K)
    print("\n[Zipfian s=2.0]")
    for kk in ["precision@k", "recall@k", "true_topk_freq_share",
               "est_topk_freq_share", "distinct_in_stream",
               "monitored_items", "max_est_count", "max_true_count",
               "mean_abs_est_error", "max_abs_est_error"]:
        print(f"  {kk:28s}: {rz[kk]}")
    print(f"  overlap size: {len(rz['overlap'])}")

    # Uniform
    u = gen_uniform(N, CARD, SEED)
    ru = run(u, K)
    print("\n[Uniform]")
    for kk in ["precision@k", "recall@k", "true_topk_freq_share",
               "est_topk_freq_share", "distinct_in_stream",
               "monitored_items", "max_est_count", "max_true_count",
               "mean_abs_est_error", "max_abs_est_error"]:
        print(f"  {kk:28s}: {ru[kk]}")
    print(f"  overlap size: {len(ru['overlap'])}")

    # Distribution shape diagnostics
    exact_z = collections.Counter(int(x) for x in z)
    exact_u = collections.Counter(int(x) for x in u)
    zc = sorted(exact_z.values(), reverse=True)
    uc = sorted(exact_u.values(), reverse=True)
    print("\n[Shape]")
    print(f"  Zipfian  top1 freq = {zc[0]} ({zc[0]/N:.4f}), "
          f"top100 share = {sum(zc[:100])/N:.4f}, "
          f"top1000 share = {sum(zc[:1000])/N:.4f}")
    print(f"  Uniform  top1 freq = {uc[0]} ({uc[0]/N:.4f}), "
          f"top100 share = {sum(uc[:100])/N:.4f}, "
          f"top1000 share = {sum(uc[:1000])/N:.4f}")

    # write a json for convenience
    import json
    out = {
        "settings": {"N": N, "K": K, "cardinality": CARD, "seed": SEED,
                     "zipf_a": 2.0},
        "zipfian": {k: v for k, v in rz.items() if k not in ("true_topk", "est_topk", "overlap")},
        "uniform": {k: v for k, v in ru.items() if k not in ("true_topk", "est_topk", "overlap")},
    }
    with open("results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nWrote results.json")


if __name__ == "__main__":
    main()
