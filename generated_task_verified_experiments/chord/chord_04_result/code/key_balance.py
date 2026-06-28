#!/usr/bin/env python3
"""
Key-distribution balance of consistent hashing on an in-process virtual Chord ring.

Setup (per task.md):
  - N = 200 physical nodes (fixed)
  - K = 1e5 random keys (fixed)
  - independent variable: v in {1,2,5,10,20} virtual nodes per physical node
  - fixed hash function (SHA-1, masked to 64-bit ring position)
  - fixed random seed -> fully reproducible

Each virtual node gets its own SHA-1 ring ID. A key is hashed to a ring position
and assigned to the successor virtual node (next ID clockwise, wrapping). Keys are
then aggregated to the owning physical node.

We measure load imbalance across the N physical nodes:
  - max/mean  = max load / mean load   (worst-case skew)
  - CV        = std(load) / mean(load)  (coefficient of variation)

max/mean is an extreme statistic, so to report a stable trend (rather than one
lucky seed) we run R independent trials -- each a fresh, deterministically-seeded
ring + key set -- and average the metrics, reporting their spread across trials.
"""

import hashlib
import numpy as np

# ---------------------------------------------------------------------------
# Fixed settings
# ---------------------------------------------------------------------------
N          = 200          # physical nodes
K          = 100_000      # keys
V_LIST     = [1, 2, 5, 10, 20]
R          = 30           # independent trials per v (master seed makes it reproducible)
MASTER_SEED = 20260626    # fixed -> whole experiment reproducible
MASK        = (1 << 64) - 1  # 64-bit ring space (collisions among ~4000 pts negligible)


def sha1_pos(label: str) -> int:
    """Map a label to a 64-bit ring position via SHA-1 (Chord's base hash)."""
    return int.from_bytes(hashlib.sha1(label.encode()).digest()[:8], "big")


# ---------------------------------------------------------------------------
# Per-trial key generation (deterministic given the seed)
# ---------------------------------------------------------------------------
def make_key_positions(trial: int) -> np.ndarray:
    """K random keys, each hashed to a 64-bit ring position.

    'random keys' = random 64-bit key labels, seeded by the trial so the key set
    is fixed/reproducible and IDENTICAL across all v (only v varies).
    """
    rng = np.random.default_rng(MASTER_SEED + 1000 * trial)
    labels = rng.integers(0, 1 << 60, size=K, dtype=np.int64)
    out = np.empty(K, dtype=np.uint64)
    buf = np.ascontiguousarray(labels).tobytes()        # 8 bytes per label
    for i in range(K):
        out[i] = int.from_bytes(hashlib.sha1(buf[8 * i:8 * i + 8]).digest()[:8], "big")
    return out


# Precompute the (identical-across-v) key positions once per trial.
KEY_POS = {t: make_key_positions(t) for t in range(R)}


# ---------------------------------------------------------------------------
# Core: assign keys to physical nodes for a given (trial, v)
# ---------------------------------------------------------------------------
def trial_loads(v: int, trial: int) -> np.ndarray:
    """Return per-physical-node key counts for one (trial, v)."""
    # ring positions of every virtual node, plus which physical node owns it
    positions = np.empty(N * v, dtype=np.uint64)
    owner     = np.empty(N * v, dtype=np.int64)
    for i in range(N):
        for j in range(v):
            positions[i * v + j] = sha1_pos(f"trial{trial}|node{i}|vnode{j}")
            owner[i * v + j] = i

    order = np.argsort(positions, kind="stable")
    sorted_pos = positions[order]
    sorted_own = owner[order]

    kp = KEY_POS[trial]

    # successor vnode = first position >= key (wrap around 0)
    idx = np.searchsorted(sorted_pos, kp, side="left")
    idx = np.where(idx == len(sorted_pos), 0, idx)
    phys = sorted_own[idx]

    counts = np.bincount(phys, minlength=N)
    return counts


# ---------------------------------------------------------------------------
# Run the sweep
# ---------------------------------------------------------------------------
def main():
    print(f"N={N}  K={K}  mean_load={K/N:.1f}  trials={R}\n")
    print(f"{'v':>3} | {'vnodes':>6} | "
          f"{'max/mean':>10} ± {'(sd)':>6} | {'CV':>8} ± {'(sd)':>6} | "
          f"{'min/mean':>9} | {'p99/mean':>9}")
    print("-" * 92)

    rows = []
    for v in V_LIST:
        max_mean = np.empty(R)
        cv       = np.empty(R)
        min_mean = np.empty(R)
        p99_mean = np.empty(R)
        for t in range(R):
            load = trial_loads(v, t)
            mean = load.mean()
            max_mean[t] = load.max() / mean
            cv[t]       = load.std() / mean          # population std / mean
            min_mean[t] = load.min() / mean
            p99_mean[t] = np.percentile(load, 99) / mean
        rows.append(dict(
            v=v,
            max_mean_mean=max_mean.mean(), max_mean_sd=max_mean.std(),
            cv_mean=cv.mean(), cv_sd=cv.std(),
            min_mean_mean=min_mean.mean(),
            p99_mean_mean=p99_mean.mean(),
        ))
        print(f"{v:>3} | {N*v:>6} | "
              f"{max_mean.mean():>10.3f} ± {max_mean.std():>6.3f} | "
              f"{cv.mean():>8.3f} ± {cv.std():>6.3f} | "
              f"{min_mean.mean():>9.3f} | {p99_mean.mean():>9.3f}")

    # save raw numbers for the plot / summary
    np.save("results.npy", rows, allow_pickle=True)

    # ---- plot ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    vs     = [r["v"] for r in rows]
    mm     = [r["max_mean_mean"] for r in rows]
    mm_sd  = [r["max_mean_sd"] for r in rows]
    cvv    = [r["cv_mean"] for r in rows]
    cv_sd  = [r["cv_sd"] for r in rows]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))

    ax1.errorbar(vs, mm, yerr=mm_sd, marker="o", capsize=4, color="C0")
    ax1.axhline(1.0, color="gray", ls="--", lw=1)
    ax1.set_xlabel("virtual nodes per physical node  v")
    ax1.set_ylabel("max / mean load")
    ax1.set_title("Worst-case skew  (max/mean)")
    ax1.set_xticks(vs)
    ax1.grid(alpha=0.3)

    ax2.errorbar(vs, cvv, yerr=cv_sd, marker="s", capsize=4, color="C1")
    ax2.axhline(0.0, color="gray", ls="--", lw=1)
    ax2.set_xlabel("virtual nodes per physical node  v")
    ax2.set_ylabel("coefficient of variation  std/mean")
    ax2.set_title("Dispersion  (CV = std/mean)")
    ax2.set_xticks(vs)
    ax2.grid(alpha=0.3)

    fig.suptitle(f"Consistent-hashing key balance on a virtual Chord ring "
                 f"(N={N} physical nodes, K={K:,} keys, {R} trials)", y=1.02)
    fig.tight_layout()
    fig.savefig("key_balance.png", dpi=130, bbox_inches="tight")
    print("\nsaved: key_balance.png, results.npy")


if __name__ == "__main__":
    main()
