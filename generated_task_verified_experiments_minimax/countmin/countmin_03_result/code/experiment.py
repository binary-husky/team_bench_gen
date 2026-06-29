"""
Count-Min Sketch: how depth d compresses the tail-failure probability
at fixed width w = 1024.

We implement Count-Min from the Cormode-Muthukrishnan paper:
    d pairwise-independent hash functions h_1..h_d : items -> {1..w}
    Update:   count[j, h_j(i)] += c_t   (j = 1..d)
    Point query: a_hat[i] = min_j count[j, h_j(i)]

Theoretical guarantee (Theorem 1, non-negative case):
    Pr[ a_hat[i] > a[i] + eps * ||a||_1 ]  <=  (1/e)^d,
with eps = e/w.  Equivalently failure probability decays like e^{-d}.

We test this empirically with a Zipfian(s=1) data stream, and report the
fraction of items whose point-query error exceeds T = eps * ||a||_1,
averaged over >=20 hash seeds.
"""

import time
import numpy as np

# ----------------------------- experiment setup ---------------------------- #
WIDTH = 1024
DS = [1, 2, 3, 4, 5, 8]
N_ITEMS = 100_000            # number of distinct items
N_UPDATES = 1_000_000        # total updates in the stream
ZIPF_S = 1.0                 # Zipf exponent
NUM_SEEDS = 25               # >= 20 seeds for stable tail estimate
STREAM_SEED = 2024           # seed for generating the data stream

# Largest prime > N_ITEMS, used as modulus for pairwise-independent hashing.
# Precomputed: next prime after 100_000 is 100_003.
P = 100_003

# ----------------------------- helpers ------------------------------------- #

def build_stream(rng, n_updates, n_items, s):
    """Sample n_updates item IDs from a Zipf(s) distribution over 1..n_items.

    Uses inverse-CDF sampling.  numpy.random.zipf only supports a > 1, but the
    task specifies s = 1.0 exactly, so we build the discrete CDF ourselves.
    """
    k = np.arange(1, n_items + 1, dtype=np.float64)
    pmf = 1.0 / np.power(k, s)
    pmf /= pmf.sum()
    cdf = np.cumsum(pmf)
    # Inverse CDF: searchsorted with uniform random variates.
    u = rng.random(n_updates)
    idx = np.searchsorted(cdf, u, side="right")
    # searchsorted can return n_items (if u == 1); clamp.
    idx = np.clip(idx, 0, n_items - 1)
    return (idx + 1).astype(np.int64)   # items numbered 1..n_items

def hash_coeffs(rng, d, p):
    """Sample d (a, b) pairs in [0, p) for pairwise-independent hashing."""
    a = rng.integers(1, p, size=d)   # avoid a == 0 to keep the function non-trivial
    b = rng.integers(0, p, size=d)
    return a, b

def hash_items(item_ids, a_coeffs, b_coeffs, p, w):
    """Compute h_j(i) = ((a_j * i + b_j) mod p) mod w for all i, j."""
    # item_ids has shape (N,); broadcasts against (d,)
    return ((item_ids[:, None] * a_coeffs[None, :] + b_coeffs[None, :]) % p) % w

def run_depth(a, item_ids, d, w, num_seeds, p, stream_seed_for_hashes):
    """For a given depth d, run `num_seeds` independent sketches and
    return the empirical tail-failure rate (mean over seeds) and its std."""
    n_items = len(a)
    eps = np.e / w
    T = eps * a.sum()

    # Use a separate Generator to draw hash seeds; the stream itself is fixed.
    hash_rng = np.random.default_rng(stream_seed_for_hashes + 1000 * d)

    rates = np.empty(num_seeds)
    for s in range(num_seeds):
        a_coef, b_coef = hash_coeffs(hash_rng, d, p)
        # h[i, j] = bucket index for item i in row j.
        h = hash_items(item_ids, a_coef, b_coef, p, w)   # (N, d)

        # Build the d x w counter matrix.  count[j, k] = sum_i a[i] * [h[i,j] == k]
        # We vectorise via np.add.at.  Time is O(N*d) which is fine for our sizes.
        counts = np.zeros((d, w), dtype=np.int64)
        # Flatten and use bincount-style accumulation.
        flat_idx = h.T.reshape(-1)               # (d*N,)
        flat_weights = np.tile(a, d)             # a repeated d times
        np.add.at(counts, (np.repeat(np.arange(d), n_items), flat_idx), flat_weights)

        # Point query: a_hat[i] = min_j counts[j, h[i, j]]
        rows = counts[np.arange(d)[None, :], h]   # (N, d)
        a_hat = rows.min(axis=1)

        # Tail failure: a_hat[i] > a[i] + T
        rates[s] = np.mean(a_hat > a + T)

    return float(rates.mean()), float(rates.std()), float(T)

# ----------------------------- main ----------------------------------------- #

def main():
    t0 = time.time()

    # 1) Build the Zipfian data stream once and use it for every (d, seed).
    stream_rng = np.random.default_rng(STREAM_SEED)
    item_ids = build_stream(stream_rng, N_UPDATES, N_ITEMS, ZIPF_S)
    item_ids = item_ids.astype(np.int64)
    assert item_ids.min() >= 1 and item_ids.max() <= N_ITEMS

    a = np.bincount(item_ids, minlength=N_ITEMS + 1)[1:].astype(np.int64)
    L1 = int(a.sum())
    eps = np.e / WIDTH
    T = eps * L1

    print(f"stream: N_ITEMS={N_ITEMS}, N_UPDATES={len(item_ids)}, "
          f"unique_seen={int((a > 0).sum())}, ||a||_1={L1}")
    print(f"width w = {WIDTH}, eps = e/w = {eps:.6f}, T = eps*||a||_1 = {T:.3f}")
    print(f"d grid = {DS}, num seeds = {NUM_SEEDS}")
    print()

    # 2) Run for each d.
    results = []
    for d in DS:
        td = time.time()
        mean_rate, std_rate, _ = run_depth(
            a=a,
            item_ids=np.arange(1, N_ITEMS + 1, dtype=np.int64),  # every item
            d=d, w=WIDTH, num_seeds=NUM_SEEDS, p=P,
            stream_seed_for_hashes=STREAM_SEED,
        )
        results.append((d, mean_rate, std_rate))
        print(f"d={d:>2d}  tail_failure_rate = {mean_rate:.4e}  "
              f"(+/- {std_rate:.2e})   [{time.time() - td:.1f}s]")

    print(f"\ntotal elapsed: {time.time() - t0:.1f}s")

    # 3) Save raw numbers so the summary can cite them.
    out = np.array(results, dtype=np.float64)
    header = "d,tail_failure_rate_mean,tail_failure_rate_std"
    np.savetxt("raw_rates.csv",
               out,
               delimiter=",",
               header=header,
               comments="")
    with open("experiment_meta.txt", "w") as f:
        f.write(f"WIDTH={WIDTH}\nEPS={eps:.8f}\nL1={L1}\nT={T:.6f}\n"
                f"N_ITEMS={N_ITEMS}\nN_UPDATES={N_UPDATES}\n"
                f"ZIPF_S={ZIPF_S}\nNUM_SEEDS={NUM_SEEDS}\n"
                f"STREAM_SEED={STREAM_SEED}\nP={P}\n")

if __name__ == "__main__":
    main()