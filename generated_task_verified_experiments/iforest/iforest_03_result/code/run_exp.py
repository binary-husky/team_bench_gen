import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score

# ---- Data generation: normal cluster + ~2% injected outliers, fixed seed ----
rng = np.random.RandomState(0)

n_normal = 2000
n_outlier = int(round(n_normal * 0.02))  # ~2% => 40
n = n_normal + n_outlier

# normal cluster: single Gaussian cluster in 5-D
mean = np.zeros(5)
cov = np.eye(5)
X_normal = rng.multivariate_normal(mean, cov, size=n_normal)

# injected outliers: far from the cluster, uniform in a wide box
low = np.full(5, 6.0)
high = np.full(5, 10.0)
X_outlier = rng.uniform(low, high, size=(n_outlier, 5))

X = np.vstack([X_normal, X_outlier])
y = np.concatenate([np.zeros(n_normal), np.ones(n_outlier)])  # 1 = anomaly/outlier

print(f"n_total={n}, n_normal={n_normal}, n_outlier={n_outlier} ({n_outlier/n*100:.2f}%)")

# ---- Train IsolationForest (psi=256, n_estimators=100, random_state=0) ----
psi = 256
model = IsolationForest(n_estimators=100, max_samples=psi, contamination='auto',
                        random_state=0, n_jobs=-1)
model.fit(X)

# decision_function: more negative = more anomalous (sklearn convention)
df = model.decision_function(X)
# score_samples: sklearn returns opposite of paper anomaly score s
ss = model.score_samples(X)

# Paper's anomaly score: s = 2^{-E[h]/c(psi)}
# sklearn score_samples = -s  (i.e. returns -2^(-E[h]/c)); verify by range
print("score_samples range:", ss.min(), ss.max())
print("decision_function range:", df.min(), df.max())

# Derive paper's s directly: s = -score_samples (since score_samples = -s in sklearn)
s_paper = -ss
print("s_paper range:", s_paper.min(), s_paper.max())

# Also compute c(psi) from paper formula and check
from math import log, gamma
def c_paper(n):
    # c(n) = 2*H(n-1) - 2*(n-1)/n, H(i) ~ ln(i)+0.5772156649
    if n > 2:
        H = lambda i: log(i) + 0.5772156649015329
        return 2.0*H(n-1) - 2.0*(n-1)/n
    elif n == 2:
        return 1.0
    else:
        return 0.0
c_psi = c_paper(psi)
print("c(psi=256) =", c_psi)

# ---- AUC: use s_paper (higher=more anomalous) and df (lower=more anomalous) ----
auc_s = roc_auc_score(y, s_paper)
auc_df = roc_auc_score(y, -df)  # negate so higher=more anomalous
print(f"AUC (paper s) = {auc_s:.4f}")
print(f"AUC (-decision_function) = {auc_df:.4f}")

# ---- Distribution stats per group ----
def stats(arr):
    return {
        'mean': float(np.mean(arr)),
        'median': float(np.median(arr)),
        'std': float(np.std(arr)),
        'q05': float(np.quantile(arr, 0.05)),
        'q25': float(np.quantile(arr, 0.25)),
        'q75': float(np.quantile(arr, 0.75)),
        'q95': float(np.quantile(arr, 0.95)),
        'min': float(np.min(arr)),
        'max': float(np.max(arr)),
    }

normal_mask = y == 0
outlier_mask = y == 1

print("\n=== Paper anomaly score s = 2^{-E[h]/c} (higher = more anomalous) ===")
print("NORMAL:", stats(s_paper[normal_mask]))
print("OUTLIER:", stats(s_paper[outlier_mask]))

print("\n=== decision_function (lower = more anomalous) ===")
print("NORMAL:", stats(df[normal_mask]))
print("OUTLIER:", stats(df[outlier_mask]))

# also path length: derive E[h] from s: E[h] = -c * log2(s) = -c*ln(s)/ln2
Eh = -c_psi * np.log(s_paper) / np.log(2.0)
print("\n=== implied avg path length E[h] ===")
print("NORMAL mean:", np.mean(Eh[normal_mask]), "median:", np.median(Eh[normal_mask]))
print("OUTLIER mean:", np.mean(Eh[outlier_mask]), "median:", np.median(Eh[outlier_mask]))

# save arrays for reference
np.savez('scores.npz', s=s_paper, df=df, Eh=Eh, y=y)
