"""Trace a single query at f=0.1, r=1."""
import sys
sys.path.insert(0, '.')
from chord_sim import ChordRing, MOD, in_interval
import random

ring = ChordRing(n=1000, r=1, seed=42)
ring.build_successor_lists()
ring.mark_dead_fraction(0.1)

print(f"live nodes: {len(ring.live_ids())} / 1000")

# random key, random requester
rng = random.Random(100)
for trial in range(5):
    key = rng.randrange(MOD)
    req = rng.choice(ring.live_ids())
    gt = ring.true_successor(key)
    result = ring.find_successor(req, key)

    print(f"\nkey={key} gt={gt} req={req} result={result} ok={result==gt}")
    cur = req
    for hop in range(20):
        n = ring.nodes[cur]
        next_alive = None
        for s in n.successor_list:
            if ring.nodes[s].alive:
                next_alive = s
                break
        if next_alive is None:
            print(f"  hop {hop}: cur={cur} pred={n.predecessor} succ_list={n.successor_list} -> STUCK (all dead)")
            break
        covers = in_interval(key, cur, next_alive)
        print(f"  hop {hop}: cur={cur} pred={n.predecessor} succ_list={n.successor_list} -> next={next_alive} covers? {covers}")
        if covers:
            break
        cur = next_alive