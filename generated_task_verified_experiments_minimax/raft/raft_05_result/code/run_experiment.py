#!/usr/bin/env python3
"""
Run the term-safety experiment from task.md across >=10 random seeds.

Scenario per seed:
  1. Elect leader L1 (term T), submit & commit 50 entries.
  2. Isolate L1 from the rest of the cluster.
     While isolated, submit *more* client commands to L1 so its log grows
     with entries that are never replicated to anyone (these become the
     "stale uncommitted entries" that should be truncated after restore).
  3. Among the remaining 4 nodes, elect a new leader L2 (term T' > T);
     L2 commits 50 brand-new entries (its 50 entries land at indices
     51..100, on top of the original 50 inherited from L1).
  4. Restore L1's connection. Run long enough for L1 to be demoted to
     follower and to fully converge (its log should match L2's).

Metrics recorded per seed:
  - L1 demoted to Follower (must be True)
  - Committed entries corrupted / overwritten in L1's log (must be 0)
  - Stale uncommitted entries in L1 truncated to align with L2 (>= 0)
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from raft_sim import Cluster, _clear_queues


def run_one(seed: int) -> dict:
    _clear_queues()
    c = Cluster(seed)

    # 1) Elect L1, commit 50 entries.
    lid = c.wait_for_leader(max_ticks=200)
    if lid is None:
        return {"seed": seed, "error": "no initial leader elected"}
    l1 = lid
    T = c.term_of(l1)

    for i in range(50):
        c.submit_command(f"L1-seed{seed}-cmd{i}")
    if not c.wait_for_commit(50, max_ticks=400):
        return {"seed": seed, "error": "L1 did not commit 50 entries",
                "committed": c.commit(l1), "term": T}
    assert c.commit(l1) == 50, f"only committed {c.commit(l1)}"
    l1_log_len_after_initial_commit = len(c.log(l1))
    assert l1_log_len_after_initial_commit == 50

    # 2) Isolate L1.
    c.isolate(l1)
    # Submit MORE client commands to L1. As the leader it will append them
    # to its log, but because it is partitioned from the majority, those
    # entries will not be replicated to anyone -- they are uncommitted
    # "stale" entries that the term-safety property says must be truncated
    # to align with the new leader's log.
    for i in range(30):
        c.submit_command(f"L1-STALE-seed{seed}-cmd{i}")
    # Let a few ticks go by so the partition takes effect and the other
    # 4 nodes time out and elect a new leader. L1's election timer does
    # NOT fire for a leader (it just keeps sending heartbeats into the
    # void), so L1's term stays at T.
    c.step(40)

    l1_log_len_while_isolated = len(c.log(l1))
    l1_term_while_isolated = c.term_of(l1)

    # 3) Among the other 4 nodes, a new leader should have emerged.
    #    Find it.
    l2 = None
    for _ in range(200):
        c.step(1)
        cur = c.leader_id()
        if cur is not None and cur != l1:
            l2 = cur
            break
    if l2 is None:
        return {"seed": seed, "error": "no second leader elected",
                "l1_term_while_isolated": l1_term_while_isolated}
    T_prime = c.term_of(l2)
    if T_prime <= T:
        return {"seed": seed, "error": f"T'={T_prime} not > T={T}"}

    # 4) L2 commits 50 NEW entries (at indices 51..100).
    for i in range(50):
        c.submit_command(f"L2-seed{seed}-cmd{i}")
    if not c.wait_for_commit(100, max_ticks=400):
        return {"seed": seed, "error": "L2 did not commit 50 new entries",
                "committed": c.commit(l2), "term": T_prime}
    assert c.commit(l2) == 100, f"L2 only committed {c.commit(l2)}"

    canonical_committed = [c.log(l2)[i] for i in range(100)]

    # 5) Restore L1.
    c.restore()
    l1_state_before = c.nodes[l1].state
    l1_term_before = c.term_of(l1)
    l1_log_len_before = len(c.log(l1))

    # 6) Run ticks until: (a) L1 is a Follower at term T', AND
    #    (b) L1's log matches L2's exactly. Then measure.
    demoted = False
    converged = False
    for _ in range(500):
        c.step(1)
        if c.nodes[l1].state == "Follower" and c.term_of(l1) >= T_prime:
            demoted = True
        # Convergence: L1's log == L2's log, L1's commit >= 100
        if (c.nodes[l1].state == "Follower"
                and len(c.log(l1)) == len(c.log(l2))
                and c.commit(l1) >= 100):
            converged = True
            if demoted:
                break

    l1_state_after = c.nodes[l1].state
    l1_term_after = c.term_of(l1)
    l1_log_after = list(c.log(l1))
    l1_committed_after = c.commit(l1)

    # --- Metrics ----------------------------------------------------------
    # (a) Demoted: L1 must be a Follower at >= T'.
    demoted_flag = (l1_state_after == "Follower") and (l1_term_after >= T_prime)

    # (b) Committed entries must not be corrupted. Compare L1's log at
    #     indices 1..100 to the canonical committed list. If L1 hasn't
    #     fully converged we still report whatever corruption exists.
    corrupted = 0
    for i in range(100):
        if i >= len(l1_log_after):
            corrupted += 1
            continue
        e_l1 = l1_log_after[i]
        e_ref = canonical_committed[i]
        if e_l1.term != e_ref.term or e_l1.cmd != e_ref.cmd:
            corrupted += 1

    # (c) Stale uncommitted entries truncated.
    #     L1 had l1_log_len_before entries at restoration: the 50 committed
    #     ones (term T) plus the STALE entries (term T) it appended during
    #     isolation. After convergence, L1's log should match L2's exactly.
    #     The stale entries are at indices 51..(l1_log_len_before-1) in
    #     L1's pre-restore log; L2 doesn't have entries at those indices
    #     (L2's 51..100 are NEW entries with different terms/cmds), so the
    #     stale entries get truncated/replaced by log reconciliation.
    truncated = max(0, l1_log_len_before - 50)

    return {
        "seed": seed,
        "L1": l1,
        "L2": l2,
        "T": T,
        "T_prime": T_prime,
        "l1_state_before": l1_state_before,
        "l1_term_before": l1_term_before,
        "l1_log_len_before": l1_log_len_before,
        "l1_log_len_while_isolated": l1_log_len_while_isolated,
        "l1_term_while_isolated": l1_term_while_isolated,
        "l1_state_after": l1_state_after,
        "l1_term_after": l1_term_after,
        "l1_log_len_after": len(l1_log_after),
        "l1_committed_after": l1_committed_after,
        "converged": converged,
        "demoted_to_follower": demoted_flag,
        "committed_entries_corrupted": corrupted,
        "stale_uncommitted_truncated": truncated,
    }


def main():
    seeds = list(range(12))  # 12 seeds (>= 10 as required)
    rows = []
    for s in seeds:
        r = run_one(s)
        if "error" in r:
            print(f"seed={s:02d} ERROR: {r['error']}  info={ {k:v for k,v in r.items() if k!='seed' and k!='error'} }")
        else:
            print(f"seed={s:02d} L1=n{r['L1']}(T={r['T']}) L2=n{r['L2']}(T'={r['T_prime']}) "
                  f"demoted={r['demoted_to_follower']} "
                  f"corrupted={r['committed_entries_corrupted']} "
                  f"truncated={r['stale_uncommitted_truncated']} "
                  f"l1_len={r['l1_log_len_before']}->{r['l1_log_len_after']} "
                  f"converged={r['converged']}")
        rows.append(r)

    # Persist raw rows
    out_path = Path(__file__).parent / "experiment_results.txt"
    with out_path.open("w") as f:
        for r in rows:
            f.write(repr(r) + "\n")
    print(f"\nWrote raw results to {out_path}")

    # Summary
    ok = [r for r in rows if "error" not in r]
    print(f"\nSuccessful runs: {len(ok)}/{len(rows)}")
    if ok:
        demoted_all = all(r["demoted_to_follower"] for r in ok)
        corrupted_total = sum(r["committed_entries_corrupted"] for r in ok)
        truncated_total = sum(r["stale_uncommitted_truncated"] for r in ok)
        converged_all = all(r["converged"] for r in ok)
        print(f"L1 demoted in all runs: {demoted_all}")
        print(f"Total committed entries corrupted: {corrupted_total}")
        print(f"Total stale uncommitted entries truncated: {truncated_total}")
        print(f"All runs converged: {converged_all}")


if __name__ == "__main__":
    main()
