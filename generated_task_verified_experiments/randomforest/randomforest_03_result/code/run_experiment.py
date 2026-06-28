import numpy as np
from sklearn.datasets import load_digits
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

X, y = load_digits(return_X_y=True)

X_tr, X_te, y_tr, y_te = train_test_split(
    X, y, test_size=0.30, random_state=42, stratify=y
)

n_estimators_list = [10, 50, 100, 200, 500, 1000]

rows = []
for n in n_estimators_list:
    clf = RandomForestClassifier(
        n_estimators=n,
        oob_score=True,
        random_state=0,
        n_jobs=-1,
    )
    clf.fit(X_tr, y_tr)
    oob_err = 1.0 - clf.oob_score_
    test_err = 1.0 - clf.score(X_te, y_te)
    rows.append((n, oob_err, test_err))
    print(f"n_estimators={n:5d}  OOB_err={oob_err:.4f}  test_err={test_err:.4f}")

print("\nDONE")
import json
print(json.dumps(rows))
