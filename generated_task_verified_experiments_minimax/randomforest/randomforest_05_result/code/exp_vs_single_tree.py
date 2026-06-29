"""Experiment: Compare RandomForest (n_estimators=200) vs single DecisionTree
on load_digits with multiple random seeds; report training & test error
(mean +/- std across seeds).
"""
import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier

# ----- Fixed settings -----
DATASET = load_digits
N_ESTIMATORS = 200
TEST_SIZE = 0.30
RANDOM_STATE_SPLITS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]  # 10 random seeds for splits
MODEL_SEED = 42  # fixed model-internal seed for reproducibility

# ----- Data -----
X, y = DATASET(return_X_y=True)
print(f"Dataset: load_digits, n_samples={X.shape[0]}, n_features={X.shape[1]}, classes={len(np.unique(y))}")

rf_train_err, rf_test_err = [], []
dt_train_err, dt_test_err = [], []

for seed in RANDOM_STATE_SPLITS:
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=TEST_SIZE, random_state=seed, stratify=y)

    rf = RandomForestClassifier(n_estimators=N_ESTIMATORS, random_state=MODEL_SEED, n_jobs=-1)
    rf.fit(Xtr, ytr)
    rf_tr = 1.0 - rf.score(Xtr, ytr)
    rf_te = 1.0 - rf.score(Xte, yte)

    dt = DecisionTreeClassifier(random_state=MODEL_SEED)
    dt.fit(Xtr, ytr)
    dt_tr = 1.0 - dt.score(Xtr, ytr)
    dt_te = 1.0 - dt.score(Xte, yte)

    rf_train_err.append(rf_tr); rf_test_err.append(rf_te)
    dt_train_err.append(dt_tr); dt_test_err.append(dt_te)
    print(f"seed={seed}: RF train_err={rf_tr:.4f} test_err={rf_te:.4f} | "
          f"DT train_err={dt_tr:.4f} test_err={dt_te:.4f}")

def stats(arr):
    a = np.asarray(arr)
    return a.mean(), a.std(ddof=1), a  # sample std

rf_tr_mean, rf_tr_std, _ = stats(rf_train_err)
rf_te_mean, rf_te_std, _ = stats(rf_test_err)
dt_tr_mean, dt_tr_std, _ = stats(dt_train_err)
dt_te_mean, dt_te_std, _ = stats(dt_test_err)

print("\n=== Summary across seeds ===")
print(f"RandomForest (n_estimators={N_ESTIMATORS}):")
print(f"  train_err: mean={rf_tr_mean:.4f}  std={rf_tr_std:.4f}")
print(f"  test_err : mean={rf_te_mean:.4f}  std={rf_te_std:.4f}")
print(f"DecisionTree (single):")
print(f"  train_err: mean={dt_tr_mean:.4f}  std={dt_tr_std:.4f}")
print(f"  test_err : mean={dt_te_mean:.4f}  std={dt_te_std:.4f}")

# Save raw per-seed values for the report
np.savez(
    "/data/workspace/admin/happy_lake/.verify_judge_minimax/randomforest/randomforest_05/results.npz",
    seeds=np.array(RANDOM_STATE_SPLITS),
    rf_train=np.array(rf_train_err),
    rf_test=np.array(rf_test_err),
    dt_train=np.array(dt_train_err),
    dt_test=np.array(dt_test_err),
)
print("\nSaved results.npz")