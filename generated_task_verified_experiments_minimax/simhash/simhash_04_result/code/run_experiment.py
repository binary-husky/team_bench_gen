"""
Experiment: effect of vector dimension d on SimHash cosine-similarity estimation.

Algorithm: Charikar's random-hyperplane SimHash (Sec. 3 of the paper).
    For vector v in R^d and a random hyperplane r ~ N(0, I_d):
        h_r(v) = 1 if r . v >= 0 else 0
    For two vectors u, v with angle theta:
        Pr[h_r(u) = h_r(v)] = 1 - theta / pi

    From the b-bit hashes, the collision fraction estimates (1 - theta/pi),
    so theta_hat = pi * (hamming_distance / b),
    and the cosine is estimated as cos(theta_hat).

Fixed settings:
    b = 256 bits
    n_pairs = 1000 vector pairs
    random seed = 42
    G = standard Gaussian in R^d (per-hyperplane)
Variable:
    d in {10, 50, 100, 500}
"""

import numpy as np
from pathlib import Path

# ----------------------------- fixed settings -----------------------------
B_BITS        = 256          # number of hash bits per vector
N_PAIRS       = 1000         # number of (u, v) pairs to evaluate
SEED          = 42           # the *single* random seed for the experiment
DIMS          = [10, 50, 100, 500]
EPS           = 1e-12       # numerical guard for norms


# ----------------------------- simhash core -------------------------------
def make_simhash(d: int, b: int, rng: np.random.Generator) -> np.ndarray:
    """Draw b random hyperplanes as a (b, d) Gaussian matrix.

    Each row is a vector r ~ N(0, I_d).  For a query vector v, the i-th
    bit of its SimHash is 1 iff R[i] . v >= 0.
    """
    return rng.standard_normal(size=(b, d))


def simhash_bits(R: np.ndarray, V: np.ndarray) -> np.ndarray:
    """Return a (n_vecs, b) 0/1 matrix of SimHash bits for each row of V."""
    return (V @ R.T >= 0).astype(np.uint8)


def cosine_similarity(U: np.ndarray, V: np.ndarray) -> np.ndarray:
    """Row-wise cosine similarity, length n_pairs."""
    nu = np.linalg.norm(U, axis=1) + EPS
    nv = np.linalg.norm(V, axis=1) + EPS
    return np.einsum("ij,ij->i", U, V) / (nu * nv)


def hamming_distance(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Row-wise Hamming distance between two (n, b) 0/1 matrices."""
    return np.sum(A != B, axis=1).astype(np.float64)


def estimate_cosine_from_hamming(hd: np.ndarray, b: int) -> np.ndarray:
    """Inverse the Charikar collision probability to get cos(theta).

    collision fraction = 1 - hd/b   ~  1 - theta/pi
    => theta_hat       = pi * hd / b
    => cos_hat         = cos(theta_hat)
    """
    theta_hat = np.pi * hd / b
    return np.cos(theta_hat)


# ----------------------------- one experiment run --------------------------
def run_one(d: int, b: int, n_pairs: int, seed: int) -> dict:
    """Run the full experiment for a single dimension d.

    To keep the random seed the ONLY stochastic driver and to make the
    d-comparison apples-to-apples, we draw all (U, V) and the hash matrix
    from the same generator in a single sequence.
    """
    rng = np.random.default_rng(seed)

    # 2*n_pairs vectors in R^d (U and V concatenated)
    V_all = rng.standard_normal(size=(2 * n_pairs, d))
    U = V_all[:n_pairs]
    V = V_all[n_pairs:]

    # b random hyperplanes in R^d
    R = make_simhash(d, b, rng)

    # Compute true cosine similarity (the "known" value)
    cos_true = cosine_similarity(U, V)

    # Hash and compute hamming distance
    H_U = simhash_bits(R, U)
    H_V = simhash_bits(R, V)
    hd  = hamming_distance(H_U, H_V)

    # Estimate cosine similarity from hamming distance
    cos_est = estimate_cosine_from_hamming(hd, b)

    # Errors (signed error so we can also see bias)
    err = cos_est - cos_true
    mae  = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err * err)))
    bias = float(np.mean(err))

    # Diagnostics on hamming distance distribution
    collision_rate = 1.0 - hd / b      # empirical Pr[h(u)=h(v)]
    # theory:  Pr[h(u)=h(v)] = 1 - theta/pi ; theta = arccos(cos_true)
    theta_true = np.arccos(np.clip(cos_true, -1.0, 1.0))
    collision_theory = 1.0 - theta_true / np.pi

    return {
        "d": d,
        "cos_true_mean": float(np.mean(cos_true)),
        "cos_true_std":  float(np.std(cos_true)),
        "cos_true_min":  float(np.min(cos_true)),
        "cos_true_max":  float(np.max(cos_true)),
        "cos_est_mean":  float(np.mean(cos_est)),
        "cos_est_std":   float(np.std(cos_est)),
        "mae":  mae,
        "rmse": rmse,
        "bias": bias,
        "hd_mean":  float(np.mean(hd)),
        "hd_std":   float(np.std(hd)),
        "collision_emp_mean":  float(np.mean(collision_rate)),
        "collision_theory_mean": float(np.mean(collision_theory)),
        "rel_err_rmse": rmse / (float(np.std(cos_true)) + EPS),
    }


# --------------------------------- main -----------------------------------
def main() -> None:
    out_dir = Path("/data/workspace/admin/happy_lake/.verify_judge_minimax/simhash/simhash_04")
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    print(f"{'d':>6} | {'MAE':>10} | {'RMSE':>10} | {'bias':>10} | "
          f"{'mean_cos_true':>14} | {'std_cos_true':>14} | "
          f"{'mean_hd':>10} | {'mean_coll(emp)':>16} | {'mean_coll(th)':>15}")
    print("-" * 130)
    for d in DIMS:
        r = run_one(d=d, b=B_BITS, n_pairs=N_PAIRS, seed=SEED)
        rows.append(r)
        print(f"{r['d']:>6} | {r['mae']:>10.6f} | {r['rmse']:>10.6f} | "
              f"{r['bias']:>10.6f} | {r['cos_true_mean']:>14.6f} | "
              f"{r['cos_true_std']:>14.6f} | {r['hd_mean']:>10.4f} | "
              f"{r['collision_emp_mean']:>16.6f} | {r['collision_theory_mean']:>15.6f}")

    # Persist raw results so the summary can quote them.
    np.savez(out_dir / "results_raw.npz",
             d=np.array([r["d"] for r in rows]),
             mae=np.array([r["mae"] for r in rows]),
             rmse=np.array([r["rmse"] for r in rows]),
             bias=np.array([r["bias"] for r in rows]),
             cos_true_mean=np.array([r["cos_true_mean"] for r in rows]),
             cos_true_std=np.array([r["cos_true_std"] for r in rows]),
             hd_mean=np.array([r["hd_mean"] for r in rows]),
             hd_std=np.array([r["hd_std"] for r in rows]),
             collision_emp=np.array([r["collision_emp_mean"] for r in rows]),
             collision_th=np.array([r["collision_theory_mean"] for r in rows]),
             rel_err_rmse=np.array([r["rel_err_rmse"] for r in rows]))

    print("\nSaved raw results to results_raw.npz")


if __name__ == "__main__":
    main()
