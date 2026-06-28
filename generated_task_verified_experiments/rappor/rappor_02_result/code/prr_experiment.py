"""
Empirical verification of RAPPOR PRR per-bit privacy ratio upper bound.

PRR (Permanent Randomized Response) for a Bloom bit b:
  With probability f, replace b with a uniform random bit;
  otherwise keep b unchanged.

Equivalent marginal probabilities:
  Pr[PRR=1 | b=1] = 1 - f/2
  Pr[PRR=1 | b=0] = f/2

Local DP per-bit upper bound:
  ratio = (2 - f) / f = e^{eps_perm}   =>   eps_perm = ln((2 - f)/f)

We empirically estimate the ratio over >=1e5 samples per group, across a grid
of f values, repeated over >=5 random seeds, and compare to theory.
"""

import numpy as np

F_GRID = [0.1, 0.25, 0.5, 0.75, 0.9]
N_SAMPLES = 200_000          # >= 1e5 per group
SEEDS = [0, 1, 2, 3, 4, 5, 6]  # >= 5 seeds


def prr(bits: np.ndarray, f: float, rng: np.random.Generator) -> np.ndarray:
    """In-process PRR.

    With probability f, replace with uniform random bit; else keep original.
    Vectorized: draw a mask of "flip" decisions and a uniform random bit column.
    """
    mask = rng.random(bits.shape) < f              # True => replace
    rand_bits = (rng.random(bits.shape) < 0.5).astype(np.int8)
    out = np.where(mask, rand_bits, bits).astype(np.int8)
    return out


def run_one(f: float, seed: int):
    rng = np.random.default_rng(seed)
    b1 = np.ones(N_SAMPLES, dtype=np.int8)
    b0 = np.zeros(N_SAMPLES, dtype=np.int8)

    p1 = prr(b1, f, rng).mean()
    p0 = prr(b0, f, rng).mean()
    return p1, p0


def main():
    print(f"{'f':>6} | {'p1_hat':>10} {'p0_hat':>10} | {'r_hat':>10} {'r_theory':>10} "
          f"| {'eps_hat':>10} {'eps_theory':>10}")
    print("-" * 90)

    rows = []
    for f in F_GRID:
        r_theory = (2 - f) / f
        eps_theory = np.log(r_theory)

        p1s, p0s = [], []
        for s in SEEDS:
            p1, p0 = run_one(f, s)
            p1s.append(p1)
            p0s.append(p0)

        p1_mean = float(np.mean(p1s))
        p0_mean = float(np.mean(p0s))
        r_hat = p1_mean / p0_mean
        eps_hat = float(np.log(r_hat))

        rows.append({
            "f": f,
            "p1_mean": p1_mean,
            "p0_mean": p0_mean,
            "p1_std": float(np.std(p1s)),
            "p0_std": float(np.std(p0s)),
            "r_hat": r_hat,
            "r_theory": float(r_theory),
            "eps_hat": eps_hat,
            "eps_theory": float(eps_theory),
            "r_se": float(np.std([a / b for a, b in zip(p1s, p0s)])),
        })

        print(f"{f:>6.2f} | {p1_mean:>10.6f} {p0_mean:>10.6f} | "
              f"{r_hat:>10.4f} {r_theory:>10.4f} | {eps_hat:>10.4f} {eps_theory:>10.4f}")

    # Monte Carlo sanity: expected std of p_hat under binomial
    print("\nExpected binomial std of p1_hat (theory 1-f/2):")
    for r in rows:
        f = r["f"]
        p = 1 - f / 2
        se = np.sqrt(p * (1 - p) / N_SAMPLES)
        print(f"  f={f:.2f}: p1_hat observed std across seeds={r['p1_std']:.6f}  "
              f"binomial SE={se:.6f}")

    return rows


if __name__ == "__main__":
    rows = main()
    # stash for summary writer
    import json
    with open("results.json", "w") as fh:
        json.dump(rows, fh, indent=2)
    print("\nWrote results.json")
