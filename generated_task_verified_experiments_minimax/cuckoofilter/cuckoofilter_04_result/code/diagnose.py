"""Diagnose the false-negative mechanism by checking each retained key whose
fingerprint got removed during a delete of a different key."""
import random
from experiment import CuckooFilter, make_keys, N, B, F, HALF, SEED

cf = CuckooFilter(28_000, b=B, f=F)
keys = make_keys(N, SEED)
for k in keys:
    cf.insert(k)

rng = random.Random(SEED)
shuffled = list(keys)
rng.shuffle(shuffled)
retained, deleted = shuffled[:HALF], shuffled[HALF:]

# For each deleted key, identify the fingerprint
deleted_fps = [cf._fingerprint_of(k) for k in deleted]

# Find retained keys whose fingerprint is still present in their candidate buckets
# vs those whose fingerprint is gone.
retained_fps = [cf._fingerprint_of(k) for k in retained]
still_in_filter = 0
gone = 0
for k, fp in zip(retained, retained_fps):
    i1, i2 = cf._indices(k, fp)
    if cf._bucket_contains(i1, fp) or cf._bucket_contains(i2, fp):
        still_in_filter += 1
    else:
        gone += 1
print(f"After deletions: still_in_filter = {still_in_filter}, gone = {gone}")

# How many of the 'gone' retained keys have a sibling with the same fp in the
# deleted set?
from collections import Counter
deleted_fp_counter = Counter(deleted_fps)
false_neg_candidates = []
for k, fp in zip(retained, retained_fps):
    i1, i2 = cf._indices(k, fp)
    if not (cf._bucket_contains(i1, fp) or cf._bucket_contains(i2, fp)):
        # fingerprint is gone -- look for siblings in deleted set
        n_deleted_siblings = deleted_fp_counter[fp]
        false_neg_candidates.append((k, fp, n_deleted_siblings))
print(f"# retained keys whose fp was wiped: {len(false_neg_candidates)}")

# Distribution of how many deleted siblings each wiped key has
dist = Counter(c[2] for c in false_neg_candidates)
print("Distribution of # deleted siblings among wiped retained keys:")
for n in sorted(dist):
    print(f"  {n} deleted siblings: {dist[n]} keys wiped")

# How many of the wiped keys have ZERO deleted siblings? Those would indicate
# a different source of FN (shouldn't happen unless we have a kick-chain bug).
zeros = sum(1 for c in false_neg_candidates if c[2] == 0)
print(f"  ... of which {zeros} have ZERO deleted siblings (unexpected)")
