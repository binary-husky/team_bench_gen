"""
Full experiment: Effect of max_features (mtry) on OOB error, test accuracy,
and between-tree correlation.

Between-tree correlation is measured as the mean off-diagonal Pearson
correlation of the per-tree indicator vectors (1 if the tree predicts the
correct label, 0 otherwise) on the held-out test set. This is the natural
empirical proxy for Breiman's correlation ρ̄.
"""

import json
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

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
)
print(f"Train size: {X_train.shape[0]}, Test size: {X_test.shape[0]}")

settings = [
    ("1", 1),
    ("sqrt", "sqrt"),
    ("p/3", p // 3),
    ("None", None),
]

print("\n" + "=" * 84)
print(
    f"{'max_features':<14}{'#feat':<8}{'OOB err':<11}{'OOB acc':<11}"
    f"{'Test acc':<11}{'avg tree acc':<14}{'mean corr ρ̄':<13}{'corr/s^2':<11}"
)
print("=" * 84)

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

    # Ensemble metrics
    y_pred = clf.predict(X_test)
    test_acc = accuracy_score(y_test, y_pred)
    oob_acc = clf.oob_score_
    oob_err = 1.0 - oob_acc

    # Per-tree indicator vector on the test set (1 if correct, 0 if wrong)
    # estimators_ predictions: shape (n_estimators, n_test_samples)
    tree_pred = np.array([t.predict(X_test) for t in clf.estimators_])
    correct = (tree_pred == y_test[None, :]).astype(np.float64)  # (T, N)

    # Average per-tree accuracy (proxy for individual strength)
    avg_tree_acc = float(correct.mean())

    # Mean pairwise Pearson correlation between per-tree indicator vectors
    # (off-diagonal average)
    # Row-center then correlation
    centered = correct - correct.mean(axis=1, keepdims=True)
    # std per tree
    std = correct.std(axis=1, ddof=0)
    std[std == 0] = 1.0  # avoid division by zero for degenerate trees
    normed = centered / std[:, None]
    # Covariance matrix
    cov = (normed @ normed.T) / correct.shape[1]
    T = cov.shape[0]
    # Off-diagonal mean
    off_diag_sum = cov.sum() - np.trace(cov)
    n_off = T * (T - 1)
    mean_corr = float(off_diag_sum / n_off)

    # Strength s = E_X,Y mr(X,Y) approximated via the empirical edge
    # Following Breiman's s = E_{X,Y} [ P(h(X,Θ)=Y) - max_{j≠Y} P(h(X,Θ)=j) ]
    # We use the per-tree indicator minus the most-frequent-other-class vote.
    # For multi-class, an easier proxy is the mean per-tree accuracy - the
    # chance level (1/num_classes).
    s_proxy = max(avg_tree_acc - 1.0 / len(np.unique(y)), 1e-6)
    rho_over_s2 = mean_corr / (s_proxy ** 2)

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
        "avg_tree_accuracy": avg_tree_acc,
        "mean_pairwise_tree_corr": mean_corr,
        "s_proxy": s_proxy,
        "rho_over_s2": rho_over_s2,
    })
    print(
        f"{label:<14}{n_eff:<8}{oob_err:<11.4f}{oob_acc:<11.4f}"
        f"{test_acc:<11.4f}{avg_tree_acc:<14.4f}{mean_corr:<13.4f}{rho_over_s2:<11.3f}"
    )

# Save
out_json = "/data/workspace/admin/happy_lake/.verify_judge_minimax/randomforest/randomforest_04/results_max_features.json"
with open(out_json, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved raw results to {out_json}")