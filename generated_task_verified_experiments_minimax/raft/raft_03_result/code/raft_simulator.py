"""
In-process Raft simulator with AppendEntries log replication & commit.

Implements the Raft consensus algorithm as described in the raft.pdf paper
(Ongaro & Ousterhout). Designed for the raft_03 task: verifying log replication
and commitIndex monotonic advance.

Design:
- Logical clock driven by ticks (1 tick = 1 simulation step).
- All messages go through in-memory mailboxes; each message takes MSG_DELAY
  ticks to deliver (logical transmission latency).
- Deterministic: seeded random number generator, no real time, no I/O.
- Three states per node: follower / candidate / leader.
- Followers / candidates can become candidates on election-timeout; candidates
  become leaders on majority votes; leader steps down on higher term seen.
- AppendEntries carries log entries and is also used as heartbeat.
- Leader tracks matchIndex[] per follower; advance commitIndex when a majority
  of matchIndex[] >= N for some index N and log[N].term == currentTerm.

Tailored to the raft_03 task:
- After leader is elected, we submit 1000 client commands.
- Records per entry: append tick, replication count (per follower), commit tick.
- Records commitIndex history (tick, commitIndex) for monotonicity checks.
"""

import random
from collections import defaultdict

# ---- Timing parameters (ticks; "reasonable" so a leader is elected quickly
# without much split-vote risk) ---------------------------------------------
ET_MIN = 60                # min election timeout
ET_MAX = 120               # max election timeout (spread = 60)
HB_INTERVAL = 15           # leader heartbeat interval (< ET_MIN/2)
MSG_DELAY = 1              # message delivery latency (logical ticks)
COMMIT_CHECK_PER_TICK = True


class LogEntry:
    __slots__ = ("term", "cmd")

    def __init__(self, term, cmd):
        self.term = term
        self.cmd = cmd


class Msg:
    """A queued message between nodes."""
    __slots__ = ("kind", "src", "dst", "data", "deliver_at")

    def __init__(self, kind, src, dst, deliver_at, **data):
        self.kind = kind
        self.src = src
        self.dst = dst
        self.data = data
        self.deliver_at = deliver_at


class Node:
    """A single Raft node."""

    def __init__(self, nid, n, sim, rng):
        self.id = nid
        self.n = n
        self.sim = sim
        self.rng = rng
        # Persistent state
        self.currentTerm = 0
        self.votedFor = None
        self.log = []  # list of LogEntry; index i corresponds to log entry i (0-indexed)
        # Volatile state
        self.commitIndex = -1
        self.lastApplied = -1
        # Leader volatile
        self.nextIndex = None
        self.matchIndex = None
        # Election
        self.state = "follower"
        self.election_deadline = None
        self.votes_received = set()
        # Heartbeat
        self.last_heartbeat_tick = -10 ** 9
        # Stats - per node
        self.last_log_len_at_tick = {}  # not really used
        # Internal: per-entry replication ticks seen by this node
        # (filled by Simulator when an AE arrives)

    # ---------------- Election timer ----------------

    def reset_election_timer(self, tick):
        timeout = self.rng.randint(ET_MIN, ET_MAX)
        self.election_deadline = tick + timeout

    # ---------------- Tick ----------------

    def on_tick(self, tick):
        if self.state == "leader":
            if tick - self.last_heartbeat_tick >= HB_INTERVAL:
                self.broadcast_append_entries(tick)
                self.last_heartbeat_tick = tick
            self.maybe_advance_commit(tick)
        elif self.state == "candidate":
            if tick >= self.election_deadline:
                self.start_election(tick)
        else:  # follower
            if tick >= self.election_deadline:
                self.start_election(tick)

    # ---------------- Elections ----------------

    def start_election(self, tick):
        self.currentTerm += 1
        self.state = "candidate"
        self.votedFor = self.id
        self.votes_received = {self.id}
        self.reset_election_timer(tick)
        last_idx = len(self.log) - 1  # 0-indexed last index
        last_term = self.log[last_idx].term if last_idx >= 0 else 0
        for dst in range(self.n):
            if dst == self.id:
                continue
            self.sim.send(Msg(
                "RV", self.id, dst, tick + MSG_DELAY,
                term=self.currentTerm,
                cand_last_index=last_idx,
                cand_last_term=last_term,
            ))

    def become_leader(self, tick):
        self.state = "leader"
        # Initialize leader volatile state (1-indexed for clarity, store as 0-indexed length)
        last_len = len(self.log)
        self.nextIndex = [last_len] * self.n
        self.matchIndex = [0] * self.n
        # Leader has all its own log entries
        if last_len > 0:
            self.matchIndex[self.id] = last_len - 1  # highest 0-indexed replicated index
        # Send initial heartbeat (and any pending entries)
        self.broadcast_append_entries(tick)
        self.last_heartbeat_tick = tick

    # ---------------- AppendEntries ----------------

    def broadcast_append_entries(self, tick):
        for dst in range(self.n):
            if dst == self.id:
                continue
            self.send_append_entries(dst, tick)

    def send_append_entries(self, dst, tick):
        if self.nextIndex is None:
            return
        ni = self.nextIndex[dst]  # 0-indexed length: e.g. 5 means next entry to send is log[5]
        prev_idx = ni - 1
        if prev_idx >= 0 and prev_idx < len(self.log):
            prev_term = self.log[prev_idx].term
        else:
            prev_term = 0
        # Send entries [ni .. end]
        entries = self.log[ni:]
        entries_data = [(e.term, e.cmd) for e in entries]
        self.sim.send(Msg(
            "AE", self.id, dst, tick + MSG_DELAY,
            term=self.currentTerm,
            prev_log_index=prev_idx,
            prev_log_term=prev_term,
            entries=entries_data,
            leader_commit=self.commitIndex,
        ))

    def handle_msg(self, msg, tick):
        kind = msg.kind
        if kind == "RV":
            self._handle_rv(msg, tick)
        elif kind == "RV_resp":
            self._handle_rv_resp(msg, tick)
        elif kind == "AE":
            self._handle_ae(msg, tick)
        elif kind == "AE_resp":
            self._handle_ae_resp(msg, tick)

    def _handle_rv(self, msg, tick):
        term = msg.data["term"]
        cand_last_idx = msg.data["cand_last_index"]
        cand_last_term = msg.data["cand_last_term"]
        my_last_idx = len(self.log) - 1
        my_last_term = self.log[my_last_idx].term if my_last_idx >= 0 else 0
        if term < self.currentTerm:
            self.sim.send(Msg("RV_resp", self.id, msg.src, tick + MSG_DELAY,
                              term=self.currentTerm, granted=False))
            return
        if term > self.currentTerm:
            self.currentTerm = term
            self.state = "follower"
            self.votedFor = None
            self.votes_received = set()
        up_to_date = (cand_last_term > my_last_term) or (
            cand_last_term == my_last_term and cand_last_idx >= my_last_idx
        )
        if (self.votedFor is None or self.votedFor == msg.src) and up_to_date:
            self.votedFor = msg.src
            self.reset_election_timer(tick)
            self.sim.send(Msg("RV_resp", self.id, msg.src, tick + MSG_DELAY,
                              term=self.currentTerm, granted=True))
        else:
            self.sim.send(Msg("RV_resp", self.id, msg.src, tick + MSG_DELAY,
                              term=self.currentTerm, granted=False))

    def _handle_rv_resp(self, msg, tick):
        if msg.data["term"] > self.currentTerm:
            self.currentTerm = msg.data["term"]
            self.state = "follower"
            self.votedFor = None
            self.votes_received = set()
            return
        if self.state != "candidate" or msg.data["term"] != self.currentTerm:
            return
        if msg.data["granted"]:
            self.votes_received.add(msg.src)
            if len(self.votes_received) > self.n / 2:
                self.become_leader(tick)

    def _handle_ae(self, msg, tick):
        term = msg.data["term"]
        if term < self.currentTerm:
            self.sim.send(Msg("AE_resp", self.id, msg.src, tick + MSG_DELAY,
                              term=self.currentTerm, success=False, match_index=-1))
            return
        if term > self.currentTerm:
            self.currentTerm = term
            self.state = "follower"
            self.votedFor = None
            self.votes_received = set()
        # Reset election timer (valid AppendEntries from current/recognized leader)
        self.reset_election_timer(tick)
        prev_idx = msg.data["prev_log_index"]
        prev_term = msg.data["prev_log_term"]
        if prev_idx >= len(self.log):
            # Follower log too short; reply with conflict at len-1
            self.sim.send(Msg("AE_resp", self.id, msg.src, tick + MSG_DELAY,
                              term=self.currentTerm, success=False, match_index=len(self.log) - 1))
            return
        if prev_idx >= 0 and self.log[prev_idx].term != prev_term:
            # Find first index of conflicting term
            conflict_term = self.log[prev_idx].term
            first_idx = prev_idx
            while first_idx > 0 and self.log[first_idx - 1].term == conflict_term:
                first_idx -= 1
            self.sim.send(Msg("AE_resp", self.id, msg.src, tick + MSG_DELAY,
                              term=self.currentTerm, success=False, match_index=first_idx - 1))
            return
        # Log consistent: truncate and append new entries
        old_len = len(self.log)
        entries = msg.data["entries"]
        # Truncate to prev_idx + 1
        self.log = self.log[: prev_idx + 1]
        # Append (these are cmd ids; we need to track replication)
        new_entries_added = []
        for (e_term, e_cmd) in entries:
            self.log.append(LogEntry(e_term, e_cmd))
            new_entries_added.append(e_cmd)
        # Update commitIndex from leader_commit (only for entries the leader claims committed)
        leader_commit = msg.data["leader_commit"]
        if leader_commit > self.commitIndex:
            old_c = self.commitIndex
            # Cannot commit beyond what we have
            self.commitIndex = min(leader_commit, len(self.log) - 1)
            if self.commitIndex != old_c:
                self.sim.notify_follower_commit(self.id, self.commitIndex, tick)
        # Track which new entries were replicated (this node, this tick)
        if new_entries_added:
            self.sim.notify_replication(self.id, new_entries_added, tick)
        # Reply success with current last index
        self.sim.send(Msg("AE_resp", self.id, msg.src, tick + MSG_DELAY,
                          term=self.currentTerm, success=True, match_index=len(self.log) - 1))

    def _handle_ae_resp(self, msg, tick):
        if msg.data["term"] > self.currentTerm:
            self.currentTerm = msg.data["term"]
            self.state = "follower"
            self.votedFor = None
            self.votes_received = set()
            return
        if self.state != "leader" or msg.data["term"] != self.currentTerm:
            return
        dst = msg.src
        if msg.data["success"]:
            mi = msg.data["match_index"]  # 0-indexed highest replicated
            if mi > self.matchIndex[dst]:
                self.matchIndex[dst] = mi
            new_ni = mi + 1
            if new_ni > self.nextIndex[dst]:
                self.nextIndex[dst] = new_ni
        else:
            mi = msg.data["match_index"]
            new_ni = max(0, mi + 1)
            if new_ni < self.nextIndex[dst]:
                self.nextIndex[dst] = new_ni
            # Retry
            self.send_append_entries(dst, tick)

    # ---------------- Commit advance ----------------

    def maybe_advance_commit(self, tick):
        """For a leader, check if commitIndex can advance (Raft Figure 2 rule)."""
        if self.state != "leader":
            return
        if not self.log:
            return
        # matchIndex[] is a list of 0-indexed "highest replicated index" for each
        # follower (including self). We sort descending and take the majority's
        # value. For N=3 majority=2 -> index 1 (2nd largest). For N=5 majority=3
        # -> index 2 (3rd largest). Python: majority_idx = (N-1)//2 means: the
        # count of elements strictly greater than a value at index majority_idx
        # is majority_idx; we need majority count.
        sorted_mi = sorted(self.matchIndex, reverse=True)
        # The number of elements >= sorted_mi[i] is i+1 (descending order).
        # For majority: we want the largest i such that i+1 > N/2.
        # i.e. the median (or higher) element.
        majority_count = self.n // 2 + 1
        # The largest replicated index with at least majority_count followers
        # having >= that index.
        N_high = sorted_mi[majority_count - 1]  # 0-indexed highest replicated
        # The commit rule also requires log[N_high].term == currentTerm.
        if (N_high > self.commitIndex
                and N_high < len(self.log)
                and self.log[N_high].term == self.currentTerm):
            old_c = self.commitIndex
            self.commitIndex = N_high
            self.sim.notify_leader_commit(self.commitIndex, tick)


class Simulator:
    """Drives the simulation: time, messages, statistics."""

    def __init__(self, n, seed):
        self.n = n
        self.rng = random.Random(seed)
        self.tick = 0
        self.nodes = []
        self.mailbox = []  # list of Msg
        self.leader = None
        # Per-entry stats (cmd id -> int index in leader's log)
        # We treat each command as an "entry index" (1..1000).
        self.append_tick = {}        # entry_idx -> tick when leader appended
        self.replicated_at = {}      # entry_idx -> {node_id: tick}
        self.committed_at = {}       # entry_idx -> tick when commitIndex reached it
        # CommitIndex history for leader (tick, commitIndex) snapshots whenever it changes
        self.commit_history = []     # list of (tick, commitIndex)
        # Init nodes
        for i in range(self.n):
            node = Node(i, n, self, self.rng)
            self.nodes.append(node)
        for node in self.nodes:
            node.reset_election_timer(0)

    # ---------------- Message passing ----------------

    def send(self, msg):
        self.mailbox.append(msg)

    def deliver_messages(self, tick):
        delivered = [m for m in self.mailbox if m.deliver_at <= tick]
        self.mailbox = [m for m in self.mailbox if m.deliver_at > tick]
        # Stable order to keep deterministic
        delivered.sort(key=lambda m: (m.deliver_at, m.kind, m.src, m.dst))
        for msg in delivered:
            self.nodes[msg.dst].handle_msg(msg, tick)

    # ---------------- Step ----------------

    def step(self):
        tick = self.tick
        self.deliver_messages(tick)
        for node in self.nodes:
            node.on_tick(tick)
        # After tick actions, record commitIndex snapshot for the leader (if any)
        leader = self._current_leader()
        if leader is not None:
            if (not self.commit_history) or self.commit_history[-1][1] != leader.commitIndex:
                self.commit_history.append((tick, leader.commitIndex))
        self.tick += 1

    def _current_leader(self):
        for node in self.nodes:
            if node.state == "leader":
                return node
        return None

    # ---------------- Leader election ----------------

    def run_until_leader(self, max_ticks=5000):
        while self.tick < max_ticks:
            self.step()
            leader = self._current_leader()
            if leader is not None:
                self.leader = leader
                return leader, self.tick
        return None, self.tick

    # ---------------- Client command submission ----------------

    def submit_command(self, cmd, tick):
        """Submit a command to the current leader (assumes leader is stable)."""
        leader = self.leader
        leader.log.append(LogEntry(leader.currentTerm, cmd))
        idx = len(leader.log) - 1
        self.append_tick[idx] = tick
        self.replicated_at[idx] = {leader.id: tick}
        # Update leader's matchIndex for itself (leader has all its own log)
        leader.matchIndex[leader.id] = idx
        # Trigger immediate replication to all followers
        leader.broadcast_append_entries(tick)
        leader.last_heartbeat_tick = tick  # avoid immediate duplicate
        # Try to advance commit immediately (single node = self, need majority)
        # For N=3 we need at least 1 follower; for N=5 we need at least 2.
        # Won't happen until followers ack.

    # ---------------- Stats callbacks ----------------

    def notify_replication(self, node_id, cmds, tick):
        """Called by follower when it has newly replicated a set of entries
        (via AE)."""
        for cmd in cmds:
            idx = cmd - 1  # cmd ids start at 1, so entry index = cmd - 1
            if idx not in self.replicated_at:
                self.replicated_at[idx] = {}
            self.replicated_at[idx][node_id] = tick

    def notify_follower_commit(self, node_id, new_commit_index, tick):
        """Called by follower when its commitIndex advances (from leaderCommit
        in AE). Records commit tick for any newly committed entries (follower
        view)."""
        # For monotonicity / commit-tracking purposes, we focus on the leader's
        # commitIndex, which is what drives commits. (Follower commitIndex can
        # lag by MSG_DELAY.) So we only need this for sanity / debugging.
        pass

    def notify_leader_commit(self, new_commit_index, tick):
        """Called by leader when commitIndex advances. Records per-entry tick
        for any newly committed entries."""
        for idx in range(0, new_commit_index + 1):
            if idx not in self.committed_at:
                self.committed_at[idx] = tick

    # ---------------- High-level run ----------------

    def run_experiment(self, num_commands=1000, max_ticks=20000, submit_per_tick=10):
        """Submit num_commands to the leader (submit_per_tick per tick),
        then continue ticking until all are committed or max_ticks reached."""
        # Phase 1: elect leader
        leader, elected_at_tick = self.run_until_leader()
        if leader is None:
            return {"error": "no_leader_elected"}
        # Phase 2: submit commands and tick until all committed
        next_cmd = 1
        submitted = 0
        while self.tick < max_ticks:
            # Submit up to submit_per_tick commands this tick
            for _ in range(submit_per_tick):
                if submitted >= num_commands:
                    break
                self.submit_command(next_cmd, self.tick)
                next_cmd += 1
                submitted += 1
            self.step()
            # Stop early if all commands committed
            if (len(self.committed_at) >= num_commands
                    and min(self.committed_at.keys()) >= 0
                    and max(k for k in self.committed_at.keys()) >= num_commands - 1):
                break
        return self.collect_stats(num_commands)

    def collect_stats(self, num_commands):
        """Collect final statistics about replication and commit."""
        latencies = []
        replication_counts = []
        committed_flags = []
        append_ticks = []
        commit_ticks = []
        all_committed = True
        for idx in range(num_commands):
            cmd = idx + 1
            at = self.append_tick.get(idx)
            ct = self.committed_at.get(idx)
            rep = self.replicated_at.get(idx, {})
            rc = len(rep)
            committed = ct is not None
            if not committed:
                all_committed = False
            replication_counts.append(rc)
            committed_flags.append(1 if committed else 0)
            append_ticks.append(at)
            commit_ticks.append(ct)
            if committed:
                latencies.append(ct - at)
            else:
                latencies.append(None)
        # commitIndex monotonicity
        monotonic = True
        prev_ci = -2
        for _, ci in self.commit_history:
            if ci < prev_ci:
                monotonic = False
                break
            prev_ci = ci
        # Latency stats (only over committed entries)
        ok_lat = [l for l in latencies if l is not None]
        if ok_lat:
            mean_lat = sum(ok_lat) / len(ok_lat)
            sorted_lat = sorted(ok_lat)
            med_lat = sorted_lat[len(sorted_lat) // 2]
            max_lat = max(ok_lat)
            min_lat = min(ok_lat)
        else:
            mean_lat = med_lat = max_lat = min_lat = None
        return {
            "n": self.n,
            "num_commands": num_commands,
            "all_committed": all_committed,
            "committed_count": len(ok_lat),
            "latency_mean": mean_lat,
            "latency_median": med_lat,
            "latency_max": max_lat,
            "latency_min": min_lat,
            "monotonic_commitIndex": monotonic,
            "commit_history_len": len(self.commit_history),
            "final_tick": self.tick,
            # Per-entry data
            "latencies": latencies,
            "replication_counts": replication_counts,
            "committed_flags": committed_flags,
            "append_ticks": append_ticks,
            "commit_ticks": commit_ticks,
            "commit_history": self.commit_history,
        }