"""
Experiment: effect of counter-slot count k on Space-Saving accuracy & memory.

Fixed: N=1e6, Zipfian(alpha=1.0) stream, seed=42.
Variable: k in {50,100,200,500}.

Reference: exact full-count (Counter) over the same stream.

Metrics per k:
  - precision@k  = |reported_top_k ∩ exact_top_k| / |reported|
  - recall@k     = |reported_top_k ∩ exact_top_k| / k
  - max over-estimation error = max_{e in monitored}(count_e - true_freq_e)
  - occupied slots / memory (counters used)
  - also record actual min counter value vs theoretical bound N/k.

Space-Saving (Metwally et al. 2005), m=k counters:
  - if element monitored: count[e] += 1
  - elif free slot:        count[e] = 1, eps[e] = 0
  - else:                  evict min-count element me (count=minv);
                          count[e] = minv+1, eps[e] = minv
  Lemma: f_i <= count_i <= f_i + min,  min <= N/m.
  Implemented with a lazy min-heap + dict for O(N log k) amortized.
"""

import heapq
import numpy as np
from collections import Counter

# ---------- fixed settings ----------
N = 1_000_000
ALPHA = 1.5          # Zipfian shape parameter (skewed, realistic; numpy zipf needs a>1)
SEED = 42
KS = [50, 100, 200, 500]

# ---------- generate the single fixed Zipfian stream ----------
rng = np.random.default_rng(SEED)
stream = rng.zipf(ALPHA, size=N).astype(np.int64)
print(f"stream: N={N}, alpha={ALPHA}, seed={SEED}, distinct={len(np.unique(stream))}")

# ---------- exact reference ----------
exact = Counter(stream.tolist())
total = sum(exact.values())
assert total == N

# exact top-k sets (deterministic tie-break: by (-freq, id))
def exact_top_k(k):
    # sort items by (freq desc, id asc)
    items = sorted(exact.items(), key=lambda kv: (-kv[1], kv[0]))
    return [it for it, _ in items[:k]]

# precompute sorted exact frequencies (desc, tie-break id asc)
_exact_sorted = sorted(exact.items(), key=lambda kv: (-kv[1], kv[0]))
exact_top_k_val = [c for _, c in _exact_sorted]  # i-th largest true freq

# ---------- Space-Saving ----------
def space_saving(stream, k):
    count = {}          # element -> estimated count (current)
    heap = []           # lazy min-heap of (count, element)
    for e in stream:
        c = count.get(e)
        if c is not None:
            c += 1
            count[e] = c
            heapq.heappush(heap, (c, e))
        elif len(count) < k:
            count[e] = 1
            heapq.heappush(heap, (1, e))
        else:
            # pop until a non-stale entry (== current count) is found
            while heap:
                minv, me = heapq.heappop(heap)
                if count.get(me) == minv:
                    break
            # evict me, install e with minv+1
            del count[me]
            count[e] = minv + 1
            heapq.heappush(heap, (minv + 1, e))
    # final min (clean heap)
    minv = None
    tmp = []
    while heap:
        v, me = heapq.heappop(heap)
        tmp.append((v, me))
        if count.get(me) == v:
            minv = v
            break
    for v, me in tmp:
        heapq.heappush(heap, (v, me))
    return count, minv

# ---------- run for each k ----------
print(f"\n{'k':>5} | {'prec@k':>7} {'rec@k':>7} | {'max_overest':>11} {'N/k_bound':>9} {'actual_min':>10} | {'f*_k':>6} {'maxerr/f*_k':>11} | {'slots':>5} {'~KiB':>7}")
rows = []
for k in KS:
    est, minv = space_saving(stream.tolist(), k)
    # reported top-k by estimated count (tie-break -count, id)
    rep = sorted(est.items(), key=lambda kv: (-kv[1], kv[0]))
    reported = [it for it, _ in rep[:k]]
    reported_set = set(reported)
    true_top = set(exact_top_k(k))
    overlap = len(reported_set & true_top)
    precision = overlap / len(reported_set) if reported_set else 0.0
    recall = overlap / k
    # max over-estimation over monitored elements
    max_over = max((cnt - exact.get(e, 0) for e, cnt in est.items()), default=0)
    theo_bound = N / k
    # k-th largest true frequency (boundary of exact top-k)
    fk = exact_top_k_val[k - 1]
    ratio = max_over / fk if fk else float('inf')
    slots = len(est)
    # memory: each slot stores (element id + count); naive 16 B/slot payload
    kib = slots * 16 / 1024.0
    print(f"{k:>5} | {precision:>7.3f} {recall:>7.3f} | {max_over:>11d} {theo_bound:>9.0f} {minv:>10d} | {fk:>6d} {ratio:>11.2f} | {slots:>5} {kib:>7.1f}")
    rows.append(dict(k=k, precision=precision, recall=recall,
                     max_over=max_over, theo_bound=theo_bound, actual_min=minv,
                     fk=fk, ratio=ratio, slots=slots, kib=kib, overlap=overlap))

# persist for the summary
import json
with open("results.json", "w") as f:
    json.dump(rows, f, indent=2)
print("\nwrote results.json")
