import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from retainiq.features import FEATURES


def metrics(y, p, capacity=.1):
    y, p = np.asarray(y), np.asarray(p)
    k = max(1, int(np.ceil(len(y)*capacity)))
    ranked = np.argsort(-p, kind="stable")[:k]
    rate = float(y.mean())
    return {"n": len(y), "prevalence": rate, "log_loss": float(log_loss(y, p, labels=[0, 1])),
            "average_precision": float(average_precision_score(y, p)),
            "roc_auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None,
            "brier": float(brier_score_loss(y, p)), "recall_at_10pct": float(y[ranked].sum()/max(1, y.sum())),
            "lift_at_10pct": float(y[ranked].mean()/rate) if rate else None}


def train(frame, output, data_audit=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if frame.empty or not frame.is_churn.isin([0, 1]).all():
        raise ValueError("Need nonempty binary outcomes")
    if not np.isfinite(frame[FEATURES].to_numpy(dtype=float)).all() or (frame[FEATURES] < 0).any().any():
        raise ValueError("Features must be finite and nonnegative")
    dates = sorted(pd.to_datetime(frame.cutoff).unique())
    if len(dates) != 3:
        raise ValueError("MVP requires exactly three chronological snapshots: train, validation, test")
    if frame.provenance.nunique() != 1:
        raise ValueError("Never mix synthetic and real observations")
    methods = frame.label_method.unique().tolist() if "label_method" in frame else ["legacy_extension_proxy"]
    if len(methods) != 1:
        raise ValueError("Never mix label definitions across evaluation periods")
    label_method = methods[0]
    splits = [frame.loc[pd.to_datetime(frame.cutoff) == d].copy() for d in dates]
    for prior, following in zip(splits, splits[1:]):
        if pd.to_datetime(prior.label_end).max() >= pd.Timestamp(following.cutoff.iloc[0]):
            raise ValueError("Label maturity embargo violated: earlier outcomes overlap next cutoff")
    for part in splits:
        if len(part) < 20 or part.is_churn.nunique() != 2:
            raise ValueError("Each chronological cohort needs >=20 rows and both classes")
        if part.msno.duplicated().any():
            raise ValueError("Duplicate subscriber at cutoff")
    a, b, c = splits
    candidates = {
        "prevalence": DummyClassifier(strategy="prior"),
        "logistic": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=42)),
        "boosted": HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=15, l2_regularization=5, early_stopping=False, random_state=42),
    }
    report = {"provenance": str(frame.provenance.iloc[0]), "feature_schema": FEATURES,
              "release_status": "synthetic_demo" if frame.provenance.iloc[0] == "synthetic" else "reference_reconstruction_research" if label_method == "kkbox_reference_gap_v1" else "historical_proxy_research_only",
              "label_method": label_method, "training_prevalence": float(a.is_churn.mean()),
              "data_audit": data_audit,
              "environment": {"python": platform.python_version(), **{p: version(p) for p in ["numpy", "pandas", "scikit-learn", "duckdb", "joblib"]}},
              "input_frame_sha256": hashlib.sha256(pd.util.hash_pandas_object(frame, index=False).values.tobytes()).hexdigest(),
              "cohort_counts": [len(part) for part in splits],
              "split_dates": [str(pd.Timestamp(d).date()) for d in dates], "validation": {},
              "protocol": "Fit train only; select minimum validation log loss; evaluate frozen winner once on test. No refit."}
    for name, model in candidates.items():
        model.fit(a[FEATURES], a.is_churn)
        report["validation"][name] = metrics(b.is_churn, model.predict_proba(b[FEATURES])[:, 1])
    winner = min(candidates, key=lambda n: report["validation"][n]["log_loss"])
    model = candidates[winner]
    p = model.predict_proba(c[FEATURES])[:, 1]
    report["selected_model"] = winner
    report["test"] = metrics(c.is_churn, p)
    report["test_baseline"] = metrics(c.is_churn, candidates["prevalence"].predict_proba(c[FEATURES])[:, 1])
    # Subscriber bootstrap on held-out cohort. Conditional on trained model; not retraining uncertainty.
    rng = np.random.default_rng(42)
    losses = []
    for _ in range(200):
        idx = rng.integers(0, len(c), len(c))
        losses.append(log_loss(c.is_churn.to_numpy()[idx], p[idx], labels=[0, 1]))
    report["test"]["log_loss_bootstrap_95pct"] = np.quantile(losses, [.025, .975]).tolist()
    observed, predicted = calibration_curve(c.is_churn, p, n_bins=8, strategy="quantile")
    report["calibration"] = {"predicted": predicted.tolist(), "observed": observed.tolist()}
    importance = permutation_importance(model, b[FEATURES], b.is_churn, scoring="neg_log_loss", n_repeats=3, random_state=42)
    report["validation_permutation_importance"] = dict(zip(FEATURES, importance.importances_mean.tolist()))
    report["limitations"] = ["Historical reconstruction assumes event dates approximate availability; no ingestion timestamps.",
        "Target is reconstructed from the supplied KKBOX reference ordering/gap rule; supplied label disagreements are reported separately. Not a Kaggle leaderboard result." if label_method == "kkbox_reference_gap_v1" else "Legacy extension proxy is not the KKBOX reference rule.",
        "Cohort requires a prior-month transaction and expiry in the prediction calendar month. Same-day transactions follow reference ordering; exact reference ties use the minimum known auto-renew flag for features.",
        "If invalid-duration quarantine is enabled, subscribers are excluded after a known negative or >=1e12-second record; less extreme positive outliers remain unaltered.",
        "Recurring subscribers may occur across periods; this estimates future risk for an existing user base.",
        "Risk is not treatment effect; no causal retention or revenue claims."]
    bundle = {"model": model, "features": FEATURES, "provenance": report["provenance"], "model_name": winner,
              "label_method": label_method, "release_status": report["release_status"],
              "training_prevalence": report["training_prevalence"], "training_cutoff": report["split_dates"][0],
              "validation_cutoff": report["split_dates"][1], "test_cutoff": report["split_dates"][2]}
    joblib.dump(bundle, output / "model.joblib")
    report["model_sha256"] = hashlib.sha256((output / "model.joblib").read_bytes()).hexdigest()
    (output / "report.json").write_text(json.dumps(report, indent=2))
    scored = c[["msno", "cutoff", "is_churn"] + FEATURES].copy()
    scored["risk"] = p
    scored.to_parquet(output / "scored.parquet", index=False)
    return report


def load_bundle(path):
    # joblib is executable serialization. Load only locally trained, trusted artifacts.
    return joblib.load(path)


def predict(bundle, records):
    frame = pd.DataFrame(records)
    if set(frame) != set(bundle["features"]):
        raise ValueError("Input must contain exactly the documented feature names")
    values = frame[bundle["features"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Features must be finite and nonnegative")
    return bundle["model"].predict_proba(frame[bundle["features"]])[:, 1].tolist()
