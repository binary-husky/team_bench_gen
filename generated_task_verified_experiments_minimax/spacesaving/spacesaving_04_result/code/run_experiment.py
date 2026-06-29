"""Verify Space-Saving error guarantees on Zipfian streams.

Implements the Space-Saving algorithm with full tracking of the three
guarantees from Metwally, Agrawal, El Abbadi (2005):
  G1 (Lemma 3 lower): For every monitored element e_i, count_i >= f_i
                      (i.e., no underestimation).
  G2 (Lemma 3 upper): For every monitored element e_i, count_i - f_i <= min,
                      i.e., max overestimation error <= current min counter.
  G3 (Lemma 2):       min counter value <= floor(N / k).

After the stream ends we also re-run with several (N, k) pairs to confirm
that the worst-case overestimation error scales with N/k.
"""

import argparse
import json
import math
from collections import defaultdict
from typing import Dict, List, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Zipfian stream generator (numerically stable; matches Zipf(alpha) ranks)
# ---------------------------------------------------------------------------
def zipf_stream(N: int, alpha: float, alphabet_size: int, rng: np.random.Generator) -> np.ndarray:
    """Return an array of length N of items drawn iid from Zipf(alpha) on
    [1, alphabet_size] using the standard inverse-CDF approach with
    harmonic-normalised probabilities.
    """
    ranks = np.arange(1, alphabet_size + 1, dtype=np.float64)
    # p_i = 1 / (i^alpha * H_{alphabet_size, alpha})
    weights = 1.0 / np.power(ranks, alpha)
    weights /= weights.sum()
    # Inverse CDF sampling.
    cdf = np.cumsum(weights)
    u = rng.random(N)
    items = np.searchsorted(cdf, u)
    # Items are 0-indexed ranks - 1, so 0 corresponds to rank 1.
    return items


# ---------------------------------------------------------------------------
# Space-Saving
# ---------------------------------------------------------------------------
class SpaceSaving:
    """Faithful re-implementation of Space-Saving (Metwally et al. 2005).

    Each item in the monitored set stores
        count  - the counter value (an upper bound on the true frequency)
        error  - the over-estimation error at insertion time
    The set is kept in a simple dict + min heap for clarity; performance is
    not the goal of the experiment.
    """

    def __init__(self, k: int):
        self.k = k
        self.counters: Dict[int, Dict] = {}
        self.min_count = 0

    def update(self, e: int) -> None:
        if e in self.counters:
            self.counters[e]["count"] += 1
            return
        if len(self.counters) < self.k:
            self.counters[e] = {"count": 1, "error": 0}
        else:
            # Replacement step.
            min_e = min(self.counters, key=lambda x: self.counters[x]["count"])
            evicted = self.counters.pop(min_e)
            new_count = evicted["count"]  # value of `min` at insertion
            self.counters[e] = {"count": new_count + 1, "error": new_count}
        # Refresh min.
        self.min_count = min(c["count"] for c in self.counters.values())


def verify_guarantees(stream: np.ndarray, k: int) -> Dict:
    """Run Space-Saving on `stream` and verify per-item guarantees.

    Per-item assertions are recorded by post-checking against the true
    frequencies (we know them because we have the whole stream).

    Returns a dict with summary statistics for each guarantee.
    """
    ss = SpaceSaving(k)
    N = len(stream)

    # First pass: build the algorithm state.
    for e in stream:
        ss.update(int(e))

    # Compute true frequencies for everything seen in the stream.
    true_freq: Dict[int, int] = defaultdict(int)
    for e in stream:
        true_freq[int(e)] += 1

    # --- Guarantee 1: every monitored count_i >= f_i -----------------------
    g1_violations: List[Tuple[int, int, int]] = []  # (item, count, true)
    for item, c in ss.counters.items():
        f = true_freq.get(item, 0)
        if c["count"] < f:
            g1_violations.append((item, c["count"], f))

    # --- Guarantee 2: max overestimation error <= current min ------------
    min_count = min(c["count"] for c in ss.counters.values())
    g2_violations: List[Tuple[int, int, int]] = []
    errors: List[int] = []
    for item, c in ss.counters.items():
        f = true_freq.get(item, 0)
        err = c["count"] - f
        errors.append(err)
        if err > min_count:
            g2_violations.append((item, err, min_count))

    # --- Guarantee 3: min counter <= floor(N / k) -------------------------
    bound_Nk = N // k
    g3_satisfied = min_count <= bound_Nk

    return {
        "N": N,
        "k": k,
        "n_monitored": len(ss.counters),
        "min_count": min_count,
        "max_count": max(c["count"] for c in ss.counters.values()),
        "bound_N_over_k": bound_Nk,
        "max_error": max(errors),
        "mean_error": float(np.mean(errors)),
        "G1_no_underestimate": {
            "holds": len(g1_violations) == 0,
            "n_violations": len(g1_violations),
            "violations_sample": g1_violations[:5],
        },
        "G2_error_le_min": {
            "holds": len(g2_violations) == 0,
            "n_violations": len(g2_violations),
            "violations_sample": g2_violations[:5],
        },
        "G3_min_le_N_over_k": {
            "holds": g3_satisfied,
            "min_count": min_count,
            "bound": bound_Nk,
        },
    }


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--N", type=int, default=10**6)
    parser.add_argument("--k", type=int, default=100)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--alphabet", type=int, default=10**5)
    parser.add_argument("--out", default="results.json")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)

    # ---- Primary run (fixed N=1e6, k=100) ---------------------------------
    print(f"[main] generating Zipfian stream N={args.N} alpha={args.alpha} "
          f"alphabet={args.alphabet} seed={args.seed}")
    stream = zipf_stream(args.N, args.alpha, args.alphabet, rng)

    primary = verify_guarantees(stream, args.k)

    # ---- Scaling study: vary N and k, hold seed fixed ---------------------
    scaling: List[Dict] = []
    # (a) hold k=100, vary N.
    for N in [10**4, 10**5, 5 * 10**5, 10**6, 2 * 10**6, 5 * 10**6]:
        s = zipf_stream(N, args.alpha, args.alphabet, rng)
        r = verify_guarantees(s, args.k)
        r["sweep_dim"] = "N"
        r["N_over_k"] = N // args.k
        scaling.append(r)
    # (b) hold N=1e6, vary k.
    N_fixed = args.N
    for k in [25, 50, 100, 200, 400, 800]:
        s = zipf_stream(N_fixed, args.alpha, args.alphabet, rng)
        r = verify_guarantees(s, k)
        r["sweep_dim"] = "k"
        r["N_over_k"] = N_fixed // k
        scaling.append(r)

    out = {"primary": primary, "scaling": scaling}
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)

    print("[main] wrote", args.out)
    print(json.dumps(primary, indent=2))


if __name__ == "__main__":
    main()