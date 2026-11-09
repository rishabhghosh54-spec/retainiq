# Real-data pilot — 2026-11-09

**Superseded historical record.** The current reference-label release, full-source audit and separate supplied-label March evaluation are documented in [REFERENCE_RELEASE.md](REFERENCE_RELEASE.md). The numbers below describe the earlier extension-only proxy and must not be quoted as current results.

## Read this qualification first

This is an executed research experiment on real KKBOX records, not a synthetic demonstration. However, the simplified renewal-extension target is **not equivalent to official churn**. On 3,760 matched subscribers at the February 2017 audit cutoff, it missed 65 of 218 official churn cases: 70.18% recall of the official churn class. Overall agreement of 98.27% hides that minority-class problem. Do not publish the model metrics as official KKBOX churn performance or a Kaggle result.

The next scientific gate is reconstruction of cancellation, subscription ordering and expiry updates using the supplied `WSDMChurnLabeller.scala` reference, with explicit tests and re-audit. Gap inspection of the 65 mismatches found qualifying extensions from 27 days before expiry through 29 days after expiry; none were exactly day 30. Changing only an inclusive deadline would therefore not solve these observed disagreements. March official labels were not compared because full expiry-plus-30-day follow-up extends beyond the available March transactions.

## Source inspection and sampling

The user supplied the full competition ZIP in Downloads. The six required transaction/listening/label `.7z` archives were extracted into ignored workspace storage. Every extraction reported successful archive integrity checks. Members and submission archives remain untouched because this MVP does not use them. Originals in Downloads were not changed.

| File | Source rows | Date range | Retained rows |
|---|---:|---|---:|
| transactions.csv | 21,547,746 | 2015-01-01–2017-02-28 | 106,501 |
| transactions_v2.csv | 1,431,009 | 2015-01-01–2017-03-31 | 6,883 |
| user_logs.csv | 392,106,543 | 2015-01-01–2017-02-28 | 1,876,432 |
| user_logs_v2.csv | 18,396,362 | 2017-03-01–2017-03-31 | 89,711 |

All transaction/listening source CSVs were SHA-256 hashed. Daily count summaries show no missing calendar days in the combined transaction/listening histories. This is coverage evidence, not proof of complete user telemetry or historical availability timestamps. The observation end assumption is 2017-03-31.

Selection used `md5_number_lower(msno) % 1000 < 5` on transaction subscribers, retaining all their events across dates. There are 11,944 selected transaction subscribers and 9,571 with listening records. Expected sampling fraction is 0.5%; this is not a claim that every cohort has exactly that fraction. Missing listening histories stay missing rather than being invented. The original listening sample was retried after a poor query plan attempted to build a lookup from the large CSV. The final plan forces a semi-join with the small selected-user table on its build side. Temporary spill files from the stopped attempt were removed.

## Validation and cleaning

Before cleaning there were 1,966,143 retained listening rows. The explicit invalid-duration policy quarantined 252 negative and two >=1e12-second positive values, affecting 153 subscribers across all dates. Original values remain in `invalid_logs`; subscribers are excluded only after the invalid event becomes historical. Less extreme positive outliers remain a limitation: the pre-cleaning sample had 656 rows above 86,400 seconds, including the two quarantined positive sentinels. Multiple devices, instrumentation, and other explanations have not been adjudicated.

Deduplication removed 14 transaction rows. The database contains 113,370 transaction rows and 1,965,889 valid listening rows. It reports 1,379 conflicting transaction user/date keys and no conflicting listening keys. Subscribers with ambiguous pre-cutoff records are excluded from the relevant snapshot. This changes the eligible population and can bias results.

## Executed modeling experiment

| Role | Cutoff | Eligible matured rows | Proxy churn rate |
|---|---|---:|---:|
| Train | 2016-07-01 | 2,899 | 6.55% |
| Validation | 2016-10-01 | 3,113 | 3.31% |
| Test | 2017-01-01 | 3,234 | 4.76% |

Features use strictly pre-cutoff events. All outcomes in each earlier cohort mature before the next cutoff. The model saw no subscriber IDs as features. Returning users can appear across periods.

Validation log loss: prevalence baseline **0.15571**, logistic regression **0.12371**, histogram gradient boosting **0.11879**. The boosted model was selected using validation only, then frozen for test.

Held-out **proxy-target** metrics: log loss **0.15329**, AP **0.37532**, ROC-AUC **0.82787**, Brier **0.03892**, Recall@10% **0.55195**, Lift@10% **5.50926**. The conditional bootstrap 95% log-loss interval is **[0.13066, 0.17456]**. These are real measured pilot outputs with a known label-validity limitation; they do not establish official-target accuracy, causal retention impact, or full-data performance.

Aggregate machine-readable reports are in `examples/real-proxy-report.json`, `examples/real-data-audit.json`, and `examples/real-source-sampling.json`. No subscriber-level data is included in those reports. Actual database, features, model and scored subscribers remain in ignored `data/` and `artifacts/kkbox-sample/` folders on the build machine.

## Application and regression checks

The final current-code run passed **10 tests**, with two HTTP-client tests deselected and one dependency deprecation warning, in **20.18 seconds**. Tests exercised complete-subscriber sampling, strict validation, negative/positive-sentinel quarantine, past/future exclusion boundaries, source-import rollback, feature leakage boundaries, censoring, renewal deadline behavior, cohort embargoes, aggregate label-audit agreement, and the synthetic dashboard. The two HTTP transport tests were not rerun in this environment; their earlier synthetic verification remains in the initial build record.

An additional check loaded the real trained model, verified direct inference-route probabilities against offline probabilities, rendered the dashboard using real artifacts, confirmed the 65-of-218 label warning was visible, and changed the review-capacity slider without errors. That is an application-code check, not a new live HTTP or hosted-deployment test. The full local artifacts include `application-check.json`. Launch the real dashboard after installing dependencies with `./run-real.ps1`.

## Reproduce after extraction

```powershell
$env:OMP_NUM_THREADS="2"
$env:OPENBLAS_NUM_THREADS="2"
retainiq sample --raw data/raw --output data/sample --buckets 5 --modulus 1000
retainiq ingest --raw data/sample --database data/kkbox-sample.duckdb --quarantine-invalid-logs
retainiq build --database data/kkbox-sample.duckdb --cutoffs 2016-07-01 2016-10-01 2017-01-01 --observation-end 2017-03-31 --output data/kkbox-features.parquet
retainiq audit --database data/kkbox-sample.duckdb --cutoffs 2016-07-01 2016-10-01 2017-01-01 --observation-end 2017-03-31 --official-labels data/raw/train.csv --output artifacts/kkbox-sample/data-audit.json
retainiq train --features data/kkbox-features.parquet --output artifacts/kkbox-sample --audit artifacts/kkbox-sample/data-audit.json
$env:RETAINIQ_ARTIFACTS="artifacts/kkbox-sample"
$env:RETAINIQ_MODEL="artifacts/kkbox-sample/model.joblib"
streamlit run src/retainiq/dashboard.py
```

Set the same model environment variable in the API terminal before starting uvicorn. Docker execution, hosted deployment, GitHub publishing, full-population training and official-label reconstruction remain outside this verified run.
