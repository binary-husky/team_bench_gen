"""
RAPPOR privacy-utility tradeoff experiment.

Pipeline:
  1. Build a candidate dictionary D with M strings + a true frequency distribution.
  2. Sample N = 5e4 reports (clients) from the true distribution.
  3. For each client, run the full RAPPOR encoder:
       - Bloom filter B (k bits, h hash functions).
       - Permanent randomized response (PRR) with parameter f -> B'.
       - Instantaneous randomized response (IRR) with (p, q) -> S (the report).
  4. Aggregate: count c_i = number of reports with bit i = 1.
  5. Decode per-bit estimates t_ij (Sec. 4 of Erlingsson et al. 2014):
       t_ij = (c_ij - (p + (1/2)*f*q - (1/2)*f*p) * N_i) / ((1 - f/2) * (q - p))
  6. Build the design matrix X (k x M) and solve least-squares / LASSO
     t_avg = X * c_hat for c_hat (counts per candidate).
  7. Report L1 and max-absolute frequency-estimation error vs. true counts.

We also run a non-private baseline (clients report true string verbatim,
server counts directly) for reference.

For each f we run >= 3 random seeds and average the error metrics.
"""

import json
import math
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
from sklearn.linear_model import Lasso


# ----------------------- Fixed experimental settings ------------------------

N = int(5e4)            # number of clients / reports
K = 128                 # Bloom filter size
H = 4                   # number of hash functions
P = 0.5                 # IRR p
Q = 0.75                # IRR q
SEEDS = [11, 22, 33]    # >= 3 random seeds per f
F_VALUES = [0.1, 0.25, 0.5, 0.75, 0.9]


# ----------------------- Candidate dictionary + true dist -------------------

def make_candidate_dict(M: int = 200) -> List[str]:
    """Build a synthetic candidate dictionary of M strings.
    The first 100 are 'common' (will get non-trivial true probability),
    the rest are 'tail' strings."""
    common = [f"common_{i:03d}" for i in range(100)]
    tail   = [f"tail_{i:04d}"   for i in range(M - 100)]
    return common + tail


def make_true_probs(M: int) -> np.ndarray:
    """Exponential-decay true frequency over the dictionary.
    Roughly Zipfian: the first ~20 strings carry most of the mass,
    the long tail has very small but non-zero probabilities."""
    rng = np.random.default_rng(0)
    raw = np.exp(-0.05 * np.arange(M))              # exp decay
    # add a little jitter so it doesn't look perfectly monotone
    jitter = 1.0 + 0.05 * rng.standard_normal(M)
    raw = np.clip(raw * jitter, 1e-6, None)
    raw /= raw.sum()
    return raw


# ----------------------- Bloom filter ---------------------------------------

def hash_string(s: str, salt: int, k: int) -> int:
    """Deterministic non-negative integer hash for (string, salt)."""
    import hashlib
    h = hashlib.sha256()
    h.update(salt.to_bytes(4, "little", signed=True))
    h.update(s.encode("utf-8"))
    return int.from_bytes(h.digest()[:8], "little") % k


def bloom_filter(value: str, k: int, h: int) -> np.ndarray:
    """Return length-k boolean Bloom filter for value with h hash functions."""
    bits = np.zeros(k, dtype=np.uint8)
    for j in range(h):
        bits[hash_string(value, j, k)] = 1
    return bits


# ----------------------- RAPPOR encoder -------------------------------------

def rappor_encode(value: str, f: float, p: float, q: float,
                  k: int, h: int, rng: np.random.Generator) -> np.ndarray:
    """Encode a single value into a length-k RAPPOR report S."""
    B = bloom_filter(value, k, h)

    # Permanent RR -> B'
    keep = rng.random(k) >= f                    # 1 - f chance to keep B
    flip = rng.random(k) < 0.5                   # for the kept-away bits, flip 50/50
    flip_mask = (~keep.astype(bool)) & flip
    one_mask  = (~keep.astype(bool)) & (~flip)
    Bp = np.where(keep, B, np.where(one_mask, 1, 0)).astype(np.uint8)

    # Instantaneous RR -> S
    u = rng.random(k)
    S = np.where(Bp == 1, u < q, u < p).astype(np.uint8)
    return S


# ----------------------- RAPPOR decoder -------------------------------------

def decode_counts(reports: np.ndarray, f: float, p: float, q: float,
                  N_eff: int) -> np.ndarray:
    """Section 4 of the paper:
        t_ij = (c_ij - (p + (1/2) f q - (1/2) f p) * N_i) /
               ((1 - f/2) (q - p))
    """
    c = reports.sum(axis=0).astype(np.float64)            # length-k
    bias = (p + 0.5 * f * q - 0.5 * f * p) * N_eff
    scale = (1.0 - f / 2.0) * (q - p)
    t = (c - bias) / scale
    return t


def lasso_decode(design: np.ndarray, t: np.ndarray, alpha: float = 1e-3,
                 positive: bool = True) -> np.ndarray:
    """Solve  t ~= X * c_hat  with non-negative LASSO.
    Returns non-negative count estimate per candidate string."""
    model = Lasso(alpha=alpha, fit_intercept=False, positive=positive,
                  max_iter=20_000)
    model.fit(design, t)
    return np.maximum(model.coef_, 0.0)


def nonneg_lstsq(design: np.ndarray, t: np.ndarray) -> np.ndarray:
    """NNLS fallback if LASSO underfits badly."""
    from scipy.optimize import nnls
    coef, _ = nnls(design, t)
    return coef


# ----------------------- End-to-end runs ------------------------------------

@dataclass
class RunResult:
    f: float
    epsilon_perm: float
    seed: int
    l1_error: float
    max_abs_error: float
    true_counts: np.ndarray
    est_counts: np.ndarray


def run_rappor_once(candidates: List[str], true_probs: np.ndarray,
                    f: float, seed: int) -> RunResult:
    rng = np.random.default_rng(seed)

    # 1) Sample N true strings
    idx = rng.choice(len(candidates), size=N, p=true_probs)
    true_strings = [candidates[i] for i in idx]

    # 2) Encode every report
    reports = np.zeros((N, K), dtype=np.uint8)
    for i, v in enumerate(true_strings):
        reports[i] = rappor_encode(v, f, P, Q, K, H, rng)

    # 3) Decode
    design = np.stack([bloom_filter(v, K, H) for v in candidates]).astype(np.float64).T  # (k, M)
    t = decode_counts(reports, f, P, Q, N)

    # 4) LASSO decode
    est = lasso_decode(design, t, alpha=5e-4, positive=True)

    # If LASSO leaves too much mass unexplained, fall back to NNLS
    resid = np.linalg.norm(design @ est - t) / max(np.linalg.norm(t), 1e-9)
    if resid > 0.5:
        est = nonneg_lstsq(design, t)

    true_counts = true_probs * N
    err = est - true_counts
    l1 = float(np.sum(np.abs(err)))
    mx = float(np.max(np.abs(err)))

    eps_perm = math.log((2.0 - f) / f)
    return RunResult(f=f, epsilon_perm=eps_perm, seed=seed,
                     l1_error=l1, max_abs_error=mx,
                     true_counts=true_counts, est_counts=est)


def run_nonprivate_baseline(candidates: List[str], true_probs: np.ndarray,
                            seed: int) -> Tuple[float, float]:
    """Clients report true string verbatim, server counts directly."""
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(candidates), size=N, p=true_probs)
    counts = np.bincount(idx, minlength=len(candidates)).astype(np.float64)
    true_counts = true_probs * N
    err = counts - true_counts
    return float(np.sum(np.abs(err))), float(np.max(np.abs(err)))


# ----------------------- Main -----------------------------------------------

def main():
    t0 = time.time()
    candidates = make_candidate_dict(M=200)
    true_probs = make_true_probs(len(candidates))
    print(f"Candidate dict M = {len(candidates)}, "
          f"top-5 true probs = {np.round(true_probs[:5], 4)}")

    results: List[RunResult] = []

    print("\n=== RAPPOR runs ===")
    for f in F_VALUES:
        eps = math.log((2.0 - f) / f)
        l1_list, mx_list = [], []
        for seed in SEEDS:
            r = run_rappor_once(candidates, true_probs, f, seed)
            results.append(r)
            l1_list.append(r.l1_error)
            mx_list.append(r.max_abs_error)
            print(f"  f={f:.2f}  eps_perm={eps:.4f}  seed={seed}  "
                  f"L1={r.l1_error:8.2f}  max={r.max_abs_error:7.2f}")
        print(f"  -> f={f:.2f}: mean L1={np.mean(l1_list):.2f}, "
              f"mean max={np.mean(mx_list):.2f}")

    print("\n=== Non-private baseline ===")
    base_l1, base_mx = [], []
    for seed in SEEDS:
        l1, mx = run_nonprivate_baseline(candidates, true_probs, seed)
        base_l1.append(l1)
        base_mx.append(mx)
        print(f"  seed={seed}  L1={l1:.2f}  max={mx:.2f}")
    print(f"  -> baseline mean L1={np.mean(base_l1):.2f}, "
          f"mean max={np.mean(base_mx):.2f}")

    # Save raw artefacts
    dump = {
        "settings": dict(N=N, K=K, H=H, p=P, q=Q, seeds=SEEDS,
                         f_values=F_VALUES, M=len(candidates)),
        "rappor": [
            dict(f=r.f, epsilon_perm=r.epsilon_perm, seed=r.seed,
                 l1_error=r.l1_error, max_abs_error=r.max_abs_error)
            for r in results
        ],
        "baseline": dict(l1_mean=float(np.mean(base_l1)),
                         l1_std=float(np.std(base_l1)),
                         max_mean=float(np.mean(base_mx)),
                         max_std=float(np.std(base_mx))),
    }
    with open("results_raw.json", "w") as fp:
        json.dump(dump, fp, indent=2)
    print(f"\nTotal runtime: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()