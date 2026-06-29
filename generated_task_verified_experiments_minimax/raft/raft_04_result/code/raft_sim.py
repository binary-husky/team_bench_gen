"""
In-process Raft simulator.
- Logical tick clock
- Deterministic (per seed) randomness for shuffled timeouts / peer ordering
- In-memory message queues, no real network / sockets
- Each node runs election, log replication, and commit logic per tick
- Leader can be "killed" mid-stream; remaining nodes must elect a new leader,
  continue committing, and keep the pre-fault committed entries intact.
"""
import random
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


# ---------- Messages ---------------------------------------------------------

@dataclass
class RequestVote:
    term: int
    candidate_id: int
    last_log_index: int
    last_log_term: int


@dataclass
class RequestVoteResponse:
    term: int
    voter_id: int
    vote_granted: bool


@dataclass
class AppendEntries:
    term: int
    leader_id: int
    prev_log_index: int
    prev_log_term: int
    entries: List
    leader_commit: int


@dataclass
class AppendEntriesResponse:
    term: int
    follower_id: int
    success: bool
    match_index: int  # for leader to update nextIndex/matchIndex


# ---------- Log Entry --------------------------------------------------------

@dataclass
class LogEntry:
    term: int
    command: Any


# ---------- Server States ----------------------------------------------------

FOLLOWER = "follower"
CANDIDATE = "candidate"
LEADER = "leader"


# ---------- Server -----------------------------------------------------------

class Server:
    def __init__(self, server_id: int, peers: List[int], rng: random.Random,
                 election_timeout_range):
        self.id = server_id
        self.peers = peers
        self.rng = rng
        self.election_timeout_range = election_timeout_range
        # persistent
        self.current_term = 0
        self.voted_for: Optional[int] = None
        # log[0] is a sentinel (term 0, no command), matching Raft's 1-indexed convention
        self.log: List[LogEntry] = [LogEntry(term=0, command=None)]
        # volatile
        self.commit_index = 0
        self.last_applied = 0
        self.role = FOLLOWER
        self.leader_id: Optional[int] = None
        # leader-only
        self.next_index: Dict[int, int] = {}
        self.match_index: Dict[int, int] = {}
        # election
        self.votes_received: set = set()
        self.election_elapsed = 0
        self.election_timeout = self._reset_election_timeout()
        # leader
        self.heartbeat_elapsed = 0
        # kill switch
        self.alive = True

    # ----- helpers --------------------------------------------------------

    def _reset_election_timeout(self):
        lo, hi = self.election_timeout_range
        # inclusive of both ends
        self.election_timeout = self.rng.randint(lo, hi)
        self.election_elapsed = 0
        return self.election_timeout

    def last_log_index(self) -> int:
        return len(self.log) - 1

    def last_log_term(self) -> int:
        if len(self.log) > 1:
            return self.log[-1].term
        return 0

    def log_term_at(self, index: int) -> int:
        if 0 < index < len(self.log):
            return self.log[index].term
        return 0

    # ----- term / step handling -------------------------------------------

    def _step_down(self, term: int, leader_hint: Optional[int] = None):
        self.current_term = term
        self.voted_for = None
        self.role = FOLLOWER
        self.leader_id = leader_hint
        self._reset_election_timeout()
        self.votes_received.clear()

    # ----- election --------------------------------------------------------

    def _start_election(self, outbox: List):
        self.current_term += 1
        self.role = CANDIDATE
        self.voted_for = self.id
        self.votes_received = {self.id}
        self.leader_id = None
        self._reset_election_timeout()
        last_idx = self.last_log_index()
        last_term = self.last_log_term()
        for peer in self.peers:
            outbox.append((peer, RequestVote(
                term=self.current_term,
                candidate_id=self.id,
                last_log_index=last_idx,
                last_log_term=last_term,
            )))

    def _handle_request_vote(self, msg: RequestVote, outbox: List):
        # If RPC term > currentTerm, step down
        if msg.term > self.current_term:
            self._step_down(msg.term)
        granted = False
        if msg.term >= self.current_term and (self.voted_for is None or self.voted_for == msg.candidate_id):
            up_to_date = (msg.last_log_term > self.last_log_term()) or \
                         (msg.last_log_term == self.last_log_term() and
                          msg.last_log_index >= self.last_log_index())
            if up_to_date:
                granted = True
                self.voted_for = msg.candidate_id
                self._reset_election_timeout()  # grant vote resets timer
        outbox.append((msg.candidate_id, RequestVoteResponse(
            term=self.current_term,
            voter_id=self.id,
            vote_granted=granted,
        )))

    def _handle_vote_response(self, msg: RequestVoteResponse, outbox: List, node_count: int):
        if self.role != CANDIDATE:
            return
        if msg.term > self.current_term:
            self._step_down(msg.term)
            return
        if msg.term != self.current_term:
            return  # stale
        if msg.vote_granted:
            self.votes_received.add(msg.voter_id)
        if len(self.votes_received) * 2 > node_count:
            self._become_leader(outbox)

    def _become_leader(self, outbox: List):
        # append a no-op entry (Raft §8); we model it implicitly with a real entry,
        # but for safety only entries after the no-op can be considered committed.
        # We'll just initialize leader state.
        self.role = LEADER
        self.leader_id = self.id
        self.next_index = {p: self.last_log_index() + 1 for p in self.peers}
        self.match_index = {p: 0 for p in self.peers}
        # send immediate heartbeats
        self._send_append_entries(outbox, batch_size=None)

    # ----- append entries -------------------------------------------------

    def _send_append_entries(self, outbox: List, batch_size: Optional[int]):
        if self.role != LEADER:
            return
        for peer in self.peers:
            ni = self.next_index[peer]
            prev_index = ni - 1
            prev_term = self.log_term_at(prev_index)
            if batch_size is None:
                # heartbeat: empty entries
                entries: List[LogEntry] = []
            else:
                start = ni
                end = min(len(self.log), start + batch_size)
                entries = self.log[start:end]
            outbox.append((peer, AppendEntries(
                term=self.current_term,
                leader_id=self.id,
                prev_log_index=prev_index,
                prev_log_term=prev_term,
                entries=entries,
                leader_commit=self.commit_index,
            )))

    def _handle_append_entries(self, msg: AppendEntries, outbox: List):
        if msg.term > self.current_term:
            self._step_down(msg.term, leader_hint=msg.leader_id)
        if msg.term < self.current_term:
            # reject stale
            outbox.append((msg.leader_id, AppendEntriesResponse(
                term=self.current_term, follower_id=self.id,
                success=False, match_index=0,
            )))
            return
        # accept the leader
        self.role = FOLLOWER
        self.leader_id = msg.leader_id
        self._reset_election_timeout()
        # consistency check
        if msg.prev_log_index > 0:
            if msg.prev_log_index >= len(self.log):
                outbox.append((msg.leader_id, AppendEntriesResponse(
                    term=self.current_term, follower_id=self.id,
                    success=False, match_index=len(self.log) - 1,
                )))
                return
            if self.log[msg.prev_log_index].term != msg.prev_log_term:
                # truncate the conflicting suffix
                self.log = self.log[:msg.prev_log_index]
                outbox.append((msg.leader_id, AppendEntriesResponse(
                    term=self.current_term, follower_id=self.id,
                    success=False, match_index=len(self.log) - 1,
                )))
                return
        # append new entries (replacing any conflicting tail)
        index = msg.prev_log_index + 1
        new_entries = msg.entries
        for i, e in enumerate(new_entries):
            if index + i < len(self.log):
                if self.log[index + i].term != e.term:
                    self.log = self.log[:index + i]
                    self.log.append(e)
            else:
                self.log.append(e)
        match_index = msg.prev_log_index + len(new_entries)
        if msg.leader_commit > self.commit_index:
            self.commit_index = min(msg.leader_commit, self.last_log_index())
        outbox.append((msg.leader_id, AppendEntriesResponse(
            term=self.current_term, follower_id=self.id,
            success=True, match_index=match_index,
        )))

    def _handle_append_response(self, msg: AppendEntriesResponse, outbox: List):
        if self.role != LEADER:
            return
        if msg.term > self.current_term:
            self._step_down(msg.term)
            return
        if msg.term != self.current_term:
            return  # stale
        if msg.success:
            self.match_index[msg.follower_id] = max(self.match_index[msg.follower_id], msg.match_index)
            self.next_index[msg.follower_id] = msg.match_index + 1
        else:
            self.next_index[msg.follower_id] = max(1, self.next_index[msg.follower_id] - 1)

    # ----- commit advancement --------------------------------------------

    def _maybe_advance_commit(self, node_count: int):
        if self.role != LEADER:
            return
        # find highest N such that a majority of match_index[i] >= N AND log[N].term == currentTerm
        for n in range(self.last_log_index(), self.commit_index, -1):
            if self.log[n].term != self.current_term:
                continue
            count = 1  # self
            for peer in self.peers:
                if self.match_index.get(peer, 0) >= n:
                    count += 1
            if count * 2 > node_count:
                self.commit_index = n
                break

    # ----- tick ------------------------------------------------------------

    def tick(self, node_count: int, batch_size: int = 64) -> List:
        """Run one logical tick. Returns list of (dst, msg) to deliver."""
        outbox: List = []
        if not self.alive:
            return outbox
        if self.role == LEADER:
            self.heartbeat_elapsed += 1
            if self.heartbeat_elapsed >= 1:  # send every tick
                self._send_append_entries(outbox, batch_size=batch_size)
                self.heartbeat_elapsed = 0
        else:
            self.election_elapsed += 1
            if self.election_elapsed >= self.election_timeout:
                self._start_election(outbox)
        return outbox

    def deliver(self, msg, node_count: int) -> List:
        """Process a single message. Returns list of (dst, reply_msg)."""
        outbox: List = []
        if not self.alive:
            return outbox
        if isinstance(msg, RequestVote):
            self._handle_request_vote(msg, outbox)
        elif isinstance(msg, RequestVoteResponse):
            self._handle_vote_response(msg, outbox, node_count)
        elif isinstance(msg, AppendEntries):
            self._handle_append_entries(msg, outbox)
        elif isinstance(msg, AppendEntriesResponse):
            self._handle_append_response(msg, outbox)
        return outbox


# ---------- Cluster (in-process simulation) --------------------------------

class Cluster:
    def __init__(self, n: int, seed: int, election_timeout_range=(20, 40),
                 batch_size: int = 64, max_ticks: int = 20000):
        self.rng = random.Random(seed)
        self.n = n
        self.ids = list(range(n))
        # build a deterministic shuffled order used for tie-break if needed
        self.peer_order = self.ids[:]
        self.rng.shuffle(self.peer_order)
        self.servers: Dict[int, Server] = {}
        for sid in self.ids:
            peers = [p for p in self.ids if p != sid]
            self.servers[sid] = Server(sid, peers, random.Random(self.rng.random()),
                                       election_timeout_range)
        self.inboxes: Dict[int, deque] = {sid: deque() for sid in self.ids}
        self.outboxes: Dict[int, List] = {sid: [] for sid in self.ids}
        self.tick_num = 0
        self.batch_size = batch_size
        self.max_ticks = max_ticks
        self.killed_leader: Optional[int] = None
        self.kill_tick: Optional[int] = None
        self.new_leader_tick: Optional[int] = None
        self.new_leader_id: Optional[int] = None
        # pre-fault snapshot of committed entries (by command value)
        self.pre_fault_committed_cmds: List[int] = []
        # queue of client requests to deliver
        self.client_queue: deque = deque()
        self.next_cmd = 0
        # leader id cache for fast lookup
        self.leader_id_cache: Optional[int] = None
        self.last_known_leader: Optional[int] = None

    # ----- client requests -------------------------------------------------

    def submit(self, cmd: Any):
        self.client_queue.append(cmd)

    def _client_deliver_to_leader(self):
        if not self.client_queue:
            return
        leader = self.current_leader_id()
        if leader is None:
            return
        cmd = self.client_queue.popleft()
        srv = self.servers[leader]
        if srv.role == LEADER and srv.alive:
            # leader appends to its own log; will replicate next tick
            srv.log.append(LogEntry(term=srv.current_term, command=cmd))

    # ----- main step -------------------------------------------------------

    def step(self):
        # 1) client injects ONE command per tick (if leader alive)
        self._client_deliver_to_leader()
        # 2) every alive server ticks and returns its outbox
        tick_msgs: List = []
        for sid in self.ids:
            srv = self.servers[sid]
            tick_msgs.extend(srv.tick(node_count=self.n, batch_size=self.batch_size))
        # 3) deliver messages to inboxes
        for (dst, msg) in tick_msgs:
            if self.servers[dst].alive:
                self.inboxes[dst].append(msg)
        # 4) each alive server processes its inbox, replies collected into a list
        reply_msgs: List = []
        for sid in self.ids:
            srv = self.servers[sid]
            while self.inboxes[sid]:
                msg = self.inboxes[sid].popleft()
                reply_msgs.extend(srv.deliver(msg, node_count=self.n))
        # 5) place replies into inboxes
        for (dst, msg) in reply_msgs:
            if self.servers[dst].alive:
                self.inboxes[dst].append(msg)
        # 6) commit advancement
        for sid in self.ids:
            self.servers[sid]._maybe_advance_commit(node_count=self.n)
        # 7) bookkeeping
        self.tick_num += 1
        # detect new leader (after kill)
        if self.killed_leader is not None and self.new_leader_id is None:
            lid = self.current_leader_id()
            if lid is not None and lid != self.killed_leader:
                self.new_leader_id = lid
                self.new_leader_tick = self.tick_num

    def current_leader_id(self) -> Optional[int]:
        for sid in self.ids:
            srv = self.servers[sid]
            if srv.alive and srv.role == LEADER:
                return sid
        return None

    def kill(self, server_id: int):
        srv = self.servers[server_id]
        srv.alive = False
        # clear its in/out queues
        self.inboxes[server_id].clear()
        for v in self.outboxes.values():
            v.clear()
        if self.killed_leader is None:
            self.kill_tick = self.tick_num
            self.killed_leader = server_id


# ---------- Experiment harness ---------------------------------------------

def run_one(seed: int,
            n: int = 5,
            election_timeout_range=(20, 40),
            pre_kill_entries: int = 100,
            post_kill_entries: int = 100,
            max_idle_ticks: int = 4000,
            verbose: bool = False) -> Dict[str, Any]:
    cluster = Cluster(n=n, seed=seed, election_timeout_range=election_timeout_range)
    # submit pre_kill entries
    for cmd in range(pre_kill_entries):
        cluster.submit(cmd)
    pre_cmds_submitted = list(range(pre_kill_entries))
    # drive simulation until we have pre_kill_entries committed on a majority
    idle = 0
    last_tick = cluster.tick_num
    while True:
        cluster.step()
        # committed count = min over alive nodes of their commit_index
        commit_counts = [cluster.servers[s].commit_index for s in cluster.ids
                         if cluster.servers[s].alive]
        if commit_counts and min(commit_counts) >= pre_kill_entries:
            break
        if cluster.tick_num == last_tick:
            idle += 1
        else:
            idle = 0
            last_tick = cluster.tick_num
        if idle > max_idle_ticks:
            return {"seed": seed, "error": "pre-kill never committed"}
        if cluster.tick_num > cluster.max_ticks:
            return {"seed": seed, "error": "pre-kill timeout"}

    # snapshot committed commands on a majority
    commits_per_node = [set(e.command for e in cluster.servers[s].log[1:cluster.servers[s].commit_index + 1])
                        for s in cluster.ids if cluster.servers[s].alive]
    # majority consensus on committed commands: every node that committed has
    # the same committed-prefix; just use a "reference" node (the leader if alive,
    # else the one with the highest commit index)
    ref_sid = max(range(n), key=lambda s: cluster.servers[s].commit_index)
    ref_log = cluster.servers[ref_sid].log[:cluster.servers[ref_sid].commit_index + 1]
    pre_fault_committed_cmds = [e.command for e in ref_log[1:]]
    pre_fault_committed_terms = [e.term for e in ref_log[1:]]
    if verbose:
        print(f"[seed {seed}] pre-fault committed={len(pre_fault_committed_cmds)} terms={set(pre_fault_committed_terms)}")

    # kill current leader
    leader = cluster.current_leader_id()
    if leader is None:
        return {"seed": seed, "error": "no leader before kill"}
    if verbose:
        print(f"[seed {seed}] killing leader {leader} at tick {cluster.tick_num}, commit_index={cluster.servers[leader].commit_index}")
    cluster.kill(leader)

    # submit post_kill entries
    for cmd in range(pre_kill_entries, pre_kill_entries + post_kill_entries):
        cluster.submit(cmd)

    # drive simulation until post_kill entries committed (or timeout)
    target = pre_kill_entries + post_kill_entries
    idle = 0
    last_tick = cluster.tick_num
    while True:
        cluster.step()
        # a post-kill entry is "committed" if it appears in some alive node's committed prefix
        any_committed_post = False
        for s in cluster.ids:
            srv = cluster.servers[s]
            if not srv.alive:
                continue
            ci = srv.commit_index
            # committed commands in [1..ci]
            cmds = [e.command for e in srv.log[1:ci + 1]]
            if any(c >= pre_kill_entries for c in cmds):
                any_committed_post = True
                break
        # OR: count the highest committed command across all alive nodes
        max_cmd_committed = 0
        for s in cluster.ids:
            srv = cluster.servers[s]
            if not srv.alive:
                continue
            ci = srv.commit_index
            for e in srv.log[1:ci + 1]:
                if e.command >= pre_kill_entries and e.command < target:
                    max_cmd_committed = max(max_cmd_committed, e.command)
        if max_cmd_committed >= target - 1:
            break
        if cluster.tick_num == last_tick:
            idle += 1
        else:
            idle = 0
            last_tick = cluster.tick_num
        if idle > max_idle_ticks:
            return {"seed": seed, "error": "post-kill idle timeout", "tick": cluster.tick_num}
        if cluster.tick_num > cluster.max_ticks:
            return {"seed": seed, "error": "post-kill max ticks", "tick": cluster.tick_num}

    # survival check: every pre-fault committed entry must still exist
    # in the new leader's log (or any node's log actually) up to its committed
    # prefix. We check the new leader's committed prefix contains all of them.
    if cluster.new_leader_id is None:
        return {"seed": seed, "error": "no new leader after kill"}
    new_leader = cluster.servers[cluster.new_leader_id]
    new_leader_cmds = set(e.command for e in new_leader.log[1:new_leader.commit_index + 1])
    survived = all(c in new_leader_cmds for c in pre_fault_committed_cmds)

    # post-kill commit rate: commands in [pre_kill..target) committed on the new leader
    post_cmds_committed = sum(1 for c in range(pre_kill_entries, target) if c in new_leader_cmds)
    post_commit_rate = post_cmds_committed / post_kill_entries

    # detection+reelection latency: ticks between kill_tick and new_leader_tick
    # (the new leader being elected)
    latency = (cluster.new_leader_tick - cluster.kill_tick) if (
        cluster.new_leader_tick is not None and cluster.kill_tick is not None
    ) else None

    return {
        "seed": seed,
        "n": n,
        "killed_leader": cluster.killed_leader,
        "new_leader": cluster.new_leader_id,
        "kill_tick": cluster.kill_tick,
        "new_leader_tick": cluster.new_leader_tick,
        "detection_reelection_latency_ticks": latency,
        "post_commit_rate": post_commit_rate,
        "post_committed_count": post_cmds_committed,
        "pre_fault_committed_count": len(pre_fault_committed_cmds),
        "pre_fault_survived": survived,
        "election_timeout_range": election_timeout_range,
    }


if __name__ == "__main__":
    import json
    results = []
    for seed in range(10):
        r = run_one(seed=seed, n=5, election_timeout_range=(20, 40),
                    pre_kill_entries=100, post_kill_entries=100, verbose=True)
        results.append(r)
        print(json.dumps(r, default=str))
    print("\nSummary:")
    latencies = [r["detection_reelection_latency_ticks"] for r in results
                 if r.get("detection_reelection_latency_ticks") is not None]
    rates = [r["post_commit_rate"] for r in results]
    survived = [r["pre_fault_survived"] for r in results]
    print(f"latencies mean={sum(latencies)/len(latencies):.2f} max={max(latencies)}")
    print(f"post-commit rate mean={sum(rates)/len(rates):.4f}")
    print(f"survival: {sum(survived)}/{len(survived)}")
