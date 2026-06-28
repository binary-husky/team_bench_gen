#!/usr/bin/env python3
"""
State-based CRDT order/duplication invariance experiment.

Verifies, in-process, that the `merge` of four state-based CRDTs
(G-Counter, PN-Counter, OR-Set, LWW-Register) as defined in
Shapiro, Preguiça, Baquero, Zawirski: "A comprehensive study of
Convergent and Commutative Replicated Data Types", Inria RR-7506, 2011
(Spec. 6, 7, 8, 15) converges to a UNIQUE final state under arbitrary
message reordering and duplication (merge is commutative + associative +
idempotent), and contrasts this with naive non-CRDT controls whose final
state depends on delivery order / repetition.

Reference specifications used (from the supplied material):
  - Spec 6  G-Counter      : payload int[n] P ; merge = element-wise max
  - Spec 7  PN-Counter     : payload int[n] P,int[n] N ; merge = elem-wise max of both
  - Spec 8  LWW-Register   : payload (x, t) ; merge = keep larger timestamp (deterministic tie-break)
  - Spec 15 OR-Set (state-based form): payload (A, R) sets of (elem,tag) ;
              merge = union of A and union of R (observed-remove / add-wins)

A "message" is a full state-based payload (one replica's local state), matching
the state-based replication model where the source ships its payload and the
receiver computes merge(self, incoming) = LUB.
"""

import random
import itertools
import json
from copy import deepcopy

# --------------------------------------------------------------------------
# CRDT payload types.  Every type exposes:
#   .copy()                 -> independent copy of self
#   .merge(other)           -> mutates self to self ⊔ other  (the join/LUB)
#   .signature()            -> canonical, hashable representation of state
#                              (used to count DISTINCT final states)
# --------------------------------------------------------------------------

class GCounter:
    """Spec 6. payload: integer vector P, one entry per replica. merge = max."""
    def __init__(self, vec=None):
        self.P = list(vec) if vec is not None else []

    def copy(self):
        return GCounter(self.P)

    def merge(self, other):
        n = max(len(self.P), len(other.P))
        a = self.P + [0] * (n - len(self.P))
        b = other.P + [0] * (n - len(other.P))
        self.P = [max(a[i], b[i]) for i in range(n)]

    def signature(self):
        return ("G-Counter", tuple(self.P))

    def value(self):
        return sum(self.P)


class PNCounter:
    """Spec 7. payload: P (increments) and N (decrements), vectors; merge = max of both."""
    def __init__(self, P=None, N=None):
        self.P = list(P) if P is not None else []
        self.N = list(N) if N is not None else []

    def copy(self):
        return PNCounter(self.P, self.N)

    def _joinvec(self, attr, other_attr):
        a = getattr(self, attr); b = other_attr
        n = max(len(a), len(b))
        a = a + [0] * (n - len(a)); b = b + [0] * (n - len(b))
        setattr(self, attr, [max(a[i], b[i]) for i in range(n)])

    def merge(self, other):
        self._joinvec('P', other.P)
        self._joinvec('N', other.N)

    def signature(self):
        return ("PN-Counter", tuple(self.P), tuple(self.N))

    def value(self):
        return sum(self.P) - sum(self.N)


class LWWRegister:
    """Spec 8. payload: (value x, timestamp t). merge keeps the larger timestamp.
    Ties on timestamp are broken deterministically (max value) so merge is a true
    total-order join -> well-defined CvRDT."""
    def __init__(self, value=None, ts=0):
        self.x = value
        self.t = ts

    def copy(self):
        return LWWRegister(self.x, self.t)

    def merge(self, other):
        if other.t > self.t or (other.t == self.t and _key(other.x) > _key(self.x)):
            self.x, self.t = other.x, other.t

    def signature(self):
        return ("LWW-Register", self.x, self.t)

    def value(self):
        return self.x


class ORSet:
    """Spec 15 (state-based form, observed-remove / add-wins).
    payload: A = set of live (element, unique-tag) pairs; R = set of tombstoned
    (element, tag) pairs. lookup(e) = exists tag: (e,tag) in A and not in R.
    merge = union of A, union of R  (component-wise union = join)."""
    def __init__(self, A=None, R=None):
        self.A = set(A) if A is not None else set()
        self.R = set(R) if R is not None else set()

    def copy(self):
        return ORSet(self.A, self.R)

    def merge(self, other):
        self.A |= other.A
        self.R |= other.R

    def signature(self):
        return ("OR-Set", frozenset(self.A), frozenset(self.R))

    def value(self):
        live = {e for (e, tag) in self.A if (e, tag) not in self.R}
        return frozenset(live)


def _key(x):
    """Total ordering helper for deterministic tie-breaks (None = bottom)."""
    return (0, ) if x is None else (1, x)


# --------------------------------------------------------------------------
# Naive (non-CRDT) controls.
# --------------------------------------------------------------------------

class NaiveDeltaCounter:
    """Plain integer counter. 'update' is += ; 'merge' applies an incoming
    increment delta by adding it. NOT idempotent (a repeated delta is counted
    twice). Addition is comm/assoc, so order alone is fine, but DUPLICATION
    changes the total -> diverges. (This is exactly the 'update += , merge
    order-sensitive accumulation' counter-example alluded to in the task.)"""
    def __init__(self, total=0):
        self.total = total

    def copy(self):
        return NaiveDeltaCounter(self.total)

    def merge(self, msg_delta):
        self.total += msg_delta          # order-insensitive, but NOT idempotent

    def signature(self):
        return ("NaiveDeltaCounter", self.total)

    def value(self):
        return self.total


class NaiveOverwriteCounter:
    """Last-write-WINS WITHOUT a timestamp: merge simply copies the incoming
    value. Final state = whatever was delivered LAST -> depends entirely on
    delivery order, and on duplication (a duplicate can flip the 'last' value).
    Fails commutativity, associativity and idempotence."""
    def __init__(self, value=0):
        self.value = value

    def copy(self):
        return NaiveOverwriteCounter(self.value)

    def merge(self, msg_value):
        self.value = msg_value           # last delivered wins -> order dependent

    def signature(self):
        return ("NaiveOverwrite", self.value)

    def value(self):
        return self.value


# --------------------------------------------------------------------------
# Fixed message-set generation (deterministic seed).  Each generator yields a
# list of "messages", where every message is a full CRDT payload (a fresh copy
# to avoid shared mutable state).  For the naive controls a message is a plain
# integer (delta or value).
# --------------------------------------------------------------------------

def gen_gcounter_messages(seed, n_replicas=6):
    rng = random.Random(seed)
    msgs = []
    for r in range(n_replicas):
        vec = [0] * n_replicas
        vec[r] = rng.randint(1, 9)            # each replica only bumps its own slot
        msgs.append(GCounter(vec))
    return msgs


def gen_pncounter_messages(seed, n_replicas=6):
    rng = random.Random(seed)
    msgs = []
    for r in range(n_replicas):
        P = [0] * n_replicas; N = [0] * n_replicas
        P[r] = rng.randint(2, 12)
        N[r] = rng.randint(0, 5)
        msgs.append(PNCounter(P, N))
    return msgs


def gen_lww_messages(seed, n=8):
    rng = random.Random(seed)
    # distinct timestamps so there is a unique global winner
    ts = list(range(1, n + 1)); rng.shuffle(ts)
    vals = [f"v{i}" for i in range(n)]
    rng.shuffle(vals)
    return [LWWRegister(vals[i], ts[i]) for i in range(n)]


def gen_orset_messages(seed, n_replicas=6, elems=("a", "b", "c", "d")):
    """Each replica adds some uniquely-tagged elements and tombstones some of
    the tags it observed, so the (A,R) join structure is exercised."""
    rng = random.Random(seed)
    msgs = []
    global_tag = itertools.count()
    # a shared pool of (elem, tag) pairs that replicas may tombstone
    pool = {}
    for e in elems:
        for _ in range(3):
            pool[next(global_tag)] = e
    for r in range(n_replicas):
        A, R = set(), set()
        # add 2-3 new unique tags for some elements
        for _ in range(rng.randint(2, 4)):
            e = rng.choice(elems)
            tag = next(global_tag)
            A.add((e, tag))
        # tombstone 0-2 tags drawn from the pool (observed removes)
        for _ in range(rng.randint(0, 2)):
            tag = rng.choice(list(pool.keys()))
            R.add((pool[tag], tag))
        msgs.append(ORSet(A, R))
    return msgs


def gen_naive_delta_messages(seed, n=8):
    rng = random.Random(seed)
    return [rng.randint(1, 9) for _ in range(n)]


def gen_naive_overwrite_messages(seed, n=8):
    rng = random.Random(seed)
    return [rng.randint(1, 50) for _ in range(n)]


# --------------------------------------------------------------------------
# Experiment: for one message set, run many delivery schemes, return the set of
# distinct final-state signatures observed.
# --------------------------------------------------------------------------

def run_crdt_schemes(make_aggregate, messages, schemes):
    """make_aggregate() -> fresh empty aggregate; aggregate.merge(msg) absorbs a
    message. Returns the set of distinct final signatures across all schemes."""
    distinct = set()
    finals = []
    for scheme in schemes:
        agg = make_aggregate()
        for m in scheme:
            agg.merge(m)
        sig = agg.signature()
        distinct.add(sig)
        finals.append(_v(agg))
    return distinct, finals


def build_schemes(messages, n_perm=100, n_dup=100, seed=20240601):
    """Build delivery schemes.
      perm_schemes : distinct random full permutations (no duplication)
      dup_schemes  : random permutation + random duplication (each message may
                     be repeated 1..3 extra times) -> exercises idempotence
    Returns (perm_schemes, dup_schemes, all_schemes).
    All schemes reference the SAME underlying message objects (or copies of
    them); for state-based merge that's fine because merge only reads `other`.
    """
    rng = random.Random(seed)
    idx = list(range(len(messages)))

    perm_schemes = []
    seen_perms = set()
    while len(perm_schemes) < n_perm:
        rng.shuffle(idx)
        key = tuple(idx)
        if key in seen_perms:
            continue
        seen_perms.add(key)
        perm_schemes.append([messages[i] for i in idx])

    dup_schemes = []
    while len(dup_schemes) < n_dup:
        order = idx[:]
        rng.shuffle(order)
        scheme = []
        for i in order:
            scheme.append(messages[i])
            # duplicate this message 0..3 extra times
            extra = rng.randint(0, 3)
            for _ in range(extra):
                scheme.append(messages[i])
        rng.shuffle(scheme)            # interleave duplicates too
        dup_schemes.append(scheme)

    return perm_schemes, dup_schemes, perm_schemes + dup_schemes


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def main():
    SEED = 42
    configs = [
        ("G-Counter",        GCounter,            gen_gcounter_messages),
        ("PN-Counter",       PNCounter,           gen_pncounter_messages),
        ("LWW-Register",     LWWRegister,         gen_lww_messages),
        ("OR-Set",           ORSet,               gen_orset_messages),
        ("Naive Δ-counter (non-CRDT)", NaiveDeltaCounter,    gen_naive_delta_messages),
        ("Naive overwrite (non-CRDT)", NaiveOverwriteCounter, gen_naive_overwrite_messages),
    ]

    results = {}
    raw = {}
    for name, cls, gen in configs:
        msgs = gen(_subseed(SEED, name))
        perm_sch, dup_sch, all_sch = build_schemes(msgs, n_perm=100, n_dup=100,
                                                   seed=_subseed(SEED, name))
        # CRDTs use .merge(other); naive controls take a plain int message.
        make = cls
        perm_d, perm_f = run_crdt_schemes(make, msgs, perm_sch)
        dup_d, dup_f   = run_crdt_schemes(make, msgs, dup_sch)
        all_d, all_f   = run_crdt_schemes(make, msgs, all_sch)
        results[name] = {
            "n_messages": len(msgs),
            "n_perm_schemes": len(perm_sch),
            "n_dup_schemes": len(dup_sch),
            "n_all_schemes": len(all_sch),
            "distinct_perm": len(perm_d),
            "distinct_dup":  len(dup_d),
            "distinct_all":  len(all_d),
            "sample_final_values": sorted({_v(f) for f in all_f}, key=_key)[:12],
        }
        raw[name] = {"perm_d": perm_d, "dup_d": dup_d, "all_d": all_d}

    # Pretty print
    print("=" * 78)
    print("State-based CRDT order/duplication invariance experiment")
    print("=" * 78)
    header = f"{'Type':<32}{'#msg':>5}{'perm':>7}{'dup':>6}{'ALL':>6}  distinct-final-states"
    print(header)
    print("-" * 78)
    for name in [c[0] for c in configs]:
        r = results[name]
        print(f"{name:<32}{r['n_messages']:>5}"
              f"{r['distinct_perm']:>7}{r['distinct_dup']:>6}{r['distinct_all']:>6}  "
              f"(perm={r['distinct_perm']}, dup={r['distinct_dup']}, all={r['distinct_all']})")

    # Save machine-readable results
    with open("crdt_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    # ---------- property-level micro-checks (commutative/associative/idempotent)
    checks = {}
    for name, cls, gen in configs[:4]:  # only CRDTs
        msgs = gen(_subseed(SEED, name))
        # idempotence: merge same msg twice == once
        a = cls(); a.merge(msgs[0]); once = a.copy()
        a.merge(msgs[0]); twice = a
        idem = once.signature() == twice.signature()
        # commutativity: m1.merge(m2) == m2.merge(m1)
        b1 = cls(); b1.merge(msgs[0]); b1.merge(msgs[1])
        b2 = cls(); b2.merge(msgs[1]); b2.merge(msgs[0])
        comm = b1.signature() == b2.signature()
        # associativity: (a⊔b)⊔c == a⊔(b⊔c)
        c1 = cls(); c1.merge(msgs[0]); c1.merge(msgs[1]); c1.merge(msgs[2])
        c2 = cls();
        tmp = cls(); tmp.merge(msgs[1]); tmp.merge(msgs[2])
        c2.merge(msgs[0]); c2.merge(tmp)
        assoc = c1.signature() == c2.signature()
        checks[name] = {"commutative": comm, "associative": assoc, "idempotent": idem}
    with open("crdt_property_checks.json", "w") as f:
        json.dump(checks, f, indent=2, default=str)
    print("\nProperty micro-checks (merge laws):")
    for k, v in checks.items():
        print(f"  {k:<16} commutative={v['commutative']}  "
              f"associative={v['associative']}  idempotent={v['idempotent']}")

    # ---------- plot
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        names = [c[0] for c in configs]
        perm = [results[n]["distinct_perm"] for n in names]
        dup  = [results[n]["distinct_dup"]  for n in names]
        allv = [results[n]["distinct_all"]  for n in names]

        x = range(len(names))
        fig, ax = plt.subplots(figsize=(11, 5.2))
        w = 0.26
        ax.bar([i - w for i in x], perm, width=w, label="permutation-only (100 schemes)",
               color="#4C78A8")
        ax.bar([i for i in x],     dup,  width=w, label="permutation + duplication (100 schemes)",
               color="#F58518")
        ax.bar([i + w for i in x], allv, width=w, label="all schemes combined (200)",
               color="#54A24B")
        ax.set_xticks(list(x))
        ax.set_xticklabels(names, rotation=18, ha="right", fontsize=9)
        ax.set_ylabel("# distinct final states")
        ax.set_yscale("log")
        ax.set_title("Distinct final states under message reordering & duplication\n"
                     "(CRDT merge → unique state = 1;  naive non-CRDT → many)")
        for i in x:
            ax.text(i - w, perm[i] + 0.1, str(perm[i]), ha="center", fontsize=8)
            ax.text(i,     dup[i]  + 0.1, str(dup[i]),  ha="center", fontsize=8)
            ax.text(i + w, allv[i] + 0.1, str(allv[i]), ha="center", fontsize=8)
        ax.axhline(1, color="red", ls="--", lw=1, alpha=0.7, label="convergence target = 1")
        ax.legend(fontsize=8, loc="upper left")
        fig.tight_layout()
        fig.savefig("crdt_distinct_states.png", dpi=130)
        print("\nSaved figure: crdt_distinct_states.png")
    except Exception as e:
        print(f"(plot skipped: {e})")

    return results, checks


def _subseed(base, name):
    return base + (sum(ord(c) for c in name) % 9973)


def _v(x):
    """Extract a readable final value from an aggregate (handles both CRDT
    objects with a value() method and naive counters whose value/total is an
    int attribute)."""
    v = getattr(x, "value", None)
    if callable(v):
        return v()
    if v is not None:
        return v
    return getattr(x, "total", x)


if __name__ == "__main__":
    main()
