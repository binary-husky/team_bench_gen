# Term Safety at Runtime — Leader Completeness Verification

**Task.** Validate the Raft term-safety guarantee at runtime:
- An ousted/stale-term leader **must not** be able to overwrite or destroy
  entries that have already been committed by a new-term majority.
- After reconnection the old leader **must** be forced to step down to
  follower, and any uncommitted entries it appended while partitioned
  **must** be truncated to match the new leader's log (log reconciliation).

## Setup

- **Simulator** — `raft_sim.py` (this directory): an in-process Raft simulator
  with 5 nodes, in-memory message queues, a logical tick clock, deterministic
  seeded randomness, no real sockets/Docker, and a partition switch that can
  isolate/restore a node from the rest of the cluster. Implementation follows
  Ongaro & Ousterhout 2014, §5.2–§5.4 (RequestVote, AppendEntries, term
  bump on higher-term messages, prevLog consistency check + truncate-on-
  conflict, leader-commit advance only for current-term entries).
- **Cluster** N=5, 1 client = 50 commands committed by L1, then 30 *stale*
  commands appended by L1 while isolated (these will be uncommitted because
  L1 cannot replicate them to a majority), then L2 is elected among the
  remaining 4 nodes and commits 50 brand-new commands.
- **Seeds** — 12 distinct seeds, each (re)randomising the entry contents and
  the timing of the partition.

## Per-run metrics table

Each row is one seeded run. The columns are:

- `L1` / `L2` — node ids of the original and the new leader.
- `T` / `T'` — terms of L1 (original) and L2 (new leader); T' > T in every run.
- `demoted` — L1's state right after reconnection: did it get forced to
  Follower at term ≥ T'?  Must be **Yes** for term safety.
- `corrupted` — number of already-committed entries (indices 1..100, the
  50 from L1's term plus the 50 from L2's term) whose **(term, cmd)**
  in L1's post-restore log disagrees with the canonical committed value.
  Must be **0** for Leader Completeness.
- `truncated` — number of L1's stale, uncommitted entries that the
  reconciler threw away when it aligned L1's log with L2's.  Must be
  **> 0** (we appended 30 such entries during isolation, so we expect
  30 per run).

| seed | L1 | L2 | T | T' | demoted | corrupted | truncated |
|:----:|:--:|:--:|:-:|:--:|:-------:|:---------:|:---------:|
|  0   |  1 |  0 | 1 |  2 |   Yes   |     0     |    30     |
|  1   |  0 |  4 | 1 |  2 |   Yes   |     0     |    30     |
|  2   |  0 |  3 | 1 |  2 |   Yes   |     0     |    30     |
|  3   |  0 |  2 | 1 |  2 |   Yes   |     0     |    30     |
|  4   |  3 |  4 | 1 |  2 |   Yes   |     0     |    30     |
|  5   |  2 |  0 | 1 |  2 |   Yes   |     0     |    30     |
|  6   |  1 |  2 | 1 |  2 |   Yes   |     0     |    30     |
|  7   |  0 |  1 | 1 |  2 |   Yes   |     0     |    30     |
|  8   |  4 |  0 | 1 |  2 |   Yes   |     0     |    30     |
|  9   |  4 |  1 | 1 |  2 |   Yes   |     0     |    30     |
| 10   |  3 |  0 | 1 |  2 |   Yes   |     0     |    30     |
| 11   |  2 |  3 | 1 |  2 |   Yes   |     0     |    30     |

**Totals across 12 seeds:** `demoted=12/12`, `Σ corrupted=0`, `Σ truncated=360`.

In every run, L1's log at the end of the experiment is byte-identical to
L2's log (100 entries, indices 1..50 from L1's term T, indices 51..100 from
L2's term T'), and L1's `commit_index` reaches 100 — full convergence
every time.

## Why each metric is what it is

### 1. L1 demoted to Follower on reconnection (12/12)

While L1 is isolated, it stays in `Leader` state at term T (it never sees
a higher-term message). On restore, the very next tick causes L1 to send
an `AppendEntries` RPC at term T. Every other node is at term T' > T, so
their reply carries term T'. L1's `handle_append_entries_resp` sees a
higher term and immediately calls `_reset_to_follower(T')`. Concretely,
in every one of the 12 runs:

```
l1_state_before = 'Leader'   l1_term_before = 1
l1_state_after  = 'Follower' l1_term_after  = 2
```

This is the §5.1 term-rule: any server with a smaller term than a
message it just received must step down.

### 2. 0 committed entries corrupted

After reconnection, the new leader L2 heartbeats L1 with `AppendEntries`.
L1 accepts (it is now a Follower) and the consistency check on
`prev_log_index=50, prev_log_term=T` succeeds: L1's log[50] has term T
because the original 50 entries were committed by majority in term T and
L1 never overwrote them. L1 then appends the 50 new entries from L2
(term T') at indices 51..100. L1's log at the end is bit-identical to
L2's. **Zero** of the 100 committed entries disagree across all 12 runs.

This is the runtime expression of **Leader Completeness** (paper §5.4,
Figure 3): a leader for term T' can only be elected if it has all
entries committed in any earlier term, so its `AppendEntries` can never
truncate a committed entry.

### 3. 30 stale uncommitted entries truncated per run (30×12 = 360)

While L1 was isolated we fed it 30 extra client commands. As the
isolated leader it appended them to its log but could not replicate
them to any peer, so they remained uncommitted. After reconnection,
L1 is a Follower and receives L2's `AppendEntries` for indices
51..100. L1's log at index 51 has a stale entry with term T (the one
L1 appended in isolation), but L2's entry at the same position has
term T'. The simulator's `handle_append_entries` therefore hits the
"if term at idx differs, truncate and replace" branch: it deletes
self.log[51:] and appends L2's entries. The 30 stale entries that
L1 had accumulated during isolation are discarded, and the slot is
filled with L2's entries. Per-seed this is exactly 30, so the total
across 12 runs is 360.

## Conclusion

Across 12 seeded replications of the standard "old leader, new term,
partition-heal" scenario on a 5-node cluster, the Raft term-safety
guarantees hold exactly as the paper predicts:

1. **L1 is *always* demoted to Follower at term T' > T** the moment it
   hears from the new-term majority — `demoted = True` in 12/12 runs.
2. **No committed entry is ever corrupted.** L1's post-restore log
   matches L2's log at every committed index; the 100 already-committed
   entries (50 from T, 50 from T') survive intact — `Σ corrupted = 0`.
3. **L1's stale uncommitted entries are truncated** to align with L2's
   log via the standard `prevLogIndex` consistency check — `Σ truncated
   = 360` (30 per run, exactly the number of uncommitted entries L1
   accumulated while partitioned).

In short: a leader with a stale term cannot overwrite a committed entry
in Raft; the moment it rejoins the majority it is forced down, and its
log is reconciled to the new leader's. The runtime evidence matches
**Leader Completeness** in §5.4 of the paper. The full experiment
finished in well under 30 minutes on a CPU-only run.
