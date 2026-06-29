"""
From-scratch RAPPOR encoding/decoding pipeline (NumPy only).

Pipeline:
  Client value v
    -> Bloom filter B (k bits, h hashes)
    -> Permanent randomized response B' (f parameter, per-bit)
    -> Instantaneous randomized response S (p, q parameters, per-bit)

Aggregation/Decoding:
  Aggregate N IRR reports S over cohort -> debias each bit by
      t_i = (obs_1_ratio - p) / (q - p)
  Build design matrix X (k x M) of Bloom filters for M candidate strings.
  Solve Lasso / least-squares for candidate frequencies.

Reference: Erlingsson, Pihur, Korolova, "RAPPOR: Randomized Aggregatable
Privacy-Preserving Ordinal Response", CCS 2014.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Constants from the task
# ---------------------------------------------------------------------------
M = 20                  # candidate dictionary size
N_CLIENTS = 20_000      # number of clients
K_BITS = 128            # Bloom filter size
H_HASHES = 4            # number of hash functions
F_PRR = 0.5             # PRR parameter (per-bit)
P_IRR = 0.5             # IRR parameter (per-bit)
Q_IRR = 0.75            # IRR parameter (per-bit)

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


# ---------------------------------------------------------------------------
# Step 1: Bloom filter
# ---------------------------------------------------------------------------
def bloom_filter(value: str, k: int = K_BITS, h: int = H_HASHES,
                 seed: int = 0) -> np.ndarray:
    """Hash value v onto a k-bit Bloom filter using h hash functions.

    Each hash function uses (hash_func_index * big_prime + hash(value)) mod k
    to derive distinct bits. This mirrors the simple hash family used in
    the RAPPOR reference implementation: ``MD5(secret || cohort || value)``
    reinterpreted mod k. Here we use numpy/sha1-based hashing on a per-cohort
    secret string to obtain reproducible, distinct hash functions.
    """
    import hashlib

    bits = np.zeros(k, dtype=np.uint8)
    encoded = value.encode("utf-8")
    for j in range(h):
        # hash the value with a per-hash secret that depends on cohort seed
        digest = hashlib.sha1(
            (str(seed) + ":" + str(j) + ":" + value).encode("utf-8")
        ).digest()
        # take first 8 bytes as big-endian unsigned int
        idx = int.from_bytes(digest[:8], "big") % k
        bits[idx] = 1
    return bits


# ---------------------------------------------------------------------------
# Step 2: Permanent randomized response
# ---------------------------------------------------------------------------
def prr(B: np.ndarray, f: float, rng: np.random.Generator) -> np.ndarray:
    """For each bit of B, produce B' where:

        B'_i = 1   with prob 1/2 f
        B'_i = 0   with prob 1/2 f
        B'_i = B_i with prob 1 - f

    Reference (Erlingsson et al. 2014, Section 2):
        P(B'_i = 1 | b_i = 1) = 1/2 f + (1 - f) = 1 - 1/2 f
        P(B'_i = 1 | b_i = 0) = 1/2 f
    """
    n = B.shape[0]
    keep = rng.random(n) < (1.0 - f)
    flip = rng.random(n) < 0.5
    Bp = np.where(keep, B, flip.astype(np.uint8))
    return Bp.astype(np.uint8)


# ---------------------------------------------------------------------------
# Step 3: Instantaneous randomized response
# ---------------------------------------------------------------------------
def irr(Bp: np.ndarray, p: float, q: float,
        rng: np.random.Generator) -> np.ndarray:
    """For each bit of B', produce S where:

        P(S_i = 1 | B'_i = 1) = q
        P(S_i = 1 | B'_i = 0) = p

    Reference (Erlingsson et al. 2014, Section 2 step 3 and Lemma 1):
        q* = P(S_i = 1 | b_i = 1) = 1/2 f (p + q) + (1 - f) q
        p* = P(S_i = 1 | b_i = 0) = 1/2 f (p + q) + (1 - f) p
    """
    flips = rng.random(Bp.shape[0])
    S = np.where(
        Bp == 1,
        (flips < q).astype(np.uint8),
        (flips < p).astype(np.uint8),
    )
    return S.astype(np.uint8)


# ---------------------------------------------------------------------------
# Step 4: Cohort simulation
# ---------------------------------------------------------------------------
@dataclass
class CohortConfig:
    f: float = F_PRR
    p: float = P_IRR
    q: float = Q_IRR
    k: int = K_BITS
    h: int = H_HASHES


def true_frequencies() -> np.ndarray:
    """A skewed distribution: a few high-frequency candidates and a long tail.

    Sorted descending so the largest frequency corresponds to CANDIDATES[0].
    """
    # power-law: p_i ∝ 1/i, normalized
    raw = np.array([1.0 / (i + 1) ** 1.3 for i in range(M)])
    return raw / raw.sum()


def simulate_cohort(true_freq: np.ndarray, cfg: CohortConfig,
                    n_clients: int, seed: int
                    ) -> Tuple[np.ndarray, np.ndarray]:
    """Simulate one cohort's worth of clients and aggregate their IRR reports.

    Returns:
        S_agg: (k,) array = sum over N clients of the IRR-report bit vectors.
        counts_true: (M,) true counts of how many clients had each candidate.
    """
    rng = np.random.default_rng(seed)

    # choose a value for each client according to the true frequencies
    chosen = rng.choice(M, size=n_clients, p=true_freq)
    counts_true = np.bincount(chosen, minlength=M).astype(np.float64)

    # precompute Bloom filter for each candidate (cohort-scoped hash family)
    B_dict = np.stack(
        [bloom_filter(CANDIDATES[i], k=cfg.k, h=cfg.h, seed=seed)
         for i in range(M)],
        axis=0,
    )  # shape (M, k)

    # encode each client
    B = B_dict[chosen]                          # (N, k)
    Bp = prr_batch(B, cfg.f, rng)               # (N, k)
    S = irr_batch(Bp, cfg.p, cfg.q, rng)        # (N, k)

    S_agg = S.sum(axis=0)                       # (k,)
    return S_agg, counts_true


def prr_batch(B: np.ndarray, f: float,
              rng: np.random.Generator) -> np.ndarray:
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


# ---------------------------------------------------------------------------
# Step 5: Debiasing and Lasso regression
# ---------------------------------------------------------------------------
def debias_bits(S_agg: np.ndarray, n_clients: int, cfg: CohortConfig
                ) -> np.ndarray:
    """Aggregate debiasing per Lemma 1 / Section 4 of the paper.

    Let c_i be the number of reports with bit i = 1 in S. The expected count
    (treating the PRR-mixed bits b'_i) for cohort j with N_j clients is

        c_i = (p + 1/2 f q - 1/2 f p) N_j + (1 - f)(q - p) t_i

    where t_i = number of clients whose underlying Bloom bit was 1. Solving
    for t_i (the count) yields:

        t_i = (c_i - (p + 1/2 f q - 1/2 f p) N) / ((1 - f)(q - p))

    The paper then divides t_i by N_j to get a per-bit proportion, but for
    the regression we want the underlying Bloom-bit COUNT vector Y of length k.
    """
    bias = cfg.p + 0.5 * cfg.f * cfg.q - 0.5 * cfg.f * cfg.p
    scale = (1.0 - cfg.f) * (cfg.q - cfg.p)
    t = (S_agg - bias * n_clients) / scale
    # clip negative numerical artifacts to 0
    return np.maximum(t, 0.0)


def fit_frequencies(t_counts: np.ndarray, candidate_blooms: np.ndarray,
                    n_clients: int) -> np.ndarray:
    """Recover candidate frequencies from per-bit Bloom-COUNT estimates.

    Following Section 4 of the paper:
        Y = vector of t_i (length k = underlying Bloom-bit count)
        X = design matrix (k x M); column i is the Bloom vector of
            candidate i (binary, with h ones).
        Y ~ X β where β is the count of clients whose value is candidate i.

    We solve min ||X β - Y||^2 s.t. β >= 0 via NNLS (or projected gradient
    fallback) and normalize the result so it sums to 1 to obtain frequencies.
    """
    Mdim, k = candidate_blooms.shape
    X = candidate_blooms.T.astype(np.float64)  # (k, M), entries in {0,1}

    try:
        from scipy.optimize import nnls

        beta, _ = nnls(X, t_counts)
    except Exception:
        beta = _projected_ls(X, t_counts)

    total = beta.sum()
    if total <= 0:
        return np.full(Mdim, 1.0 / Mdim)
    return beta / total


def _projected_ls(X: np.ndarray, y: np.ndarray,
                  iters: int = 8000, lr: float = 1.0,
                  l2: float = 1e-6) -> np.ndarray:
    """Projected-gradient solver for min ||X c - y||^2 s.t. c >= 0.

    Uses an adaptive step size for stability on potentially badly-scaled
    problems.
    """
    n, m = X.shape
    c = np.zeros(m)
    XtX = X.T @ X
    Xty = X.T @ y
    # Lipschitz constant of gradient is the largest eigenvalue of XtX; we
    # estimate it cheaply from the diagonal + a few matvecs.
    L = np.linalg.norm(XtX, ord=2) + l2
    step = 1.0 / L
    for _ in range(iters):
        grad = XtX @ c - Xty + l2 * c
        c = c - step * grad
        np.maximum(c, 0, out=c)
    return c


# ---------------------------------------------------------------------------
# Main experiment loop
# ---------------------------------------------------------------------------
def run_single_seed(seed: int) -> dict:
    cfg = CohortConfig()
    true_freq = true_frequencies()

    S_agg, counts_true = simulate_cohort(true_freq, cfg, N_CLIENTS, seed)

    # Aggregate-debias to recover underlying Bloom-bit COUNTS
    t_counts = debias_bits(S_agg, N_CLIENTS, cfg)

    # Build candidate Bloom dictionary (cohort-scoped)
    B_dict = np.stack(
        [bloom_filter(CANDIDATES[i], k=cfg.k, h=cfg.h, seed=seed)
         for i in range(M)],
        axis=0,
    )

    est_freq = fit_frequencies(t_counts, B_dict, N_CLIENTS)

    l1_err = float(np.abs(est_freq - true_freq).sum())
    max_err = float(np.max(np.abs(est_freq - true_freq)))
    return dict(seed=seed,
                true_freq=true_freq.tolist(),
                est_freq=est_freq.tolist(),
                l1_err=l1_err,
                max_err=max_err)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    parser.add_argument("--out", type=str,
                        default="rappor_results.json")
    args = parser.parse_args()

    results = [run_single_seed(s) for s in args.seeds]

    l1 = np.array([r["l1_err"] for r in results])
    mx = np.array([r["max_err"] for r in results])

    print(f"Seeds: {args.seeds}")
    print(f"L1 error  mean={l1.mean():.4f}  std={l1.std():.4f}  per-seed={l1.tolist()}")
    print(f"Max error mean={mx.mean():.4f}  std={mx.std():.4f}  per-seed={mx.tolist()}")

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()