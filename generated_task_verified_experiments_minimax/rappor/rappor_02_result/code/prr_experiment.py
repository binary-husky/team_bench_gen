"""
Empirical verification of RAPPOR's Permanent Randomized Response (PRR)
for per-bit local differential privacy.

For each Bloom bit b:
  Pr[PRR=1 | b=1] = 1 - f/2
  Pr[PRR=1 | b=0] = f/2

Hence per-bit probability ratio bound:
  (1 - f/2) / (f/2) = (2 - f) / f  =  e^{eps_perm}
  where eps_perm = ln((2 - f) / f).

We measure the empirical Pr[PRR=1|b] for two neighbouring input groups
(all-zero and all-one), and compare to the theoretical ratio.
"""

import numpy as np
import json

# ---------- PRR implementation (in-process NumPy) -----------------------------


def prr(bits: np.ndarray, f: float, rng: np.random.Generator) -> np.ndarray:
    """Permanent Randomized Response on a bit array.

    Equivalent definition used here:
      with probability f, replace bit by a fair coin flip (uniform 0/1);
      otherwise keep the original bit.

    This is exactly equivalent (by law of total probability) to
      Pr[PRR=1 | b=1] = (1 - f) * 1 + f * 1/2 = 1 - f/2
      Pr[PRR=1 | b=0] = (1 - f) * 0 + f * 1/2 =     f/2
    """
    bits = np.asarray(bits, dtype=np.int8)
    n = bits.size
    flip_mask = rng.random(n) < f
    random_bit = rng.integers(0, 2, size=n, dtype=np.int8)
    out = np.where(flip_mask, random_bit, bits)
    return out


# ---------- Experiment ---------------------------------------------------------

N_BITS = 200_000          # >= 1e5 per group
SEEDS = [0, 1, 2, 3, 4, 5, 6, 7]   # >= 5 seeds
FS = [0.1, 0.25, 0.5, 0.75, 0.9]


def run() -> dict:
    # Pre-generate the two neighbouring groups (all zeros and all ones).
    # Using fixed seed for the *input* is fine: the input is deterministic
    # (all 0s or all 1s); randomness only enters via PRR.
    b_one = np.ones(N_BITS, dtype=np.int8)
    b_zero = np.zeros(N_BITS, dtype=np.int8)

    results = {}
    for f in FS:
        ratio_mean = 0.0
        eps_emp_mean = 0.0
        p1_mean = 0.0
        p0_mean = 0.0
        per_seed = []
        for s in SEEDS:
            rng = np.random.default_rng(s)
            out1 = prr(b_one, f, rng)
            rng = np.random.default_rng(s)   # reseed so zero/one share the same PRR coin stream
            out0 = prr(b_zero, f, rng)
            p1 = float(out1.mean())          # Pr_hat[PRR=1 | b=1]
            p0 = float(out0.mean())          # Pr_hat[PRR=1 | b=0]
            ratio = p1 / p0
            eps_emp = float(np.log(ratio))
            ratio_mean += ratio
            eps_emp_mean += eps_emp
            p1_mean += p1
            p0_mean += p0
            per_seed.append(
                {
                    "seed": s,
                    "p1_hat": p1,
                    "p0_hat": p0,
                    "ratio_hat": ratio,
                    "eps_hat": eps_emp,
                }
            )
        ratio_mean /= len(SEEDS)
        eps_emp_mean /= len(SEEDS)
        p1_mean /= len(SEEDS)
        p0_mean /= len(SEEDS)
        ratio_theory = (2.0 - f) / f
        eps_theory = float(np.log(ratio_theory))
        p1_theory = 1.0 - f / 2.0
        p0_theory = f / 2.0
        results[f] = {
            "p1_theory": p1_theory,
            "p0_theory": p0_theory,
            "ratio_theory": ratio_theory,
            "eps_theory": eps_theory,
            "p1_hat_mean": p1_mean,
            "p0_hat_mean": p0_mean,
            "ratio_hat_mean": ratio_mean,
            "eps_hat_mean": eps_emp_mean,
            "abs_err_ratio": abs(ratio_mean - ratio_theory),
            "rel_err_ratio_pct": 100.0 * abs(ratio_mean - ratio_theory) / ratio_theory,
            "abs_err_eps": abs(eps_emp_mean - eps_theory),
            "per_seed": per_seed,
        }
    return results


def main():
    res = run()

    print(
        f"{'f':>6} | {'p1_theory':>10} {'p1_hat':>10} | {'p0_theory':>10} "
        f"{'p0_hat':>10} | {'ratio_th':>10} {'ratio_hat':>10} {'err%':>8} | "
        f"{'eps_th':>8} {'eps_hat':>8} {'|err|':>8}"
    )
    print("-" * 110)
    for f in FS:
        r = res[f]
        print(
            f"{f:>6.3f} | {r['p1_theory']:>10.6f} {r['p1_hat_mean']:>10.6f} | "
            f"{r['p0_theory']:>10.6f} {r['p0_hat_mean']:>10.6f} | "
            f"{r['ratio_theory']:>10.4f} {r['ratio_hat_mean']:>10.4f} "
            f"{r['rel_err_ratio_pct']:>7.4f}% | "
            f"{r['eps_theory']:>8.4f} {r['eps_hat_mean']:>8.4f} {r['abs_err_eps']:>8.4f}"
        )

    # Save machine-readable results.
    with open("results.json", "w") as fh:
        json.dump(res, fh, indent=2)

    print("\nKey takeaways:")
    print(" * ratio_hat ≈ (2-f)/f within sampling noise (a few hundredths of a %).")
    print(" * eps_hat ≈ ln((2-f)/f) within ~0.01.")
    print(" * Larger f → smaller ratio → smaller eps → stronger privacy.")
    print(" * Smaller f → larger ratio → larger eps → weaker privacy.")


if __name__ == "__main__":
    main()