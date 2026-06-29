"""Debug: inspect what's actually in the top-k after Space-Saving."""
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
true_top50 = sorted_items[:50]

print("True top-50 by frequency (item, freq):")
for i, (it, f) in enumerate(true_top50):
    print(f"  {i+1:3d}: item={it:5d} freq={f}")

for k in [50, 100]:
    print(f"\n=== k={k} ===")
    ss = SpaceSaving(k)
    ss.update_batch(stream)
    top = ss.top_k(50)
    print(f"Space-Saving's top-50 (item, est_count, error, true_freq):")
    for i, (it, c, err) in enumerate(top):
        true_f = exact.get(it, 0)
        print(f"  {i+1:3d}: item={it:5d} est_count={c:6d} err={err:5d} true_freq={true_f:6d}")

    # How many of true top-50 are present in the SS's slots?
    ss_items = set(int(it) for it in ss.item[:ss.size])
    present = sum(1 for it, _ in true_top50 if it in ss_items)
    print(f"\nTrue top-50 items present in any SS slot: {present}/50")

    # How many of true top-50 are in SS top-50?
    top_items = set(t[0] for t in top)
    correct = sum(1 for it, _ in true_top50 if it in top_items)
    print(f"True top-50 items in SS top-50: {correct}/50  (precision=recall={correct/50:.3f})")