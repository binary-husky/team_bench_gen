"""OOB error vs held-out test error for RandomForest on digits.

Fixed settings (per spec): load_digits (1797x64, 10 classes), n_estimators=200,
oob_score=True, 70/30 train/test split per seed. Records OOB error (1-oob_score_)
and held-out test error (1 - test accuracy) across seeds.
"""
import numpy as np
from sklearn.datasets import load_digits
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

SEEDS = list(range(10))  # 10 seeds
X, y = load_digits(return_X_y=True)

rows = []
for s in SEEDS:
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.30, random_state=s, stratify=y)
    clf = RandomForestClassifier(n_estimators=200, oob_score=True, random_state=s, n_jobs=-1)
    clf.fit(Xtr, ytr)
    oob_err = 1.0 - clf.oob_score_
    test_acc = clf.score(Xte, yte)
    test_err = 1.0 - test_acc
    diff = oob_err - test_err
    rows.append((s, oob_err, test_err, diff))
    print(f"seed={s:2d}  OOB_err={oob_err:.4f}  test_err={test_err:.4f}  diff(OOB-test)={diff:+.4f}")

oob = np.array([r[1] for r in rows])
te = np.array([r[2] for r in rows])
diff = np.array([r[3] for r in rows])
print("\n=== summary over 10 seeds ===")
print(f"OOB err : mean={oob.mean():.4f} std={oob.std():.4f} min={oob.min():.4f} max={oob.max():.4f}")
print(f"test err: mean={te.mean():.4f} std={te.std():.4f} min={te.min():.4f} max={te.max():.4f}")
print(f"|diff|  : mean={np.abs(diff).mean():.4f} max={np.abs(diff).max():.4f}")
print(f"mean diff (OOB-test) = {diff.mean():+.4f}")
# OOB within sampling noise of test? compare std of diff vs typical error scale
print(f"corr(OOB,test) = {np.corrcoef(oob, te)[0,1]:.3f}")

import json, os
out = {
  "n_seeds": len(SEEDS),
  "n_estimators": 200,
  "dataset": "load_digits (1797x64, 10 classes)",
  "split": "70/30 stratified",
  "per_seed": [{"seed": r[0], "oob_err": r[1], "test_err": r[2], "diff_oob_minus_test": r[3]} for r in rows],
  "oob_err_mean": float(oob.mean()), "oob_err_std": float(oob.std()),
  "test_err_mean": float(te.mean()), "test_err_std": float(te.std()),
  "abs_diff_mean": float(np.abs(diff).mean()), "abs_diff_max": float(np.abs(diff).max()),
  "mean_diff": float(diff.mean()),
  "corr_oob_test": float(np.corrcoef(oob, te)[0,1]),
}
with open(os.path.join(os.path.dirname(__file__), "..", "results", "oob_vs_test.json"), "w") as f:
    json.dump(out, f, indent=2)
print("\nwrote results/oob_vs_test.json")
