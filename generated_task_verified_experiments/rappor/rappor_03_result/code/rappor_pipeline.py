"""
RAPPOR encode-decode pipeline from scratch (NumPy, CPU only).

Pipeline:
  value v -> Bloom vector B (k bits, h hashes)
  -> PRR (per-bit param f)
  -> IRR (per-bit params p, q)
  -> aggregate N client IRR reports, debias each bit to recover Bloom-bit
     probabilities, then non-negative least squares / Lasso over the candidate
     dictionary to recover per-candidate frequencies.

Fixed experimental setup (see task.md):
  M = 20 candidate strings, custom true freq (few high + long tail)
  N = 2e4 clients
  Bloom: k = 128, h = 4
  PRR f = 0.5 ; IRR p = 0.5, q = 0.75
  >= 3 random seeds, report mean.
"""

import hashlib
import numpy as np
from scipy.optimize import nnls
from sklearn.linear_model import Lasso

# ----------------------------------------------------------------------------
# Parameters (fixed by task)
# ----------------------------------------------------------------------------
K = 128        # Bloom bits
H = 4          # number of hash functions
F = 0.5        # PRR per-bit flip prob
P = 0.5        # IRR P(report=1 | PRR=0)
Q = 0.75       # IRR P(report=1 | PRR=1)
N = 20000      # clients
M = 20         # candidate dictionary size

CANDIDATES = [
    "google.com", "youtube.com", "facebook.com", "amazon.com", "wikipedia.org",
    "twitter.com", "instagram.com", "linkedin.com", "reddit.com", "netflix.com",
    "github.com", "stackoverflow.com", "dropbox.com", "spotify.com", "ebay.com",
    "cnn.com", "weather.com", "espn.com", "pinterest.com", "tumblr.com",
]

# True frequency distribution: a few high-frequency + long tail.
TRUE_FREQ = np.array([
    0.20, 0.15, 0.12, 0.10, 0.08,
    0.06, 0.05, 0.04, 0.035, 0.03,
    0.025, 0.02, 0.015, 0.012, 0.010,
    0.008, 0.006, 0.005, 0.003, 0.002,
])
TRUE_FREQ = TRUE_FREQ / TRUE_FREQ.sum()  # ensure normalized


# ----------------------------------------------------------------------------
# Hashing / Bloom
# ----------------------------------------------------------------------------
def hash_bits(value, h, k):
    """Return h bit positions for a string value."""
    bits = []
    for i in range(h):
        digest = hashlib.md5(("%d|%s" % (i, value)).encode("utf-8")).hexdigest()
        pos = int(digest, 16) % k
        bits.append(pos)
    return bits


def bloom_vector(value, h, k):
    """Bloom vector B in {0,1}^k for value."""
    B = np.zeros(k, dtype=np.int8)
    for pos in hash_bits(value, h, k):
        B[pos] = 1
    return B


def candidate_matrix(candidates, h, k):
    """A: shape (M, k), row j = Bloom vector of candidate j."""
    A = np.zeros((len(candidates), k), dtype=np.float64)
    for j, s in enumerate(candidates):
        A[j] = bloom_vector(s, h, k)
    return A


# ----------------------------------------------------------------------------
# RAPPOR encoding
# ----------------------------------------------------------------------------
def prr(B, f, rng):
    """Permanent Randomized Response.

    For each bit: with prob f output a fresh Bernoulli(0.5) bit, else keep B[i].
    E[PRR_i] = (1-f)*B[i] + f/2.
    """
    rand_flip = rng.random(len(B)) < f
    fresh = (rng.random(len(B)) < 0.5).astype(np.int8)
    out = np.where(rand_flip, fresh, B)
    return out.astype(np.int8)


def irr(P, p, q, rng):
    """Instantaneous Randomized Response.

    report_i ~ Bernoulli(q) if PRR_i=1 else Bernoulli(p).
    """
    prob = np.where(P == 1, q, p)
    return (rng.random(len(P)) < prob).astype(np.int8)


def encode_client(value, h, k, f, p, q, rng):
    """Full client-side encoding: value -> IRR report (k bits)."""
    B = bloom_vector(value, h, k)
    P = prr(B, f, rng)
    R = irr(P, p, q, rng)
    return R


# ----------------------------------------------------------------------------
# Aggregation / decoding
# ----------------------------------------------------------------------------
def debias_bit_probs(reports, p, q, f):
    """From N IRR reports (shape (N,k)), estimate per-bit Bloom-bit prob.

    obs proportion x_i ~ p + (q-p)*((1-f)*B_i + f/2)
    => Bloom-bit prob estimate = ((x_i - p)/(q-p) - f/2) / (1-f)
    """
    x = reports.mean(axis=0)                 # observed 1-proportion per bit
    t = (x - p) / (q - p)                    # estimate of (1-f)*B + f/2
    b_hat = (t - f / 2.0) / (1.0 - f)        # estimate of Bloom-bit prob
    return np.clip(b_hat, 0.0, 1.0)


def decode_nnls(A, b_hat):
    """Non-negative least squares: min ||A^T freq - b_hat||, freq >= 0.
    A shape (M,k); b_hat shape (k,). Then normalize to sum 1.
    """
    freq, _ = nnls(A.T, b_hat)
    s = freq.sum()
    if s > 0:
        freq = freq / s
    return freq


def decode_lasso(A, b_hat, alpha=1e-4):
    """Lasso regression with non-negativity (positive=True)."""
    model = Lasso(alpha=alpha, positive=True, fit_intercept=False,
                  max_iter=20000, selection="cyclic")
    model.fit(A.T, b_hat)
    freq = np.clip(model.coef_, 0, None)
    s = freq.sum()
    if s > 0:
        freq = freq / s
    return freq


# ----------------------------------------------------------------------------
# Experiment driver
# ----------------------------------------------------------------------------
def run_seed(seed, candidates, true_freq, n, h, k, f, p, q, decoder="nnls"):
    rng = np.random.default_rng(seed)
    A = candidate_matrix(candidates, h, k)

    # sample each client's true string according to true_freq
    idx = rng.choice(len(candidates), size=n, p=true_freq)
    reports = np.zeros((n, k), dtype=np.int8)
    for i in range(n):
        reports[i] = encode_client(candidates[idx[i]], h, k, f, p, q, rng)

    b_hat = debias_bit_probs(reports, p, q, f)

    if decoder == "nnls":
        freq_hat = decode_nnls(A, b_hat)
    else:
        freq_hat = decode_lasso(A, b_hat)

    l1 = np.abs(freq_hat - true_freq).sum()
    maxerr = np.abs(freq_hat - true_freq).max()
    return freq_hat, l1, maxerr, b_hat


def main():
    seeds = [1, 2, 3, 7]
    print("True freq (sum=%.4f):" % TRUE_FREQ.sum(), np.round(TRUE_FREQ, 4))
    print("Candidate strings:", CANDIDATES)
    print()

    all_hat_nnls = []
    all_hat_lasso = []
    metrics_nnls = []
    metrics_lasso = []

    for seed in seeds:
        fh, l1, mx, bhat = run_seed(seed, CANDIDATES, TRUE_FREQ, N, H, K, F, P, Q,
                                    decoder="nnls")
        all_hat_nnls.append(fh)
        metrics_nnls.append((l1, mx))
        print("[seed %d] NNLS  L1=%.4f  max|err|=%.4f" % (seed, l1, mx))

        fh2, l12, mx2, _ = run_seed(seed, CANDIDATES, TRUE_FREQ, N, H, K, F, P, Q,
                                    decoder="lasso")
        all_hat_lasso.append(fh2)
        metrics_lasso.append((l12, mx2))
        print("[seed %d] Lasso L1=%.4f  max|err|=%.4f" % (seed, l12, mx2))

    mean_hat = np.mean(all_hat_nnls, axis=0)
    mean_l1 = np.mean([m[0] for m in metrics_nnls])
    mean_max = np.mean([m[1] for m in metrics_nnls])
    std_l1 = np.std([m[0] for m in metrics_nnls])

    mean_hat_l = np.mean(all_hat_lasso, axis=0)
    mean_l1_l = np.mean([m[0] for m in metrics_lasso])
    mean_max_l = np.mean([m[1] for m in metrics_lasso])

    print()
    print("=" * 70)
    print("Per-candidate: true vs NNLS-est (mean over %d seeds)" % len(seeds))
    print("%-22s %8s %8s %8s" % ("candidate", "true", "est", "abs_err"))
    for j, s in enumerate(CANDIDATES):
        print("%-22s %8.4f %8.4f %8.4f" % (s, TRUE_FREQ[j], mean_hat[j],
                                          abs(mean_hat[j] - TRUE_FREQ[j])))
    print("-" * 70)
    print("NNLS  mean L1=%.4f  mean max|err|=%.4f  (std L1=%.4f)" %
          (mean_l1, mean_max, std_l1))
    print("Lasso mean L1=%.4f  mean max|err|=%.4f" % (mean_l1_l, mean_max_l))

    # save results to npz for the summary writer
    np.savez("rappor_results.npz",
             candidates=np.array(CANDIDATES),
             true_freq=TRUE_FREQ,
             est_nnls=mean_hat,
             est_lasso=mean_hat_l,
             metrics_nnls=np.array(metrics_nnls),
             metrics_lasso=np.array(metrics_lasso),
             seeds=np.array(seeds))


if __name__ == "__main__":
    main()
