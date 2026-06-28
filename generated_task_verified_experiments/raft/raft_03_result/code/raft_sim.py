#!/usr/bin/env python3
"""
In-process Raft simulator (Python, in-memory message queue, logical tick clock,
deterministic seed, no real network / socket / docker).

Reproduces AppendEntries log replication + commit (commitIndex advancement).

Goal: verify that an entry is committed once replicated on a strict majority of
nodes, and that commitIndex advances monotonically.

Model notes
-----------
- Logical "tick" clock. Each message is given a deliver_tick = send_tick + delay,
  where delay is drawn from a small seeded distribution {1..MAX_DELAY}. This is
  *not* loss (every message is eventually delivered); it just models realistic
  per-message network jitter so that the order-statistic difference between
  N=3 (need 1 follower ack) and N=5 (need 2 follower acks) is observable.
- All nodes are fully interconnected; no drops, no partitions, no crashes
  (failure scenarios are left to _04/_05).
- Raft rules implemented faithfully: randomized election timeout to pick a
  leader (avoids split-vote), AppendEntries with prevLogIndex/prevLogTerm
  consistency check + conflict truncation, leaderCommit propagation, and the
  leader commit rule: advance commitIndex to the largest N in the current term
  replicated on a strict majority.
"""

import random
import statistics
from collections import defaultdict

# --- tunable (fixed across runs) ---
HEARTBEAT_INTERVAL = 2          # ticks between leader heartbeats
ELECTION_TIMEOUT_LO = 20        # ticks
ELECTION_TIMEOUT_HI = 40        # ticks
MAX_DELAY = 3                   # per-message delivery delay drawn from {1..MAX_DELAY}
NUM_COMMANDS = 1000
SEEDS = [1, 2, 3, 4, 5]
MAX_TICKS = 200000


class Message:
    __slots__ = ("deliver_tick", "src", "dst", "mtype", "payload")

    def __init__(self, deliver_tick, src, dst, mtype, payload):
        self.deliver_tick = deliver_tick
        self.src = src
        self.dst = dst
        self.mtype = mtype
        self.payload = payload


class Node:
    def __init__(self, nid, n):
        self.id = nid
        self.n = n
        self.majority = n // 2 + 1
        self.term = 0
        self.voted_for = None
        self.log = [(0, None)]          # index 0 = dummy sentinel (term 0)
        self.commit_index = 0
        self.last_applied = 0
        self.state = "follower"
        # leader-only
        self.next_index = {}
        self.match_index = {}
        # election timer
        self.election_timeout = 0
        self.election_elapsed = 0
        self.inbox = []

    # --- log helpers (1-indexed; log[0] is sentinel) ---
    def last_log_index(self):
        return len(self.log) - 1

    def last_log_term(self):
        return self.log[-1][0]

    def log_term_at(self, idx):
        if 0 <= idx < len(self.log):
            return self.log[idx][0]
        return -1

    def reset_election_timer(self, rng):
        self.election_timeout = rng.randint(ELECTION_TIMEOUT_LO, ELECTION_TIMEOUT_HI)
        self.election_elapsed = 0


class Sim:
    def __init__(self, n, seed):
        self.n = n
        self.seed = seed
        self.rng = random.Random(seed)
        self.nodes = [Node(i, n) for i in range(n)]
        self.tick = 0
        self.queue = []                     # list of Message (deliver_tick)
        self.leader_id = None
        # per-entry recording (index -> value)
        self.append_tick = {}               # index -> tick leader appended it
        self.commit_tick = {}               # index -> tick commitIndex first covered it
        self.rep_at_commit = {}             # index -> #nodes holding entry at commit time
        self.commit_index_history = []      # (tick, commit_index) each time it changes
        self.monotonic_violations = 0
        # submission control
        self.commands_submitted = 0
        self.phase = "election"             # "election" | "submit" | "drain"

    # --- messaging ---
    def send(self, src, dst, mtype, payload):
        delay = self.rng.randint(1, MAX_DELAY)
        self.queue.append(Message(self.tick + delay, src, dst, mtype, payload))

    def deliver(self):
        if not self.queue:
            return
        keep = []
        for m in self.queue:
            if m.deliver_tick <= self.tick:
                self.nodes[m.dst].inbox.append(m)
            else:
                keep.append(m)
        self.queue = keep

    # --- election ---
    def start_election(self, node):
        node.state = "candidate"
        node.term += 1
        node.voted_for = node.id
        node.votes_received = {node.id}
        node.reset_election_timer(self.rng)
        last_idx = node.last_log_index()
        last_term = node.last_log_term()
        for peer in range(self.n):
            if peer == node.id:
                continue
            self.send(node.id, peer, "RequestVote",
                      {"term": node.term, "candidate": node.id,
                       "last_log_index": last_idx, "last_log_term": last_term})

    def handle_request_vote(self, node, m):
        p = m.payload
        term = p["term"]
        if term < node.term:
            self.send(node.id, m.src, "RequestVoteReply",
                      {"term": node.term, "granted": False})
            return
        if term > node.term:
            node.term = term
            node.voted_for = None
            node.state = "follower"
        # up-to-date check
        cand_last_idx = p["last_log_index"]
        cand_last_term = p["last_log_term"]
        my_last_term = node.last_log_term()
        my_last_idx = node.last_log_index()
        up_to_date = (cand_last_term > my_last_term or
                      (cand_last_term == my_last_term and cand_last_idx >= my_last_idx))
        granted = False
        if node.voted_for is None or node.voted_for == p["candidate"]:
            if up_to_date:
                node.voted_for = p["candidate"]
                granted = True
                node.reset_election_timer(self.rng)
        self.send(node.id, m.src, "RequestVoteReply",
                  {"term": node.term, "granted": granted})

    def handle_request_vote_reply(self, node, m):
        if node.state != "candidate":
            return
        p = m.payload
        if p["term"] > node.term:
            node.term = p["term"]
            node.state = "follower"
            node.voted_for = None
            return
        if p["granted"]:
            node.votes_received.add(m.src)
            if len(node.votes_received) >= node.majority:
                self.become_leader(node)

    def become_leader(self, node):
        node.state = "leader"
        self.leader_id = node.id
        last_idx = node.last_log_index()
        node.next_index = {i: last_idx + 1 for i in range(self.n) if i != node.id}
        node.match_index = {i: 0 for i in range(self.n) if i != node.id}
        # immediately send a heartbeat round
        self.send_append_entries(node, force_all=True)

    # --- append entries ---
    def send_append_entries(self, leader, force_all=False):
        last_idx = leader.last_log_index()
        for peer in range(self.n):
            if peer == leader.id:
                continue
            nxt = leader.next_index[peer]
            has_data = nxt <= last_idx
            if not has_data and not force_all:
                continue
            prev_idx = nxt - 1
            prev_term = leader.log_term_at(prev_idx)
            entries = leader.log[nxt:]               # list of (term, cmd)
            self.send(leader.id, peer, "AppendEntries",
                      {"term": leader.term, "leader": leader.id,
                       "prev_log_index": prev_idx, "prev_log_term": prev_term,
                       "entries": entries, "leader_commit": leader.commit_index})

    def handle_append_entries(self, node, m):
        p = m.payload
        term = p["term"]
        if term < node.term:
            self.send(node.id, m.src, "AppendEntriesReply",
                      {"term": node.term, "success": False, "match_index": node.last_log_index()})
            return
        if term > node.term:
            node.term = term
            node.voted_for = None
        node.state = "follower"
        node.reset_election_timer(self.rng)
        prev_idx = p["prev_log_index"]
        prev_term = p["prev_log_term"]
        # consistency check
        if prev_idx > 0:
            if prev_idx >= len(node.log) or node.log[prev_idx][0] != prev_term:
                # conflict: reply with our last index so leader backs up
                self.send(node.id, m.src, "AppendEntriesReply",
                          {"term": node.term, "success": False,
                           "match_index": node.last_log_index()})
                return
        # append / truncate
        conflict_start = prev_idx + 1
        for i, entry in enumerate(p["entries"]):
            idx = conflict_start + i
            if idx < len(node.log):
                if node.log[idx][0] != entry[0]:
                    # truncate from here
                    del node.log[idx:]
                    node.log.append(entry)
                # else identical, skip
            else:
                node.log.append(entry)
        new_last = node.last_log_index()
        # advance commit_index from leader_commit
        if p["leader_commit"] > node.commit_index:
            node.commit_index = min(p["leader_commit"], new_last)
        self.send(node.id, m.src, "AppendEntriesReply",
                  {"term": node.term, "success": True, "match_index": new_last})

    def handle_append_entries_reply(self, leader, m):
        p = m.payload
        peer = m.src
        if p["term"] > leader.term:
            leader.term = p["term"]
            leader.state = "follower"
            leader.voted_for = None
            return
        if not p["success"]:
            # back up next_index to match_index+1 (simplified conflict handling)
            leader.next_index[peer] = max(1, p["match_index"] + 1)
            return
        leader.match_index[peer] = max(leader.match_index[peer], p["match_index"])
        leader.next_index[peer] = p["match_index"] + 1
        self.maybe_advance_commit(leader)

    def maybe_advance_commit(self, leader):
        # find largest N in current term replicated on strict majority
        last_idx = leader.last_log_index()
        for n_idx in range(last_idx, leader.commit_index, -1):
            if leader.log[n_idx][0] != leader.term:
                continue
            # count nodes holding this index (leader counts)
            count = 1  # leader itself
            for peer in range(self.n):
                if peer == leader.id:
                    continue
                if leader.match_index.get(peer, 0) >= n_idx:
                    count += 1
            if count >= leader.majority:
                # commit everything up to n_idx
                old = leader.commit_index
                leader.commit_index = n_idx
                self.record_commit(leader, old, n_idx)
                break

    def record_commit(self, leader, old_ci, new_ci):
        # monotonic check
        if self.commit_index_history:
            _, prev_ci = self.commit_index_history[-1]
            if new_ci < prev_ci:
                self.monotonic_violations += 1
        self.commit_index_history.append((self.tick, leader.commit_index))
        # record per-entry commit times for newly committed indices
        for idx in range(old_ci + 1, new_ci + 1):
            if idx == 0:
                continue
            self.commit_tick[idx] = self.tick
            # replication count at commit time (leader + followers with match>=idx)
            cnt = 1
            for peer in range(self.n):
                if peer == leader.id:
                    continue
                if leader.match_index.get(peer, 0) >= idx:
                    cnt += 1
            self.rep_at_commit[idx] = cnt

    # --- client command ---
    def submit_command(self, cmd):
        leader = self.nodes[self.leader_id]
        idx = leader.last_log_index() + 1
        leader.log.append((leader.term, cmd))
        self.append_tick[idx] = self.tick
        self.commands_submitted += 1

    # --- per-tick node logic ---
    def node_tick(self, node):
        # process inbox
        for m in node.inbox:
            if m.mtype == "RequestVote":
                self.handle_request_vote(node, m)
            elif m.mtype == "RequestVoteReply":
                self.handle_request_vote_reply(node, m)
            elif m.mtype == "AppendEntries":
                self.handle_append_entries(node, m)
            elif m.mtype == "AppendEntriesReply":
                self.handle_append_entries_reply(node, m)
        node.inbox = []

        if node.state == "leader":
            # send AppendEntries for any new data; heartbeat periodically
            last_idx = node.last_log_index()
            need_send = any(node.next_index[p] <= last_idx for p in node.next_index)
            if self.tick % HEARTBEAT_INTERVAL == 0 or need_send:
                self.send_append_entries(node, force_all=(not need_send))
        else:
            node.election_elapsed += 1
            if node.election_elapsed >= node.election_timeout:
                self.start_election(node)

    # --- main loop ---
    def run(self):
        # phase 1: elect a leader
        max_elect = 1000
        while self.leader_id is None and self.tick < max_elect:
            self.tick += 1
            self.deliver()
            for node in self.nodes:
                self.node_tick(node)
        if self.leader_id is None:
            raise RuntimeError(f"no leader elected (N={self.n}, seed={self.seed})")

        # phase 2: stream NUM_COMMANDS commands, one per tick
        self.phase = "submit"
        while self.commands_submitted < NUM_COMMANDS and self.tick < MAX_TICKS:
            self.tick += 1
            self.deliver()
            self.submit_command(self.commands_submitted)
            for node in self.nodes:
                self.node_tick(node)

        # phase 3: drain until all committed
        self.phase = "drain"
        target = NUM_COMMANDS
        leader = self.nodes[self.leader_id]
        while leader.commit_index < target and self.tick < MAX_TICKS:
            self.tick += 1
            self.deliver()
            for node in self.nodes:
                self.node_tick(node)

        return self.collect()

    def collect(self):
        leader = self.nodes[self.leader_id]
        final_commit = leader.commit_index
        all_committed = final_commit >= NUM_COMMANDS
        latencies = []
        rep_counts = []
        strict_majority_at_commit = True
        maj = leader.majority
        for idx in range(1, NUM_COMMANDS + 1):
            if idx in self.commit_tick and idx in self.append_tick:
                lat = self.commit_tick[idx] - self.append_tick[idx]
                latencies.append(lat)
                rc = self.rep_at_commit.get(idx, 0)
                rep_counts.append(rc)
                if rc < maj:
                    strict_majority_at_commit = False
            # entries not committed are simply absent from latencies
        committed_count = len(latencies)
        return {
            "n": self.n,
            "seed": self.seed,
            "leader_id": self.leader_id,
            "leader_term": leader.term,
            "final_commit_index": final_commit,
            "committed_count": committed_count,
            "all_committed": all_committed,
            "commit_fraction": committed_count / NUM_COMMANDS,
            "lat_min": min(latencies) if latencies else None,
            "lat_mean": statistics.mean(latencies) if latencies else None,
            "lat_median": statistics.median(latencies) if latencies else None,
            "lat_max": max(latencies) if latencies else None,
            "lat_stdev": statistics.pstdev(latencies) if len(latencies) > 1 else 0.0,
            "rep_min": min(rep_counts) if rep_counts else None,
            "rep_mean": statistics.mean(rep_counts) if rep_counts else None,
            "rep_max": max(rep_counts) if rep_counts else None,
            "strict_majority_at_commit": strict_majority_at_commit,
            "monotonic_violations": self.monotonic_violations,
            "final_tick": self.tick,
        }


def run_group(n):
    results = []
    for seed in SEEDS:
        sim = Sim(n, seed)
        r = sim.run()
        results.append(r)
        print(f"  N={n} seed={seed}: leader=L{r['leader_id']} term={r['leader_term']} "
              f"committed={r['committed_count']}/{NUM_COMMANDS} "
              f"final_ci={r['final_commit_index']} "
              f"lat(mean/med/max)={r['lat_mean']:.2f}/{r['lat_median']}/{r['lat_max']} "
              f"rep(min/mean/max)={r['rep_min']}/{r['rep_mean']:.2f}/{r['rep_max']} "
              f"strict_maj={r['strict_majority_at_commit']} "
              f"mono_viol={r['monotonic_violations']} ticks={r['final_tick']}")
    return results


def agg(results):
    means = [r["lat_mean"] for r in results if r["lat_mean"] is not None]
    meds = [r["lat_median"] for r in results if r["lat_median"] is not None]
    maxs = [r["lat_max"] for r in results if r["lat_max"] is not None]
    fracs = [r["commit_fraction"] for r in results]
    monos = [r["monotonic_violations"] for r in results]
    strict = [r["strict_majority_at_commit"] for r in results]
    rep_means = [r["rep_mean"] for r in results if r["rep_mean"] is not None]
    rep_mins = [r["rep_min"] for r in results if r["rep_min"] is not None]
    return {
        "n": results[0]["n"],
        "seeds": len(results),
        "lat_mean_of_means": statistics.mean(means),
        "lat_mean_of_medians": statistics.mean(meds),
        "lat_mean_of_maxs": statistics.mean(maxs),
        "lat_max_overall": max(maxs),
        "commit_fraction_mean": statistics.mean(fracs),
        "commit_fraction_min": min(fracs),
        "any_monotonic_violation": any(v > 0 for v in monos),
        "all_strict_majority": all(strict),
        "rep_mean_of_means": statistics.mean(rep_means),
        "rep_min_overall": min(rep_mins),
    }


def main():
    print("=== Raft replication/commit simulator ===")
    print(f"NUM_COMMANDS={NUM_COMMANDS} SEEDS={SEEDS} "
          f"ELECTION_TIMEOUT=[{ELECTION_TIMEOUT_LO},{ELECTION_TIMEOUT_HI}] "
          f"HEARTBEAT={HEARTBEAT_INTERVAL} MAX_DELAY={MAX_DELAY}\n")
    all_results = {}
    aggs = {}
    for n in (3, 5):
        print(f"--- N={n} ---")
        res = run_group(n)
        all_results[n] = res
        a = agg(res)
        aggs[n] = a
        print(f"  AGG N={n}: lat(mean/med/max avg)={a['lat_mean_of_means']:.2f}/"
              f"{a['lat_mean_of_medians']:.2f}/{a['lat_mean_of_maxs']:.2f} "
              f"max_overall={a['lat_max_overall']} "
              f"commit_frac(min)={a['commit_fraction_min']} "
              f"mono_viol={a['any_monotonic_violation']} "
              f"all_strict_maj={a['all_strict_majority']} "
              f"rep_mean={a['rep_mean_of_means']:.2f} rep_min={a['rep_min_overall']}\n")

    # persist for the summary writer
    import json
    with open("results.json", "w") as f:
        json.dump({"per_run": {str(k): v for k, v in all_results.items()},
                   "agg": {str(k): v for k, v in aggs.items()}}, f, indent=2)
    print("wrote results.json")


if __name__ == "__main__":
    main()
