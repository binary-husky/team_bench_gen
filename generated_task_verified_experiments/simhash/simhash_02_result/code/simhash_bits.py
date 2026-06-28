"""SimHash: accuracy of estimating cosine similarity from Hamming distance, vs bit count b.

Spec fixed settings: d=100, ~1000 vector pairs, fixed seed; b in {16,64,256,1024};
sketch = sign(G @ v), G is b x d random gaussian. Estimate angle from hamming:
theta_hat = pi * (hamming_dist / b); cos_hat = cos(theta_hat). Compare to true cosine.
Metrics: MAE, RMSE, mean error (bias). Compare to O(1/sqrt(b)).
"""
import numpy as np

SEED = 12345
D = 100
N_PAIRS = 1000
BS = [16, 64, 256, 1024]
RNG = np.random.default_rng(SEED)

# Generate 2*N_PAIRS random vectors, form N_PAIRS pairs with known cosine sim.
V = RNG.standard_normal((2 * N_PAIRS, D))
V = V / np.linalg.norm(V, axis=1, keepdims=True)
A = V[:N_PAIRS]
B = V[N_PAIRS:]
true_cos = (A * B).sum(axis=1)               # in [-1,1]
true_ang = np.arccos(np.clip(true_cos, -1, 1))  # radians

results = {}
print(f"{'b':>5} {'MAE':>10} {'RMSE':>10} {'mean_err(bias)':>14} {'std_err':>10} {'RMSE*sqrt(b)':>14}")
for b in BS:
    G = RNG.standard_normal((b, D))           # b x d gaussian
    sa = np.sign(A @ G.T)                     # N x b in {-1,+1}
    sb = np.sign(B @ G.T)
    # hamming distance per pair
    ham = (sa != sb).sum(axis=1)              # count of differing bits
    ang_hat = np.pi * ham / b                 # theta_hat = pi * (hd/b)
    cos_hat = np.cos(ang_hat)
    err = cos_hat - true_cos                  # estimation error per pair
    mae = np.mean(np.abs(err))
    rmse = np.sqrt(np.mean(err ** 2))
    mean_err = np.mean(err)
    std_err = np.std(err)
    results[b] = dict(mae=float(mae), rmse=float(rmse), mean_err=float(mean_err),
                      std_err=float(std_err), rmse_sqrt_b=float(rmse * np.sqrt(b)))
    print(f"{b:>5} {mae:>10.5f} {rmse:>10.5f} {mean_err:>+14.5f} {std_err:>10.5f} {rmse*np.sqrt(b):>14.5f}")

# O(1/sqrt(b)) check: RMSE * sqrt(b) ~ const; halving error needs 4x bits
print("\n=== O(1/sqrt(b)) check ===")
base = results[BS[0]]['rmse']
for b in BS:
    pred = base * np.sqrt(BS[0]) / np.sqrt(b)   # predicted RMSE if O(1/sqrt(b))
    actual = results[b]['rmse']
    print(f"b={b:5d}: predicted RMSE={pred:.5f}  actual={actual:.5f}  ratio(actual/pred)={actual/pred:.3f}")

# halving check: from b to 4b, RMSE should ~halve
print("\n=== halving (b -> 4b) check ===")
for i in range(len(BS) - 1):
    b0, b1 = BS[i], BS[i + 1]
    if b1 == 4 * b0:
        r0, r1 = results[b0]['rmse'], results[b1]['rmse']
        print(f"b {b0}->{b1}: RMSE {r0:.5f}->{r1:.5f}  ratio={r1/r0:.3f} (expect ~0.5)")

# bias check
print("\n=== bias (mean error ~ 0) ===")
for b in BS:
    print(f"b={b:5d}: mean_err={results[b]['mean_err']:+.5f}")

import json, os
with open(os.path.join(os.path.dirname(__file__), "..", "results", "bits_accuracy.json"), "w") as f:
    json.dump({"seed": SEED, "d": D, "n_pairs": N_PAIRS, "bs": BS,
               "per_b": {str(k): v for k, v in results.items()},
               "true_cos_mean": float(true_cos.mean())}, f, indent=2)
print("\nwrote results/bits_accuracy.json")
