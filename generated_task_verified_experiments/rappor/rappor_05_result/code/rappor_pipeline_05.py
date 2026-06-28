"""
RAPPOR privacy-utility sweep (NumPy, CPU only).

Reuses the full RAPPOR encode-decode pipeline from rappor_03/04. We sweep the
PRR parameter f (the privacy knob) and measure frequency-estimation error,
comparing against a non-private direct-count baseline.

PRR (Permanent Randomized Response):
    B'_i = B_i with prob (1-f), else a fresh Bernoulli(1/2) bit.   (equivalently
    "kept with prob 1 - f/2, flipped with prob f/2")
    => local DP guarantee  eps_perm = ln((2-f)/f).
IRR (Instantaneous RR): report_i ~ Bernoulli(q) if B'_i=1 else Bernoulli(p).

Fixed setup: N=5e4, Bloom k=128 h=4, IRR p=0.5 q=0.75, M=20 candidates.
Sweep f in {0.1,0.25,0.5,0.75,0.9}  (eps_perm from ~2.94 down to ~0.20).
>=3 seeds per f; also >=3 seeds for the non-private baseline.
"""

import hashlib
import numpy as np
from scipy.optimize import nnls

# ----------------------------------------------------------------------------
# Fixed parameters
# ----------------------------------------------------------------------------
K = 128        # Bloom bits
H = 4          # number of hash functions
P = 0.5        # IRR P(report=1 | PRR=0)
Q = 0.75       # IRR P(report=1 | PRR=1)
N = 50000      # clients
M = 20         # candidate dictionary size

CANDIDATES = [
    "google.com", "youtube.com", "facebook.com", "amazon.com", "wikipedia.org",
    "twitter.com", "instagram.com", "linkedin.com", "reddit.com", "netflix.com",
    "github.com", "stackoverflow.com", "dropbox.com", "spotify.com", "ebay.com",
    "cnn.com", "weather.com", "espn.com", "pinterest.com", "tumblr.com",
]

TRUE_FREQ = np.array([
    0.20, 0.15, 0.12, 0.10, 0.08,
    0.06, 0.05, 0.04, 0.035, 0.03,
    0.025, 0.02, 0.015, 0.012, 0.010,
    0.008, 0.006, 0.005, 0.003, 0.002,
])
TRUE_FREQ = TRUE_FREQ / TRUE_FREQ.sum()

F_GRID = [0.1, 0.25, 0.5, 0.75, 0.9]
SEEDS = [1, 2, 3, 7]


def eps_perm(f):
    return np.log((2.0 - f) / f)


# ----------------------------------------------------------------------------
# Hashing / Bloom
# ----------------------------------------------------------------------------
def hash_bits(value, h, k):
    bits = []
    for i in range(h):
        digest = hashlib.md5(("%d|%s" % (i, value)).encode("utf-8")).hexdigest()
        pos = int(digest, 16) % k
        bits.append(pos)
    return bits


def bloom_vector(value, h, k):
    B = np.zeros(k, dtype=np.int8)
    for pos in hash_bits(value, h, k):
        B[pos] = 1
    return B


def candidate_matrix(candidates, h, k):
    A = np.zeros((len(candidates), k), dtype=np.float64)
    for j, s in enumerate(candidates):
        A[j] = bloom_vector(s, h, k)
    return A


# ----------------------------------------------------------------------------
# RAPPOR encoding
# ----------------------------------------------------------------------------
def prr(B, f, rng):
    rand_flip = rng.random(len(B)) < f
    fresh = (rng.random(len(B)) < 0.5).astype(np.int8)
    return np.where(rand_flip, fresh, B).astype(np.int8)


def irr(P_rr, p, q, rng):
    prob = np.where(P_rr == 1, q, p)
    return (rng.random(len(P_rr)) < prob).astype(np.int8)


def encode_client(value, h, k, f, p, q, rng):
    B = bloom_vector(value, h, k)
    P_ = prr(B, f, rng)
    return irr(P_, p, q, rng)


# ----------------------------------------------------------------------------
# Decoding
# ----------------------------------------------------------------------------
def debias_bit_probs(reports, p, q, f):
    """Estimate per-bit Bloom-bit prob from N IRR reports.

    x_i ~ p + (q-p)*((1-f)*B_i + f/2)
    => B_hat = ((x_i - p)/(q-p) - f/2) / (1-f)
    """
    x = reports.mean(axis=0)
    t = (x - p) / (q - p)
    b_hat = (t - f / 2.0) / (1.0 - f)
    return np.clip(b_hat, 0.0, 1.0)


def decode_nnls(A, b_hat):
    freq, _ = nnls(A.T, b_hat)
    s = freq.sum()
    if s > 0:
        freq = freq / s
    return freq


# ----------------------------------------------------------------------------
# Experiment drivers
# ----------------------------------------------------------------------------
def run_rappor(seed, candidates, true_freq, n, h, k, f, p, q):
    rng = np.random.default_rng(seed)
    A = candidate_matrix(candidates, h, k)
    idx = rng.choice(len(candidates), size=n, p=true_freq)
    reports = np.zeros((n, k), dtype=np.int8)
    for i in range(n):
        reports[i] = encode_client(candidates[idx[i]], h, k, f, p, q, rng)
    b_hat = debias_bit_probs(reports, p, q, f)
    freq_hat = decode_nnls(A, b_hat)
    l1 = np.abs(freq_hat - true_freq).sum()
    maxerr = np.abs(freq_hat - true_freq).max()
    return freq_hat, l1, maxerr


def run_baseline(seed, candidates, true_freq, n):
    """Non-private direct counting: clients report true strings honestly."""
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(candidates), size=n, p=true_freq)
    counts = np.bincount(idx, minlength=len(candidates)).astype(np.float64)
    freq_hat = counts / counts.sum()
    l1 = np.abs(freq_hat - true_freq).sum()
    maxerr = np.abs(freq_hat - true_freq).max()
    return freq_hat, l1, maxerr


def main():
    print("True freq (sum=%.4f):" % TRUE_FREQ.sum(), np.round(TRUE_FREQ, 4))
    print("N=%d  k=%d  h=%d  p=%.2f  q=%.2f" % (N, K, H, P, Q))
    print()

    results = {}  # f -> list of (l1, maxerr)

    # ---- RAPPOR sweep over f ----
    for f in F_GRID:
        ep = eps_perm(f)
        mets = []
        for seed in SEEDS:
            _, l1, mx = run_rappor(seed, CANDIDATES, TRUE_FREQ, N, H, K, f, P, Q)
            mets.append((l1, mx))
            print("[f=%.2f eps=%.3f seed=%d] L1=%.4f  max|err|=%.4f"
                  % (f, ep, seed, l1, mx))
        l1s = np.array([m[0] for m in mets])
        mxs = np.array([m[1] for m in mets])
        results[f] = (ep, l1s, mxs)
        print("  -> f=%.2f eps=%.3f  mean L1=%.4f (std=%.4f)  "
              "mean max|err|=%.4f (std=%.4f)"
              % (f, ep, l1s.mean(), l1s.std(), mxs.mean(), mxs.std()))
        print()

    # ---- Non-private baseline ----
    base_mets = []
    for seed in SEEDS:
        _, l1, mx = run_baseline(seed, CANDIDATES, TRUE_FREQ, N)
        base_mets.append((l1, mx))
        print("[baseline seed=%d] L1=%.4f  max|err|=%.4f" % (seed, l1, mx))
    b_l1 = np.array([m[0] for m in base_mets])
    b_mx = np.array([m[1] for m in base_mets])
    print("  -> BASELINE mean L1=%.4f (std=%.4f)  mean max|err|=%.4f (std=%.4f)"
          % (b_l1.mean(), b_l1.std(), b_mx.mean(), b_mx.std()))
    print()

    # ---- save ----
    save = dict(
        candidates=np.array(CANDIDATES),
        true_freq=TRUE_FREQ,
        f_grid=np.array(F_GRID),
        eps=np.array([eps_perm(f) for f in F_GRID]),
        seeds=np.array(SEEDS),
        baseline_l1=b_l1, baseline_max=b_mx,
    )
    for f in F_GRID:
        ep, l1s, mxs = results[f]
        tag = ("f%d" % int(f * 100))
        save["l1_" + tag] = l1s
        save["max_" + tag] = mxs
    np.savez("rappor_results_05.npz", **save)

    # ---- summary table ----
    print("=" * 78)
    print("%-8s %-10s %-16s %-16s" % ("f", "eps_perm", "L1 (mean±std)", "max|err| (mean±std)"))
    print("-" * 78)
    for f in F_GRID:
        ep, l1s, mxs = results[f]
        print("%-8.2f %-10.3f %.4f±%.4f    %.4f±%.4f"
              % (f, ep, l1s.mean(), l1s.std(), mxs.mean(), mxs.std()))
    print("%-8s %-10s %.4f±%.4f    %.4f±%.4f"
          % ("base", "inf", b_l1.mean(), b_l1.std(), b_mx.mean(), b_mx.std()))
    print("=" * 78)


if __name__ == "__main__":
    main()
