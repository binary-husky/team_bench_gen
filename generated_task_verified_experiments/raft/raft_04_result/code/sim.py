"""
In-process Raft simulator (deterministic, CPU-only, no network/socket/docker).
Implements leader election, log replication, and failover per the Raft paper
(Ongaro & Ousterhout, "In Search of an Understandable Consensus Algorithm",
extended version) found in ./raft_material/raft.pdf.

Logical tick clock; in-memory message queue; deterministic per-seed RNG.
"""

import random
import sys
import json


# ----------------------------- data structures ----------------------------- #

class Log:
    """1-indexed log. log[0] is a sentinel (index 0, term 0)."""
    def __init__(self):
        self.terms = [0]   # terms[i] = term of entry at index i (index 0 = sentinel)
        self.cmds = [None]

    def __len__(self):
        return len(self.terms) - 1   # number of real entries

    def last_index(self):
        return len(self.terms) - 1

    def last_term(self):
        return self.terms[-1]

    def term_at(self, idx):
        if idx < 0 or idx >= len(self.terms):
            return 0
        return self.terms[idx]

    def cmd_at(self, idx):
        return self.cmds[idx]

    def append(self, term, cmd):
        self.terms.append(term)
        self.cmds.append(cmd)
        return self.last_index()

    def truncate_after(self, idx):
        """Keep entries [0..idx], discard everything after idx."""
        self.terms = self.terms[:idx + 1]
        self.cmds = self.cmds[:idx + 1]


FOLLOWER = "follower"
CANDIDATE = "candidate"
LEADER = "leader"
DEAD = "dead"


class Node:
    def __init__(self, nid, n_nodes, rng):
        self.id = nid
        self.n = n_nodes
        self.rng = rng
        self.state = FOLLOWER
        self.current_term = 0
        self.voted_for = None
        self.log = Log()
        self.commit_index = 0
        self.last_applied = 0
        # leader-side
        self.next_index = {}
        self.match_index = {}
        # election timing
        self.election_elapsed = 0
        self.election_timeout = self._draw_timeout()
        # heartbeat
        self.heartbeat_elapsed = 0
        # votes gathered (candidate)
        self.votes_received = set()
        # became-leader-at tick (for instrumentation)
        self.became_leader_tick = None

    def _draw_timeout(self):
        return self.rng.randint(20, 40)

    @property
    def is_alive(self):
        return self.state != DEAD

    # ---- RPC senders produce message dicts ---- #

    def _send(self, queue, to, msg):
        msg["from"] = self.id
        msg["to"] = to
        queue.append(msg)

    # ---- node periodic tick (timers / heartbeats) ---- #
    def tick(self, tick, send_queue):
        if not self.is_alive:
            return
        if self.state == LEADER:
            self.heartbeat_elapsed += 1
            if self.heartbeat_elapsed >= HEARTBEAT_INTERVAL:
                self.heartbeat_elapsed = 0
                for peer in range(self.n):
                    if peer == self.id:
                        continue
                    self._send_append_entries(send_queue, peer)
        else:
            # follower or candidate: election timer
            self.election_elapsed += 1
            if self.election_elapsed >= self.election_timeout:
                self._start_election(send_queue)

    def _start_election(self, send_queue):
        self.state = CANDIDATE
        self.current_term += 1
        self.voted_for = self.id
        self.votes_received = {self.id}
        self.election_elapsed = 0
        self.election_timeout = self._draw_timeout()
        li = self.log.last_index()
        lt = self.log.last_term()
        for peer in range(self.n):
            if peer == self.id:
                continue
            self._send(send_queue, peer, {
                "type": "RequestVote",
                "term": self.current_term,
                "candidateId": self.id,
                "lastLogIndex": li,
                "lastLogTerm": lt,
            })

    def _send_append_entries(self, send_queue, peer):
        ni = self.next_index.get(peer, self.log.last_index() + 1)
        prev_index = ni - 1
        prev_term = self.log.term_at(prev_index)
        # batch entries from ni onward
        entries = []
        for i in range(ni, self.log.last_index() + 1):
            entries.append({"index": i, "term": self.log.term_at(i),
                            "cmd": self.log.cmd_at(i)})
        self._send(send_queue, peer, {
            "type": "AppendEntries",
            "term": self.current_term,
            "leaderId": self.id,
            "prevLogIndex": prev_index,
            "prevLogTerm": prev_term,
            "entries": entries,
            "leaderCommit": self.commit_index,
        })

    # ---- message handling ---- #
    def handle(self, msg, tick, send_queue):
        if not self.is_alive:
            return
        mtype = msg["type"]
        if mtype == "RequestVote":
            self._on_request_vote(msg, send_queue)
        elif mtype == "RequestVoteResponse":
            self._on_request_vote_response(msg, tick, send_queue)
        elif mtype == "AppendEntries":
            self._on_append_entries(msg, send_queue)
        elif mtype == "AppendEntriesResponse":
            self._on_append_entries_response(msg, send_queue)

    def _step_down(self, term):
        if term > self.current_term:
            self.current_term = term
            self.voted_for = None
            if self.state != DEAD:
                self.state = FOLLOWER

    def _on_request_vote(self, msg, send_queue):
        term = msg["term"]
        if term < self.current_term:
            self._send(send_queue, msg["from"], {
                "type": "RequestVoteResponse", "term": self.current_term,
                "voteGranted": False})
            return
        if term > self.current_term:
            self._step_down(term)
        # now term == current_term
        up_to_date = ((msg["lastLogTerm"] > self.log.last_term()) or
                      (msg["lastLogTerm"] == self.log.last_term() and
                       msg["lastLogIndex"] >= self.log.last_index()))
        grant = False
        if (self.voted_for is None or self.voted_for == msg["candidateId"]) and up_to_date:
            self.voted_for = msg["candidateId"]
            self.election_elapsed = 0
            self.election_timeout = self._draw_timeout()
            grant = True
        self._send(send_queue, msg["from"], {
            "type": "RequestVoteResponse", "term": self.current_term,
            "voteGranted": grant})

    def _on_request_vote_response(self, msg, tick, send_queue):
        if self.state != CANDIDATE:
            return
        if msg["term"] > self.current_term:
            self._step_down(msg["term"])
            return
        if msg["term"] != self.current_term:
            return
        if msg["voteGranted"]:
            self.votes_received.add(msg["from"])
            if len(self.votes_received) >= majority(self.n):
                self._become_leader(tick, send_queue)

    def _become_leader(self, tick, send_queue):
        self.state = LEADER
        self.became_leader_tick = tick
        last = self.log.last_index()
        for peer in range(self.n):
            if peer == self.id:
                continue
            self.next_index[peer] = last + 1
            self.match_index[peer] = 0
        self.heartbeat_elapsed = HEARTBEAT_INTERVAL  # send immediately
        # send initial empty heartbeats
        for peer in range(self.n):
            if peer == self.id:
                continue
            self._send_append_entries(send_queue, peer)

    def _on_append_entries(self, msg, send_queue):
        term = msg["term"]
        if term < self.current_term:
            self._send(send_queue, msg["from"], {
                "type": "AppendEntriesResponse", "term": self.current_term,
                "success": False, "matchIndex": self.log.last_index()})
            return
        if term > self.current_term:
            self._step_down(term)
        # term == current_term; this is a valid leader
        if self.state != DEAD:
            self.state = FOLLOWER
        self.election_elapsed = 0
        self.election_timeout = self._draw_timeout()

        prev_index = msg["prevLogIndex"]
        prev_term = msg["prevLogTerm"]
        # consistency check
        if self.log.term_at(prev_index) != prev_term:
            self._send(send_queue, msg["from"], {
                "type": "AppendEntriesResponse", "term": self.current_term,
                "success": False, "matchIndex": self.log.last_index()})
            return
        # append entries, deleting any conflicting suffix
        entries = msg["entries"]
        for e in entries:
            idx = e["index"]
            if self.log.term_at(idx) != 0:  # entry exists
                if self.log.term_at(idx) != e["term"]:
                    # conflict: truncate from idx onward
                    self.log.truncate_after(idx - 1)
                    self.log.append(e["term"], e["cmd"])
                # else identical, skip
            else:
                self.log.append(e["term"], e["cmd"])
        # advance commit
        if msg["leaderCommit"] > self.commit_index:
            new_commit = min(msg["leaderCommit"], self.log.last_index())
            if new_commit > self.commit_index:
                self.commit_index = new_commit
        self._send(send_queue, msg["from"], {
            "type": "AppendEntriesResponse", "term": self.current_term,
            "success": True, "matchIndex": self.log.last_index()})

    def _on_append_entries_response(self, msg, send_queue):
        if self.state != LEADER:
            return
        if msg["term"] > self.current_term:
            self._step_down(msg["term"])
            return
        if msg["term"] != self.current_term:
            return
        peer = msg["from"]
        if msg["success"]:
            self.match_index[peer] = max(self.match_index.get(peer, 0),
                                         msg["matchIndex"])
            self.next_index[peer] = self.match_index[peer] + 1
        else:
            # decrement nextIndex and retry next heartbeat
            self.next_index[peer] = max(1, self.next_index.get(peer, 1) - 1)
        self._update_commit_index()

    def _update_commit_index(self):
        # find largest N in (commit_index, last_index] s.t. majority
        # matchIndex >= N and log[N].term == current_term
        for n in range(self.log.last_index(), self.commit_index, -1):
            if self.log.term_at(n) != self.current_term:
                continue
            count = 1  # self
            for peer in range(self.n):
                if peer == self.id:
                    continue
                if self.match_index.get(peer, 0) >= n:
                    count += 1
            if count >= majority(self.n):
                self.commit_index = n
                return

    # ---- client submission ---- #
    def submit(self, cmd):
        """Append a new entry as leader. Returns its index, or None if not leader."""
        if self.state != LEADER:
            return None
        idx = self.log.append(self.current_term, cmd)
        return idx


def majority(n):
    return n // 2 + 1


# ------------------------------ simulator ------------------------------ #

HEARTBEAT_INTERVAL = 4


class Simulator:
    def __init__(self, seed, n_nodes=5, n_pre=100, n_post=100,
                 election_lo=20, election_hi=40):
        self.seed = seed
        self.rng = random.Random(seed)
        self.n = n_nodes
        self.nodes = [Node(i, n_nodes, self.rng) for i in range(n_nodes)]
        self.pending_send = []   # messages produced this tick, delivered next tick
        self.delivery = []        # messages to deliver this tick
        self.tick = 0
        self.n_pre = n_pre
        self.n_post = n_post
        # instrumentation
        self.first_leader_id = None
        self.first_leader_tick = None
        self.kill_tick = None
        self.killed_id = None
        self.new_leader_id = None
        self.new_leader_tick = None
        self.pre_commit_at_kill = 0
        self.pre_entries = {}      # index -> cmd for the first 100 submitted
        self.post_committed = 0
        self.survived = 0
        # post-kill client queue
        self.post_queue = []

    # ----- helpers ----- #
    def current_leader(self):
        """Return an alive leader node id, or None."""
        for nd in self.nodes:
            if nd.is_alive and nd.state == LEADER:
                return nd.id
        return None

    def leader_node(self):
        lid = self.current_leader()
        return self.nodes[lid] if lid is not None else None

    def step(self):
        """Advance one logical tick."""
        self.tick += 1
        # 1. deliver messages addressed to alive nodes
        to_deliver = self.delivery
        self.delivery = self.pending_send
        self.pending_send = []
        # actually deliver what was queued for this tick
        msgs = self.delivery
        self.delivery = []
        for msg in msgs:
            tgt = self.nodes[msg["to"]]
            if tgt.is_alive and msg["from"] is not None and self.nodes[msg["from"]].is_alive:
                tgt.handle(msg, self.tick, self.pending_send)
        # 2. node tick logic (timers / heartbeats)
        for nd in self.nodes:
            nd.tick(self.tick, self.pending_send)
        # 3. post-kill client submission pump
        if self.kill_tick is not None and self.post_queue:
            ld = self.leader_node()
            if ld is not None and len(ld.log) - 100 < self.n_post:
                # hand the leader one pending command per tick
                cmd = self.post_queue.pop(0)
                idx = ld.submit(cmd)
                # immediate replication
                for peer in range(self.n):
                    if peer == ld.id:
                        continue
                    ld._send_append_entries(self.pending_send, peer)
                del idx

    def run_until_leader(self, max_ticks=2000):
        while self.tick < max_ticks:
            lid = self.current_leader()
            if lid is not None and self.first_leader_id is None:
                self.first_leader_id = lid
                self.first_leader_tick = self.tick
            if self.first_leader_id is not None:
                # require a stable leader (one that has replicated heartbeat)
                if self.tick - self.first_leader_tick >= 2:
                    return True
            self.step()
        return self.first_leader_id is not None

    def submit_pre(self):
        """Submit n_pre entries to the first leader, wait until committed."""
        ld = self.leader_node()
        assert ld is not None, "no leader to submit pre-kill entries"
        for i in range(self.n_pre):
            cmd = "pre_%d" % i
            self.pre_entries[i + 1] = cmd
            ld.submit(cmd)
            # replicate immediately
            for peer in range(self.n):
                if peer == ld.id:
                    continue
                ld._send_append_entries(self.pending_send, peer)

    def wait_until_committed(self, target_index, max_ticks=10000):
        while self.tick < max_ticks:
            ld = self.leader_node()
            if ld is not None and ld.commit_index >= target_index:
                return True
            self.step()
        return False

    def kill_leader(self):
        ld = self.leader_node()
        assert ld is not None, "no leader to kill"
        self.killed_id = ld.id
        self.pre_commit_at_kill = ld.commit_index
        ld.state = DEAD
        ld.next_index = {}
        ld.match_index = {}
        self.kill_tick = self.tick
        # purge any in-flight messages to/from the dead node
        self.delivery = [m for m in self.delivery if m["to"] != ld.id and m["from"] != ld.id]
        self.pending_send = [m for m in self.pending_send
                             if m["to"] != ld.id and m["from"] != ld.id]

    def enqueue_post(self):
        for i in range(self.n_post):
            self.post_queue.append("post_%d" % i)

    def run_post_failover(self, max_ticks=20000):
        """Run until all post entries committed or time limit."""
        target = self.n_pre + self.n_post
        while self.tick < max_ticks:
            # detect new leader
            if self.new_leader_id is None:
                lid = self.current_leader()
                if lid is not None and lid != self.killed_id:
                    self.new_leader_id = lid
                    self.new_leader_tick = self.tick
            # check completion
            ld = self.leader_node()
            if ld is not None and ld.commit_index >= target:
                break
            self.step()
        # final measurements
        ld = self.leader_node()
        if ld is None:
            # take any alive node's max commit
            best = max((nd.commit_index for nd in self.nodes if nd.is_alive), default=0)
            self.post_committed = max(0, best - self.n_pre)
        else:
            self.post_committed = max(0, ld.commit_index - self.n_pre)
        # survival: do the new leader's log (entries 1..n_pre) match originals?
        survivor_node = None
        if self.new_leader_id is not None:
            survivor_node = self.nodes[self.new_leader_id]
        elif ld is not None:
            survivor_node = ld
        if survivor_node is not None:
            ok = 0
            for i in range(1, self.n_pre + 1):
                if (survivor_node.log.term_at(i) != 0 and
                        survivor_node.log.cmd_at(i) == self.pre_entries.get(i)):
                    ok += 1
            self.survived = ok
        else:
            self.survived = 0


def run_seed(seed, n_pre=100, n_post=100):
    sim = Simulator(seed=seed, n_pre=n_pre, n_post=n_post)
    ok1 = sim.run_until_leader()
    sim.submit_pre()
    ok2 = sim.wait_until_committed(n_pre)
    sim.kill_leader()
    sim.enqueue_post()
    sim.run_post_failover()
    failover_latency = (sim.new_leader_tick - sim.kill_tick
                        if sim.new_leader_tick is not None else None)
    return {
        "seed": seed,
        "first_leader": sim.first_leader_id,
        "first_leader_tick": sim.first_leader_tick,
        "killed_id": sim.killed_id,
        "kill_tick": sim.kill_tick,
        "pre_commit_at_kill": sim.pre_commit_at_kill,
        "new_leader_id": sim.new_leader_id,
        "new_leader_tick": sim.new_leader_tick,
        "failover_latency": failover_latency,
        "post_committed": sim.post_committed,
        "post_ratio": sim.post_committed / n_post,
        "survived": sim.survived,
        "survival_rate": sim.survived / n_pre,
        "ok_leader_elected": ok1,
        "ok_pre_committed": ok2,
    }


def main():
    seeds = list(range(1, 13))  # 12 seeds
    results = []
    for s in seeds:
        r = run_seed(s)
        results.append(r)
        print("seed=%2d killed=%d new_leader=%d failover=%s post_commit=%d/100 survived=%d/100"
              % (r["seed"], r["killed_id"], r["new_leader_id"],
                 r["failover_latency"], r["post_committed"], r["survived"]))
    # summary stats
    lats = [r["failover_latency"] for r in results if r["failover_latency"] is not None]
    lats_sorted = sorted(lats)
    import statistics
    stats = {
        "n_seeds": len(results),
        "failover_mean": statistics.mean(lats) if lats else None,
        "failover_median": statistics.median(lats) if lats else None,
        "failover_max": max(lats) if lats else None,
        "failover_min": min(lats) if lats else None,
        "post_ratio_mean": statistics.mean([r["post_ratio"] for r in results]),
        "post_ratio_min": min([r["post_ratio"] for r in results]),
        "survival_rate_mean": statistics.mean([r["survival_rate"] for r in results]),
        "survival_rate_min": min([r["survival_rate"] for r in results]),
    }
    out = {"results": results, "stats": stats}
    with open("results_raft_04.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\n=== STATS ===")
    for k, v in stats.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
