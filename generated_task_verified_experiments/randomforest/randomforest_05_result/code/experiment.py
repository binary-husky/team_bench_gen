"""
Experiment: Random Forest vs single Decision Tree (variance reduction / overfitting resistance).

Fixed settings:
  - Dataset: load_digits (sklearn, 8x8 grayscale digits, 1797 samples, 64 features, 10 classes)
  - Split: 70/30 train/test, stratified
  - RandomForestClassifier(n_estimators=200, random_state=SEED, n_jobs=-1)
  - DecisionTreeClassifier(random_state=SEED)
  - Seed set: SEEDS = range(0, 20)  (each seed -> a different 70/30 split AND model init)

Independent variable: model type (RF vs single tree).
Measured: train error = 1 - accuracy, test error = 1 - accuracy, per seed.
"""
import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score

SEEDS = list(range(0, 20))
TEST_SIZE = 0.30

X, y = load_digits(return_X_y=True)
print(f"Dataset: load_digits  n_samples={X.shape[0]}  n_features={X.shape[1]}  n_classes={len(np.unique(y))}")

rows = []
for seed in SEEDS:
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=seed, stratify=y
    )
    # (a) Random Forest
    rf = RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=-1)
    rf.fit(Xtr, ytr)
    rf_tr_err = 1.0 - accuracy_score(ytr, rf.predict(Xtr))
    rf_te_err = 1.0 - accuracy_score(yte, rf.predict(Xte))

    # (b) Single decision tree
    dt = DecisionTreeClassifier(random_state=seed)
    dt.fit(Xtr, ytr)
    dt_tr_err = 1.0 - accuracy_score(ytr, dt.predict(Xtr))
    dt_te_err = 1.0 - accuracy_score(yte, dt.predict(Xte))

    rows.append((seed, rf_tr_err, rf_te_err, dt_tr_err, dt_te_err))
    print(f"seed={seed:2d} | RF train_err={rf_tr_err:.4f} test_err={rf_te_err:.4f} | "
          f"DT train_err={dt_tr_err:.4f} test_err={dt_te_err:.4f}")

arr = np.array(rows, dtype=float)
rf_tr = arr[:, 1]; rf_te = arr[:, 2]; dt_tr = arr[:, 3]; dt_te = arr[:, 4]

def stats(x):
    return float(np.mean(x)), float(np.std(x, ddof=1))

rf_tr_m, rf_tr_s = stats(rf_tr)
rf_te_m, rf_te_s = stats(rf_te)
dt_tr_m, dt_tr_s = stats(dt_tr)
dt_te_m, dt_te_s = stats(dt_te)

print("\n===== AGGREGATE OVER %d SEEDS =====" % len(SEEDS))
print(f"RF  train error: mean={rf_tr_m:.4f} std={rf_tr_s:.4f}")
print(f"RF  test  error: mean={rf_te_m:.4f} std={rf_te_s:.4f}")
print(f"DT  train error: mean={dt_tr_m:.4f} std={dt_tr_s:.4f}")
print(f"DT  test  error: mean={dt_te_m:.4f} std={dt_te_s:.4f}")
print(f"RF vs DT test-error mean improvement: {dt_te_m - rf_te_m:.4f} "
      f"({(dt_te_m - rf_te_m)/dt_te_m*100:.1f}% relative)")
print(f"RF vs DT test-error std  reduction : {dt_te_s - rf_te_s:.4f} "
      f"(ratio DT/RF = {dt_te_s/rf_te_s:.2f}x)")
print(f"RF train-test gap: {rf_te_m - rf_tr_m:.4f}")
print(f"DT train-test gap: {dt_te_m - dt_tr_m:.4f}")

# save raw rows for the summary
np.save("results.npy", arr)
with open("results.txt", "w") as f:
    f.write("seed,rf_train_err,rf_test_err,dt_train_err,dt_test_err\n")
    for r in rows:
        f.write("%d,%.6f,%.6f,%.6f,%.6f\n" % r)
