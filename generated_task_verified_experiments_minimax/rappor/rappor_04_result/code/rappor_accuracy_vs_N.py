"""
RAPPOR accuracy vs. number of clients (N).

Reuses the full encode/decode pipeline of rappor_03 (Bloom -> PRR -> IRR
-> debias -> NNLS) and sweeps N in {2e3, 5e3, 1e4, 2e4, 5e4, 1e5} with
several random seeds each. The goal is to verify that the frequency
estimation error shrinks ~ 1/sqrt(N) — the standard Monte-Carlo / CLT
rate for mean-of-aggregated-noisy-bits estimators.

Fixed experimental setup (per task):
  - Candidate dictionary:  M = 20  strings
  - True freq:  power-law skewed distribution (same as _03)
  - Bloom:      k = 128 bits, h = 4 hashes
  - PRR:        f = 0.5
  - IRR:        p = 0.5,  q = 0.75
  - Sweep N over {2e3, 5e3, 1e4, 2e4, 5e4, 1e5}
  - seeds per N: 3 (configurable)

Outputs:
  - rappor_04_results.json  (raw per-seed L1 / max errors)
  - rappor_04_summary.csv   (mean +/- std for plotting)
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from typing import List

import numpy as np

# Re-use all primitives from the previous task (kept here inline so the
# script is self-contained and does not depend on the _03 path).

M = 20
K_BITS = 128
H_HASHES = 4
F_PRR = 0.5
P_IRR = 0.5
Q_IRR = 0.75

CANDIDATES = [
    "https://news.example.com",
    "https://mail.example.com",
    "https://search.example.com",
    "https://shop.example.com",
    "https://video.example.com",
    "https://music.example.com",
    "https://maps.example.com",
    "https://weather.example.com",
    "https://sports.example.com",
    "https://finance.example.com",
    "https://travel.example.com",
    "https://food.example.com",
    "https://books.example.com",
    "https://games.example.com",
    "https://social.example.com",
    "https://edu.example.com",
    "https://health.example.com",
    "https://tech.example.com",
    "https://fashion.example.com",
    "https://misc.example.com",
]
assert len(CANDIDATES) == M

# --------------------------------------------------------------------- #
# Step 1: Bloom filter                                                  #
# --------------------------------------------------------------------- #
def bloom_filter(value: str, k: int = K_BITS, h: int = H_HASHES,
                 seed: int = 0) -> np.ndarray:
    import hashlib
    bits = np.zeros(k, dtype=np.uint8)
    for j in range(h):
        digest = hashlib.sha1(
            (str(seed) + ":" + str(j) + ":" + value).encode("utf-8")
        ).digest()
        idx = int.from_bytes(digest[:8], "big") % k
        bits[idx] = 1
    return bits


# --------------------------------------------------------------------- #
# Step 2 + 3: PRR and IRR (vectorised for speed)                        #
# --------------------------------------------------------------------- #
def prr_batch(B: np.ndarray, f: float, rng: np.random.Generator) -> np.ndarray:
    keep = rng.random(B.shape) < (1.0 - f)
    flip = (rng.random(B.shape) < 0.5).astype(np.uint8)
    return np.where(keep, B, flip).astype(np.uint8)


def irr_batch(Bp: np.ndarray, p: float, q: float,
              rng: np.random.Generator) -> np.ndarray:
    flips = rng.random(Bp.shape)
    out = np.empty(Bp.shape, dtype=np.uint8)
    mask_one = Bp == 1
    out[mask_one] = (flips[mask_one] < q).astype(np.uint8)
    out[~mask_one] = (flips[~mask_one] < p).astype(np.uint8)
    return out


# --------------------------------------------------------------------- #
# Cohort simulation                                                     #
# --------------------------------------------------------------------- #
def true_frequencies() -> np.ndarray:
    """Same skewed (power-law-ish) distribution as _03."""
    raw = np.array([1.0 / (i + 1) ** 1.3 for i in range(M)])
    return raw / raw.sum()


def simulate_cohort(true_freq: np.ndarray, n_clients: int, seed: int
                    ):
    """Run the full client-side pipeline once for `n_clients` clients.

    Returns (S_agg, counts_true, B_dict) where
        S_agg       : (k,) sum of IRR reports over all clients
        counts_true : (M,) observed counts of each candidate value
        B_dict      : (M, k) Bloom-filter dictionary (cohort-scoped)
    """
    rng = np.random.default_rng(seed)
    chosen = rng.choice(M, size=n_clients, p=true_freq)
    counts_true = np.bincount(chosen, minlength=M).astype(np.float64)

    B_dict = np.stack(
        [bloom_filter(CANDIDATES[i], k=K_BITS, h=H_HASHES, seed=seed)
         for i in range(M)],
        axis=0,
    )  # (M, k)

    B = B_dict[chosen]                          # (N, k)
    Bp = prr_batch(B, F_PRR, rng)               # (N, k)
    S = irr_batch(Bp, P_IRR, Q_IRR, rng)        # (N, k)
    S_agg = S.sum(axis=0)                       # (k,)
    return S_agg, counts_true, B_dict


# --------------------------------------------------------------------- #
# Step 5: Debias + frequency recovery (NNLS)                             #
# --------------------------------------------------------------------- #
def debias_bits(S_agg: np.ndarray, n_clients: int) -> np.ndarray:
    """Per-bit debiasing.  See rappor_03 / Lemma 1 of the paper."""
    obs_ratio = S_agg / n_clients
    bias = P_IRR + 0.5 * F_PRR * Q_IRR - 0.5 * F_PRR * P_IRR
    scale = (1.0 - F_PRR) * (Q_IRR - P_IRR)
    p_hat = (obs_ratio - bias) / scale
    return np.clip(p_hat, 0.0, 1.0)


def fit_frequencies(p_hat: np.ndarray, candidate_blooms: np.ndarray) -> np.ndarray:
    """Solve min ||X c - p_hat||^2  s.t. c >= 0  via scipy NNLS,
    then normalise to sum to 1."""
    from scipy.optimize import nnls
    X = candidate_blooms.T.astype(np.float64) * (1.0 / candidate_blooms.shape[0])
    c, _ = nnls(X, p_hat)
    total = c.sum()
    if total <= 0:
        return np.full(M, 1.0 / M)
    return c / total


# --------------------------------------------------------------------- #
# Per-seed run                                                          #
# --------------------------------------------------------------------- #
def run_one(n_clients: int, seed: int) -> dict:
    true_freq = true_frequencies()
    S_agg, _counts_true, B_dict = simulate_cohort(true_freq, n_clients, seed)
    p_hat = debias_bits(S_agg, n_clients)
    est_freq = fit_frequencies(p_hat, B_dict)
    l1_err = float(np.abs(est_freq - true_freq).sum())
    max_err = float(np.max(np.abs(est_freq - true_freq)))
    return dict(N=n_clients, seed=seed,
                true_freq=true_freq.tolist(),
                est_freq=est_freq.tolist(),
                l1_err=l1_err, max_err=max_err)


# --------------------------------------------------------------------- #
# Main                                                                  #
# --------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--Ns", type=int, nargs="+",
                    default=[2_000, 5_000, 10_000, 20_000, 50_000, 100_000])
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--out_json", type=str,
                    default="rappor_04_results.json")
    ap.add_argument("--out_csv", type=str,
                    default="rappor_04_summary.csv")
    args = ap.parse_args()

    t0 = time.time()
    raw = []
    for N in args.Ns:
        for s in args.seeds:
            ts = time.time()
            r = run_one(N, s)
            dt = time.time() - ts
            print(f"  N={N:>7d}  seed={s}  "
                  f"L1={r['l1_err']:.4f}  max={r['max_err']:.4f}  "
                  f"({dt:5.1f}s)")
            raw.append(r)

    with open(args.out_json, "w") as f:
        json.dump(raw, f, indent=2)
    print(f"\nwrote {args.out_json}  ({time.time() - t0:.1f}s total)")

    # Build the per-N summary CSV
    Ns = sorted({r["N"] for r in raw})
    rows = []
    for N in Ns:
        l1 = np.array([r["l1_err"] for r in raw if r["N"] == N])
        mx = np.array([r["max_err"] for r in raw if r["N"] == N])
        rows.append({
            "N": N,
            "L1_mean": float(l1.mean()),
            "L1_std":  float(l1.std(ddof=0)),
            "Max_mean": float(mx.mean()),
            "Max_std":  float(mx.std(ddof=0)),
            "n_seeds":  int(l1.size),
        })
    with open(args.out_csv, "w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["N", "L1_mean", "L1_std", "Max_mean", "Max_std", "n_seeds"]
        )
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote {args.out_csv}")
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
