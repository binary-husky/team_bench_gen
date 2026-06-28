"""
Space-Saving top-k accuracy experiment.

Reference: Metwally, Agrawal, El Abbadi, "A Comprehensive Study of Frequent
Elements Estimation Techniques" (2005). Figure 1 gives the algorithm:

  Space-Saving(m counters, stream S):
    for each element e in S:
      if e is monitored:         increment its counter
      else:                      em = element with least hits (min)
                                  replace em with e
                                  increment countm (so new count = min+1)
                                  set eps_m = min   (over-estimation bound)

Estimated frequency f_hat(e) = count(e)  (always >= true f ; never under-estimates).
Per-element over-estimation eps_e is tracked; guaranteed hits = count - eps.

We measure, vs an exact full-count ground truth:
  - precision@k and recall@k of the reported top-k (k=100)
  - frequency over-estimation error f_hat - f  (mean / max, only for monitored)
"""

import numpy as np
import json

# ----------------------------------------------------------------------
# Fixed configuration (no independent variable -> single accuracy run)
# ----------------------------------------------------------------------
N          = 1_000_000      # stream length
K          = 100            # top-k, and number of Space-Saving counters m=k
ALPHABET   = 50_000         # |A| distinct item ids
S          = 1.5            # Zipf skew parameter (paper's "realistic skew" alpha=1.5)
SEED       = 1729           # fixed random seed

rng = np.random.default_rng(SEED)

# ----------------------------------------------------------------------
# 1. Generate a Zipf-skewed stream over a fixed alphabet.
#    p_i proportional to 1 / i^S , i = 1..ALPHABET  (rank->id identity).
# ----------------------------------------------------------------------
ranks = np.arange(1, ALPHABET + 1, dtype=np.float64)
probs = 1.0 / (ranks ** S)
probs /= probs.sum()

# Sample N items (ids 1..ALPHABET). choice with p is O(N) given a fixed CDF.
stream = rng.choice(ALPHABET, size=N, replace=True, p=probs) + 1  # ids 1..A
print(f"Generated stream: N={N}, |A|={ALPHABET}, Zipf s={S}, seed={SEED}")
print(f"Distinct items actually seen: {len(np.unique(stream))}")

# ----------------------------------------------------------------------
# 2. Exact ground-truth frequencies (full count).
# ----------------------------------------------------------------------
true_counts = np.bincount(stream, minlength=ALPHABET + 1)  # index = id
# true top-k by descending frequency (ties broken by id)
true_order = np.argsort(-true_counts, kind="stable")
true_topk = set(true_order[:K].tolist())
true_topk_arr = true_order[:K]
print(f"True top-{K} freq range: {true_counts[true_topk_arr[0]]} .. "
      f"{true_counts[true_topk_arr[-1]]}")
print(f"True #{K}-th freq: {true_counts[true_topk_arr[-1]]}")

# ----------------------------------------------------------------------
# 3. Space-Saving with m = K counters (Stream-Summary semantics).
# ----------------------------------------------------------------------
# Maintain, for the monitored set of size m:
#   count[e], eps[e]   (kept in dicts keyed by id)
# We need fast min lookup. For N=1e6, k=100, a heap-based min is fine,
# but to match the paper exactly (evict the least counter) we use a
# min-heap of (count, id). When id's count changes we lazily skip stale
# heap entries.
import heapq

m = K
count = {}      # id -> estimated count
eps   = {}      # id -> over-estimation bound (value of min at insertion)
min_heap = []   # (count, id) min-heap

# Convert to a plain-python int buffer once: numpy-scalar dict keys/heap
# comparisons are slow and error-prone over 1e6 iterations.
stream_list = stream.tolist()

for e in stream_list:
    c = count.get(e)
    if c is not None:
        # monitored -> increment
        c += 1
        count[e] = c
        heapq.heappush(min_heap, (c, e))
    elif len(count) < m:
        # free counter available: occupy it with count 1, eps 0 (min was 0)
        count[e] = 1
        eps[e]   = 0
        heapq.heappush(min_heap, (1, e))
    else:
        # replacement step: evict element with least hits (min)
        # pop stale heap entries until the top matches a live counter
        while min_heap:
            mc, mid = min_heap[0]
            if count.get(mid) == mc:
                break
            heapq.heappop(min_heap)
        mc, mid = heapq.heappop(min_heap)   # current true min
        min_val = mc
        del count[mid]
        del eps[mid]
        count[e] = min_val + 1
        eps[e]   = min_val
        heapq.heappush(min_heap, (min_val + 1, e))

# ----------------------------------------------------------------------
# 4. Reported top-k from Space-Saving: the k largest estimated counts.
# ----------------------------------------------------------------------
est_items = list(count.items())  # (id, count)
est_items.sort(key=lambda x: -x[1])
ss_topk_arr = np.array([i for i, _ in est_items[:K]])
ss_topk = set(ss_topk_arr.tolist())

# precision@k, recall@k
tp = len(ss_topk & true_topk)
precision = tp / K
recall    = tp / K          # |true_topk| == K == |reported|, so recall==precision here
print(f"precision@{K} = {precision:.4f}")
print(f"recall@{K}    = {recall:.4f}")

# ----------------------------------------------------------------------
# 5. Frequency over-estimation error  f_hat - f   (>=0 guaranteed).
#    Examine the reported top-k and all monitored elements.
# ----------------------------------------------------------------------
errs_topk = []
errs_all  = []
for eid, fhat in count.items():
    f = int(true_counts[eid])
    err = fhat - f
    assert err >= 0, f"under-estimation! id={eid} fhat={fhat} f={f}"
    errs_all.append((eid, f, fhat, err))
    if eid in ss_topk:
        errs_topk.append((eid, f, fhat, err))

errs_topk.sort(key=lambda x: -x[3])
errs_all.sort(key=lambda x: -x[3])

def stats(name, errs):
    if not errs:
        print(f"{name}: no elements"); return None
    over = [e[3] for e in errs]
    ratios = [e[3] / e[1] for e in errs if e[1] > 0]
    res = {
        "n": len(errs),
        "mean_overestimate": float(np.mean(over)),
        "max_overestimate": int(np.max(over)),
        "mean_relative_overestimate": float(np.mean(ratios)) if ratios else None,
        "max_relative_overestimate": float(np.max(ratios)) if ratios else None,
    }
    print(f"{name}: {res}")
    return res

# Breakdown: monitored elements that ARE in the true top-k (true positives)
# vs. those that are NOT (false positives).  For true positives the absolute
# over-estimation is the meaningful accuracy figure; for false positives the
# true frequency is tiny so the relative error is huge but uninteresting.
errs_tp  = [t for t in errs_all if t[0] in true_topk]
errs_fp  = [t for t in errs_all if t[0] not in true_topk]

st_topk = stats("reported top-k over-estimation (all)", errs_topk)
st_all  = stats("all monitored over-estimation", errs_all)
st_tp   = stats("TRUE-POSITIVE monitored (in true top-k)", errs_tp)
st_fp   = stats("FALSE-POSITIVE monitored (not in true top-k)", errs_fp)

# min counter value at end (over-estimation upper bound per Lemma 3)
final_min = min(count.values())
print(f"final min counter = {final_min}  (bound on any eps_i)")

# top-5 worst-overestimated among reported top-k
print("\nWorst over-estimation among reported top-k (id, true_f, est_f, err):")
for eid, f, fhat, err in errs_topk[:5]:
    print(f"  id={eid:6d}  f={f:7d}  f_hat={fhat:7d}  err={err:6d}  "
          f"rel={ (err/f) if f else float('nan'):.4f}")

# ----------------------------------------------------------------------
# 6. Write summary.
# ----------------------------------------------------------------------
summary = {
    "config": {"N": N, "K": K, "alphabet": ALPHABET, "zipf_s": S, "seed": SEED,
               "counters_m": m},
    "true_topk_freq_max": int(true_counts[true_topk_arr[0]]),
    "true_topk_freq_min_kth": int(true_counts[true_topk_arr[-1]]),
    "precision_at_k": precision,
    "recall_at_k": recall,
    "true_positives": tp,
    "final_min_counter": final_min,
    "overestimation_topk": st_topk,
    "overestimation_all_monitored": st_all,
    "overestimation_true_positives": st_tp,
    "overestimation_false_positives": st_fp,
    "false_positives_in_report": len(errs_fp),
    "true_topk_members_missing": K - len(errs_tp),
}
with open("results.json", "w") as fh:
    json.dump(summary, fh, indent=2)
print("\nWrote results.json")
