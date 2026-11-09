# RetainIQ model card — reference release

## Intended use and outcome

Historical research, subscriber-risk ranking and interview demonstrations. The trained target is `kkbox_reference_gap_v1`, a documented reproduction of the supplied Scala cohort/order/renewal-gap rules. It is not an intervention-response probability, autonomous offer policy, contemporary SaaS forecast, or deployed production model.

Training requires an observed transaction in the month before cutoff and reference-ordered expiry in the prediction month. Future cancellations can shorten expiry before the first noncancel event. Gap <30 means renewal; gap >=30 means churn. Complete observation through original expiry +30 is required uniformly. Reference reconstruction and supplied KKBOX labels disagree and are never silently substituted for one another.

## Features and estimator

Eight features: days to recorded expiry, observed transaction tenure, transaction count and paid amount over 90 days, auto-renew flag, active listening days, seconds and sum of daily unique-song counts over 30 days. All use events strictly before cutoff. No IDs, official labels or profile snapshots enter the feature matrix.

Candidates are training-prevalence baseline, standardized logistic regression, and histogram gradient boosting with fixed parameters (100 iterations, 15 leaves, L2=5, no random internal early-stopping split). October validation log loss selects the winner; no test-based threshold or hyperparameter search. No resampling or class weighting distorts prevalence. Artifact metadata records feature schema, label method, source provenance, model identity and split dates.

## Evaluations that answer different questions

Reference-reconstructed cohorts: July 2016 train (3,626), October 2016 validation (3,982), January 2017 retrospective test (4,121). Boosted model validation log loss 0.11293. January reference-target test log loss 0.14300, ROC-AUC 0.79142, AP 0.28971. January results are retrospective after revision of a previously inspected proxy; they are not described as a pristine holdout.

Separate March 2017 evaluation uses supplied `train_v2.csv` labels on 4,034 matched sampled subscribers with pre-March features. The same frozen model obtains log loss 0.21321 (baseline 0.22734), AP 0.30894, ROC-AUC 0.76193, Brier 0.04980, Recall@10% 0.50 and Lift@10% 4.99257. The conditional subscriber-bootstrap 95% log-loss interval is [0.18653,0.23755]. These scores apply only to the matched monthly cohort after data-quality exclusions, not every label-file subscriber or the competition leaderboard.

## Reliability, interpretation and limitations

Calibration is displayed, not claimed to be solved. Reconstruction/supplied-target differences and prevalence drift can cause underprediction. The model is frozen; March was not used for calibration, selection, retraining or capacity tuning. Bootstrap intervals are conditional on one model and one cohort; they exclude retraining uncertainty and changing temporal conditions.

Validation permutation importance measures predictive dependence, not causality or individual explanations. Review capacity is a ranking choice. Offer benefit and saved revenue require randomized assignment, power/guardrail planning, and intention-to-treat analysis.

No source arrival timestamps exist. Event-date cutoff correctness is tested, while actual historical ingestion availability cannot be proven. Refresh files contain backdated transactions and may alter reconstructed history. No demographic fairness or modern production drift audit has been performed. Negative and overflow-scale positive durations are quarantined; less extreme positives, telemetry absence and monthly selection remain limitations.

Deployment is local only. The API validates batches up to 1,000, exposes outcome/provenance metadata, and returns 503 without a model. Model files use executable serialization; load only trusted artifacts. Inference is bounded local serving, not a tested high-concurrency service. Docker, remote CI and hosted operations remain unverified.
