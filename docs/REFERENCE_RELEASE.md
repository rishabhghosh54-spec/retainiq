# RetainIQ 0.2 — verified reference-label release

This is the current release record. The extension-only pilot in `REAL_DATA_RUN.md` is superseded. Correctness here means a documented outcome definition, independent implementation checks, explicit disagreement with supplied labels, and evaluation that does not train on its test cohort. It does not mean that imperfect historical data has become perfect or that every uncertainty has been resolved.

## What changed

The original label proxy treated any later membership extension as retention. It did not reproduce the reference's cancellation state updates or first-subscription rule. The replacement:

1. Requires a transaction in the preceding calendar month, with latest reference-ordered expiry in the prediction calendar month.
2. Orders dates forward; within a date, compares concatenated decimal plan-price, plan-days and payment-method signatures lexicographically descending; puts subscription before cancellation; sorts renewal expiries ascending and cancellation expiries descending.
3. Walks future cancellations, shortening the relevant expiry when needed, until the first noncancel transaction.
4. Uses renewal gap <30 days for retention and >=30 days for churn. A fully observed window with no renewal is churn.
5. Requires complete observation through original expiry plus 30 days for every reconstructed outcome, including early renewals. This avoids outcome-dependent censoring.

These are a port of the supplied `WSDMChurnLabeller.scala`, not a claim that the comparator is a real event timestamp. Its SHA-256 is `CD93CB64E6A82C983E3E8B4BE2534ADF291213F5F5EFC82409FB578FE1A03693`. The original concatenation/string comparison is deliberately retained, including cases where numeric price ordering would differ. Columns needed for ordering are now preserved at ingestion; older databases must be re-ingested.

Feature state uses the same prior-month ordering. Same-day transactions are no longer discarded wholesale. For exact reference-ordering ties, minimum observed auto-renew is a deterministic feature convention. Listening conflicts and invalid durations remain pre-cutoff exclusions. Predictions cover a calendar month, so valid expiry proximity includes day 30 for 31-day months.

## Independent and full-source validation

SQL is the operational implementation. A separately written Python sort/state-walk acts as a slower oracle. They agree on all 4,186 sampled February candidates: zero cohort, expiry or outcome disagreements. Unit fixtures additionally cover same-plan subscription/cancellation ordering, different plans, lexical signatures, repeated cancels, repeated renewals, early renewal, no activity, day 29/30/31, prior-month eligibility, and uniform censoring.

The separate full transaction audit scans **22,978,755** source rows, validates key/numeric/date contracts, and retains **22,975,416** exact-distinct rows. No listening-based or subscriber-sampling exclusion is applied to this label audit. The reconstructed February cohort contains 856,144 users; 856,085 intersect the supplied February labels.

| Supplied target | Reconstructed retained | Reconstructed churn |
|---|---:|---:|
| Retained | 817,233 | 168 |
| Churn | 10,357 | 28,327 |

Overall agreement is **98.7706%**, with **10,525** disagreements. Recall of supplied churn under the reconstructed rule is **73.2267%**. The sample intersection has 55 disagreements out of 4,186. These numbers are distinct from predictive model accuracy. They demonstrate that following the supplied reference and reproducing the supplied label file are not identical claims. Source revisions, differing cohort rules or label construction may contribute, but exact causes for every residual have not been established. No labels were overwritten to force agreement.

A related [Databricks reconstruction workflow](https://www.databricks.com/notebooks/churn/1-data-preparation.html) also treats reconstruction as an explicit data-preparation step. Our correctness evidence is the locally inspected reference code, independent oracle, test fixtures, hashes, and measured audits—not another project's reported accuracy.

## Modeling and chronological protocol

Training uses a deterministic 0.5% sample of transaction subscribers, retaining all their available transactions/listening. The model experiment is not full-population training. Full source scanning and the full transaction audit are separate engineering evidence.

| Role | Cutoff | Reference-labeled eligible rows |
|---|---|---:|
| Train | 2016-07-01 | 3,626 |
| Validation | 2016-10-01 | 3,982 |
| Revised retrospective test | 2017-01-01 | 4,121 |

Every feature uses events strictly before its cutoff. Each earlier cohort's original expiry-plus-30-day window finishes before the next cutoff. IDs, supplied labels and unversioned demographic snapshots are excluded from the feature matrix. The test has returning subscribers; the estimand is future risk for an existing subscription base, not unseen-user generalization.

Fixed candidates are prevalence baseline, standardized logistic regression and histogram gradient boosting. October validation log losses are **0.13796**, **0.12507** and **0.11293**, respectively. The boosted model wins on validation and remains frozen. No March tuning, refit, calibration or threshold search is performed.

The January reference-target test has log loss **0.14300** (baseline **0.17002**), ROC-AUC **0.79142**, AP **0.28971**, Brier **0.03389**, Recall@10% **0.56970**, Lift@10% **5.68455**, and conditional 95% log-loss interval **[0.12523,0.16340]**. It is explicitly retrospective: January had already been inspected under the earlier proxy. Changing outcome definitions does not restore a pristine holdout.

## Separate supplied-label evaluation

March outcomes cannot all be reconstructed through expiry +30 from transactions ending March 31. That prevents complete March reconstruction; it does **not** prevent evaluating a frozen model against the separately supplied March label file. The latter is treated as external ground truth, with that assumption disclosed.

March features are built using events strictly before **2017-03-01**, without requiring future observations. The eligible monthly feature cohort contains 4,138 sampled users; 4,034 match supplied `train_v2.csv` labels and 104 have no matching supplied label. The model and all selection decisions were frozen before evaluating those labels.

| March supplied-label metric | Frozen model | Frozen prevalence baseline |
|---|---:|---:|
| Log loss | 0.21321 | 0.22734 |
| Average precision | 0.30894 | 0.05999 |
| ROC-AUC | 0.76193 | 0.50000 |
| Brier | 0.04980 | 0.05643 |
| Recall at 10% review capacity | 0.50000 | 0.10331 |
| Lift at 10% | 4.99257 | 1.03152 |

The conditional subscriber-bootstrap 95% log-loss interval is **[0.18653,0.23755]**. Baseline top-K ties use stable row order and are arbitrary; its log loss and prevalence are the meaningful baseline quantities. These are sampled, eligibility-filtered supplied-label results, not a leaderboard score. Label/feature population shifts and calibration limitations remain visible.

## Current limitations and release status

The final executed suite reports **30 passed, 2 deselected in 21.31 seconds**. The two deselected cases are ASGI HTTP transport tests: a timed stack trace isolated the local Windows restriction to `asyncio` creating its internal socket pair, before application requests ran. Core prediction/serialization parity, Pydantic input validation, missing-model behavior and maturity guards are tested without networking. The HTTP cases remain enabled in normal CI; no remote CI pass is claimed.

The real dashboard rendered successfully, displayed both reconstructed/supplied-target evaluations and the discrepancy warning, and passed review-cohort and capacity-slider interaction checks. Inference from the trained real model matched offline probabilities. The updated synthetic CLI demo was rerun successfully. These checks do not establish live network serving, Docker behavior or deployed availability.

The 0.2.0 Python wheel also built successfully. An additional strengthened quarantine test passed after the full suite, explicitly checking both the current reference pipeline and legacy pipeline against future invalid records. Exact package, code and report hashes are recorded in `examples/verified-run.json`.

Follow-up: after the user started the dashboard locally, the live in-app browser review verified all four tabs, March figures, cohort switching and capacity-slider interaction. See [the dashboard review record](DASHBOARD_REVIEW.md). The subsequent [live API review](API_REVIEW.md) passed seven HTTP checks and exact offline-model prediction parity. Docker, remote CI and remote deployment remain unverified; the live API missing-model scenario was not exercised.

- Source arrival timestamps are unavailable. Event-time cutoffs are tested, but original production ingestion-time availability cannot be proven, especially for backdated refresh transactions.
- Daily source presence is coverage evidence, not proof of individual completeness. Zero listening can represent inactivity or missing telemetry.
- The explicit quarantine removes 252 negative and two overflow-scale positive sample durations. It excludes affected subscribers only after the event; less extreme positive outliers remain unresolved.
- Reference-rule and supplied-label targets disagree. March supplied labels cannot all be independently reconstructed without April transactions. No vendor-label equivalence is claimed.
- Full-population model training, demographic fairness, distributed scaling and contemporary SaaS/FinTech transfer have not been validated.
- No causal offer benefit, saved revenue, public deployment, completed Docker run or successful remote CI run is claimed.

The deliverable is a reproducible portfolio research project with a functioning local application and audit evidence. These qualifications should accompany any CV, interview or publication claims.

## Reproduce

Use the README's sample/ingest/build/audit/train/evaluate-official commands. The operational database is `data/kkbox-reference.duckdb`; model artifacts are in `artifacts/reference`. `run-real.ps1` loads that current folder. The old pilot database and artifacts are retained locally for comparison and are not the default real dashboard.

Aggregate current evidence is in `examples/reference-report.json`, `reference-full-audit.json`, `reference-sample-audit.json`, `reference-oracle-check.json`, `official-march-evaluation.json`, and `reference-application-check.json`. Raw data, features, scores and executable model binaries remain ignored by Git. Model/label-file checksums and environment versions are in the machine-readable reports.
