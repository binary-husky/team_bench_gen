"""Quick sanity check across multiple seeds to confirm overall trend."""
import hashlib, statistics, random, bisect, time

N = 200
K = 100_000
VS = [1, 2, 5, 10, 20]
M_MOD = 1 << 160


def sha1_int(s):
    return int.from_bytes(hashlib.sha1(s.encode("utf-8")).digest(), "big")


def make_virtual_node_ids(v):
    vnodes = []
    for pid in range(N):
        for j in range(v):
            h = sha1_int(f"node-{pid}-vnode-{j}")
            vnodes.append((h, pid))
    vnodes.sort(key=lambda x: x[0])
    return vnodes


def assign(vnodes, key_hashes):
    ring = [h for (h, _) in vnodes]
    pids = [pid for (_, pid) in vnodes]
    L = len(ring)
    loads = [0] * N
    for kh in key_hashes:
        idx = bisect.bisect_left(ring, kh)
        if idx == L:
            idx = 0
        loads[pids[idx]] += 1
    return loads


def stats(loads):
    mean = sum(loads) / len(loads)
    std = statistics.pstdev(loads)
    return max(loads) / mean, std / mean


# Aggregate over multiple seeds
SEEDS = [1, 7, 42, 100, 2024, 12345]
agg = {v: {"max_over_mean": [], "cv": []} for v in VS}

for seed in SEEDS:
    rng = random.Random(seed)
    key_strs = [f"key-{rng.randrange(1<<31)}-{rng.randrange(1<<31)}" for _ in range(K)]
    key_hashes = [sha1_int(s) for s in key_strs]
    for v in VS:
        vnodes = make_virtual_node_ids(v)
        loads = assign(vnodes, key_hashes)
        mm, cv = stats(loads)
        agg[v]["max_over_mean"].append(mm)
        agg[v]["cv"].append(cv)

print(f"Averaged over {len(SEEDS)} seeds")
print(f"{'v':>4}  {'max/mean (avg±std)':>22}  {'CV (avg±std)':>22}")
for v in VS:
    mms = agg[v]["max_over_mean"]
    cvs = agg[v]["cv"]
    mm_avg = sum(mms)/len(mms)
    mm_std = statistics.pstdev(mms)
    cv_avg = sum(cvs)/len(cvs)
    cv_std = statistics.pstdev(cvs)
    print(f"{v:>4}  {mm_avg:>10.4f} ± {mm_std:.4f}  {cv_avg:>10.4f} ± {cv_std:.4f}")
