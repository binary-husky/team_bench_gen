"""More detailed debug: examine precision@k semantics."""
import sys
sys.path.insert(0, '/data/workspace/admin/happy_lake/.verify_judge_minimax/spacesaving/spacesaving_03')
from experiment import zipf_stream, SpaceSaving
from collections import Counter

N = 1_000_000
ALPHA = 1.5
ALPHABET = 10_000
SEED = 42

stream = zipf_stream(N, ALPHA, ALPHABET, SEED)
exact = Counter(stream.tolist())
sorted_items = sorted(exact.items(), key=lambda x: (-x[1], x[0]))
true_top500 = sorted_items[:500]

for k in [50, 100, 200, 500]:
    print(f"\n=== k={k} ===")
    ss = SpaceSaving(k)
    ss.update_batch(stream)
    ss_items = list(zip(ss.item[:ss.size].tolist(), ss.count[:ss.size].tolist(), ss.error[:ss.size].tolist()))

    # Sort by count descending
    ss_items.sort(key=lambda x: -x[1])

    # Compute (count - error) for each slot
    print(f"Min counter = {ss.count[:ss.size].min()}, max = {ss.count[:ss.size].max()}")
    print(f"Boundary stats at rank k=50:")
    # The 50th highest count in SS
    counts_desc = sorted(ss.count[:ss.size].tolist(), reverse=True)
    lo = max(0, k-3)
    hi = min(len(counts_desc), k+3)
    print(f"  counts[{lo}:{hi}] = {counts_desc[lo:hi]}")
    if k-1 < len(counts_desc):
        print(f"  #items with count == count[{k-1}]={counts_desc[k-1]} : {sum(1 for c in ss.count[:ss.size] if c == counts_desc[k-1])}")
    if k < len(counts_desc):
        print(f"  #items with count == count[{k}]={counts_desc[k]} : {sum(1 for c in ss.count[:ss.size] if c == counts_desc[k])}")

    # Take SS's top-k (which is what 'precision@k' should refer to)
    top = ss.top_k(k)
    top_set = set(t[0] for t in top)
    true_set = set(it for it, _ in true_top500[:k])
    overlap = len(top_set & true_set)
    print(f"  overlap = {overlap}/{k}, precision=recall={overlap/k:.3f}")

    # Compute the "guaranteed top-k" per paper's Theorem 6 / Query-Top-k algorithm
    # Items with (count - error) >= count_{k+1} are guaranteed
    sorted_by_count_desc = sorted(ss_items, key=lambda x: -x[1])
    # count_{k+1} is the (k+1)-th highest count
    if len(sorted_by_count_desc) > k:
        count_kp1 = sorted_by_count_desc[k][1]  # (k+1)th highest count (0-indexed = k)
    else:
        count_kp1 = 0
    guaranteed = [t for t in sorted_by_count_desc if (t[1] - t[2]) >= count_kp1]
    print(f"  count_{{k+1}} = {count_kp1}")
    print(f"  guaranteed top-k (count-error >= count_{{k+1}}): {len(guaranteed)} items")
    # How many of guaranteed are truly in top-k?
    g_set = set(t[0] for t in guaranteed)
    g_correct = len(g_set & true_set)
    print(f"  of which truly in top-k: {g_correct}/{k}")