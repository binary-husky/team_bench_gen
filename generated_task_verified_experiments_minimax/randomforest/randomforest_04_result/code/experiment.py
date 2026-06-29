"""
Experiment: Effect of max_features (mtry) on OOB error and test accuracy
of RandomForestClassifier on load_digits dataset.

Data: load_digits (p=64 features), 70/30 split (fixed seed).
For max_features ∈ {1, 'sqrt'(≈8), p/3(≈21), None(全部 p)}:
  - Train RandomForestClassifier(n_estimators=200, oob_score=True, random_state=0)
  - Record OOB error (1 - oob_score) and test accuracy.
"""

import numpy as np
from sklearn.datasets import load_digits
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# Fixed settings
RANDOM_STATE = 0
TEST_SIZE = 0.30
N_ESTIMATORS = 200

# Load data
digits = load_digits()
X, y = digits.data, digits.target
p = X.shape[1]
print(f"Dataset: load_digits, n_samples={X.shape[0]}, n_features={p}, classes={len(np.unique(y))}")

# 70/30 split, fixed seed
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
)
print(f"Train size: {X_train.shape[0]}, Test size: {X_test.shape[0]}")

# max_features values to test (exactly as specified by task)
settings = [
    ("1", 1),
    ("sqrt", "sqrt"),
    ("p/3", p // 3),
    ("None", None),
]

print("\n" + "=" * 72)
print(f"{'max_features':<14}{'#features':<12}{'OOB error':<14}{'OOB acc':<12}{'Test acc':<12}")
print("=" * 72)

results = []
for label, mf in settings:
    clf = RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        max_features=mf,
        oob_score=True,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)
    test_acc = accuracy_score(y_test, y_pred)
    oob_acc = clf.oob_score_
    oob_err = 1.0 - oob_acc

    # Effective number of features sampled per split
    if mf is None:
        n_eff = p
    elif mf == "sqrt":
        n_eff = int(np.sqrt(p))
    else:
        n_eff = int(mf)

    results.append({
        "label": label,
        "max_features": mf,
        "n_eff": n_eff,
        "oob_error": float(oob_err),
        "oob_accuracy": float(oob_acc),
        "test_accuracy": float(test_acc),
    })
    print(f"{label:<14}{n_eff:<12}{oob_err:<14.4f}{oob_acc:<12.4f}{test_acc:<12.4f}")

# Save raw results
import json
out_json = "/data/workspace/admin/happy_lake/.verify_judge_minimax/randomforest/randomforest_04/results_max_features.json"
with open(out_json, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved raw results to {out_json}")