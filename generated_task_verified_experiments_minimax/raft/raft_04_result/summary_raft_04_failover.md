# Raft Failover Experiment (Raft_04)

**Goal.** Verify that an in‑process Raft cluster of N = 5 tolerates a mid‑stream
leader crash: a new leader is elected within a bounded time, post‑crash client
commands continue to be committed, and every entry that was committed *before*
the crash survives the leader change (no loss).

**Setup (fixed).**

| Item | Value |
| --- | --- |
| Cluster size `N` | 5 |
| Election‑timeout range | `[20, 40]` logical ticks (spread chosen to avoid split votes) |
| Pre‑crash client commands | 100 |
| Crash | "Kill" the current leader after the 100 pre‑crash commands are committed on a majority (and the leader's own log carries them). Killed node stops heart‑beating, drops incoming/outgoing traffic; the remaining 4 nodes keep running. |
| Post‑crash client commands | 100 (submitted immediately after the kill) |
| Number of runs | 10 different deterministic seeds (`seed = 0 … 9`); per seed, randomness decides server timeouts and the order in which servers start their elections |
| Time clock | Logical tick (in‑memory). Each tick every alive server advances its election/heartbeat counters and, if a leader, sends one round of `AppendEntries`. Messages are delivered in the same tick they are sent. |
| Network | None — pure in‑process inboxes; delivery is reliable within a tick. |

**Simulator.** `raft_sim.py` (≈530 lines) — each `Server` is a state machine
implementing the Raft roles (Follower / Candidate / Leader), RPCs
(`RequestVote`, `AppendEntries`, plus their responses), term/step‑down, log
matching with conflict truncation, leader commit advancement, and randomized
election timeouts. The `Cluster` drives the tick and shuffles in‑memory
message queues. Killing a server simply flips `alive = False`, clears its
in/out queues, and excludes it from all subsequent rounds.

---

## 1. Metrics

Let `kill_tick` be the logical tick at which the leader is killed, and
`new_leader_tick` the first tick at which a *different* server is observed in
the `LEADER` state. Then:

* **Detection + re‑election latency** = `new_leader_tick − kill_tick`
  (logical ticks).
* **Post‑crash commit rate** = (number of post‑crash commands whose command
  value appears in the new leader's committed log prefix) / 100.
* **Pre‑fault survival** = "True" iff every pre‑crash committed command
  (commands 0 … 99) is still present in the new leader's committed log
  prefix (i.e. no committed entry was lost across the leader change).

### 1.1 Per‑seed table

| Seed | Killed leader | New leader | kill_tick | new_leader_tick | Latency (ticks) | Post‑commit rate | Pre‑fault survived |
| ---: | :---: | :---: | ---: | ---: | ---: | ---: | :---: |
| 0 | 0 | 4 | 123 | 145 | 22 | 1.00 | ✅ |
| 1 | 0 | 1 | 128 | 155 | 27 | 1.00 | ✅ |
| 2 | 3 | 4 | 127 | 152 | 25 | 1.00 | ✅ |
| 3 | 1 | 4 | 130 | 158 | 28 | 1.00 | ✅ |
| 4 | 1 | 3 | 127 | 157 | 30 | 1.00 | ✅ |
| 5 | 1 | 4 | 127 | 152 | 25 | 1.00 | ✅ |
| 6 | 1 | 2 | 124 | 149 | 25 | 1.00 | ✅ |
| 7 | 3 | 0 | 130 | 153 | 23 | 1.00 | ✅ |
| 8 | 1 | 4 | 126 | 151 | 25 | 1.00 | ✅ |
| 9 | 4 | 3 | 126 | 150 | 24 | 1.00 | ✅ |

Raw numbers are in `results_raft_04_failover.json`.

### 1.2 Aggregates across 10 seeds

| Metric | Min | Median | Mean | Max | Stdev |
| --- | ---: | ---: | ---: | ---: | ---: |
| Detection + re‑election latency (ticks) | 22 | 25.0 | **25.4** | 30 | 2.37 |
| Post‑crash commit rate (100 post commands) | 1.00 | 1.00 | **1.000** | 1.00 | 0.00 |
| Pre‑fault committed entries surviving | 100% | 100% | **100%** | 100% | 0% |

* Killed‑leader distribution: server 0 → 2, server 1 → 5, server 3 → 2, server 4 → 1 (server 2 was never leader pre‑kill under these 10 seeds; that is incidental — the harness kills whatever node happens to be leader at the moment).
* New‑leader distribution: server 0 → 1, 1 → 1, 2 → 1, 3 → 2, 4 → 5 — different from the killed distribution, confirming failover actually transferred leadership.

### 1.3 Latency distribution (ASCII)

```
22 ticks | ## (1)
23 ticks | # (1)
24 ticks | # (1)
25 ticks | ##### (5)
26 ticks | 
27 ticks | # (1)
28 ticks | # (1)
29 ticks | 
30 ticks | # (1)
```

### 1.4 Latency vs. election‑timeout range

The election timeout is uniformly drawn from `[20, 40]` ticks. A new leader
*must* wait for at least one follower to time out and propose, plus a majority
of votes to come back. The lower bound on the observed latency is therefore
≈ min election timeout (20) plus a few ticks of vote round‑trip; the upper
bound is ≈ 2 × max election timeout (≈ 80) if a split vote forces a retry.
All 10 observed latencies sit in the **22 – 30 tick** band — comfortably
within the expected `~one election timeout` and far below the worst case of
two full timeouts, which means no split‑vote retry happened in any run.

---

## 2. Conclusion

* **Bounded failover.** In all 10 seeds, a new leader is elected within
  **22 – 30 logical ticks** (mean 25.4, median 25, max 30) of the old leader
  being killed. This is on the order of one election timeout, exactly the
  bound predicted by Raft's randomized election design. No run required a
  second (split‑vote) round.
* **Continued commitment after failover.** All 100 post‑crash commands
  submitted to the cluster *after* the leader was killed were ultimately
  committed by the new leader — post‑crash commit rate is **1.000** (100%)
  in every seed.
* **No loss of pre‑fault committed entries.** In every seed, the new leader's
  committed log prefix contains all 100 commands that were committed before
  the crash. The pre‑fault committed‑entry survival rate is **100%** (10/10).
  Raft's leader completeness property (`§5.4.1` of the paper) holds in
  practice: every committed entry survives the leader change because the new
  leader must have an up‑to‑date log to be elected (its `lastLogTerm` /
  `lastLogIndex` is at least as recent as any follower's, and at least one
  follower with the committed entry votes for it), and `AppendEntries`
  conflict‑resolution then catches up any lagging replicas before they
  advance their own `commitIndex`.

Together these three results confirm that the in‑process Raft implementation
provides the expected **fault tolerance** for a single mid‑stream leader
crash in a 5‑node cluster: leadership is transferred within roughly one
election timeout, the cluster continues to commit new entries afterwards, and
no entry that was already committed is lost. End‑to‑end runtime of the whole
experiment (10 seeds × 200 entries) was under 30 s on CPU.
