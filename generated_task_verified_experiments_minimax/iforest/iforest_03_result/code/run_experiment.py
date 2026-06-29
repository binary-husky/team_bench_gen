"""
Experiment: Distribution of anomaly scores (and path lengths) for normal vs. anomalous points
in IsolationForest, using a synthetic dataset (normal clusters + ~2% injected outliers, fixed seed).

Per the task:
- psi = 256, n_estimators = 100, random_state = 0
- Compute both s = 2^(-E[h(x)]/c(psi)) (per the paper) and sklearn's decision_function
- Report mean / median / quantiles for normal and anomalous points
- Report AUC using true labels

Outputs:
- raw_scores.csv          (one row per point with labels and scores)
- experiment_output.txt   (the human-readable summary that we will quote in the writeup)
"""
import os
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.ensemble._iforest import _average_path_length
from sklearn.metrics import roc_auc_score

# ---------- 0. Reproducibility ----------
SEED = 0
rng = np.random.default_rng(SEED)

# ---------- 1. Synthetic data generation ----------
D = 2
N_NORMAL_PER_CLUSTER = 1500
N_ANOM_PER_CLUSTER = 60
NORMAL_CLUSTER_CENTERS = np.array([[0.0, 0.0], [6.0, 0.0], [0.0, 6.0]])
ANOM_CLUSTER_CENTERS  = np.array([[10.0, 10.0], [-10.0, -6.0]])

normal_parts = [rng.normal(loc=c, scale=1.0, size=(N_NORMAL_PER_CLUSTER, D))
                for c in NORMAL_CLUSTER_CENTERS]
X_normal = np.vstack(normal_parts)

anom_parts = [rng.normal(loc=c, scale=0.6, size=(N_ANOM_PER_CLUSTER, D))
              for c in ANOM_CLUSTER_CENTERS]
X_anom = np.vstack(anom_parts)

X = np.vstack([X_normal, X_anom])
y = np.r_[np.zeros(len(X_normal), dtype=int),
          np.ones(len(X_anom),    dtype=int)]
print(f"n_total = {len(X)}, n_normal = {len(X_normal)}, "
      f"n_anom = {len(X_anom)}, contamination = {len(X_anom)/len(X):.4f}")

perm = rng.permutation(len(X))
X, y = X[perm], y[perm]

# ---------- 2. Fit IsolationForest (psi=256, n_estimators=100, random_state=0) ----------
PSI = 256
N_ESTIMATORS = 100
RANDOM_STATE = 0

model = IsolationForest(
    n_estimators=N_ESTIMATORS,
    max_samples=PSI,
    random_state=RANDOM_STATE,
    contamination="auto",
    n_jobs=1,
)
model.fit(X)

# c(psi) from the paper: average path length of an unsuccessful BST search of size psi.
c_psi = float(_average_path_length(np.array([PSI]))[0])
print(f"c(psi={PSI}) = {c_psi:.6f}")

# ---------- 3. Anomaly scores and path lengths ----------
#   sklearn's _compute_score_samples (private) returns exactly
#       s_paper = 2^(-E[h(x)]/c(psi))
#   so score_samples (public) returns -s_paper and decision_function
#       = score_samples - offset_  with offset_=-0.5 (contamination='auto')
#       = -s_paper + 0.5.
#
#   We independently compute E[h(x)] by averaging the per-tree path lengths
#   (including the c(T.size) adjustment, per Algorithm 3 of the paper).
from sklearn.tree._tree import TREE_LEAF

per_tree_lengths = np.zeros((len(X), N_ESTIMATORS))
for t_idx, est in enumerate(model.estimators_):
    tree = est.tree_
    for j in range(len(X)):
        node = 0
        d = 0
        while tree.children_left[node] != TREE_LEAF:
            a = tree.feature[node]
            if X[j, a] < tree.threshold[node]:
                node = tree.children_left[node]
            else:
                node = tree.children_right[node]
            d += 1
        # Adjustment for an unbuilt subtree at a multi-instance leaf
        if tree.n_node_samples[node] > 1:
            d += float(_average_path_length(np.array([tree.n_node_samples[node]]))[0])
        per_tree_lengths[j, t_idx] = d

E_h = per_tree_lengths.mean(axis=1)
s_paper = np.power(2.0, -E_h / c_psi)
df = model.decision_function(X)              # = 0.5 - s_paper

# Sanity check
s_skl_neg = model.score_samples(X)
assert np.allclose(s_paper, -s_skl_neg, atol=1e-8), \
    "paper s != -sklearn.score_samples"
print("Cross-check passed: paper s = 2^-E[h]/c(psi) == -sklearn.score_samples")

# ---------- 4. Distribution comparison ----------
def stats(name, vals):
    return {
        "group":   name,
        "n":       len(vals),
        "mean":    float(np.mean(vals)),
        "median":  float(np.median(vals)),
        "std":     float(np.std(vals, ddof=1)),
        "min":     float(np.min(vals)),
        "p05":     float(np.percentile(vals, 5)),
        "p25":     float(np.percentile(vals, 25)),
        "p50":     float(np.percentile(vals, 50)),
        "p75":     float(np.percentile(vals, 75)),
        "p95":     float(np.percentile(vals, 95)),
        "max":     float(np.max(vals)),
    }

rows = []
rows.append(stats("normal_Eh",  E_h[y == 0]))
rows.append(stats("anomaly_Eh", E_h[y == 1]))
rows.append(stats("normal_s_paper",  s_paper[y == 0]))
rows.append(stats("anomaly_s_paper", s_paper[y == 1]))
rows.append(stats("normal_df",  df[y == 0]))
rows.append(stats("anomaly_df", df[y == 1]))
df_stats = pd.DataFrame(rows)
print("\n=== Distribution comparison ===")
print(df_stats.to_string(index=False))

# ---------- 5. AUC ----------
auc_s_paper = roc_auc_score(y, s_paper)
auc_negEh   = roc_auc_score(y, -E_h)
auc_negDf   = roc_auc_score(y, -df)
print(f"\n=== AUC (higher score => more anomalous) ===")
print(f"AUC using paper's s = 2^-E[h]/c(psi) : {auc_s_paper:.4f}")
print(f"AUC using -E[h(x)] (path length view): {auc_negEh:.4f}")
print(f"AUC using -decision_function         : {auc_negDf:.4f}")

# ---------- 6. Persist artefacts ----------
HERE = os.path.dirname(os.path.abspath(__file__))
out_csv = os.path.join(HERE, "raw_scores.csv")
pd.DataFrame({
    "y":       y,
    "E_h":     E_h,
    "s_paper": s_paper,
    "df":      df,
}).to_csv(out_csv, index=False)

with open(os.path.join(HERE, "experiment_output.txt"), "w") as f:
    f.write(f"SEED = {SEED}\n")
    f.write(f"n_total = {len(X)}, n_normal = {len(X_normal)}, "
            f"n_anom = {len(X_anom)}\n")
    f.write(f"contamination = {len(X_anom)/len(X):.4f}\n")
    f.write(f"psi = {PSI}, n_estimators = {N_ESTIMATORS}, "
            f"random_state = {RANDOM_STATE}\n")
    f.write(f"c(psi) = {c_psi:.6f}\n\n")
    f.write("=== Distribution comparison ===\n")
    f.write(df_stats.to_string(index=False))
    f.write("\n\n=== AUC (higher score => more anomalous) ===\n")
    f.write(f"AUC using paper's s = 2^-E[h]/c(psi) : {auc_s_paper:.4f}\n")
    f.write(f"AUC using -E[h(x)] (path length view) : {auc_negEh:.4f}\n")
    f.write(f"AUC using -decision_function          : {auc_negDf:.4f}\n")

print("\nWrote raw_scores.csv and experiment_output.txt")
