"""
Verify the error guarantees of the Space-Saving algorithm
(Metwally, Agrawal, El Abbadi, 2005) on a Zipfian stream.

Three guarantees (paper notation: m = number of counters = k):
  (G1) No under-estimation: for every monitored element e_i,
       count_i >= f_i  (Lemma 3: 0 <= eps_i, count_i = f_i + eps_i >= f_i).
  (G2) Max over-estimation error <= current minimum counter value `min`
       (Lemma 3: eps_i <= min  =>  count_i - f_i <= min).
  (G3) min <= N/k  (Lemma 2: min <= floor(N/m)).

Plus: confirm the bound tightens as N/k shrinks (vary k at fixed N,
and vary N at fixed k).
"""

import numpy as np
import heapq
from collections import Counter

SEED = 42
S_ZIPF = 1.1          # Zipf parameter
DOMAIN = 10000        # alphabet size |A|
N_MAIN = 1_000_000
K_MAIN = 100


def generate_stream(N, domain, s, seed):
    rng = np.random.default_rng(seed)
    # numpy's zipf: P(x) ~ x^{-s}, s>1. shift to 0-based ids.
    return rng.zipf(s, size=N).astype(np.int64) - 1


def space_saving(stream, k):
    """Run Space-Saving with k counters.

    Returns:
      monitored: dict element -> (count, eps)
      true_freq: Counter of true frequencies (only for elements seen)
      n: stream length
    """
    monitored = {}        # element -> [count, eps]
    heap = []             # lazy min-heap of (count, element)
    n = 0
    for e in stream:
        e = int(e)
        n += 1
        if e in monitored:
            c = monitored[e][0] + 1
            monitored[e][0] = c
            heapq.heappush(heap, (c, e))
        else:
            if len(monitored) < k:
                monitored[e] = [1, 0]
                heapq.heappush(heap, (1, e))
            else:
                # find current minimum (lazy)
                while heap:
                    c, el = heap[0]
                    if el in monitored and monitored[el][0] == c:
                        break
                    heapq.heappop(heap)
                c_min, e_min = heap[0]
                # replacement: evict e_min, install e
                del monitored[e_min]
                new_c = c_min + 1
                monitored[e] = [new_c, c_min]   # eps = min
                heapq.heappush(heap, (new_c, e))
                # stale entry for e_min remains; lazily ignored
    return monitored, n


def current_min(monitored):
    return min(c for c, _ in monitored.values())


def verify_three_guarantees(monitored, true_freq, n, k):
    """Check G1, G2, G3. Return dict of results."""
    min_c = current_min(monitored)

    # G1: every monitored estimate >= true frequency
    g1_violations = []
    overest = []
    for e, (c, eps) in monitored.items():
        tf = true_freq.get(e, 0)
        if c < tf:
            g1_violations.append((e, c, tf))
        overest.append(c - tf)   # actual over-estimation (>=0 if G1 holds)

    max_overest = max(overest) if overest else 0
    max_overest_elem = None
    for e, (c, eps) in monitored.items():
        if c - true_freq.get(e, 0) == max_overest:
            max_overest_elem = e
            break

    # G2: max over-estimation <= min
    g2_ok = (max_overest <= min_c)

    # also check the stored eps bound: eps_i <= min (Lemma 3)
    eps_max = max(eps for _, eps in monitored.values())
    eps_bound_ok = (eps_max <= min_c)

    # G3: min <= N/k
    g3_ok = (min_c <= n / k)

    return {
        "N": n, "k": k, "N/k": n / k,
        "min": min_c,
        "g1_ok": (len(g1_violations) == 0),
        "g1_num_violations": len(g1_violations),
        "g1_violations_sample": g1_violations[:5],
        "max_overest": max_overest,
        "max_overest_elem": max_overest_elem,
        "g2_ok": g2_ok,
        "eps_max": eps_max,
        "eps_bound_ok": eps_bound_ok,
        "g3_ok": g3_ok,
        "g3_slack": (n / k) - min_c,
    }


def main():
    print("=" * 70)
    print("MAIN RUN: Zipfian stream, N=1e6, k=100, s=1.1, domain=10000, seed=42")
    print("=" * 70)
    stream = generate_stream(N_MAIN, DOMAIN, S_ZIPF, SEED)
    true_freq = Counter(stream.tolist())
    monitored, n = space_saving(stream, K_MAIN)
    r = verify_three_guarantees(monitored, true_freq, n, K_MAIN)
    for kk, vv in r.items():
        print(f"  {kk}: {vv}")

    print("\nTrue top-10 freqs:", [true_freq[i] for i in
          sorted(range(DOMAIN + 1), key=lambda x: -true_freq.get(x, 0))[:10]])
    # show a few monitored estimates vs truth
    print("Sample monitored (e: count, eps, true_f, overest):")
    items = sorted(monitored.items(), key=lambda kv: -kv[1][0])[:10]
    for e, (c, eps) in items:
        print(f"    e={e}: count={c}, eps={eps}, true_f={true_freq.get(e,0)}, "
              f"overest={c - true_freq.get(e,0)}")

    # ---- Bound-tightening sweep: vary k at fixed N ----
    print("\n" + "=" * 70)
    print("SWEEP A: vary k at fixed N=1e6 (bound N/k shrinks as k grows)")
    print("=" * 70)
    print(f"{'k':>6} {'N/k':>10} {'min':>10} {'max_overest':>12} "
          f"{'eps_max':>10} {'G1':>4} {'G2':>4} {'G3':>4}")
    sweepA = []
    for k in [50, 100, 200, 400, 800, 1600]:
        mon, nn = space_saving(stream, k)
        rr = verify_three_guarantees(mon, true_freq, nn, k)
        sweepA.append((k, rr))
        print(f"{k:>6} {rr['N/k']:>10.1f} {rr['min']:>10} "
              f"{rr['max_overest']:>12} {rr['eps_max']:>10} "
              f"{str(rr['g1_ok']):>4} {str(rr['g2_ok']):>4} {str(rr['g3_ok']):>4}")

    # ---- Bound-tightening sweep: vary N at fixed k ----
    print("\n" + "=" * 70)
    print("SWEEP B: vary N at fixed k=100 (bound N/k grows with N)")
    print("=" * 70)
    print(f"{'N':>12} {'N/k':>10} {'min':>10} {'max_overest':>12} "
          f"{'eps_max':>10} {'G1':>4} {'G2':>4} {'G3':>4}")
    sweepB = []
    for N in [100_000, 250_000, 500_000, 1_000_000, 2_000_000]:
        st = generate_stream(N, DOMAIN, S_ZIPF, SEED)
        tf = Counter(st.tolist())
        mon, nn = space_saving(st, K_MAIN)
        rr = verify_three_guarantees(mon, tf, nn, K_MAIN)
        sweepB.append((N, rr))
        print(f"{N:>12} {rr['N/k']:>10.1f} {rr['min']:>10} "
              f"{rr['max_overest']:>12} {rr['eps_max']:>10} "
              f"{str(rr['g1_ok']):>4} {str(rr['g2_ok']):>4} {str(rr['g3_ok']):>4}")

    return r, sweepA, sweepB


if __name__ == "__main__":
    main()
