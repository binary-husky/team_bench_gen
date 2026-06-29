"""Deeper per-bucket analysis: per-pair errors and how they distribute
across the true-cosine range for each dimension d."""

import numpy as np
from pathlib import Path

B_BITS  = 256
N_PAIRS = 1000
SEED    = 42
DIMS    = [10, 50, 100, 500]
EPS     = 1e-12

OUT = Path("/data/workspace/admin/happy_lake/.verify_judge_minimax/simhash/simhash_04")


# --- helpers (duplicated so this file is self-contained) -------------------
def make_simhash(d, b, rng):
    return rng.standard_normal(size=(b, d))


def simhash_bits(R, V):
    return (V @ R.T >= 0).astype(np.uint8)


def cosine_sim(U, V):
    nu = np.linalg.norm(U, axis=1) + EPS
    nv = np.linalg.norm(V, axis=1) + EPS
    return np.einsum("ij,ij->i", U, V) / (nu * nv)


def hamming(A, B):
    return np.sum(A != B, axis=1).astype(np.float64)


def estimate_cos(hd, b):
    return np.cos(np.pi * hd / b)


def run(d, b, n_pairs, seed):
    rng = np.random.default_rng(seed)
    V_all = rng.standard_normal(size=(2 * n_pairs, d))
    U, V = V_all[:n_pairs], V_all[n_pairs:]
    R = make_simhash(d, b, rng)
    c_true = cosine_sim(U, V)
    hU = simhash_bits(R, U)
    hV = simhash_bits(R, V)
    hd = hamming(hU, hV)
    c_est = estimate_cos(hd, b)
    return c_true, c_est, hd


def main():
    print(f"{'d':>6} | {'MAE':>9} | {'RMSE':>9} | {'std(true)':>10} | "
          f"{'RMSE/std':>9} | {'sign-match':>11}")
    print("-" * 80)
    bucket_edges = np.array([-1.0, -0.5, 0.0, 0.5, 1.0])
    per_d_buckets = {}
    for d in DIMS:
        c_true, c_est, hd = run(d, B_BITS, N_PAIRS, SEED)
        err = c_est - c_true
        mae  = float(np.mean(np.abs(err)))
        rmse = float(np.sqrt(np.mean(err * err)))
        std_t = float(np.std(c_true))
        sign_match = float(np.mean(np.sign(c_true * c_est) > 0))
        print(f"{d:>6} | {mae:>9.5f} | {rmse:>9.5f} | {std_t:>10.5f} | "
              f"{rmse/(std_t+EPS):>9.4f} | {sign_match:>11.4f}")

        # bucket the true similarities
        bucket_idx = np.digitize(c_true, bucket_edges) - 1
        bucket_idx = np.clip(bucket_idx, 0, len(bucket_edges) - 2)
        bk = {}
        for k in range(len(bucket_edges) - 1):
            mask = bucket_idx == k
            if mask.sum() == 0:
                continue
            ce = c_est[mask]
            ct = c_true[mask]
            e  = ce - ct
            bk[f"[{bucket_edges[k]:+.1f},{bucket_edges[k+1]:+.1f}]"] = {
                "count": int(mask.sum()),
                "mae": float(np.mean(np.abs(e))),
                "rmse": float(np.sqrt(np.mean(e * e))),
                "cos_true_mean": float(np.mean(ct)),
            }
        per_d_buckets[d] = bk

    print("\nPer-bucket breakdown:")
    for d in DIMS:
        print(f"\n  d = {d}:")
        bk = per_d_buckets[d]
        print(f"    {'bucket':>16} | {'n':>5} | {'mean(true)':>11} | "
              f"{'MAE':>9} | {'RMSE':>9}")
        for name, stats in bk.items():
            print(f"    {name:>16} | {stats['count']:>5} | "
                  f"{stats['cos_true_mean']:>11.5f} | {stats['mae']:>9.5f} | "
                  f"{stats['rmse']:>9.5f}")


if __name__ == "__main__":
    main()
