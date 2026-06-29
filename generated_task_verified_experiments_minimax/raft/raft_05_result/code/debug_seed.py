#!/usr/bin/env python3
"""Debug why some seeds fail to elect a second leader."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from raft_sim import Cluster, _clear_queues


def debug_seed(seed: int, max_ticks: int = 500):
    _clear_queues()
    c = Cluster(seed)
    lid = c.wait_for_leader(max_ticks=200)
    print(f"[seed {seed}] initial leader={lid}")
    if lid is None:
        return

    # Skip the 50-entry commit
    for i in range(50):
        c.submit_command(f"cmd{i}")
    c.wait_for_commit(50, max_ticks=400)
    print(f"[seed {seed}] committed 50, now isolating node {lid}")

    c.isolate(lid)
    # Just step and see what happens
    for t in range(max_ticks):
        c.step(1)
        if t % 10 == 0:
            states = [n.state for n in c.nodes]
            terms = [n.current_term for n in c.nodes]
            print(f"  tick {t}: states={states} terms={terms} leader={c.leader_id()}")
        if c.leader_id() is not None and c.leader_id() != lid:
            print(f"  *** new leader at tick {t+1}: {c.leader_id()}")
            return
    print(f"  *** NO new leader after {max_ticks} ticks")


if __name__ == "__main__":
    for s in [1, 2, 3, 6]:
        debug_seed(s, max_ticks=100)
        print()
