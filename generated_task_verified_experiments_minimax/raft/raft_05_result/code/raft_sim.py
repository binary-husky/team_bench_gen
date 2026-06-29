#!/usr/bin/env python3
"""
In-process Raft simulator used to verify term safety (Leader Completeness).

Features:
- 5-node cluster, in-memory message queues, logical tick clock.
- Deterministic seeded randomness (no real network/socket/Docker).
- Can isolate/restore a node from the rest of the cluster (network partition).
- Replicates Raft election + log replication from the original paper:
    * Section 5.2 Leader election (term, voted_for, randomized election timeouts)
    * Section 5.3 Log replication (AppendEntries, prevLog consistency check,
      commitIndex advance, log reconciliation / truncate-on-mismatch)
    * Section 5.4 Safety (term safety, leader completeness, log matching)
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Optional


# --------------------------------------------------------------------------- #
#  Log entry / message definitions
# --------------------------------------------------------------------------- #


@dataclass
class LogEntry:
    term: int
    cmd: str  # client command (opaque string)


@dataclass
class Message:
    """Envelope of an RPC. ``kind`` selects which fields are meaningful."""
    kind: str            # "RequestVote", "RequestVoteResp", "AppendEntries", "AppendEntriesResp"
    src: int
    dst: int
    term: int = 0
    # RequestVote
    last_log_index: int = 0
    last_log_term: int = 0
    candidate_id: int = 0
    vote_granted: bool = False
    voter_id: int = 0
    # AppendEntries
    prev_log_index: int = 0
    prev_log_term: int = 0
    entries: list = field(default_factory=list)
    leader_commit: int = 0
    # AppendEntries response
    success: bool = False
    conflict_index: int = 0
    match_index: int = 0


# --------------------------------------------------------------------------- #
#  Raft node
# --------------------------------------------------------------------------- #


# All communication passes through these two dicts keyed by (src, dst).
REQUEST_VOTE: dict[tuple[int, int], list[Message]] = {}
APPEND_ENTRIES: dict[tuple[int, int], list[Message]] = {}


def _deliver(kind_dict, msg):
    kind_dict[(msg.src, msg.dst)].append(msg)


def _clear_queues():
    REQUEST_VOTE.clear()
    APPEND_ENTRIES.clear()
    for k in range(5):
        for j in range(5):
            REQUEST_VOTE[(k, j)] = []
            APPEND_ENTRIES[(k, j)] = []


class RaftNode:
    def __init__(self, node_id: int, rng: random.Random):
        self.id = node_id
        self.rng = rng
        self.state = "Follower"            # Follower | Candidate | Leader
        self.current_term = 0
        self.voted_for: Optional[int] = None
        self.log: list[LogEntry] = []
        self.commit_index = 0              # highest known-committed index (0-based)
        self.last_applied = 0
        self.votes_received: set[int] = set()
        self.election_elapsed = 0
        self.election_timeout = self._new_election_timeout()
        self.heartbeat_elapsed = 0
        self.heartbeat_interval = 1        # tick
        # Leader-only state
        self.next_index: dict[int, int] = {}
        self.match_index: dict[int, int] = {}

    # -------- helpers ------------------------------------------------------ #

    def last_log_index(self) -> int:
        return len(self.log)

    def last_log_term(self) -> int:
        return self.log[-1].term if self.log else 0

    def log_term_at(self, idx: int) -> int:
        """1-based ``idx`` -> term of the entry at that index, 0 if none."""
        if idx == 0:
            return 0
        if 1 <= idx <= len(self.log):
            return self.log[idx - 1].term
        return -1  # beyond end (shouldn't be queried normally)

    def _new_election_timeout(self) -> int:
        # Per paper §5.2: randomized, 150-300 ms analogue. We use 6-10 ticks.
        return self.rng.randint(6, 10)

    def _reset_to_follower(self, term: int):
        self.state = "Follower"
        self.current_term = term
        self.voted_for = None
        self.votes_received = set()
        self.election_timeout = self._new_election_timeout()
        self.election_elapsed = 0
        self.heartbeat_elapsed = 0

    # -------- main tick ---------------------------------------------------- #

    def tick(self):
        if self.state in ("Follower", "Candidate"):
            self.election_elapsed += 1
            if self.election_elapsed >= self.election_timeout:
                self._start_election()
        if self.state == "Leader":
            self.heartbeat_elapsed += 1
            if self.heartbeat_elapsed >= self.heartbeat_interval:
                self.heartbeat_elapsed = 0
                self._broadcast_append_entries(heartbeat_only=True)
        self._apply_committed()

    # -------- client command ---------------------------------------------- #

    def submit_command(self, cmd: str) -> bool:
        """Append a client command. Leaders only; false otherwise."""
        if self.state != "Leader":
            return False
        self.log.append(LogEntry(self.current_term, cmd))
        self._broadcast_append_entries(heartbeat_only=False)
        return True

    # -------- election ----------------------------------------------------- #

    def _start_election(self):
        self.state = "Candidate"
        self.current_term += 1
        self.voted_for = self.id
        self.votes_received = {self.id}
        self.election_timeout = self._new_election_timeout()
        self.election_elapsed = 0
        for peer in range(5):
            if peer == self.id:
                continue
            _deliver(REQUEST_VOTE, Message(
                kind="RequestVote",
                src=self.id,
                dst=peer,
                term=self.current_term,
                last_log_index=self.last_log_index(),
                last_log_term=self.last_log_term(),
                candidate_id=self.id,
            ))

    # -------- replication -------------------------------------------------- #

    def _broadcast_append_entries(self, heartbeat_only: bool):
        for peer in range(5):
            if peer == self.id:
                continue
            self._send_append_entries(peer, heartbeat_only=heartbeat_only)

    def _send_append_entries(self, peer: int, heartbeat_only: bool = False):
        # next_index is 1-based. Default 1 if leader's log empty.
        ni = self.next_index.get(peer, max(1, len(self.log)))
        prev_idx = ni - 1
        prev_term = self.log_term_at(prev_idx)
        # If the leader's log is shorter than prev_idx + 1, send a heartbeat
        # with no new entries. This happens right after becoming leader and
        # before the first successful client command.
        entries: list[LogEntry] = []
        if not heartbeat_only and ni <= len(self.log):
            entries = [copy.copy(e) for e in self.log[ni - 1:]]
        _deliver(APPEND_ENTRIES, Message(
            kind="AppendEntries",
            src=self.id,
            dst=peer,
            term=self.current_term,
            prev_log_index=prev_idx,
            prev_log_term=prev_term,
            entries=entries,
            leader_commit=self.commit_index,
        ))

    def _maybe_advance_commit_index(self):
        if self.state != "Leader":
            return
        # Find the largest N such that a majority of match_index[i] >= N
        # AND log[N].term == current_term (paper §5.4.2 / Fig 8).
        mids = sorted(self.match_index.values(), reverse=True)
        # Majority of 5 is 3 (counting leader itself = idx len(self.log)).
        mids.append(len(self.log))
        mids.sort(reverse=True)
        majority_n = mids[len(mids) // 2]  # median; for 5 -> 3rd-largest
        if majority_n > self.commit_index and \
                self.log_term_at(majority_n) == self.current_term:
            self.commit_index = majority_n

    def _apply_committed(self):
        while self.last_applied < self.commit_index:
            self.last_applied += 1

    # -------- RPC handlers ------------------------------------------------- #

    def handle_request_vote(self, msg: Message) -> Optional[Message]:
        if msg.term > self.current_term:
            self._reset_to_follower(msg.term)
        grant = False
        if msg.term == self.current_term and \
                (self.voted_for is None or self.voted_for == msg.candidate_id):
            # §5.4.1 / §5.4.3: up-to-date check (Raft compares (term, idx))
            my_last_term = self.last_log_term()
            my_last_idx = self.last_log_index()
            up_to_date = (msg.last_log_term > my_last_term) or \
                (msg.last_log_term == my_last_term and
                 msg.last_log_index >= my_last_idx)
            if up_to_date:
                grant = True
                self.voted_for = msg.candidate_id
                self.election_timeout = self._new_election_timeout()
                self.election_elapsed = 0
        return Message(
            kind="RequestVoteResp",
            src=self.id, dst=msg.src, term=self.current_term,
            vote_granted=grant, voter_id=self.id,
        )

    def handle_append_entries(self, msg: Message) -> Optional[Message]:
        if msg.term < self.current_term:
            return Message(
                kind="AppendEntriesResp",
                src=self.id, dst=msg.src, term=self.current_term,
                success=False, match_index=0,
            )
        if msg.term > self.current_term:
            self._reset_to_follower(msg.term)
        # Valid leader -> become follower
        self.state = "Follower"
        self.voted_for = None
        self.election_timeout = self._new_election_timeout()
        self.election_elapsed = 0

        # Consistency check on prev_log_index
        if msg.prev_log_index > len(self.log):
            # Follower is behind; ask leader to back up.
            return Message(
                kind="AppendEntriesResp",
                src=self.id, dst=msg.src, term=self.current_term,
                success=False, match_index=len(self.log),
            )
        if msg.prev_log_index > 0 and \
                self.log[msg.prev_log_index - 1].term != msg.prev_log_term:
            # Conflict: drop the conflicting entry and everything after
            # (log reconciliation / truncation). Report the index of the
            # first entry of the conflicting term.
            conflict_term = self.log[msg.prev_log_index - 1].term
            first_idx = msg.prev_log_index
            for j in range(msg.prev_log_index - 1, -1, -1):
                if self.log[j].term != conflict_term:
                    first_idx = j + 2
                    break
            else:
                first_idx = 1
            del self.log[first_idx - 1:]
            return Message(
                kind="AppendEntriesResp",
                src=self.id, dst=msg.src, term=self.current_term,
                success=False, conflict_index=first_idx,
                match_index=len(self.log),
            )

        # Append any new entries (truncating extras as in §5.3)
        for e in msg.entries:
            if e.cmd is None:
                continue
            idx = msg.prev_log_index + msg.entries.index(e) + 1
            if idx <= len(self.log):
                if self.log[idx - 1].term != e.term:
                    del self.log[idx - 1:]
                    self.log.append(LogEntry(e.term, e.cmd))
            else:
                self.log.append(LogEntry(e.term, e.cmd))

        if msg.leader_commit > self.commit_index:
            self.commit_index = min(msg.leader_commit, len(self.log))

        return Message(
            kind="AppendEntriesResp",
            src=self.id, dst=msg.src, term=self.current_term,
            success=True, match_index=len(self.log),
        )

    # -------- RPC responses ----------------------------------------------- #

    def handle_request_vote_resp(self, msg: Message):
        if msg.term > self.current_term:
            self._reset_to_follower(msg.term)
            return
        if self.state != "Candidate" or msg.term != self.current_term:
            return
        if msg.vote_granted:
            self.votes_received.add(msg.voter_id)
            if len(self.votes_received) >= 3:  # majority of 5
                self._become_leader()

    def _become_leader(self):
        self.state = "Leader"
        self.next_index = {p: max(1, len(self.log) + 1) for p in range(5) if p != self.id}
        self.match_index = {p: 0 for p in range(5) if p != self.id}
        # Append an empty no-op entry to commit prior entries (§5.4.2).
        # Many implementations skip this if log is already empty.
        # We don't add a noop for simplicity; majority commit advances
        # naturally when new entries land.
        self.heartbeat_elapsed = 0
        self._broadcast_append_entries(heartbeat_only=True)

    def handle_append_entries_resp(self, msg: Message):
        if msg.term > self.current_term:
            self._reset_to_follower(msg.term)
            return
        if self.state != "Leader" or msg.term != self.current_term:
            return
        peer = msg.src
        if msg.success:
            self.match_index[peer] = max(self.match_index.get(peer, 0), msg.match_index)
            self.next_index[peer] = self.match_index[peer] + 1
            self._maybe_advance_commit_index()
        else:
            # Back up next_index and retry. The conflict_index hint speeds
            # convergence; we use the simpler "decrement by 1" approach to
            # closely follow the paper.
            self.next_index[peer] = max(1, self.next_index[peer] - 1)
            self._send_append_entries(peer, heartbeat_only=False)


# --------------------------------------------------------------------------- #
#  Cluster driver
# --------------------------------------------------------------------------- #


class Cluster:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.nodes: list[RaftNode] = [RaftNode(i, random.Random(seed + i + 1))
                                      for i in range(5)]
        self.partition: Optional[set[int]] = None  # node IDs that are cut off
        self.tick_count = 0

    # -------- partition control ------------------------------------------- #

    def isolate(self, node_id: int):
        """Cut off ``node_id`` from the rest of the cluster."""
        self.partition = {node_id}

    def restore(self):
        self.partition = None

    def _allowed(self, src: int, dst: int) -> bool:
        if self.partition is None:
            return True
        # In a partition, a node in the isolated set can only talk to itself
        # (which is meaningless) and not to nodes outside.
        if (src in self.partition) != (dst in self.partition):
            return False
        return True

    # -------- step --------------------------------------------------------- #

    def deliver(self) -> int:
        """Process all queued messages. Returns number of messages delivered."""
        delivered = 0
        # RequestVote
        for (src, dst), q in list(REQUEST_VOTE.items()):
            while q:
                m = q.pop(0)
                if not self._allowed(m.src, m.dst):
                    continue
                if m.kind == "RequestVote":
                    resp = self.nodes[m.dst].handle_request_vote(m)
                    if resp is not None:
                        if self._allowed(resp.src, resp.dst):
                            REQUEST_VOTE[(resp.src, resp.dst)].append(resp)
                else:  # RequestVoteResp
                    self.nodes[m.dst].handle_request_vote_resp(m)
                delivered += 1
        # AppendEntries
        for (src, dst), q in list(APPEND_ENTRIES.items()):
            while q:
                m = q.pop(0)
                if not self._allowed(m.src, m.dst):
                    continue
                if m.kind == "AppendEntries":
                    resp = self.nodes[m.dst].handle_append_entries(m)
                    if resp is not None:
                        if self._allowed(resp.src, resp.dst):
                            APPEND_ENTRIES[(resp.src, resp.dst)].append(resp)
                else:  # AppendEntriesResp
                    self.nodes[m.dst].handle_append_entries_resp(m)
                delivered += 1
        return delivered

    def step(self, n: int = 1) -> int:
        """Advance simulation by n ticks. Returns total messages delivered."""
        total = 0
        for _ in range(n):
            for n_ in self.nodes:
                n_.tick()
            self.tick_count += 1
            total += self.deliver()
        return total

    # -------- scenario ----------------------------------------------------- #

    def leader_id(self) -> Optional[int]:
        """Return the highest-term leader (handles split-brain, where an
        isolated L1 can remain in ``Leader`` state with a stale term while
        a new L2 emerges in a fresh term)."""
        best_id = None
        best_term = -1
        for n in self.nodes:
            if n.state == "Leader" and n.current_term > best_term:
                best_term = n.current_term
                best_id = n.id
        return best_id

    def term_of(self, node_id: int) -> int:
        return self.nodes[node_id].current_term

    def log(self, node_id: int) -> list[LogEntry]:
        return self.nodes[node_id].log

    def commit(self, node_id: int) -> int:
        return self.nodes[node_id].commit_index

    def submit_command(self, cmd: str) -> Optional[int]:
        """Submit a client command to the current leader. Returns leader id."""
        lid = self.leader_id()
        if lid is None:
            return None
        self.nodes[lid].submit_command(cmd)
        return lid

    def wait_for_leader(self, max_ticks: int = 200) -> Optional[int]:
        for _ in range(max_ticks):
            lid = self.leader_id()
            if lid is not None:
                return lid
            self.step(1)
        return None

    def wait_for_commit(self, target: int, max_ticks: int = 200) -> bool:
        lid = self.leader_id()
        for _ in range(max_ticks):
            if lid is not None and self.commit(lid) >= target:
                return True
            self.step(1)
        return False
