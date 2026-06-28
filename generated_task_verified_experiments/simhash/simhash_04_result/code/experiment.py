"""
Study the effect of vector dimension d on SimHash cosine-similarity estimation error.

SimHash (Charikar 2002, sign random projections):
  bit_i(x) = 1[ G_i . x > 0 ],  G_i ~ N(0, I_d)
  For two vectors with angle theta,  Pr[ bit differs ] = theta / pi  (dimension-free).
  Estimator:  theta_hat = pi * (Hamming_dist / b);  cos_hat = cos(theta_hat).

Fixed settings: b=256, n_pairs=1000, random seed, G generation procedure.
Only independent variable: d in {10, 50, 100, 500}.
"""
import numpy as np

B = 256
N_PAIRS = 1000
SEED = 42
DS = [10, 50, 100, 500]


def make_pair(d, s, rng):
    """Return unit vectors u, v with exact cosine similarity s in R^d."""
    u = rng.standard_normal(d)
    u /= np.linalg.norm(u)
    w = rng.standard_normal(d)
    # orthogonalize w against u
    w = w - (w @ u) * u
    nw = np.linalg.norm(w)
    if nw < 1e-12:           # extremely unlikely; resample
        w = rng.standard_normal(d)
        w = w - (w @ u) * u
        nw = np.linalg.norm(w)
    w /= nw
    v = s * u + np.sqrt(max(0.0, 1.0 - s * s)) * w
    return u, v


def run(d, seed=SEED):
    rng = np.random.default_rng(seed)
    # Fixed G generation: same seed, shape (B, d)
    G = rng.standard_normal((B, d))

    # target cosine similarities sampled uniformly in [-1, 1]
    targets = rng.uniform(-1.0, 1.0, size=N_PAIRS)

    errs = np.empty(N_PAIRS)
    trues = np.empty(N_PAIRS)
    ests = np.empty(N_PAIRS)
    for i, s in enumerate(targets):
        u, v = make_pair(d, float(s), rng)
        hu = (G @ u) > 0
        hv = (G @ v) > 0
        H = int(np.count_nonzero(hu != hv))
        theta_hat = np.pi * H / B
        cos_hat = np.cos(theta_hat)
        trues[i] = s
        ests[i] = cos_hat
        errs[i] = cos_hat - s

    mae = float(np.mean(np.abs(errs)))
    rmse = float(np.sqrt(np.mean(errs ** 2)))
    bias = float(np.mean(errs))
    return dict(d=d, mae=mae, rmse=rmse, bias=bias,
                trues=trues, ests=ests, errs=errs)


if __name__ == "__main__":
    print(f"b={B}, n_pairs={N_PAIRS}, seed={SEED}")
    rows = []
    for d in DS:
        r = run(d)
        rows.append(r)
        print(f"d={d:4d}  MAE={r['mae']:.5f}  RMSE={r['rmse']:.5f}  bias={r['bias']:+.5f}")

    # multi-seed stability check (seed only varies here; reported as auxiliary)
    print("\n-- multi-seed stability (5 seeds) --")
    for d in DS:
        maes, rmses = [], []
        for sd in range(5):
            r = run(d, seed=sd)
            maes.append(r['mae']); rmses.append(r['rmse'])
        print(f"d={d:4d}  MAE={np.mean(maes):.5f}+-{np.std(maes):.5f}  "
              f"RMSE={np.mean(rmses):.5f}+-{np.std(rmses):.5f}")

    # save raw rows for the summary
    import json
    with open("results.json", "w") as f:
        json.dump([{k: v for k, v in r.items() if k not in ('trues', 'ests', 'errs')}
                   for r in rows], f, indent=2)
