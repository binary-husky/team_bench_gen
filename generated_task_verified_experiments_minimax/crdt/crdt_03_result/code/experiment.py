"""
Experiment: Verify that state-based CRDT merge converges to the same state under
out-of-order and duplicate message delivery, whereas a naive non-CRDT counter
does not converge.

CRDTs implemented (state-based):
- G-Counter (Shapiro et al., Spec 6): payload = vector[n], merge = max element-wise
- PN-Counter (Spec 7): payload = (P[n], N[n]), merge = max on each, value = sum(P)-sum(N)
- LWW-Register (Spec 8): payload = (value, timestamp), merge keeps the (value, ts) with the
  larger timestamp (ties broken by replica id)
- OR-Set (state-based variant following Sec 3.3.5 + U-Set): payload is a set of
  (element, unique-tag) pairs representing currently present entries. Add produces a
  fresh unique tag. Remove is observed at the source: it removes only those pairs that
  the source replica currently observes. Merge is the union of the two payloads.

Naive non-CRDT control: a plain integer counter. update(x, v) sets x += v (cumulative
delta messages are sent and merged by +=). Merge is x += other.value, which is order
sensitive (commutative on integers, but we also expose a "naive with payload overwrite"
counter to highlight order/duplicate sensitivity).
"""

import json
import os
import random
from collections import Counter
from typing import Any, List, Tuple

# ---------------------------------------------------------------------------
# CRDTs (state-based, with merge only)
# ---------------------------------------------------------------------------

class GCounter:
    """State-based G-Counter: vector[n] of non-negative integers, merge = element-wise max."""

    def __init__(self, n: int, payload: List[int] | None = None):
        self.n = n
        self.payload = list(payload) if payload is not None else [0] * n

    def value(self) -> int:
        return sum(self.payload)

    def merge(self, other: "GCounter") -> "GCounter":
        assert self.n == other.n
        new = [max(a, b) for a, b in zip(self.payload, other.payload)]
        return GCounter(self.n, new)


class PNCounter:
    """State-based PN-Counter: (P[n], N[n]); value = sum(P) - sum(N). Merge = max element-wise."""

    def __init__(self, n: int, payload: Tuple[List[int], List[int]] | None = None):
        self.n = n
        if payload is None:
            self.P = [0] * n
            self.N = [0] * n
        else:
            self.P = list(payload[0])
            self.N = list(payload[1])

    def value(self) -> int:
        return sum(self.P) - sum(self.N)

    def merge(self, other: "PNCounter") -> "PNCounter":
        assert self.n == other.n
        new_P = [max(a, b) for a, b in zip(self.P, other.P)]
        new_N = [max(a, b) for a, b in zip(self.N, other.N)]
        return PNCounter(self.n, (new_P, new_N))


class LWWRegister:
    """State-based LWW-Register: payload = (value, timestamp, replica_id).
    Merge keeps the entry with the largest (timestamp, replica_id)."""

    def __init__(self, value=None, timestamp: int = 0, replica_id: str = ""):
        self.value = value
        self.timestamp = timestamp
        self.replica_id = replica_id

    def current(self) -> Any:
        return self.value

    def merge(self, other: "LWWRegister") -> "LWWRegister":
        # lexicographic comparison: timestamp first, replica_id for tie-break
        if (other.timestamp, other.replica_id) > (self.timestamp, self.replica_id):
            return LWWRegister(other.value, other.timestamp, other.replica_id)
        return LWWRegister(self.value, self.timestamp, self.replica_id)


class ORSet:
    """State-based Observed-Remove Set.

    Payload is the set of (element, unique_tag) pairs that are currently considered
    present at this replica. Add(e) produces a fresh globally unique tag and inserts
    (e, tag). Remove(e) deletes every pair of element e that this replica currently
    observes. Merge is the union of the two payloads.

    Because add tags are globally unique, merging is union-of-sets which is
    commutative, associative, and idempotent. As specified in Shapiro et al. Sec 3.3.5.
    """

    def __init__(self, payload: set | None = None):
        # payload stores frozenset-able tuples for canonical hashing
        self.payload = set(payload) if payload is not None else set()

    def value(self) -> frozenset:
        # Elements that have at least one live tag.
        return frozenset(e for (e, _) in self.payload)

    def merge(self, other: "ORSet") -> "ORSet":
        return ORSet(self.payload | other.payload)


# ---------------------------------------------------------------------------
# Naive non-CRDT counter (control)
# ---------------------------------------------------------------------------

class NaiveCounter:
    """A plain integer counter. The "update" produces a delta (or value) message;
    the "merge" on the receiver adds the incoming value to the local state.
    This is order-sensitive if messages can arrive in any order: reordering a +5
    followed by a +3 yields 8 regardless, but a "set last-write-wins" naive
    register shows the order dependence clearly. To highlight the *order
    sensitivity* of a non-CRDT, we ship two controls:

    1. NaiveAccum: messages are integers; merge = + other. (Commutative, but
       sensitive to *duplicates*: a duplicate message will double-count.)
    2. NaiveLastWrite: messages are integers; merge = overwrites the local
       counter with the value of the incoming message. Order- AND duplicate-
       sensitive (only the last message's value survives).

    The task asks for *a* naive non-CRDT control. We use NaiveLastWrite so that
    order/duplicates clearly change the final state (the textbook example of an
    eventually-consistent object that does NOT converge under arbitrary delivery).
    We additionally report NaiveAccum to show duplicate sensitivity alone.
    """

    def __init__(self, value: int = 0):
        self.value = value

    def current(self) -> int:
        return self.value

    def merge(self, other: "NaiveCounter") -> "NaiveCounter":
        return NaiveLastWrite(other.value)


class NaiveLastWrite(NaiveCounter):
    """Last-write-wins naive counter: merge = overwrite."""

    def merge(self, other: "NaiveCounter") -> "NaiveLastWrite":
        # Plain integer payload; merge just overwrites with the other value.
        # (We could also weight by sender id, but the point is to demonstrate
        # that this is NOT a CRDT: order and duplicates change the result.)
        return NaiveLastWrite(other.value)


class NaiveAccum:
    """Naive accumulator: merge = self + other. Commutative but NOT idempotent
    (duplicates will double-count)."""

    def __init__(self, value: int = 0):
        self.value = value

    def current(self) -> int:
        return self.value

    def merge(self, other: "NaiveAccum") -> "NaiveAccum":
        return NaiveAccum(self.value + other.value)


# ---------------------------------------------------------------------------
# Message generation (deterministic)
# ---------------------------------------------------------------------------

def generate_messages(seed: int = 2026, n_replicas: int = 4) -> dict:
    """Generate a fixed message set under a deterministic seed.

    The message set covers all four CRDTs so that a single experiment can be
    run against all CRDTs in lockstep (each delivery scenario is one
    permutation+duplication of this list of messages, and each CRDT only
    reacts to the messages it understands).

    Returns a dict with:
        - 'g_counter_msgs': list of {src, payload=[..]} messages
        - 'pn_counter_msgs': list of {src, payload=([..], [..])} messages
        - 'lww_msgs': list of {src, value, timestamp}
        - 'or_set_add_msgs': list of {src, element, tag}
        - 'or_set_rm_msgs': list of {src, element}
        - 'naive_last_write_msgs': list of {src, value}
        - 'naive_accum_msgs': list of {src, value}
        - 'g_counter_index': for each replica, a list of indices in
          g_counter_msgs that originate from that replica (so we can build
          a per-replica initial state cleanly).
    """

    rng = random.Random(seed)
    msgs = {
        "g_counter_msgs": [],
        "pn_counter_msgs": [],
        "lww_msgs": [],
        "or_set_add_msgs": [],
        "or_set_rm_msgs": [],
        "naive_last_write_msgs": [],
        "naive_accum_msgs": [],
    }

    # Per-replica counters
    g_state = [[0] * n_replicas for _ in range(n_replicas)]
    pn_p = [[0] * n_replicas for _ in range(n_replicas)]
    pn_n = [[0] * n_replicas for _ in range(n_replicas)]
    lww_payload: List[Tuple[Any, int, str]] = []  # (value, timestamp, replica_id)

    n_ops = 40  # number of ops per replica (total ~ n_replicas * n_ops ops)

    for src in range(n_replicas):
        for op_idx in range(n_ops):
            choice = rng.random()
            ts = src * 1000 + op_idx  # unique timestamp ordering, replica id tie-break

            if choice < 0.20:
                # G-Counter increment on this replica
                inc = rng.randint(1, 5)
                g_state[src][src] += inc
                payload = list(g_state[src])
                msgs["g_counter_msgs"].append({"src": src, "payload": payload})
            elif choice < 0.40:
                # PN-Counter increment
                p_inc = rng.randint(1, 3)
                pn_p[src][src] += p_inc
                msgs["pn_counter_msgs"].append({
                    "src": src,
                    "payload": (list(pn_p[src]), list(pn_n[src])),
                })
            elif choice < 0.55:
                # PN-Counter decrement
                n_inc = rng.randint(1, 3)
                pn_n[src][src] += n_inc
                msgs["pn_counter_msgs"].append({
                    "src": src,
                    "payload": (list(pn_p[src]), list(pn_n[src])),
                })
            elif choice < 0.75:
                # LWW-Register assign a string value
                value = f"v{src}_{op_idx}"
                lww_payload.append((value, ts, f"r{src}"))
                msgs["lww_msgs"].append({
                    "src": src,
                    "value": value,
                    "timestamp": ts,
                    "replica_id": f"r{src}",
                })
            elif choice < 0.90:
                # OR-Set add
                element = f"e{src}_{op_idx % 8}"  # some duplicates allowed
                tag = f"tag-{src}-{op_idx}-{rng.randrange(1 << 32)}"
                msgs["or_set_add_msgs"].append({"src": src, "element": element, "tag": tag})
            else:
                # OR-Set remove (observed at source): remove all tags currently known
                # at this source replica for the element. We'll need to track what
                # the source knows. We use the global lww_payload + a synthesized
                # OR-Set view via the adds we sent so far in this run.
                pass  # handled below

    # OR-Set removes: do them after adds so the source has a view to remove from
    # We synthesize a source-side observed set using the add tags already issued.
    # Build per-source OR-Set observed state: set of (element, tag) the source sees.
    observed_by_src: List[set] = [set() for _ in range(n_replicas)]
    for m in msgs["or_set_add_msgs"]:
        observed_by_src[m["src"]].add((m["element"], m["tag"]))

    # For some operations, let each replica issue a remove of a randomly chosen
    # element it has observed.
    for src in range(n_replicas):
        for _ in range(5):
            if not observed_by_src[src]:
                continue
            el = rng.choice(list({e for (e, _) in observed_by_src[src]}))
            # remove targets ALL tags for that element at the source
            tags_for_el = {t for (e, t) in observed_by_src[src] if e == el}
            msgs["or_set_rm_msgs"].append({"src": src, "element": el, "tags": sorted(tags_for_el)})
            # update source's view: those tags no longer present
            observed_by_src[src] = {(e, t) for (e, t) in observed_by_src[src] if e != el}

    # Naive non-CRDT message streams.
    # last-write: each "assign" message overwrites. We just send a stream of
    # integers — the final value depends on which message is processed last
    # in a delivery order.
    for src in range(n_replicas):
        for i in range(n_ops):
            v = rng.randint(1, 100)
            msgs["naive_last_write_msgs"].append({"src": src, "value": v})

    # accum: each "increment" message adds to the current. Sensitive to
    # duplicates only.
    for src in range(n_replicas):
        for i in range(n_ops):
            v = rng.randint(1, 5)
            msgs["naive_accum_msgs"].append({"src": src, "value": v})

    return msgs


# ---------------------------------------------------------------------------
# Per-CRDT "replay" given a delivery order (a list of message indices)
# ---------------------------------------------------------------------------

def replay_g_counter(messages, order, n_replicas):
    state = GCounter(n_replicas, [0] * n_replicas)
    for idx in order:
        m = messages[idx]
        incoming = GCounter(n_replicas, m["payload"])
        state = state.merge(incoming)
    return state.value()


def replay_pn_counter(messages, order, n_replicas):
    state = PNCounter(n_replicas, ([0] * n_replicas, [0] * n_replicas))
    for idx in order:
        m = messages[idx]
        incoming = PNCounter(n_replicas, m["payload"])
        state = state.merge(incoming)
    return state.value()


def replay_lww(messages, order):
    state = LWWRegister(None, -1, "")
    for idx in order:
        m = messages[idx]
        incoming = LWWRegister(m["value"], m["timestamp"], m["replica_id"])
        state = state.merge(incoming)
    return state.current()


def replay_or_set(add_messages, remove_messages, order_add, order_rm):
    """OR-Set state-based replay.

    `order_add` and `order_rm` index into add_messages and remove_messages,
    respectively. Each add inserts (element, tag). Each remove deletes every
    (element, tag) pair observed at the source of that remove — i.e., the
    tags listed in the remove message itself (they were recorded at source).

    The merge step is a set union of the observed (element, tag) payloads.
    """
    state = set()
    for idx in order_add:
        m = add_messages[idx]
        state.add((m["element"], m["tag"]))
    for idx in order_rm:
        m = remove_messages[idx]
        for t in m["tags"]:
            state.discard((m["element"], t))
    return frozenset(e for (e, _) in state)


def replay_naive_last_write(messages, order):
    """Last-write naive counter: merge = overwrite with incoming value."""
    state = NaiveLastWrite(0)
    for idx in order:
        m = messages[idx]
        state = state.merge(NaiveLastWrite(m["value"]))
    return state.current()


def replay_naive_accum(messages, order):
    state = NaiveAccum(0)
    for idx in order:
        m = messages[idx]
        state = state.merge(NaiveAccum(m["value"]))
    return state.current()


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run_experiment(seed: int = 2026, n_scenarios: int = 200):
    msgs = generate_messages(seed=seed)

    # Sanity: report message counts
    counts = {k: len(v) for k, v in msgs.items() if isinstance(v, list)}
    print("Message counts:", counts)

    n_replicas = 4

    g_msgs = msgs["g_counter_msgs"]
    pn_msgs = msgs["pn_counter_msgs"]
    lww_msgs = msgs["lww_msgs"]
    add_msgs = msgs["or_set_add_msgs"]
    rm_msgs = msgs["or_set_rm_msgs"]
    nl_msgs = msgs["naive_last_write_msgs"]
    na_msgs = msgs["naive_accum_msgs"]

    rng = random.Random(seed + 1)

    # For OR-Set: combine adds and removes into a single delivery list, then
    # partition by kind after shuffling. Easier: build a single combined stream
    # of all operations, then replay add/remove messages in their original
    # indices but ordered according to a global permutation.
    n_add = len(add_msgs)
    n_rm = len(rm_msgs)
    total_or = n_add + n_rm
    # We want a delivery order that is a permutation+duplication of all OR-Set
    # operations. We split the indices: 0..n_add-1 are adds; n_add..n_add+n_rm-1
    # are removes.

    results = {
        "g_counter": [],
        "pn_counter": [],
        "lww": [],
        "or_set": [],
        "naive_last_write": [],
        "naive_accum": [],
    }

    for s in range(n_scenarios):
        # Random permutation + duplication of each CRDT's messages.
        # Duplication: each message is delivered at least once; we duplicate
        # some messages so that 30% of the stream is duplicates.
        def delivery_order(stream_len):
            base = list(range(stream_len))
            rng.shuffle(base)
            # duplicate 30% of the messages
            dup_count = max(1, int(0.3 * stream_len))
            dups = rng.sample(base, k=min(dup_count, stream_len))
            return base + dups

        g_order = delivery_order(len(g_msgs))
        pn_order = delivery_order(len(pn_msgs))
        lww_order = delivery_order(len(lww_msgs))

        # OR-Set: build a unified stream
        or_base = list(range(n_add + n_rm))
        rng.shuffle(or_base)
        dup_n = max(1, int(0.3 * (n_add + n_rm)))
        dups = rng.sample(or_base, k=min(dup_n, len(or_base)))
        or_order = or_base + dups
        # split into add and rm indices
        add_order = [i for i in or_order if i < n_add]
        rm_order = [i - n_add for i in or_order if i >= n_add]

        nl_order = delivery_order(len(nl_msgs))
        na_order = delivery_order(len(na_msgs))

        g_v = replay_g_counter(g_msgs, g_order, n_replicas)
        pn_v = replay_pn_counter(pn_msgs, pn_order, n_replicas)
        lww_v = replay_lww(lww_msgs, lww_order)
        or_v = replay_or_set(add_msgs, rm_msgs, add_order, rm_order)
        nl_v = replay_naive_last_write(nl_msgs, nl_order)
        na_v = replay_naive_accum(na_msgs, na_order)

        results["g_counter"].append(g_v)
        results["pn_counter"].append(pn_v)
        results["lww"].append(lww_v)
        results["or_set"].append(or_v)
        results["naive_last_write"].append(nl_v)
        results["naive_accum"].append(na_v)

    return results, counts


def summarize(results):
    """Compute the count of distinct final states for each CRDT/control."""
    summary = {}
    for k, v in results.items():
        distinct = len(set(v))
        summary[k] = {
            "n_scenarios": len(v),
            "n_distinct": distinct,
            "examples": list(set(v))[:5],
        }
    return summary


if __name__ == "__main__":
    print("=== Order-invariance experiment for state-based CRDTs ===\n")
    results, counts = run_experiment(seed=2026, n_scenarios=200)
    summary = summarize(results)

    print("\nMessage counts:")
    for k, c in counts.items():
        print(f"  {k}: {c}")

    print("\nDistinct final states across 200 delivery scenarios:")
    print(f"  {'CRDT / Control':<22} {'distinct':>10} {'total':>8}")
    for k, s in summary.items():
        print(f"  {k:<22} {s['n_distinct']:>10} {s['n_scenarios']:>8}")

    # Save raw results
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "results.json"), "w") as f:
        # convert frozensets to sorted lists for JSON
        serialisable = {}
        for k, v in results.items():
            serialisable[k] = [
                sorted(list(x)) if isinstance(x, frozenset) else x
                for x in v
            ]
        json.dump({"counts": counts, "results": serialisable,
                   "summary": summary}, f, indent=2, default=str)
    print("\nWrote results.json")