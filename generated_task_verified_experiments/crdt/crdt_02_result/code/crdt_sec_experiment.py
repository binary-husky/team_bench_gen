"""
State-based CRDT (CvRDT) Strong Eventual Consistency (SEC) convergence experiment.

Implements 5 state-based CRDTs in-process (no network); replicas are in-memory
objects and merge messages are exchanged over an in-memory full-mesh topology.

Reference: Shapiro et al., "A comprehensive study of Convergent and Commutative
Replicated Data Types" (2011), crdt_material/crdt_shapiro_2011.pdf .

For every CvRDT, merge(x,y) == x ⊔ y (least upper bound over the state partial
order), which is commutative, idempotent and associative -> states form a
monotonic join-semilattice -> Strong Eventual Consistency holds (Def. 2.4/2.5).
"""

import random
import copy
import statistics

CRDT_NAMES = ["G-Counter", "PN-Counter", "G-Set", "OR-Set", "LWW-Register"]
ELEMENT_POOL = [f"e{i}" for i in range(40)]   # small pool so adds/removes overlap


# --------------------------------------------------------------------------- #
#  CvRDT implementations  (each: local update(s) + merge = join)              #
# --------------------------------------------------------------------------- #
def _vmax_into(a, b):
    """Component-wise max of equal-length int lists, in place. Returns changed."""
    changed = False
    for i in range(len(a)):
        if b[i] > a[i]:
            a[i] = b[i]
            changed = True
    return changed


class GCounter:
    """G-Counter (Spec. 6): payload = vector P, one entry per replica.
    increment(i): P[i]+=1 ; merge = component-wise max ; value = sum(P)."""
    def __init__(self, n):
        self.P = [0] * n

    def increment(self, i):
        self.P[i] += 1

    def merge(self, other):
        return _vmax_into(self.P, other.P)

    def value(self):
        return sum(self.P)

    def state(self):
        return tuple(self.P)                 # canonical state

    def equal(self, other):
        return self.P == other.P


class PNCounter:
    """PN-Counter (Spec. 7): two G-Counters P (increments) and N (decrements).
    value = sum(P) - sum(N) ; merge = merge both."""
    def __init__(self, n):
        self.P = [0] * n
        self.N = [0] * n

    def increment(self, i):
        self.P[i] += 1

    def decrement(self, i):
        self.N[i] += 1

    def merge(self, other):
        c1 = _vmax_into(self.P, other.P)
        c2 = _vmax_into(self.N, other.N)
        return c1 or c2

    def value(self):
        return sum(self.P) - sum(self.N)

    def state(self):
        return (tuple(self.P), tuple(self.N))

    def equal(self, other):
        return self.P == other.P and self.N == other.N


class GSet:
    """G-Set (Spec. 11): grow-only set. add(e): S|= {e} ; merge = union."""
    def __init__(self):
        self.S = set()

    def add(self, e):
        self.S.add(e)

    def merge(self, other):
        before = len(self.S)
        self.S |= other.S
        return len(self.S) != before

    def value(self):
        return frozenset(self.S)

    def state(self):
        return frozenset(self.S)

    def equal(self, other):
        return self.S == other.S


class ORSet:
    """Observed-Remove Set (Spec. 15): payload set S of (element, unique-tag).
    add(e): S |= {(e, fresh-tag)} ; remove(e): S \\= observed pairs {(e,u) in S} ;
    merge = union of pairs. Internally dict element -> set(tags)."""
    def __init__(self):
        self.M = {}                          # element -> set of unique tags

    def add(self, tag, e):
        self.M.setdefault(e, set()).add(tag)

    def remove(self, e):
        if e in self.M:                      # remove all currently-observed tags
            del self.M[e]

    def merge(self, other):
        changed = False
        for e, tags in other.M.items():
            cur = self.M.get(e)
            if cur is None:
                self.M[e] = set(tags)
                changed = True
            else:
                new = tags - cur
                if new:
                    cur |= new
                    changed = True
        return changed

    def value(self):
        return frozenset(e for e, tags in self.M.items() if tags)

    def state(self):
        pairs = set()
        for e, tags in self.M.items():
            for t in tags:
                pairs.add((e, t))
        return frozenset(pairs)              # canonical state (element,tag) set

    def equal(self, other):
        return self.state() == other.state()


class LWWRegister:
    """LWW-Register (Spec. 10): payload (value, timestamp). set(v): assign new
    timestamp ; merge = keep the higher timestamp. Timestamp is a totally
    ordered (logical_clock, node_id) pair (Lamport-style, node_id breaks ties)
    so merges are unambiguous and form a join-semilattice."""
    def __init__(self):
        self.val = None
        self.ts = (-1, -1)                   # (clock, node_id); larger wins

    def set(self, value, clock, node):
        ts = (clock, node)
        if ts > self.ts:                     # local set always advances
            self.val, self.ts = value, ts

    def merge(self, other):
        if other.ts > self.ts:
            self.val, self.ts = other.val, other.ts
            return True
        return False

    def value(self):
        return self.val

    def state(self):
        return (self.val, self.ts)

    def equal(self, other):
        return self.ts == other.ts           # ts equal => val equal too


# --------------------------------------------------------------------------- #
#  Replica: one in-memory node carrying one instance of each CRDT            #
# --------------------------------------------------------------------------- #
class Replica:
    def __init__(self, rid, n):
        self.rid = rid
        self.n = n
        self.gc = GCounter(n)
        self.pn = PNCounter(n)
        self.gs = GSet()
        self.orset = ORSet()
        self.lww = LWWRegister()
        # per-replica logical clocks for unique tag / timestamp generation
        self.or_clock = 0
        self.lww_clock = 0

    def crdts(self):
        return {
            "G-Counter": self.gc,
            "PN-Counter": self.pn,
            "G-Set": self.gs,
            "OR-Set": self.orset,
            "LWW-Register": self.lww,
        }


def do_local_op(rep, rng):
    """Apply one random local update, uniformly mixing all 5 CRDT types."""
    kind = rng.randrange(5)
    if kind == 0:                                   # G-Counter increment
        rep.gc.increment(rep.rid)
    elif kind == 1:                                 # PN-Counter inc/dec
        if rng.random() < 0.5:
            rep.pn.increment(rep.rid)
        else:
            rep.pn.decrement(rep.rid)
    elif kind == 2:                                 # G-Set add
        rep.gs.add(rng.choice(ELEMENT_POOL))
    elif kind == 3:                                 # OR-Set add / remove
        e = rng.choice(ELEMENT_POOL)
        if rng.random() < 0.35 and e in rep.orset.M:
            rep.orset.remove(e)
        else:
            rep.or_clock += 1
            rep.orset.add((rep.rid, rep.or_clock), e)
    else:                                           # LWW-Register set
        rep.lww_clock += 1
        rep.lww.set(rng.randrange(1000), rep.lww_clock, rep.rid)


def local_phase(replicas, total_ops, rng):
    """Each replica executes a random local-op sequence; total ops ~ total_ops."""
    per = total_ops // len(replicas)
    for rep in replicas:
        for _ in range(per):
            do_local_op(rep, rng)


def snapshot(replicas):
    """Deep-copy every replica's full CRDT payload (synchronous-round semantics)."""
    snaps = []
    for r in replicas:
        snaps.append({k: copy.deepcopy(c) for k, c in r.crdts().items()})
    return snaps


def converged_states_equal(replicas):
    """Return per-CRDT bool: do all replicas hold the identical canonical state?"""
    out = {}
    for name in CRDT_NAMES:
        states = [r.crdts()[name].state() for r in replicas]
        out[name] = all(s == states[0] for s in states)
    return out


def converged_values_equal(replicas):
    """Sanity: do all replicas agree on the user-visible value (query result)?"""
    out = {}
    for name in CRDT_NAMES:
        vals = [r.crdts()[name].value() for r in replicas]
        out[name] = all(v == vals[0] for v in vals)
    return out


# --------------------------------------------------------------------------- #
#  Exchange model A: deterministic synchronous FULL-MESH broadcast            #
#  Each round every replica pushes its full state to all N-1 peers and        #
#  merges all incoming (merging from the round-start snapshot).               #
# --------------------------------------------------------------------------- #
def run_fullmesh(replicas, max_rounds=100):
    rounds = 0
    while True:
        rounds += 1
        snaps = snapshot(replicas)
        changed = False
        for i, r in enumerate(replicas):
            for j in range(len(replicas)):
                if i == j:
                    continue
                for name, c in r.crdts().items():
                    if c.merge(snaps[j][name]):
                        changed = True
        if not changed:
            break
        if rounds >= max_rounds:
            break
    return rounds


# --------------------------------------------------------------------------- #
#  Exchange model B: epidemic push-pull GOSSIP over the full-mesh topology.   #
#  Each round every replica picks a uniformly-random peer and both merge      #
#  each other's full state (merging from round-start snapshot). Classic       #
#  anti-entropy; rounds scale ~O(log N).                                       #
# --------------------------------------------------------------------------- #
def run_gossip(replicas, rng, max_rounds=2000):
    n = len(replicas)
    rounds = 0
    while True:
        rounds += 1
        snaps = snapshot(replicas)
        # pick one random peer per replica this round (push-pull, bidirectional)
        peers = []
        for i in range(n):
            j = i
            while j == i:
                j = rng.randrange(n)
            peers.append(j)
        changed = False
        for i in range(n):
            j = peers[i]
            for name, c in enumerate_pairs(replicas[i], snaps[j]):
                if c.merge(snaps[j][name]):
                    changed = True
            for name, c in enumerate_pairs(replicas[j], snaps[i]):
                if c.merge(snaps[i][name]):
                    changed = True
        if not changed:
            break
        if rounds >= max_rounds:
            break
    return rounds


def enumerate_pairs(replica, snap):
    for name in CRDT_NAMES:
        yield name, replica.crdts()[name]


# --------------------------------------------------------------------------- #
#  Experiment driver                                                          #
# --------------------------------------------------------------------------- #
SEEDS = list(range(8))      # 8 seeds per N (>= 5 required)
NS = [3, 4, 5]


def run_experiment():
    results = {N: {m: {"fullmesh": [], "gossip": [],
                       "ok_fullmesh": [], "ok_gossip": [],
                       "total_ops": []} for m in CRDT_NAMES} for N in NS}
    # rounds are shared across CRDTs inside one run (one replica carries all 5),
    # so we also keep a per-(N,seed, model) aggregate.
    rounds_fullmesh = {N: [] for N in NS}
    rounds_gossip = {N: [] for N in NS}
    allcrdt_ok_fullmesh = {N: [] for N in NS}   # all 5 CRDTs converged (bool)
    allcrdt_ok_gossip = {N: [] for N in NS}

    for N in NS:
        for seed in SEEDS:
            rng = random.Random(seed * 1009 + N * 37)
            total_ops = rng.randint(1000, 10000)   # 1e3-1e4 mixed updates

            # ---- Model A: synchronous full-mesh ----
            reps = [Replica(i, N) for i in range(N)]
            local_phase(reps, total_ops, rng)
            rf = run_fullmesh(reps)
            eqf = converged_states_equal(reps)
            vlf = converged_values_equal(reps)
            rounds_fullmesh[N].append(rf)
            allcrdt_ok_fullmesh[N].append(all(eqf.values()) and all(vlf.values()))
            for m in CRDT_NAMES:
                results[N][m]["ok_fullmesh"].append(eqf[m] and vlf[m])
                results[N][m]["fullmesh"].append(rf)
                results[N][m]["total_ops"].append(total_ops)

            # ---- Model B: gossip (fresh identical workload, same seed) ----
            rng2 = random.Random(seed * 1009 + N * 37)
            total_ops2 = rng2.randint(1000, 10000)  # same as total_ops (same seed)
            reps2 = [Replica(i, N) for i in range(N)]
            local_phase(reps2, total_ops2, rng2)
            rg = run_gossip(reps2, rng2)
            eqg = converged_states_equal(reps2)
            vlg = converged_values_equal(reps2)
            rounds_gossip[N].append(rg)
            allcrdt_ok_gossip[N].append(all(eqg.values()) and all(vlg.values()))
            for m in CRDT_NAMES:
                results[N][m]["ok_gossip"].append(eqg[m] and vlg[m])
                results[N][m]["gossip"].append(rg)

    return (results, rounds_fullmesh, rounds_gossip,
            allcrdt_ok_fullmesh, allcrdt_ok_gossip)


def main():
    (results, rf, rg, okf, okg) = run_experiment()

    print("=" * 78)
    print("SEC CONVERGENCE EXPERIMENT  (5 CvRDTs, full-mesh, deterministic seeds)")
    print("=" * 78)
    for N in NS:
        ops = results[N]["G-Counter"]["total_ops"]
        print(f"\nN = {N} replicas | seeds = {len(SEEDS)} | total_ops/run (mixed) "
              f"range [{min(ops)},{max(ops)}]")
        print(f"  Model A synchronous full-mesh: all-CRDT converged = "
              f"{sum(okf[N])}/{len(okf[N])}  mean rounds = "
              f"{statistics.mean(rf[N]):.2f}")
        print(f"  Model B random gossip:         all-CRDT converged = "
              f"{sum(okg[N])}/{len(okg[N])}  mean rounds = "
              f"{statistics.mean(rg[N]):.2f}")
        print("  per-CRDT correctness (state AND value equal across all replicas):")
        for m in CRDT_NAMES:
            cf = sum(results[N][m]["ok_fullmesh"])
            cg = sum(results[N][m]["ok_gossip"])
            print(f"    {m:14s}  fullmesh {cf}/{len(SEEDS)}   "
                  f"gossip {cg}/{len(SEEDS)}")

    # One worked example: show converged values are identical across replicas.
    print("\n" + "-" * 78)
    print("Worked example (N=5, seed=0) — converged query values per replica:")
    rng = random.Random(0 * 1009 + 5 * 37)
    reps = [Replica(i, 5) for i in range(5)]
    local_phase(reps, rng.randint(1000, 10000), rng)
    run_fullmesh(reps)
    hdr = "replica |  GCounter  PNCounter  GSet#  ORSet#  LWW"
    print(hdr)
    print("-" * len(hdr))
    for r in reps:
        print(f"   {r.rid}    |   {r.gc.value():6d}   {r.pn.value():7d}   "
              f"{len(r.gs.value()):4d}   {len(r.orset.value()):5d}   "
              f"{r.lww.value()}")
    eq = converged_states_equal(reps)
    print("  state-equal across all 5 replicas:",
          {k: bool(v) for k, v in eq.items()})


if __name__ == "__main__":
    main()
