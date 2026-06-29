"""
SimHash accuracy vs bits experiment (Charikar 2002, random hyperplane).

Setup (all fixed across runs):
  - d = 100 (vector dimensionality)
  - n_pairs = 1000 (number of random vector pairs)
  - seed = 42
  - G: a 1024 x d Gaussian random matrix, kept fixed; for each b we use
       the first b rows. This makes G literally the same matrix across b
       and "the only independent variable is b".

For each b in {16, 64, 256, 1024}:
  - sketch(v) = sign(G[:b] @ v) ∈ {0, 1}^b
  - angle_est = pi * (hamming / b)
  - cos_est   = cos(angle_est)
  - Compare angle_est / cos_est with true values, compute MAE / RMSE.
"""

import json
import numpy as np

# ---------------- fixed settings ----------------
D = 100
N_PAIRS = 1000
SEED = 42
B_VALUES = [16, 64, 256, 1024]
B_MAX = max(B_VALUES)

# ---------------- random generation ----------------
rng = np.random.default_rng(SEED)

# 2 * N_PAIRS random d-dimensional vectors, drawn as iid standard normal.
V = rng.standard_normal((2 * N_PAIRS, D))         # (2000, 100)

# Fixed G: a 1024 x d Gaussian matrix.
G_MAX = rng.standard_normal((B_MAX, D))           # (1024, 100)

# ---------------- ground truth cosine / angle ----------------
# Normalize vectors to unit length
V_n = V / np.linalg.norm(V, axis=1, keepdims=True)

# Pair (i):  u = V[2i], v = V[2i+1]
u = V_n[0::2]   # (1000, 100)
v = V_n[1::2]   # (1000, 100)

cos_true = np.sum(u * v, axis=1)                  # in [-1, 1]
cos_true_clipped = np.clip(cos_true, -1.0, 1.0)
angle_true = np.arccos(cos_true_clipped)          # in [0, pi]

print(f"cos_true  : mean={cos_true.mean():.4f}  std={cos_true.std():.4f}  "
      f"min={cos_true.min():.4f}  max={cos_true.max():.4f}")
print(f"angle_true: mean={angle_true.mean():.4f}  std={angle_true.std():.4f}  "
      f"min={angle_true.min():.4f}  max={angle_true.max():.4f}  "
      f"(pi/2 = {np.pi/2:.4f})")
print()

# ---------------- main loop over b ----------------
results = []
sketches_full = None
for b in B_VALUES:
    G = G_MAX[:b, :]                              # (b, 100)

    # Project and binarize. sign(0) on floats has measure zero for continuous
    # Gaussian projections, so we can use (raw >= 0) safely.
    raw = G @ V.T                                 # (b, 2000)
    sketches = (raw >= 0).astype(np.int8)         # (b, 2000) in {0, 1}
    if b == B_MAX:
        sketches_full = sketches

    # Hamming distance per pair
    hamming = np.sum(sketches[:, 0::2] != sketches[:, 1::2], axis=0)  # (1000,)

    # Estimates
    hamming_ratio = hamming / b
    angle_est = np.pi * hamming_ratio
    cos_est   = np.cos(angle_est)

    # Errors
    err_cos   = cos_est   - cos_true
    err_angle = angle_est - angle_true

    mae_cos   = float(np.mean(np.abs(err_cos)))
    rmse_cos  = float(np.sqrt(np.mean(err_cos ** 2)))
    mae_angle = float(np.mean(np.abs(err_angle)))
    rmse_angle= float(np.sqrt(np.mean(err_angle ** 2)))

    # Std of estimates (sanity check vs theoretical)
    std_hr   = float(hamming_ratio.std())
    std_ang  = float(angle_est.std())
    std_cos  = float(cos_est.std())

    r = {
        "b": b,
        "mae_cos":  mae_cos,
        "rmse_cos": rmse_cos,
        "mae_angle":  mae_angle,
        "rmse_angle": rmse_angle,
        "rmse_cos_x_sqrt_b":   rmse_cos  * (b ** 0.5),
        "rmse_angle_x_sqrt_b": rmse_angle * (b ** 0.5),
        "mae_cos_x_sqrt_b":    mae_cos   * (b ** 0.5),
        "mae_angle_x_sqrt_b":  mae_angle * (b ** 0.5),
        "std_hamming_ratio":   std_hr,
        "std_angle_est":       std_ang,
        "std_cos_est":         std_cos,
    }
    results.append(r)
    print(f"b={b:>4}  MAE_cos={mae_cos:.5f}  RMSE_cos={rmse_cos:.5f}  "
          f"MAE_ang={mae_angle:.5f}  RMSE_ang={rmse_angle:.5f}  "
          f"std(cos_est)={std_cos:.5f}")

print()

# ---------------- ratio test (slope) ----------------
# Fit log(err) vs log(b) to estimate the empirical scaling exponent.
log_b = np.log(np.array(B_VALUES, dtype=float))
log_rmse_cos   = np.log(np.array([r["rmse_cos"]   for r in results]))
log_rmse_angle = np.log(np.array([r["rmse_angle"] for r in results]))
log_mae_cos    = np.log(np.array([r["mae_cos"]    for r in results]))
log_mae_angle  = np.log(np.array([r["mae_angle"]  for r in results]))

slope_rmse_cos,   c_rmse_cos   = np.polyfit(log_b, log_rmse_cos,   1)
slope_rmse_angle, c_rmse_angle = np.polyfit(log_b, log_rmse_angle, 1)
slope_mae_cos,    c_mae_cos    = np.polyfit(log_b, log_mae_cos,    1)
slope_mae_angle,  c_mae_angle  = np.polyfit(log_b, log_mae_angle,  1)

print("Fitted log-log slope  err ~ b^slope")
print(f"  RMSE(cos)   : slope = {slope_rmse_cos:+.4f}  (expected -0.5)")
print(f"  RMSE(angle) : slope = {slope_rmse_angle:+.4f}  (expected -0.5)")
print(f"  MAE(cos)    : slope = {slope_mae_cos:+.4f}  (expected -0.5)")
print(f"  MAE(angle)  : slope = {slope_mae_angle:+.4f}  (expected -0.5)")
print()

# ---------------- constant-of-proportionality test ----------------
# If err ≈ c / sqrt(b), then err * sqrt(b) should be approximately constant.
print("err * sqrt(b) (should be roughly constant if err ~ 1/sqrt(b)):")
print(f"{'b':>6} {'RMSE_cos*sqrt(b)':>18} {'RMSE_ang*sqrt(b)':>18} {'MAE_cos*sqrt(b)':>17} {'MAE_ang*sqrt(b)':>17}")
for r in results:
    print(f"{r['b']:>6} {r['rmse_cos_x_sqrt_b']:>18.5f} {r['rmse_angle_x_sqrt_b']:>18.5f} "
          f"{r['mae_cos_x_sqrt_b']:>17.5f} {r['mae_angle_x_sqrt_b']:>17.5f}")
print()

# Save artifacts
with open("results.json", "w") as f:
    json.dump({
        "config": {"d": D, "n_pairs": N_PAIRS, "seed": SEED,
                   "b_values": B_VALUES, "G_rows": B_MAX},
        "ground_truth": {
            "cos_mean":   float(cos_true.mean()),
            "cos_std":    float(cos_true.std()),
            "cos_min":    float(cos_true.min()),
            "cos_max":    float(cos_true.max()),
            "angle_mean": float(angle_true.mean()),
            "angle_std":  float(angle_true.std()),
            "angle_min":  float(angle_true.min()),
            "angle_max":  float(angle_true.max()),
        },
        "results": results,
        "loglog_slopes": {
            "rmse_cos":   float(slope_rmse_cos),
            "rmse_angle": float(slope_rmse_angle),
            "mae_cos":    float(slope_mae_cos),
            "mae_angle":  float(slope_mae_angle),
        },
    }, f, indent=2)

# Also save the first 64 sketches of the b=1024 case for the record
np.save("sketches_b1020.npy", sketches_full[:64, :20])  # tiny sanity sample

print("Saved results.json")
