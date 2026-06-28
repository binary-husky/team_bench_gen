"""
CRDT message-cost study (task crdt_04).

Compares two in-process CRDT counter forms, increment-only:
  * state-based (payload / CvRDT) G-Counter  -- Spec 6 of Shapiro et al. 2011:
        payload integer[n] P; increment: P[g] := P[g] + 1; merge: component-wise max.
        After each local increment the replica broadcasts its FULL vector P (length N).
  * op-based (CmRDT) counter                 -- Spec 5 of Shapiro et al. 2011:
        payload integer i; increment downstream: i := i + 1.
        Each local increment broadcasts a single fixed-size op ("replica i +1").

Fixed setup (per task.md):
  N = 5 replicas.
  M in {1e3, 5e3, 1e4, 5e4} total increments, split EVENLY across replicas (M/N each).
  >= 3 seeds randomise the interleaving order of the operations.

Model: synchronous in-process, reliable + instant delivery. After each increment the
broadcast payload is measured with its JSON byte length. Because every prior broadcast
was delivered instantly, the broadcaster's local vector equals the global vector V, so
the broadcast payload == current global V (the G-Counter full state). This is the
natural in-process reading and makes results essentially deterministic (order only
shifts the digit-length distribution slightly between seeds).

Byte accounting:
  * per-message bytes  = len(JSON(payload)) for one broadcast.
  * state per-message bytes = average over all M broadcasts (grows with M).
  * op   per-message bytes   = constant.
  * total transfer bytes (primary) = sum over the M broadcasts of payload bytes
    (each broadcast counted once). We also report the wire total = (N-1) x primary,
    since each broadcast is delivered to the other N-1 replicas; this multiplies BOTH
    forms by the same factor, so the ratio / conclusion is unchanged.
"""

import json
import random

N = 5
M_LIST = [1_000, 5_000, 10_000, 50_000]
SEEDS = [1, 7, 42]  # 3 seeds (>= 3)


def state_msg_bytes(V):
    """G-Counter full-state payload = the per-replica count vector (length N), JSON."""
    return len(json.dumps(V).encode("utf-8"))


def op_msg_bytes(i):
    """CmRDT increment op = {'src': i, 'op': 'inc'}; fixed size for single-digit i."""
    return len(json.dumps({"src": i, "op": "inc"}).encode("utf-8"))


def run_one(M, seed):
    per = M // N  # even split: each replica increments exactly M/N times
    assert per * N == M, "M must be divisible by N"
    rng = random.Random(seed)
    seq = []
    for r in range(N):
        seq += [r] * per
    rng.shuffle(seq)  # randomise interleaving (seed-dependent)

    V = [0] * N
    state_bytes_sum = 0   # sum of payload bytes over the M broadcasts
    op_bytes_sum = 0
    state_min, state_max = None, None
    for i in seq:
        V[i] += 1                 # local increment at replica i
        sb = state_msg_bytes(V)   # broadcast full state vector
        ob = op_msg_bytes(i)      # broadcast single increment op
        state_bytes_sum += sb
        op_bytes_sum += ob
        state_min = sb if state_min is None else min(state_min, sb)
        state_max = sb if state_max is None else max(state_max, sb)

    n = M  # one broadcast per increment
    return {
        "M": M,
        "seed": seed,
        "n_broadcasts": n,
        "state_total_bytes": state_bytes_sum,            # primary total (count once)
        "state_per_msg_avg": state_bytes_sum / n,
        "state_per_msg_min": state_min,
        "state_per_msg_max": state_max,
        "op_total_bytes": op_bytes_sum,                  # = M * const
        "op_per_msg": op_bytes_sum / n,                  # constant
        "final_V": list(V),
    }


def main():
    print(f"N = {N} replicas | seeds = {SEEDS} | total broadcasts per (M,seed) = M\n")
    header = (
        f"{'M':>7} | "
        f"{'op/msg(B)':>9}  {'op_total(B)':>11} | "
        f"{'state/msg avg':>13}  {'state/msg[min..max]':>20}  {'state_total(B)':>14} | "
        f"{'state/op tot':>12}"
    )
    print(header)
    print("-" * len(header))

    summary_rows = []
    for M in M_LIST:
        runs = [run_one(M, s) for s in SEEDS]
        # op is exactly identical across seeds; state differs only trivially
        op_pm = runs[0]["op_per_msg"]
        op_tot = sum(r["op_total_bytes"] for r in runs) / len(SEEDS)
        st_pm_avg = sum(r["state_per_msg_avg"] for r in runs) / len(SEEDS)
        st_pm_spread = (min(r["state_per_msg_avg"] for r in runs),
                        max(r["state_per_msg_avg"] for r in runs))
        st_tot = sum(r["state_total_bytes"] for r in runs) / len(SEEDS)
        st_min = min(r["state_per_msg_min"] for r in runs)
        st_max = max(r["state_per_msg_max"] for r in runs)
        ratio = st_tot / op_tot
        final_V = runs[0]["final_V"]

        print(
            f"{M:>7} | "
            f"{op_pm:>9.1f}  {op_tot:>11.0f} | "
            f"{st_pm_avg:>13.2f}  "
            f"{f'[{st_min}..{st_max}]':>20}  {st_tot:>14.0f} | "
            f"{ratio:>12.3f}"
        )
        summary_rows.append({
            "M": M,
            "op_per_msg": op_pm,
            "op_total": op_tot,
            "state_per_msg_avg": st_pm_avg,
            "state_per_msg_spread": st_pm_spread,
            "state_per_msg_minmax": (st_min, st_max),
            "state_total": st_tot,
            "ratio_state_over_op": ratio,
            "final_V": final_V,
            "wire_mult": N - 1,
        })

    print("\nNotes:")
    print(f"  * Each broadcast fans out to N-1 = {N-1} peers; wire bytes = table x {N-1} for BOTH forms (ratio unchanged).")
    print("  * op message is constant: " + json.dumps({"src": 0, "op": "inc"}))
    for r in summary_rows:
        print(f"  * M={r['M']:<6}: op_total={r['op_total']:.0f} B  state_total={r['state_total']:.0f} B  "
              f"state/op={r['ratio_state_over_op']:.3f}  final_V={r['final_V']}")

    # write a JSON for the summary step
    with open("crdt_04_results.json", "w") as f:
        json.dump(summary_rows, f, indent=2)
    print("\nwrote crdt_04_results.json")


if __name__ == "__main__":
    main()
