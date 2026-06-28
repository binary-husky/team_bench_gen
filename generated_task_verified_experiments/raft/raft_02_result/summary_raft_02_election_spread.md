# Election-Timeout Spread vs. Time-to-Elect & Split-Vote Rate

## What was built

A from-scratch, **in-process Raft election simulator** in Python (`raft_sim.py`),
derived from the Raft paper (`raft_material/raft.pdf`). It is **tick-based,
deterministic, single-process** — no sockets, no threads, no Docker, no real
clocks. Messages are delivered through an in-memory FIFO queue with a fixed
1-tick latency; all timers are measured in logical ticks.

**State machine reproduced:** `Follower → Candidate → Leader` with the full
RequestVote election and empty-AppendEntries heartbeats. On election-timeout a
node increments its term, becomes Candidate, votes for itself, broadcasts
`RequestVote`, and **restarts its randomized election timeout** (paper §5). A
peer grants a vote when the candidate's term ≥ its own and it has not already
voted (logs are empty and identical, so the log-up-to-date check is trivially
satisfied — the experiment isolates the *timing* dynamic). A Candidate that
collects a strict majority (`N//2+1 = 3`) becomes Leader and emits a heartbeat
every `H` ticks, which resets followers' timers. A term in which ≥1 candidate
ran but no leader was elected is recorded as a **split-vote**.

## Fixed experimental setup (as specified)

| parameter | value |
|---|---|
| Cluster size `N` | 5 |
| `T_min` (election-timeout floor) | 15 ticks |
| Heartbeat interval `H = T_min/3` | 5 ticks |
| Spread grid `spread = T_max − T_min` | `{0, 1·H, 5·H, 10·H, 20·H}` = `{0, 5, 25, 50, 100}` |
| Repetitions per spread | 60 distinct seeds (seeds `1000..1059`) |
| Per-run cap | 6000 ticks (only the `spread=0` deadlock ever reaches it) |
| Message latency | 1 tick |

All nodes start as Followers, `term=0`, no leader (cold start). Each run is a
fresh, independent cold-start election; the RNG seed alone determines the
outcome.

## Results — table

| spread (ticks) | spread / H | T_max | median time-to-elect (ticks) | mean ± max | split-vote rate | # seeds electing a leader |
|---:|---:|---:|---:|---:|---:|---:|
| 0   | 0·H | 15  | **— (never)** | — (deadlock) | **1.000** | 0 / 60 |
| 5   | 1·H | 20  | 17 | 17.7 / 32 | 0.017 | 60 / 60 |
| 25  | 5·H | 40  | 19 | 20.7 / 31 | 0.000 | 60 / 60 |
| 50  | 10·H| 65  | 22 | 24.9 / 45 | 0.000 | 60 / 60 |
| 100 | 20·H| 115 | 28 | 32.4 / 68 | 0.000 | 60 / 60 |

> "— (never)" = no leader is ever elected: the run hits the 6000-tick cap
> (≈400 election terms attempted, all deadlocked) because every node fires in
> perfect lockstep.

### Split-vote rate vs. spread (ASCII)

```
1.00 |####                                   spread=0   : 1.000 (perpetual deadlock)
0.80 |
0.60 |
0.40 |
0.20 |
0.05 |   #                                   spread=1·H : 0.017 (1/60)
0.00 |      ##########################       spread≥5·H : 0.000
     +--+--+--+--+--+--
       0  1H 5H 10H 20H        (spread)
```

### Median time-to-elect vs. spread (ASCII)

```
ticks
 30 |                               *
 25 |                          *
 20 |                    *
 17 |           *
 15 | (deadlock)                             <- T_min = 15 floor
  0 +--+--+--+--+--+--
       0  1H 5H 10H 20H        (spread)
          T_max:  20 40 65 115
```

## Conclusion

1. **`spread = 0` ⇒ split-vote rate ≈ 1.** With identical timeouts every node
   fires at the *same* tick, every node votes for itself in the same term, no
   one ever reaches a strict majority, and — because the timeouts stay identical
   on every reset — the nodes re-fire in lockstep on the next cycle too. The
   election is a **perpetual split-vote deadlock**: across all 60 seeds, zero
   leaders were elected (split rate = 1.000). This is exactly the failure mode
   the paper warns about and the reason Raft mandates *randomized* timeouts.

2. **Split-vote rate collapses as soon as any spread is introduced.** A single
   heartbeat's worth of spread (`spread = 1·H = 5`) already breaks the symmetry
   enough that 59/60 seeds elect a leader on the first term (split rate 0.017);
   by `spread = 5·H` the rate is **0.000** and stays at 0 for all larger
   spreads. The decay is steep and monotonic, confirming that the split-vote
   hazard is concentrated entirely in the "near-zero spread" regime.

3. **Time-to-elect grows slowly and stays far below `T_max`.** The leader is
   whoever's timer fires *first*, so time-to-elect tracks the **minimum of 5
   uniform samples** from `[T_min, T_max]`, plus a ~2–3 tick election round-trip
   (candidate → RequestVote → vote → heartbeat). Measured medians (17, 19, 22,
   28 ticks) line up with the theoretical minimum-of-5 median
   `T_min + spread·(1 − 0.5^(1/5)) ≈ {15.6, 18.2, 21.5, 27.9}` plus overhead.
   Even at `spread = 20·H` (`T_max = 115`), election completes in **~28 ticks** —
   an order of magnitude below `T_max`. So increasing spread buys a *huge* drop
   in split-vote risk for only a *sublinear* (≈spread/6) cost in election speed:
   the design sweet spot is a few heartbeats of spread, where split rate is ~0
   and time-to-elect is still essentially `~T_min`.

**Net:** randomized election-timeout spread is the lever that trades a
near-certain split-vote deadlock (spread = 0) for fast, reliable leader
election. A spread of a handful of heartbeats is sufficient to drive the
split-vote rate to ~0 while keeping time-to-elect on the order of `T_min`,
well below `T_max`.
