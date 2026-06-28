import numpy as np
from sklearn.datasets import load_digits
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

X, y = load_digits(return_X_y=True)
p = X.shape[1]  # 64
print(f"n_samples={X.shape[0]}, p={p}")

X_tr, X_te, y_tr, y_te = train_test_split(
    X, y, test_size=0.30, random_state=0, stratify=y
)

settings = [
    (1, "1"),
    ("sqrt", "sqrt(≈8)"),
    (p // 3, "p/3(≈21)"),
    (None, "None(全部 p=64)"),
]

results = []
for mf, label in settings:
    rf = RandomForestClassifier(
        n_estimators=200,
        max_features=mf,
        oob_score=True,
        random_state=0,
        n_jobs=-1,
    )
    rf.fit(X_tr, y_tr)
    test_acc = rf.score(X_te, y_te)
    oob_err = 1.0 - rf.oob_score_

    # inter-tree correlation: get per-tree predictions on test set, compute
    # mean pairwise correlation of indicator-style agreement across samples.
    # Use tree predicted class labels -> build one-hot-ish agreement via
    # correlation of each tree's prediction-indicator vectors per class.
    tree_preds = np.array([tree.predict(X_te) for tree in rf.estimators_])
    n_trees = tree_preds.shape[0]
    # Build binary indicator matrix per class, then average pairwise corr.
    classes = np.unique(y_te)
    corrs = []
    for c in classes:
        mat = (tree_preds == c).astype(float)  # (n_trees, n_samples)
        # pairwise correlation between tree rows
        matc = mat - mat.mean(axis=1, keepdims=True)
        # corr between row i and row j
        denom = np.sqrt((matc ** 2).sum(axis=1, keepdims=True))
        denom[denom == 0] = 1.0
        norm = matc / denom
        G = norm @ norm.T
        # take upper triangle (exclude diagonal)
        iu = np.triu_indices(n_trees, k=1)
        vals = G[iu]
        vals = vals[~np.isnan(vals)]
        corrs.extend(vals.tolist())
    mean_corr = float(np.mean(corrs)) if corrs else float("nan")

    eff = mf if isinstance(mf, int) else (int(np.sqrt(p)) if mf == "sqrt" else p)
    print(f"max_features={label:14s} eff={eff:3d} | test_acc={test_acc:.4f} "
          f"oob_err={oob_err:.4f} | tree_corr={mean_corr:.4f}")
    results.append((label, eff, test_acc, oob_err, mean_corr))

print("\nDONE")
# save to a pickle-ish text for reference
import json
with open("results.json", "w") as f:
    json.dump([
        {"max_features": l, "eff_mf": e, "test_acc": float(a),
         "oob_err": float(o), "mean_tree_corr": float(c)}
        for (l, e, a, o, c) in results
    ], f, indent=2)
