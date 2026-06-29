"""
Experiment: Compare IsolationForest (iForest) vs LocalOutlierFactor (LOF) baseline.

Fixed settings (only the detection method varies):
- Same dataset, fixed random_state.
- iForest: n_estimators=100, max_samples (psi)=256, random_state=0.
- LOF:   n_neighbors=20, novelty=False (original LOF), random data seed 0.

We report:
- AUC (roc_auc_score with y=1 = anomaly)
- Train time (fit)
- Predict time (score the same data X)
- Total time

For more reliable measurements we repeat each timed step and use the mean.
"""

import json
import time
from pathlib import Path

import numpy as np
from sklearn.datasets import make_classification
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler

# -------- fixed settings --------
RANDOM_STATE = 0  # fixed across data and both methods
N_SAMPLES = 5000
N_FEATURES = 20
N_INFORMATIVE = 15
N_REDUNDANT = 3
OUTLIER_FRAC = 0.05  # 5% anomalies (true anomalies -> label 1)
N_TREES = 100        # n_estimators
MAX_SAMPLES = 256    # psi (sub-sampling size)
LOF_N_NEIGHBORS = 20
N_REPEATS = 5        # repeat each timed step this many times for reliability

# Save outputs in the directory of this script
HERE = Path(__file__).resolve().parent
RESULTS_JSON = HERE / "results_vs_baseline.json"


def generate_data(random_state: int):
    """Generate a fixed dataset with known anomaly labels.

    Uses make_classification; minority class (y=1) is treated as the
    anomaly class for AUC. Features are standardized to give LOF a fair
    distance-based scale.
    """
    X, y = make_classification(
        n_samples=N_SAMPLES,
        n_features=N_FEATURES,
        n_informative=N_INFORMATIVE,
        n_redundant=N_REDUNDANT,
        n_clusters_per_class=2,
        weights=[1 - OUTLIER_FRAC, OUTLIER_FRAC],
        flip_y=0.0,
        class_sep=1.5,
        random_state=random_state,
    )
    X = StandardScaler().fit_transform(X)
    return X, y.astype(int)


def _time_mean(fn, repeats: int) -> float:
    """Average wall time of ``fn`` over ``repeats`` runs."""
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    return float(np.mean(times))


def run_isolation_forest(X, y):
    """iForest: sklearn convention is decision_function higher = more normal.
    Negate so higher = more anomalous for AUC with y=1=anomaly.
    """
    # ---- train timing ----
    def _fit():
        IsolationForest(
            n_estimators=N_TREES,
            max_samples=MAX_SAMPLES,
            random_state=RANDOM_STATE,
            n_jobs=1,
        ).fit(X)

    train_time = _time_mean(_fit, N_REPEATS)

    # ---- build the model once for scoring ----
    clf = IsolationForest(
        n_estimators=N_TREES,
        max_samples=MAX_SAMPLES,
        random_state=RANDOM_STATE,
        n_jobs=1,
    )
    clf.fit(X)

    # ---- predict timing ----
    def _predict():
        clf.decision_function(X)

    predict_time = _time_mean(_predict, N_REPEATS)

    raw = clf.decision_function(X)
    scores = -raw  # higher = more anomalous
    auc = roc_auc_score(y, scores)

    return {
        "method": "IsolationForest (iForest)",
        "params": {
            "n_estimators": N_TREES,
            "max_samples (psi)": MAX_SAMPLES,
            "random_state": RANDOM_STATE,
        },
        "train_time_s": train_time,
        "predict_time_s": predict_time,
        "total_time_s": train_time + predict_time,
        "auc": auc,
        "n_samples": int(X.shape[0]),
        "n_anomalies": int(y.sum()),
        "anomaly_fraction": float(y.mean()),
        "score_convention": "negated decision_function (higher = more anomalous)",
        "timing_repeats": N_REPEATS,
    }


def run_lof(X, y):
    """LOF (novelty=False): ``negative_outlier_factor_`` is the per-sample
    anomaly score (HIGHER = more anomalous), already computed during fit.

    For a fair "predict" timing we evaluate on the same data via
    ``fit_predict`` -- this mirrors the standard unsupervised LOF usage and
    re-runs the full scoring pass over X.
    """
    # ---- train timing (fit only) ----
    def _fit():
        LocalOutlierFactor(
            n_neighbors=LOF_N_NEIGHBORS,
            novelty=False,
            n_jobs=1,
        ).fit(X)

    train_time = _time_mean(_fit, N_REPEATS)

    # ---- predict timing (fit_predict on same X) ----
    clf = LocalOutlierFactor(
        n_neighbors=LOF_N_NEIGHBORS,
        novelty=False,
        n_jobs=1,
    )

    def _predict():
        clf.fit_predict(X)

    predict_time = _time_mean(_predict, N_REPEATS)

    # Compute scores via fit (one full pass)
    clf = LocalOutlierFactor(
        n_neighbors=LOF_N_NEIGHBORS,
        novelty=False,
        n_jobs=1,
    )
    clf.fit(X)
    # ``negative_outlier_factor_`` is the negative of the LOF offset; LOWER
    # (more negative) means MORE anomalous. Negate so that HIGHER = more
    # anomalous (matches the convention used for iForest scores above).
    scores = -clf.negative_outlier_factor_
    auc = roc_auc_score(y, scores)

    return {
        "method": "LocalOutlierFactor (LOF)",
        "params": {
            "n_neighbors": LOF_N_NEIGHBORS,
            "novelty": False,
            "metric": "minkowski",
            "random_state (data)": RANDOM_STATE,
        },
        "train_time_s": train_time,
        "predict_time_s": predict_time,
        "total_time_s": train_time + predict_time,
        "auc": auc,
        "n_samples": int(X.shape[0]),
        "n_anomalies": int(y.sum()),
        "anomaly_fraction": float(y.mean()),
        "score_convention": "-negative_outlier_factor_ (higher = more anomalous)",
        "timing_repeats": N_REPEATS,
    }


def main():
    print("Generating data (random_state=0)...")
    X, y = generate_data(RANDOM_STATE)
    print(f"  shape: {X.shape}; anomalies: {y.sum()} ({y.mean()*100:.2f}%)")

    print("\n--- IsolationForest (iForest) ---")
    iforest_res = run_isolation_forest(X, y)
    print(f"  AUC={iforest_res['auc']:.4f}; "
          f"train={iforest_res['train_time_s']*1000:.2f} ms; "
          f"predict={iforest_res['predict_time_s']*1000:.2f} ms; "
          f"total={iforest_res['total_time_s']*1000:.2f} ms")

    print("\n--- LocalOutlierFactor (LOF) baseline ---")
    lof_res = run_lof(X, y)
    print(f"  AUC={lof_res['auc']:.4f}; "
          f"train={lof_res['train_time_s']*1000:.2f} ms; "
          f"predict={lof_res['predict_time_s']*1000:.2f} ms; "
          f"total={lof_res['total_time_s']*1000:.2f} ms")

    # Summary
    summary = {
        "data": {
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "n_anomalies": int(y.sum()),
            "anomaly_fraction": float(y.mean()),
            "random_state": RANDOM_STATE,
        },
        "iforest": iforest_res,
        "lof": lof_res,
        "delta_auc_iforest_minus_lof": iforest_res["auc"] - lof_res["auc"],
        "ratio_total_time_lof_over_iforest": (
            lof_res["total_time_s"] / iforest_res["total_time_s"]
            if iforest_res["total_time_s"] > 0 else float("inf")
        ),
        "ratio_train_time_lof_over_iforest": (
            lof_res["train_time_s"] / iforest_res["train_time_s"]
            if iforest_res["train_time_s"] > 0 else float("inf")
        ),
        "ratio_predict_time_lof_over_iforest": (
            lof_res["predict_time_s"] / iforest_res["predict_time_s"]
            if iforest_res["predict_time_s"] > 0 else float("inf")
        ),
    }

    with open(RESULTS_JSON, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nWrote JSON: {RESULTS_JSON}")
    return summary


if __name__ == "__main__":
    main()