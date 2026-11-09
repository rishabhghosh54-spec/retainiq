"""Evaluation against supplied labels, kept separate from reconstructed outcomes."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import log_loss

from retainiq.features import FEATURES, snapshot
from retainiq.model import load_bundle, metrics, predict


def evaluate_official(database, model_path, labels_path, cutoff, observation_end, output):
    bundle = load_bundle(model_path)
    cutoff = pd.Timestamp(cutoff)
    if cutoff <= pd.Timestamp(bundle["test_cutoff"]):
        raise ValueError("External evaluation must follow all prior evaluation cutoffs")
    # Training/validation outcomes mature at most 60 days after their month start.
    if pd.Timestamp(bundle["validation_cutoff"]) + pd.DateOffset(months=1) + pd.Timedelta(days=30) >= cutoff:
        raise ValueError("Validation label maturity overlaps external evaluation")
    frame = snapshot(database, cutoff, observation_end, labels=False)
    labels = pd.read_csv(labels_path, dtype={"msno": str})
    if labels.msno.duplicated().any() or not labels.is_churn.isin([0, 1]).all():
        raise ValueError("Supplied labels must have unique IDs and binary outcomes")
    joined = frame.merge(labels[["msno", "is_churn"]], on="msno", validate="one_to_one")
    if len(joined) < 20 or joined.is_churn.nunique() != 2:
        raise ValueError("External evaluation needs >=20 rows and both classes")
    probabilities = np.array(predict(bundle, joined[FEATURES].to_dict("records")))
    report = {"target": "supplied_official_labels", "cutoff": str(cutoff.date()), "label_file": Path(labels_path).name,
              "label_file_sha256": hashlib.sha256(Path(labels_path).read_bytes()).hexdigest(),
              "model_sha256": hashlib.sha256(Path(model_path).read_bytes()).hexdigest(),
              "model": bundle["model_name"], "training_label_method": bundle["label_method"],
              "eligible_feature_rows": len(frame), "matched_rows": len(joined),
              "feature_rows_without_supplied_label": len(frame)-len(joined),
              "test": metrics(joined.is_churn, probabilities),
              "baseline": metrics(joined.is_churn, np.full(len(joined), bundle["training_prevalence"])),
              "protocol": "Previously frozen model; pre-cutoff features only; supplied external labels used only for evaluation. No fitting, recalibration, selection or threshold tuning on this cohort.",
              "limitations": ["Sampled monthly reference-eligible subscribers with valid listening history; not the full competition population.",
                  "Training uses reference-reconstructed outcomes; evaluation uses supplied labels, which disagree on an audited prior cohort.",
                  "No April transaction history to reconstruct March outcomes independently; supplied labels are treated as external ground truth.",
                  "No source arrival timestamps; historical availability is assumed from event dates.",
                  "No causal retention, revenue, or Kaggle leaderboard claim."]}
    rng = np.random.default_rng(42)
    y = joined.is_churn.to_numpy()
    losses = []
    for _ in range(200):
        idx = rng.integers(0, len(y), len(y))
        losses.append(log_loss(y[idx], probabilities[idx], labels=[0, 1]))
    report["test"]["log_loss_bootstrap_95pct"] = np.quantile(losses, [.025, .975]).tolist()
    observed, predicted = calibration_curve(y, probabilities, n_bins=8, strategy="quantile")
    report["calibration"] = {"predicted": predicted.tolist(), "observed": observed.tolist()}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    joined["risk"] = probabilities
    joined.to_parquet(output.with_suffix(".scored.parquet"), index=False)
    return report
