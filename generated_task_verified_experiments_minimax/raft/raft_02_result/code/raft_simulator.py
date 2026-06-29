#!/usr/bin/env python3
"""
In-process Raft simulator studying election timeout spread vs. election speed
and split-vote occurrence.

Design notes:
- N logical nodes, in-memory message queues, logical tick clock.
- Election timeout uniformly sampled from [T_min, T_max] (in ticks) at start
  of each candidacy; re-sampled after each election-round completion.
- Heartbeat interval fixed: H = T_min // 3.
- Deterministic per-seed via Python's random.Random.
- No real network, no sockets, no Docker.
- Only follower/candidate/leader + RequestVote + AppendEntries (heartbeat).
"""

import random
import statistics
import json


class Message:
    # Pre-declared slots covering all fields used by the simulator.
    # Includes both RequestVote and AppendEntries variants plus responses.
    __slots__ = (
        "sender",
        "receiver",
        "msg_type",
        "term",
        "last_log_index",
        "last_log_term",
        "prev_log_index",
        "prev_log_term",
        "entries",
        "leader_commit",
        "vote_granted",
        "success",
    )

    def __init__(self, sender, receiver, msg_type, term, **kwargs):
        self.sender = sender
        self.receiver = receiver
        self.msg_type = msg_type
        self.term = term
        # Defaults for fields that may or may not be set per message type
        self.last_log_index = kwargs.get("last_log_index", 0)
        self.last_log_term = kwargs.get("last_log_term", 0)
        self.prev_log_index = kwargs.get("prev_log_index", 0)
        self.prev_log_term = kwargs.get("prev_log_term", 0)
        self.entries = kwargs.get("entries", [])
        self.leader_commit = kwargs.get("leader_commit", 0)
        self.vote_granted = kwargs.get("vote_granted", False)
        self.success = kwargs.get("success", False)


class RaftNode:
    def __init__(self, node_id, n_nodes, t_min, t_max, heartbeat_interval, rng):
        self.id = node_id
        self.n_nodes = n_nodes
        self.t_min = t_min
        self.t_max = t_max
        self.heartbeat_interval = heartbeat_interval
        self.rng = rng

        # Persistent state
        self.current_term = 0
        self.voted_for = None
        self.log = []  # not used for cold-start election but kept for completeness

        # Role
        self.state = "follower"
        self.leader_id = None

        # Election/heartbeat timing
        self.election_deadline = self._sample_election_timeout()  # counted from tick 0
        self.heartbeat_deadline = None

        # Candidate vote tracking
        self.votes = set()

    # -- helpers --
    def _sample_election_timeout(self):
        if self.t_max <= self.t_min:
            return self.t_min
        return self.t_min + self.rng.randint(0, self.t_max - self.t_min)

    def _reset_election_timeout(self, current_tick):
        self.election_deadline = current_tick + self._sample_election_timeout()

    # -- state transitions --
    def _become_follower(self, term, current_tick):
        self.state = "follower"
        self.leader_id = None
        self.current_term = term
        self.voted_for = None
        self.votes = set()
        self._reset_election_timeout(current_tick)

    def _become_candidate(self, current_tick):
        self.state = "candidate"
        self.leader_id = None
        self.current_term += 1
        self.voted_for = self.id
        self.votes = {self.id}
        self._reset_election_timeout(current_tick)

    def _become_leader(self):
        self.state = "leader"
        self.leader_id = self.id
        self.heartbeat_deadline = None  # triggers immediate heartbeat

    # -- tick processing --
    def tick(self, current_tick, sim):
        if self.state == "follower":
            if current_tick >= self.election_deadline:
                # Promote to candidate
                self._become_candidate(current_tick)
                sim.on_term_started(self.current_term, current_tick)
                self._send_request_vote(current_tick, sim)
        elif self.state == "candidate":
            if current_tick >= self.election_deadline:
                # Election timed out without majority -> split-vote
                sim.on_term_ended_without_leader(self.current_term)
                self._become_candidate(current_tick)
                sim.on_term_started(self.current_term, current_tick)
                self._send_request_vote(current_tick, sim)
        elif self.state == "leader":
            if self.heartbeat_deadline is None or current_tick >= self.heartbeat_deadline:
                self._send_heartbeats(current_tick, sim)

    def _send_request_vote(self, current_tick, sim):
        last_log_index = len(self.log)
        last_log_term = self.log[-1]["term"] if self.log else 0
        for other in range(self.n_nodes):
            if other != self.id:
                sim.send_message(
                    Message(
                        sender=self.id,
                        receiver=other,
                        msg_type="RequestVote",
                        term=self.current_term,
                        last_log_index=last_log_index,
                        last_log_term=last_log_term,
                    ),
                    current_tick,
                )

    def _send_heartbeats(self, current_tick, sim):
        for other in range(self.n_nodes):
            if other != self.id:
                sim.send_message(
                    Message(
                        sender=self.id,
                        receiver=other,
                        msg_type="AppendEntries",
                        term=self.current_term,
                        prev_log_index=len(self.log),
                        prev_log_term=0,
                        entries=[],
                        leader_commit=0,
                    ),
                    current_tick,
                )
        self.heartbeat_deadline = current_tick + self.heartbeat_interval

    # -- RPC handlers --
    def receive_message(self, msg, current_tick, sim):
        if msg.msg_type == "RequestVote":
            if msg.term > self.current_term:
                self._become_follower(msg.term, current_tick)

            grant = False
            if msg.term == self.current_term:
                if self.voted_for is None or self.voted_for == msg.sender:
                    # Log up-to-date check: for cold-start all logs empty => trivially up-to-date
                    grant = True
                    self.voted_for = msg.sender
                    self._reset_election_timeout(current_tick)

            sim.send_message(
                Message(
                    sender=self.id,
                    receiver=msg.sender,
                    msg_type="RequestVoteResponse",
                    term=self.current_term,
                    vote_granted=grant,
                ),
                current_tick,
            )

        elif msg.msg_type == "RequestVoteResponse":
            if msg.term > self.current_term:
                self._become_follower(msg.term, current_tick)
                return

            if self.state != "candidate" or msg.term != self.current_term:
                return

            if msg.vote_granted:
                self.votes.add(msg.sender)
                if len(self.votes) > self.n_nodes / 2:
                    sim.on_leader_elected(self.id, self.current_term, current_tick)
                    self._become_leader()
                    self._send_heartbeats(current_tick, sim)

        elif msg.msg_type == "AppendEntries":
            if msg.term > self.current_term:
                self._become_follower(msg.term, current_tick)

            if msg.term == self.current_term:
                if self.state != "follower":
                    self._become_follower(msg.term, current_tick)
                self.leader_id = msg.sender
                self._reset_election_timeout(current_tick)
                sim.send_message(
                    Message(
                        sender=self.id,
                        receiver=msg.sender,
                        msg_type="AppendEntriesResponse",
                        term=self.current_term,
                        success=True,
                    ),
                    current_tick,
                )
            else:
                sim.send_message(
                    Message(
                        sender=self.id,
                        receiver=msg.sender,
                        msg_type="AppendEntriesResponse",
                        term=self.current_term,
                        success=False,
                    ),
                    current_tick,
                )


class Simulator:
    def __init__(self, n_nodes, t_min, t_max, heartbeat_interval, message_delay, seed):
        self.n_nodes = n_nodes
        self.t_min = t_min
        self.t_max = t_max
        self.heartbeat_interval = heartbeat_interval
        self.message_delay = message_delay
        self.seed = seed

        self.rng = random.Random(seed)
        self.nodes = [
            RaftNode(i, n_nodes, t_min, t_max, heartbeat_interval, self.rng)
            for i in range(n_nodes)
        ]

        self.tick = 0
        self.pending_messages = []  # list of (delivery_tick, Message)

        # Results
        self.leader_elected_tick = None
        self.elected_leader_id = None
        self.elected_term = None
        self.split_vote_occurred = False
        self.terms_with_leaders = set()
        self.terms_started = set()

    def send_message(self, msg, current_tick):
        delivery_tick = current_tick + self.message_delay
        self.pending_messages.append((delivery_tick, msg))

    def on_term_started(self, term, current_tick):
        self.terms_started.add(term)

    def on_term_ended_without_leader(self, term):
        if term not in self.terms_with_leaders:
            self.split_vote_occurred = True

    def on_leader_elected(self, node_id, term, current_tick):
        self.terms_with_leaders.add(term)
        if self.leader_elected_tick is None or current_tick < self.leader_elected_tick:
            self.leader_elected_tick = current_tick
            self.elected_leader_id = node_id
            self.elected_term = term

    def _deliver_messages(self):
        delivered = []
        remaining = []
        for delivery_tick, msg in self.pending_messages:
            if delivery_tick <= self.tick:
                delivered.append(msg)
            else:
                remaining.append((delivery_tick, msg))
        self.pending_messages = remaining
        for msg in delivered:
            self.nodes[msg.receiver].receive_message(msg, self.tick, self)

    def run(self, max_ticks):
        # Stability window after leader election: 3 heartbeats
        stability_window = 3 * self.heartbeat_interval

        while self.tick < max_ticks:
            self.tick += 1

            # 1) Deliver any messages whose delivery tick <= current
            self._deliver_messages()

            # 2) Process node timeouts/heartbeats
            for node in self.nodes:
                node.tick(self.tick, self)

            # 3) Stability check
            if self.leader_elected_tick is not None:
                elapsed = self.tick - self.leader_elected_tick
                if elapsed >= stability_window:
                    # Ensure no candidate in a higher term exists
                    any_higher_candidate = False
                    for n in self.nodes:
                        if n.state == "candidate" and n.current_term > self.elected_term:
                            any_higher_candidate = True
                            break
                    if not any_higher_candidate:
                        break

        return self.leader_elected_tick, self.split_vote_occurred


def run_experiment(spread, n_seeds, t_min=30, n_nodes=5, message_delay=1, max_ticks=5000):
    t_max = t_min + spread
    heartbeat_interval = max(1, t_min // 3)

    times_to_elect = []
    split_votes = []

    for seed in range(n_seeds):
        sim = Simulator(n_nodes, t_min, t_max, heartbeat_interval, message_delay, seed)
        leader_tick, split_vote = sim.run(max_ticks)
        times_to_elect.append(leader_tick)
        split_votes.append(split_vote)

    valid_times = [t for t in times_to_elect if t is not None]
    if valid_times:
        median_time = statistics.median(valid_times)
        mean_time = statistics.mean(valid_times)
        min_time = min(valid_times)
        max_time = max(valid_times)
        p25 = statistics.quantiles(valid_times, n=4)[0] if len(valid_times) >= 4 else min_time
        p75 = statistics.quantiles(valid_times, n=4)[2] if len(valid_times) >= 4 else max_time
    else:
        median_time = None
        mean_time = None
        min_time = None
        max_time = None
        p25 = None
        p75 = None

    split_vote_rate = sum(split_votes) / len(split_votes)
    no_leader_rate = sum(1 for t in times_to_elect if t is None) / len(times_to_elect)

    return {
        "spread": spread,
        "t_min": t_min,
        "t_max": t_max,
        "heartbeat_interval": heartbeat_interval,
        "n_nodes": n_nodes,
        "message_delay": message_delay,
        "n_seeds": n_seeds,
        "median_time_to_elect": median_time,
        "mean_time_to_elect": mean_time,
        "min_time_to_elect": min_time,
        "max_time_to_elect": max_time,
        "p25_time_to_elect": p25,
        "p75_time_to_elect": p75,
        "split_vote_rate": split_vote_rate,
        "no_leader_rate": no_leader_rate,
        "times_to_elect": times_to_elect,
        "split_votes": split_votes,
    }


if __name__ == "__main__":
    n_seeds = 100  # >= 30 per spec
    t_min = 30
    heartbeat_interval = t_min // 3  # 10 ticks
    spreads = [
        0,
        1 * heartbeat_interval,
        5 * heartbeat_interval,
        10 * heartbeat_interval,
        20 * heartbeat_interval,
    ]

    print(f"Running experiment: N=5, T_min={t_min}, H={heartbeat_interval}, seeds={n_seeds}")
    print(f"Spreads (in ticks): {spreads}")
    print()

    results = []
    for spread in spreads:
        r = run_experiment(spread, n_seeds, t_min=t_min)
        results.append(r)
        med = r["median_time_to_elect"]
        med_s = "n/a (no leader)" if med is None else f"{med}"
        print(
            f"spread={r['spread']:>4} (T_max={r['t_max']:>3}): "
            f"median time-to-elect={med_s:>16} | "
            f"split-vote rate={r['split_vote_rate']:.2%} | "
            f"no-leader rate={r['no_leader_rate']:.2%}"
        )

    # Save raw results
    with open("experiment_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\nResults saved to experiment_results.json")