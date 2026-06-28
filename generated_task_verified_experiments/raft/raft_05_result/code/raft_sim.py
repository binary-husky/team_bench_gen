#!/usr/bin/env python3
"""
In-process Raft simulator (CPU-only, no network/socket/Docker).

Verifies term-safety / Leader Completeness at runtime:
  - An old-term (deposed) leader L1 cannot overwrite entries committed by
    the new-term leader L2.
  - L1 is forced to step down to follower when it sees the higher term.
  - L1's stale uncommitted entries (appended while partitioned) are truncated
    to reconcile with L2's log.

Design: memory message queues, logical tick clock, deterministic per-seed RNG,
partition = drop messages between the isolated node and the rest.
"""

import random

N_NODES = 5
HEARTBEAT_INTERVAL = 3
ELECTION_TIMEOUT_MIN = 20
ELECTION_TIMEOUT_MAX = 45


class Entry:
    __slots__ = ("term", "cmd", "index")

    def __init__(self, term, cmd, index):
        self.term = term
        self.cmd = cmd
        self.index = index


def majority(n):
    return n // 2 + 1


class Node:
    def __init__(self, nid):
        self.id = nid
        self.currentTerm = 0
        self.votedFor = None
        self.log = [None]  # 1-indexed; log[0] sentinel
        self.commitIndex = 0
        self.lastApplied = 0
        self.state = "follower"  # follower | candidate | leader
        self.leader_id = None
        self.votesReceived = set()
        self.nextIndex = {}
        self.matchIndex = {}
        self.election_timer = 0
        self.heartbeat_timer = 0

    # --- log helpers ---
    def lastLogIndex(self):
        return len(self.log) - 1

    def lastLogTerm(self):
        return self.log[-1].term if len(self.log) > 1 else 0

    def term_at(self, idx):
        if 1 <= idx < len(self.log):
            return self.log[idx].term
        return 0

    def reset_election_timer(self, rng):
        self.election_timer = rng.randint(ELECTION_TIMEOUT_MIN, ELECTION_TIMEOUT_MAX)

    # --- state transitions ---
    def step_down(self, term):
        self.currentTerm = term
        self.votedFor = None
        self.state = "follower"
        self.leader_id = None

    def become_leader(self, sim):
        self.state = "leader"
        self.leader_id = self.id
        last = self.lastLogIndex()
        for p in range(N_NODES):
            if p == self.id:
                continue
            self.nextIndex[p] = last + 1
            self.matchIndex[p] = 0
        # immediate heartbeat
        self.broadcast_append(sim)

    # --- message senders ---
    def start_election(self, sim):
        self.state = "candidate"
        self.currentTerm += 1
        self.votedFor = self.id
        self.votesReceived = {self.id}
        for p in range(N_NODES):
            if p == self.id:
                continue
            sim.send({
                "type": "RequestVote",
                "src": self.id, "dst": p,
                "term": self.currentTerm,
                "candidateId": self.id,
                "lastLogIndex": self.lastLogIndex(),
                "lastLogTerm": self.lastLogTerm(),
            })

    def broadcast_append(self, sim):
        for p in range(N_NODES):
            if p == self.id:
                continue
            self.send_append_to(p, sim)

    def send_append_to(self, p, sim):
        if self.state != "leader":
            return
        ni = self.nextIndex.get(p, 1)
        prev = ni - 1
        entries = [Entry(e.term, e.cmd, e.index) for e in self.log[ni:]]
        sim.send({
            "type": "AppendEntries",
            "src": self.id, "dst": p,
            "term": self.currentTerm,
            "leaderId": self.id,
            "prevLogIndex": prev,
            "prevLogTerm": self.term_at(prev),
            "entries": entries,
            "leaderCommit": self.commitIndex,
        })

    # --- RPC handlers ---
    def handle(self, m, sim):
        t = m["type"]
        if t == "RequestVote":
            self.on_request_vote(m, sim)
        elif t == "RequestVoteReply":
            self.on_request_vote_reply(m, sim)
        elif t == "AppendEntries":
            self.on_append_entries(m, sim)
        elif t == "AppendEntriesReply":
            self.on_append_entries_reply(m, sim)

    def on_request_vote(self, m, sim):
        if m["term"] < self.currentTerm:
            sim.send({"type": "RequestVoteReply", "src": self.id, "dst": m["src"],
                      "term": self.currentTerm, "grant": False})
            return
        if m["term"] > self.currentTerm:
            self.step_down(m["term"])
        # up-to-date check
        my_last_term = self.lastLogTerm()
        up_to_date = (m["lastLogTerm"] > my_last_term) or (
            m["lastLogTerm"] == my_last_term and m["lastLogIndex"] >= self.lastLogIndex())
        grant = False
        if (self.votedFor is None or self.votedFor == m["candidateId"]) and up_to_date:
            self.votedFor = m["candidateId"]
            self.reset_election_timer(sim.rng)
            grant = True
        sim.send({"type": "RequestVoteReply", "src": self.id, "dst": m["src"],
                  "term": self.currentTerm, "grant": grant})

    def on_request_vote_reply(self, m, sim):
        if self.state != "candidate":
            return
        if m["term"] > self.currentTerm:
            self.step_down(m["term"])
            return
        if m["term"] != self.currentTerm or not m["grant"]:
            return
        self.votesReceived.add(m["src"])
        if len(self.votesReceived) >= majority(N_NODES):
            self.become_leader(sim)

    def on_append_entries(self, m, sim):
        if m["term"] < self.currentTerm:
            sim.send({"type": "AppendEntriesReply", "src": self.id, "dst": m["src"],
                      "term": self.currentTerm, "success": False, "matchIndex": 0})
            return
        if m["term"] > self.currentTerm:
            self.step_down(m["term"])
        # recognize leader, reset timer
        self.state = "follower"
        self.leader_id = m["leaderId"]
        self.reset_election_timer(sim.rng)

        # consistency check
        if m["prevLogIndex"] > self.lastLogIndex():
            sim.send({"type": "AppendEntriesReply", "src": self.id, "dst": m["src"],
                      "term": self.currentTerm, "success": False,
                      "conflictIndex": self.lastLogIndex() + 1, "matchIndex": 0})
            return
        if self.term_at(m["prevLogIndex"]) != m["prevLogTerm"]:
            ct = self.term_at(m["prevLogIndex"])
            i = m["prevLogIndex"]
            while i > 1 and self.term_at(i - 1) == ct:
                i -= 1
            sim.send({"type": "AppendEntriesReply", "src": self.id, "dst": m["src"],
                      "term": self.currentTerm, "success": False,
                      "conflictIndex": i, "matchIndex": 0})
            return

        # append / reconcile
        new_last = m["prevLogIndex"]
        for e in m["entries"]:
            if e.index < len(self.log):
                if self.log[e.index].term != e.term:
                    # truncate from here, append new
                    self.log = self.log[:e.index]
                    self.log.append(e)
                    if self.commitIndex >= e.index:
                        self.commitIndex = e.index - 1
                # else identical, keep
            else:
                self.log.append(e)
            new_last = e.index

        if m["leaderCommit"] > self.commitIndex:
            self.commitIndex = min(m["leaderCommit"], self.lastLogIndex())

        sim.send({"type": "AppendEntriesReply", "src": self.id, "dst": m["src"],
                  "term": self.currentTerm, "success": True, "matchIndex": new_last})

    def on_append_entries_reply(self, m, sim):
        if m["term"] > self.currentTerm:
            self.step_down(m["term"])
            return
        if self.state != "leader" or m["term"] != self.currentTerm:
            return
        if m["success"]:
            self.matchIndex[m["src"]] = m["matchIndex"]
            self.nextIndex[m["src"]] = m["matchIndex"] + 1
            self.advance_commit()
        else:
            ni = self.nextIndex.get(m["src"], 1)
            if "conflictIndex" in m and m["conflictIndex"] is not None:
                ni = min(ni, m["conflictIndex"])
            else:
                ni = max(1, ni - 1)
            self.nextIndex[m["src"]] = ni
            self.send_append_to(m["src"], sim)

    def advance_commit(self):
        for idx in range(self.lastLogIndex(), self.commitIndex, -1):
            if self.log[idx].term != self.currentTerm:
                continue
            count = 1
            for p in range(N_NODES):
                if p == self.id:
                    continue
                if self.matchIndex.get(p, 0) >= idx:
                    count += 1
            if count >= majority(N_NODES):
                self.commitIndex = idx
                break

    # --- client submit (only call on a leader) ---
    def submit(self, cmd, sim):
        idx = self.lastLogIndex() + 1
        self.log.append(Entry(self.currentTerm, cmd, idx))
        self.broadcast_append(sim)

    # --- tick ---
    def tick(self, sim):
        if self.state == "leader":
            self.heartbeat_timer -= 1
            if self.heartbeat_timer <= 0:
                self.broadcast_append(sim)
                self.heartbeat_timer = HEARTBEAT_INTERVAL
        else:
            self.election_timer -= 1
            if self.election_timer <= 0:
                self.reset_election_timer(sim.rng)
                self.start_election(sim)


class Sim:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.nodes = {i: Node(i) for i in range(N_NODES)}
        self.pending = []   # messages generated this tick, routed next tick
        self.inbox = {i: [] for i in range(N_NODES)}
        self.isolated = set()
        self.clock = 0
        for n in self.nodes.values():
            n.reset_election_timer(self.rng)
            n.heartbeat_timer = HEARTBEAT_INTERVAL

    def send(self, m):
        self.pending.append(m)

    def route(self):
        # move pending into inboxes respecting partition
        for m in self.pending:
            src, dst = m["src"], m["dst"]
            if (src in self.isolated) ^ (dst in self.isolated):
                continue  # partitioned: drop
            self.inbox[dst].append(m)
        self.pending = []

    def step(self):
        self.clock += 1
        self.route()
        for i in range(N_NODES):
            ib = self.inbox[i]
            node = self.nodes[i]
            while ib:
                node.handle(ib.pop(0), self)
        for i in range(N_NODES):
            self.nodes[i].tick(self)

    def run_for(self, ticks):
        for _ in range(ticks):
            self.step()

    def leader(self):
        for n in self.nodes.values():
            if n.state == "leader":
                return n
        return None

    def leader_among(self, ids):
        for i in ids:
            if self.nodes[i].state == "leader":
                return self.nodes[i]
        return None


def run_until_leader(sim, among=None, max_ticks=400):
    for _ in range(max_ticks):
        sim.step()
        if among is None:
            ld = sim.leader()
        else:
            ld = sim.leader_among(among)
        if ld is not None:
            return ld
    return None


def run_until_committed(sim, target_commit, node_ids, max_ticks=600):
    for _ in range(max_ticks):
        sim.step()
        if all(sim.nodes[i].commitIndex >= target_commit for i in node_ids):
            return True
    return False


def run_experiment(seed):
    sim = Sim(seed)

    # Phase 1: elect L1, commit 50 entries
    L1 = run_until_leader(sim)
    if L1 is None:
        raise RuntimeError(f"seed {seed}: no L1 elected")
    T = L1.currentTerm
    L1_cmds = []
    for _ in range(50):
        cmd = sim.rng.randint(1, 1_000_000)
        L1_cmds.append(cmd)
        L1.submit(cmd, sim)
    # ensure ALL nodes replicate+commit (cleaner for next phase)
    ok = run_until_committed(sim, 50, list(range(N_NODES)), max_ticks=600)
    if not ok:
        raise RuntimeError(f"seed {seed}: L1 entries not committed on all")

    # record canonical committed entries from L1 (indices 1..50)
    canonical_old = {i: (sim.nodes[L1.id].log[i].term, sim.nodes[L1.id].log[i].cmd)
                     for i in range(1, 51)}

    # Phase 2: isolate L1
    # tiny seed-driven delay for partition timing
    delay = sim.rng.randint(0, 5)
    sim.run_for(delay)
    sim.isolated = {L1.id}

    # L1 appends stale uncommitted entries during isolation (can't commit)
    n_stale = sim.rng.randint(3, 8)
    stale_cmds = []
    for _ in range(n_stale):
        cmd = sim.rng.randint(1, 1_000_000)
        stale_cmds.append(cmd)
        L1.submit(cmd, sim)  # appended at term T, won't replicate (partitioned)
    sim.run_for(10)  # let L1 try (drops)

    # record L1's stale entry indices = 51 .. 50+n_stale, all term T
    stale_indices = list(range(51, 51 + n_stale))

    # Phase 3: remaining 4 elect L2 (term T' > T), commit 50 NEW entries
    others = [i for i in range(N_NODES) if i != L1.id]
    L2 = run_until_leader(sim, among=others, max_ticks=400)
    if L2 is None:
        raise RuntimeError(f"seed {seed}: no L2 elected among {others}")
    T2 = L2.currentTerm
    if not (T2 > T):
        raise RuntimeError(f"seed {seed}: T2={T2} not > T={T}")
    L2_cmds = []
    for _ in range(50):
        cmd = sim.rng.randint(1, 1_000_000)
        L2_cmds.append(cmd)
        L2.submit(cmd, sim)
    # commit on majority of the (non-isolated) cluster -> global commit valid
    ok = run_until_committed(sim, 100, others, max_ticks=800)
    if not ok:
        raise RuntimeError(f"seed {seed}: L2 entries not committed")

    # canonical NEW committed entries (indices 51..100), term T2
    canonical_new = {i: (sim.nodes[L2.id].log[i].term, sim.nodes[L2.id].log[i].cmd)
                     for i in range(51, 101)}

    # confirm L1 still leader at term T while isolated (stale, uncommitted)
    L1_was_leader_T = (L1.state == "leader" and L1.currentTerm == T)
    # L1 stale entries still present & uncommitted before restore
    stale_present_before = all(
        L1.term_at(i) == T and L1.log[i].cmd == stale_cmds[i - 51]
        for i in stale_indices)

    # Phase 4: restore L1's connection. L1 still term-T leader tries AppendEntries.
    sim.isolated = set()
    sim.run_for(800)  # plenty for stepdown + reconciliation

    # --- Metrics ---
    # (a) L1 stepped down to follower at the higher term
    stepped_down = (L1.state != "leader") and (L1.currentTerm >= T2)

    # (b) committed-entry integrity: L2's committed NEW entries (51..100, term T2)
    #     overwritten/corrupted by L1's old term-T AppendEntries?
    #     Count deviations across all nodes.
    broken_new = 0
    for nid in range(N_NODES):
        nd = sim.nodes[nid]
        for i in range(51, 101):
            if i >= len(nd.log):
                broken_new += 1
                continue
            exp_t, exp_c = canonical_new[i]
            if nd.log[i].term != exp_t or nd.log[i].cmd != exp_c:
                broken_new += 1

    # also confirm old committed entries (1..50, term T) intact
    broken_old = 0
    for nid in range(N_NODES):
        nd = sim.nodes[nid]
        for i in range(1, 51):
            if i >= len(nd.log):
                broken_old += 1
                continue
            exp_t, exp_c = canonical_old[i]
            if nd.log[i].term != exp_t or nd.log[i].cmd != exp_c:
                broken_old += 1

    # (c) L1's stale uncommitted entries truncated to match L2's log
    #     Each stale index should now hold a term-T2 entry (overwritten), not term T.
    truncated = 0
    for i in stale_indices:
        if i >= len(L1.log):
            truncated += 1  # removed entirely
        else:
            if L1.log[i].term != T:  # no longer the stale term-T entry
                truncated += 1

    # L1 should have fully reconciled to L2's committed log
    L1_reconciled = (L1.lastLogIndex() >= 100 and L1.commitIndex >= 100)

    return {
        "seed": seed,
        "T": T,
        "T2": T2,
        "n_stale": n_stale,
        "L1_was_leader_T_isolated": L1_was_leader_T,
        "stale_present_before": stale_present_before,
        "stepped_down": stepped_down,
        "broken_new_committed": broken_new,
        "broken_old_committed": broken_old,
        "truncated_stale": truncated,
        "L1_reconciled": L1_reconciled,
    }


def main():
    seeds = list(range(1, 13))  # 12 seeds (>= 10)
    results = []
    for s in seeds:
        r = run_experiment(s)
        results.append(r)
        print(f"seed={r['seed']:2d} T={r['T']} T2={r['T2']} "
              f"stale={r['n_stale']} stepdown={r['stepped_down']} "
              f"broken_new={r['broken_new_committed']} broken_old={r['broken_old_committed']} "
              f"trunc={r['truncated_stale']} reconciled={r['L1_reconciled']}")

    # summary checks
    all_stepdown = all(r["stepped_down"] for r in results)
    all_zero_broken = all(r["broken_new_committed"] == 0 for r in results)
    all_truncated = all(r["truncated_stale"] == r["n_stale"] for r in results)
    all_reconciled = all(r["L1_reconciled"] for r in results)
    print("\n--- SUMMARY ---")
    print(f"all L1 stepped down:        {all_stepdown}")
    print(f"all broken_new == 0:        {all_zero_broken}")
    print(f"all stale truncated==stale: {all_truncated}")
    print(f"all L1 reconciled to 100:   {all_reconciled}")

    return results


if __name__ == "__main__":
    main()
