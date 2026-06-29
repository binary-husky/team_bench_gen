"""
Experiment: Effect of n_estimators on OOB and held-out test error
for RandomForestClassifier on the load_digits dataset.

Per task.md:
  - Dataset: load_digits
  - Split: 70/30 with a fixed random seed
  - For n_estimators in {10, 50, 100, 200, 500, 1000}:
        RandomForestClassifier(oob_score=True, random_state=0)
  - Record OOB error and held-out test error
  - Only n_estimators varies.
"""
import numpy as np
from sklearn.datasets import load_digits
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# ---------- Fixed settings (only n_estimators varies) ----------
DATA_SEED = 0          # seed for the 70/30 train/test split
MODEL_SEED = 0         # random_state for the RandomForestClassifier
TEST_SIZE = 0.30       # 70/30 split -> 30% held out
N_TREES_LIST = [10, 50, 100, 200, 500, 1000]

# ---------- Data ----------
digits = load_digits()
X, y = digits.data, digits.target

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=TEST_SIZE, random_state=DATA_SEED, stratify=y
)

print(f"Dataset: load_digits")
print(f"  Total samples: {X.shape[0]}, features: {X.shape[1]}, classes: {len(np.unique(y))}")
print(f"  Train size: {X_train.shape[0]} ({1 - TEST_SIZE:.0%})")
print(f"  Test size : {X_test.shape[0]} ({TEST_SIZE:.0%})")
print(f"  Data split seed: {DATA_SEED}")
print()

# ---------- Sweep over n_estimators ----------
results = []
print(f"{'n_estimators':>12} | {'OOB score':>10} | {'OOB error':>10} | "
      f"{'Test score':>10} | {'Test error':>10} | {'Train score':>11}")
print("-" * 78)

for n_trees in N_TREES_LIST:
    rf = RandomForestClassifier(
        n_estimators=n_trees,
        oob_score=True,
        random_state=MODEL_SEED,
        n_jobs=-1,
    )
    rf.fit(X_train, y_train)

    oob_acc = rf.oob_score_
    oob_err = 1.0 - oob_acc

    test_acc = accuracy_score(y_test, rf.predict(X_test))
    test_err = 1.0 - test_acc

    train_acc = accuracy_score(y_train, rf.predict(X_train))

    results.append({
        "n_estimators": n_trees,
        "oob_score": oob_acc,
        "oob_error": oob_err,
        "test_score": test_acc,
        "test_error": test_err,
        "train_score": train_acc,
        "train_error": 1.0 - train_acc,
    })

    print(f"{n_trees:>12} | {oob_acc:>10.4f} | {oob_err:>10.4f} | "
          f"{test_acc:>10.4f} | {test_err:>10.4f} | {train_acc:>11.4f}")

# ---------- Convergence diagnostics ----------
oob_errs = np.array([r["oob_error"] for r in results])
test_errs = np.array([r["test_error"] for r in results])

print()
print("Convergence / stability diagnostics:")
print(f"  OOB error  : min={oob_errs.min():.4f}, max={oob_errs.max():.4f}, "
      f"max-min={oob_errs.max() - oob_errs.min():.4f}")
print(f"  Test error : min={test_errs.min():.4f}, max={test_errs.max():.4f}, "
      f"max-min={test_errs.max() - test_errs.min():.4f}")

# Pairwise consecutive changes
for i in range(1, len(N_TREES_LIST)):
    d_oob = oob_errs[i] - oob_errs[i - 1]
    d_test = test_errs[i] - test_errs[i - 1]
    print(f"  Delta {N_TREES_LIST[i - 1]:>4} -> {N_TREES_LIST[i]:>4}: "
          f"OOB {d_oob:+.4f}, Test {d_test:+.4f}")

# OOB vs Test gap
print()
print("OOB / Test gap (|OOB err - Test err|):")
for r in results:
    gap = r["oob_error"] - r["test_error"]
    print(f"  n={r['n_estimators']:>4}: OOB={r['oob_error']:.4f}, "
          f"Test={r['test_error']:.4f}, gap={gap:+.4f}")
