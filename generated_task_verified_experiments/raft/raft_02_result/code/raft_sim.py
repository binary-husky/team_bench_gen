"""
In-process Raft election simulator (tick-based, deterministic).

Reproduces Follower/Candidate/Leader state machine + RequestVote election +
heartbeat (empty AppendEntries), per the Raft paper. Used to study how the
"spread" (T_max - T_min) of randomized election timeouts affects
time-to-elect and split-vote rate.

No real network / sockets / threads / docker. Single process, in-memory
message queue, logical tick clock, deterministic RNG.

Logs are kept empty & identical across nodes so vote-granting is governed
purely by term + votedFor (the timing dynamics under study).
"""

import random
import json
from collections import deque, defaultdict

# ---- Fixed experimental setup (do not change) ----------------------------
N = 5                              # cluster size
T_MIN = 15                         # election-timeout lower bound (ticks)
H = T_MIN // 3                     # heartbeat interval = T_min/3 = 5
SPREADS = [0, 1 * H, 5 * H, 10 * H, 20 * H]   # {0, 5, 25, 50, 100}
SEEDS_PER_SPREAD = 60             # >= 30 different seeds per spread
MAX_TICKS = 6000                  # per-run cap (spread=0 never elects -> hits cap)
MSG_LATENCY = 1                   # messages delivered MSG_LATENCY ticks after send
MAJORITY = N // 2 + 1             # 3


class Node:
    __slots__ = ("id", "state", "term", "voted_for", "votes",
                 "eto_elapsed", "eto_timeout", "hb_elapsed")

    def __init__(self, nid):
        self.id = nid
        self.state = "Follower"
        self.term = 0
        self.voted_for = None
        self.votes = set()
        self.eto_elapsed = 0
        self.eto_timeout = 0
        self.hb_elapsed = 0


class Cluster:
    """One cold-start election run with a fixed seed and spread."""

    def __init__(self, seed, spread):
        self.seed = seed
        self.t_min = T_MIN
        self.t_max = T_MIN + spread
        self.rng = random.Random(seed)
        self.nodes = [Node(i) for i in range(N)]
        for nd in self.nodes:
            nd.eto_timeout = self.rng.randint(self.t_min, self.t_max)
        self.tick = 0
        self.msg_q = deque()          # (delivery_tick, seq, msg)
        self.seq = 0
        # split-vote bookkeeping
        self.candidate_in_term = defaultdict(bool)
        self.leader_in_term = defaultdict(bool)
        self.leader_tick = None
        self.split_terms = set()

    # ---- message helpers (each message carries dest as last field) -------
    def _send(self, msg):
        self.seq += 1
        self.msg_q.append((self.tick + MSG_LATENCY, self.seq, msg))

    def _broadcast_rv(self, cand):
        for nid in range(N):
            if nid == cand.id:
                continue
            # ("RV", term, cand_id, lastLogIndex, lastLogTerm, dest)
            self._send(("RV", cand.term, cand.id, 0, 0, nid))

    def _broadcast_hb(self, leader):
        for nid in range(N):
            if nid == leader.id:
                continue
            self._send(("HB", leader.term, leader.id, nid))

    def _send_rvr(self, cand_id, voter, term, granted):
        self._send(("RVR", term, voter.id, cand_id, granted, cand_id))

    # ---- election start ---------------------------------------------------
    def _start_election(self, nd):
        nd.term += 1
        nd.state = "Candidate"
        nd.voted_for = nd.id
        nd.votes = {nd.id}
        self.candidate_in_term[nd.term] = True
        # restart randomized election timeout (paper: restart at start of election)
        nd.eto_timeout = self.rng.randint(self.t_min, self.t_max)
        nd.eto_elapsed = 0
        self._broadcast_rv(nd)

    # ---- RPC delivery -----------------------------------------------------
    def _deliver(self, msg):
        kind = msg[0]
        nd = self.nodes[msg[-1]]
        if kind == "RV":
            _, term, cand_id, _last_idx, _last_term, _dest = msg
            if term < nd.term:
                self._send_rvr(cand_id, nd, term, False)
                return
            if term > nd.term:
                nd.term = term
                nd.state = "Follower"
                nd.voted_for = None
            # logs empty & equal -> candidate log always up-to-date
            grant = (nd.voted_for is None or nd.voted_for == cand_id)
            if grant:
                nd.voted_for = cand_id
                nd.state = "Follower"
                nd.eto_timeout = self.rng.randint(self.t_min, self.t_max)
                nd.eto_elapsed = 0
            self._send_rvr(cand_id, nd, term, grant)
        elif kind == "RVR":
            _, term, voter_id, cand_id, granted, _dest = msg
            if nd.state != "Candidate" or nd.term != term:
                return
            if granted:
                nd.votes.add(voter_id)
                if len(nd.votes) >= MAJORITY and self.leader_tick is None:
                    nd.state = "Leader"
                    self.leader_in_term[nd.term] = True
                    self.leader_tick = self.tick
                    self._broadcast_hb(nd)
                    nd.hb_elapsed = 0
        elif kind == "HB":
            _, term, leader_id, _dest = msg
            if term >= nd.term:
                if term > nd.term:
                    nd.term = term
                nd.state = "Follower"
                nd.eto_timeout = self.rng.randint(self.t_min, self.t_max)
                nd.eto_elapsed = 0

    # ---- main loop --------------------------------------------------------
    def run(self):
        while self.tick < MAX_TICKS and self.leader_tick is None:
            self.tick += 1
            # 1) deliver messages scheduled for this tick (FIFO by send seq)
            batch = []
            while self.msg_q and self.msg_q[0][0] <= self.tick:
                batch.append(self.msg_q.popleft())
            batch.sort(key=lambda x: x[1])
            for _dtk, _seq, msg in batch:
                self._deliver(msg)
            # 2) advance per-node timers
            for nd in self.nodes:
                if nd.state == "Leader":
                    nd.hb_elapsed += 1
                    if nd.hb_elapsed >= H:
                        nd.hb_elapsed = 0
                        self._broadcast_hb(nd)
                    continue
                nd.eto_elapsed += 1
                if nd.eto_elapsed >= nd.eto_timeout:
                    # election timer fires -> this term had candidates but no leader?
                    if (nd.term > 0 and self.candidate_in_term[nd.term]
                            and not self.leader_in_term[nd.term]):
                        self.split_terms.add(nd.term)
                    self._start_election(nd)
        # runs that hit the cap without a leader: every candidate term was a split
        for t in list(self.candidate_in_term.keys()):
            if self.candidate_in_term[t] and not self.leader_in_term[t]:
                self.split_terms.add(t)
        return self


def run_one(seed, spread):
    return Cluster(seed, spread).run()


def main():
    results = {}
    for spread in SPREADS:
        t2e = []
        split_count = 0
        never = 0
        for s in range(SEEDS_PER_SPREAD):
            seed = 1000 + s
            c = run_one(seed, spread)
            if c.leader_tick is None:
                never += 1
                split_count += 1            # deadlock == perpetual split-vote
                t2e.append(None)
            else:
                t2e.append(c.leader_tick)
                if c.split_terms:
                    split_count += 1
        elected = [t for t in t2e if t is not None]
        elected_sorted = sorted(elected)
        med = elected_sorted[len(elected_sorted) // 2] if elected_sorted else None
        results[spread] = {
            "T_min": T_MIN,
            "T_max": T_MIN + spread,
            "spread_ticks": spread,
            "spread_in_H": None if H == 0 else round(spread / H, 2),
            "n_seeds": SEEDS_PER_SPREAD,
            "n_elected": len(elected),
            "n_never_elected": never,
            "median_t2e": med,
            "min_t2e": min(elected) if elected else None,
            "max_t2e_elected": max(elected) if elected else None,
            "mean_t2e": round(sum(elected) / len(elected), 2) if elected else None,
            "split_rate": round(split_count / SEEDS_PER_SPREAD, 3),
            "split_count": split_count,
        }
    print(json.dumps(results, indent=2))
    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
