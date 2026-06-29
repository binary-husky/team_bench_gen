"""
Count-Min Sketch: width w vs point-query overestimation error.

Fixed depth d=5. Widths w in {128,256,512,1024,2048,4096}.
Stream length N=1e6, item universe size n=1e5.
Two frequency distributions: Uniform and Zipfian(s=1.0).
Repeat each (w, distribution) with >=3 hash seeds and average.
"""
import time
import struct
import numpy as np
import mmh3

rng = np.random.default_rng(20260528)

# ---------- Stream generation ----------
N = 1_000_000
N_ITEMS = 100_000


def gen_uniform_stream(rng):
    """Each of 1e5 items equally likely. Return (stream, true_counts)."""
    stream = rng.integers(0, N_ITEMS, size=N, dtype=np.int64)
    counts = np.bincount(stream, minlength=N_ITEMS).astype(np.float64)
    return stream, counts


def gen_zipfian_stream(rng, s=1.0):
    """Zipfian(s) over items 0..N_ITEMS-1 (probability ~ 1/i^s)."""
    ranks = np.arange(1, N_ITEMS + 1, dtype=np.float64)
    p = 1.0 / (ranks ** s)
    p /= p.sum()
    stream = rng.choice(N_ITEMS, size=N, replace=True, p=p).astype(np.int64)
    counts = np.bincount(stream, minlength=N_ITEMS).astype(np.float64)
    return stream, counts


# ---------- Hash family (pairwise-independent-ish via mmh3) ----------
def build_buckets(w, d, seed):
    """
    Precompute bucket[j][i] = h_{seed,j}(i) for every item id i in [0, N_ITEMS).
    Each (seed, j) uses a distinct hash salt so different rows are independent
    across items, and different seeds are fully independent.
    Returns: array of shape (d, N_ITEMS), dtype int64, values in [0, w).
    """
    items = np.arange(N_ITEMS, dtype=np.int64)
    bucket = np.empty((d, N_ITEMS), dtype=np.int64)
    for j in range(d):
        col = np.empty(N_ITEMS, dtype=np.int64)
        salt = (seed * 131 + j) & 0xFFFFFFFF
        for i in range(N_ITEMS):
            col[i] = mmh3.hash128(struct.pack("<q", int(items[i])), seed=salt, signed=False) % w
        bucket[j] = col
    return bucket


def run_one(stream, true_counts, w, d, seed):
    """
    Build CM sketch with width w, depth d, hash seed; feed stream; return per-item estimates.
    Uses np.bincount per row for fast vectorized counting.
    """
    bucket = build_buckets(w, d, seed)  # (d, N_ITEMS)

    counts = np.zeros((d, w), dtype=np.int64)
    for j in range(d):
        counts[j] = np.bincount(bucket[j, stream], minlength=w)

    # Per-item estimate = min across rows
    per_row = np.take_along_axis(counts, bucket, axis=1)  # (d, N_ITEMS)
    estimates = per_row.min(axis=0).astype(np.float64)
    return estimates


def summarize_overestimates(estimates, true_counts):
    over = estimates - true_counts
    over = np.maximum(over, 0.0)
    mean = float(over.mean())
    p99 = float(np.percentile(over, 99))
    return mean, p99


# ---------- Driver ----------
def run():
    d = 5
    widths = [128, 256, 512, 1024, 2048, 4096]
    n_seeds = 3
    seeds = [11, 22, 33]

    # Pre-generate streams once (so Zipfian/uniform are identical across seeds/w)
    t0 = time.time()
    stream_uni, counts_uni = gen_uniform_stream(rng)
    stream_zip, counts_zip = gen_zipfian_stream(rng, s=1.0)
    print(f"Stream generation: {time.time()-t0:.2f}s")
    print(f"Uniform: total={counts_uni.sum():.0f}, max={counts_uni.max()}, "
          f"min={counts_uni.min()}, ||a||_1={counts_uni.sum():.0f}")
    print(f"Zipfian: total={counts_zip.sum():.0f}, max={counts_zip.max()}, "
          f"min={counts_zip.min()}, ||a||_1={counts_zip.sum():.0f}")
    print()

    results = {"uniform": {"w": [], "mean": [], "p99": []},
               "zipfian": {"w": [], "mean": [], "p99": []}}

    for label, stream, true_counts in [
        ("uniform", stream_uni, counts_uni),
        ("zipfian", stream_zip, counts_zip),
    ]:
        print(f"=== Distribution: {label} ===")
        for w in widths:
            t0 = time.time()
            means, p99s = [], []
            for seed in seeds[:n_seeds]:
                est = run_one(stream, true_counts, w, d, seed)
                m, p = summarize_overestimates(est, true_counts)
                means.append(m)
                p99s.append(p)
            mean_m = float(np.mean(means))
            mean_p = float(np.mean(p99s))
            results[label]["w"].append(w)
            results[label]["mean"].append(mean_m)
            results[label]["p99"].append(mean_p)
            dt = time.time() - t0
            print(f"  w={w:5d}  mean_err={mean_m:.4f}  p99_err={mean_p:.2f}  ({dt:.2f}s)")
        print()

    import json
    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)
    return results


if __name__ == "__main__":
    res = run()
    print("DONE")