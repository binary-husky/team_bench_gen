"""Debug script - inspect failing lookups over many queries."""
import sys
sys.path.insert(0, '.')
from chord_sim import ChordRing, MOD
import random

ring = ChordRing(n=1000, r=1, seed=42)
ring.rebuild()

rng = random.Random(43)
wrong_cases = []
for _ in range(2000):
    key = rng.randrange(MOD)
    gt = ring.true_successor(key)
    req = rng.choice(ring.live_ids())
    result = ring.find_successor(req, key)
    if result != gt:
        wrong_cases.append((key, gt, req, result))

print(f"wrong cases: {len(wrong_cases)} / 2000")
for key, gt, req, result in wrong_cases[:10]:
    node = ring.nodes[req]
    print(f"key={key} gt={gt} req={req} result={result}")
    print(f"   req pred={node.predecessor} succ_list={node.successor_list[:5]}")
    # walk the path
    cur = req
    for hop in range(10):
        n = ring.nodes[cur]
        s = n.succ
        print(f"   hop {hop}: at {cur}, pred={n.predecessor}, succ={s}, succ_list={n.successor_list[:5]}")
        if s and MOD > key > cur and s > key:
            break
        if cur == gt:
            break
        # advance to candidate
        cand = None
        for ss in n.successor_list:
            if ss != cur and ring.nodes[ss].alive:
                # is ss in (cur, key)?
                if cur < key and cur < ss < key:
                    cand = ss
                elif cur > key and (ss > cur or ss < key):
                    cand = ss
        if cand is None:
            print("   stuck")
            break
        cur = cand