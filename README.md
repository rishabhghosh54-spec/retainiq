# RetainIQ

**Subscription churn research with auditable labels, chronological evaluation, and a working decision dashboard.**

RetainIQ turns KKBOX transaction and listening histories into historical subscriber features, reconstructs cancellation-aware renewal outcomes, compares them with supplied labels, and serves a frozen churn model through Streamlit and FastAPI.

## Verified results, with their scope

| Evidence | Executed result |
|---|---|
| Full transaction audit | 22,978,755 source rows; 856,085 matched supplied February labels |
| Reference implementation check | SQL and independent Python agree on all 4,186 sampled February candidates |
| Full reconstruction/supplied-label agreement | 98.77%; 10,525 disagreements retained and reported |
| Modeling population | Deterministic 0.5% sample of transaction subscribers, with complete available histories |
| March supplied-label evaluation | 4,034 eligible matched subscribers; ROC-AUC 0.762; AP 0.309 |
| March log loss | 0.2132 versus frozen prevalence baseline 0.2273 |
| Review capacity | Highest-risk 10% captures 50% of supplied churn cases; lift 4.99x |

These are measured research results, not a Kaggle leaderboard score, full-population model result, causal retention effect, or production deployment. The supplied labels and reference reconstruction are distinct targets. The original extension-only proxy is superseded. Read [the current verified release](docs/REFERENCE_RELEASE.md) and [model card](docs/MODEL_CARD.md) before citing results.

## Quick start: no private data required

Python 3.11+; 3.12 recommended. The executed Windows environment used Python 3.14.6. Exact tested top-level package versions are recorded in `requirements-verified.txt` (an environment snapshot, not a complete dependency lock).

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
$env:OMP_NUM_THREADS="2"
$env:OPENBLAS_NUM_THREADS="2"
retainiq demo
streamlit run src/retainiq/dashboard.py
```

Open http://localhost:8501. Synthetic mode is visibly labeled and never substitutes synthetic results for real-data results. Windows shortcut after installation: `./run-demo.ps1`.

In a second activated terminal:

```powershell
uvicorn retainiq.api:app --host 127.0.0.1 --port 8000
```

Interactive API documentation: http://localhost:8000/docs. Example request to `POST /predict`:

```json
{"records":[{"days_to_expiry":10,"tenure_days":180,"transactions_90d":3,"paid_90d":447,"auto_renew":1,"active_days_30d":20,"seconds_30d":12000,"unique_songs_30d":150}]}
```

The API consumes point-in-time features, returns outcome-definition/provenance metadata, and rejects unknown fields, invalid flags, nonfinite values and batches above 1,000. It returns 503 without a model. Only load trusted locally trained joblib files.

## Real data

Acquire the original and v2 transaction/listening files plus supplied label files through your authorized [KKBOX competition account](https://www.kaggle.com/competitions/kkbox-churn-prediction-challenge/data). Keep credentials private. ZIP archives contain nested `.7z` archives; extract both layers to `data/raw`. Nested refresh folders are discovered automatically. Members and submission files are unused.

```powershell
# Optional: install Kaggle tooling and download after configuring credentials/accepting rules.
python -m pip install -e ".[data]"
retainiq access --raw data/raw
retainiq download --raw data/raw
# Extract ZIP and .7z archives, then:
retainiq sample --raw data/raw --output data/sample --buckets 5 --modulus 1000
retainiq ingest --raw data/sample --database data/kkbox-reference.duckdb --quarantine-invalid-logs
retainiq build --database data/kkbox-reference.duckdb --cutoffs 2016-07-01 2016-10-01 2017-01-01 --observation-end 2017-03-31 --output data/reference-features.parquet
retainiq audit --database data/kkbox-reference.duckdb --cutoffs 2016-07-01 2016-10-01 2017-01-01 --observation-end 2017-03-31 --official-labels data/raw/train.csv --output artifacts/reference/data-audit.json
retainiq train --features data/reference-features.parquet --output artifacts/reference --audit artifacts/reference/data-audit.json
retainiq evaluate-official --database data/kkbox-reference.duckdb --model artifacts/reference/model.joblib --labels data/raw/data/churn_comp_refresh/train_v2.csv --cutoff 2017-03-01 --observation-end 2017-03-31 --output artifacts/reference/official-evaluation.json
```

Adjust the supplied-label path to your actual extraction layout. `--observation-end` attests a complete transaction observation date; a maximum event timestamp alone does not prove completeness. Cutoffs are timezone-free first-of-month calendar dates. These dates were checked against the supplied files; do not reuse them for a different dataset without auditing coverage.

For the separate full-population **transaction label audit**, not full-population model training:

```powershell
retainiq validate-reference --raw data/raw --database data/full-transactions.duckdb --official-labels data/raw/train.csv --output artifacts/reference/full-label-audit.json
```

Launch the real dashboard with `./run-real.ps1`, or set `RETAINIQ_ARTIFACTS=artifacts/reference`. For API inference set `RETAINIQ_MODEL=artifacts/reference/model.joblib` before starting uvicorn. Models load at startup; restart after changing artifacts.

On Windows you can instead double-click **Start-RetainIQ.cmd** in the existing project folder, or **Start-RetainIQ-API.cmd** for the API. These check dependencies, use the current real model, and stay on localhost. See [the dashboard review instructions](docs/DASHBOARD_REVIEW.md) for the demonstration flow and verified queue sizes. Trained artifacts are already present on the build machine but are intentionally excluded from the source ZIP.

## The temporal and label contract

At month-start T, the reference cohort requires a transaction in the preceding calendar month and a reference-ordered latest expiry inside the prediction month. History includes cancellations rather than treating a cancellation flag as churn. Ordering reproduces the supplied Scala code: event date ascending, concatenated decimal plan-price/plan-days/payment-method signature descending **lexicographically**, subscription before cancellation, then ascending renewal expiries or descending cancellation expiries. Exact reference ties use the minimum known auto-renew flag for features; that is a deterministic convention, not a claim of true event order.

Future cancellations shorten the relevant expiry until the first subsequent noncancel subscription. A gap **less than 30 days** is retained; a gap of 30 or more days is churn. No subscription by the fully observed deadline is churn. Historical labels are included only when the original recorded expiry plus 30 days is fully observed, even if a renewal occurred early. The original `legacy` extension-only target remains explicit opt-in for historical reproducibility; mixed label methods are rejected in training.

Features use events strictly before T: 30-day listening, 90-day payment history, observed tenure, expiry proximity and auto-renew state. IDs and supplied labels never enter model features. Sum of daily unique-song counts is not month-wide distinct songs. Missing logs are encoded as zero, with completeness limitations documented. Invalid negative or >=1e12-second durations can be quarantined, preserving original values; affected users become ineligible only after the invalid event. Less extreme positive outliers remain unresolved.

Training/validation/test cutoffs are July 2016, October 2016 and January 2017, with outcome-maturity embargoes. Validation alone selects prevalence baseline, logistic regression or histogram gradient boosting. The frozen winner is then tested. January is a revised retrospective backtest, because an earlier proxy version had already been inspected. March uses separately supplied labels after model freezing; no April transaction history is needed to **evaluate supplied labels**, but its absence prevents independently reconstructing all March outcomes.

## Architecture

```text
Authorized CSVs -> source hashes + daily coverage -> deterministic whole-user sample
 -> validated DuckDB tables + quarantine -> reference ordering/gap SQL + historical features
 -> Parquet -> chronological candidate models -> frozen model + JSON reports
 -> separate supplied-label evaluation -> Streamlit and FastAPI
```

Ingestion and SQL aggregation use disk-backed DuckDB; aggregate training data fits memory. This is not distributed training. The executed model experiment uses a subscriber sample; the source scan and transaction-label audit cover full source files. Keep extracted data, databases, trained binaries and subscriber-level scores out of GitHub. Only aggregate reports are included under `examples/`.

## Verification and packaging

```powershell
pytest -q
docker compose up --build
```

CI is configured for Python 3.12 on Linux, including synthetic training. Docker runs non-root with read-only artifact mounts and localhost ports. GitHub Actions on Linux passed all 34 tests and synthetic training. The public-demo Docker image also built, generated its synthetic experiment, started, and passed its health probe in [CI run 42643413362](https://github.com/rishabhghosh54-spec/retainiq/actions/runs/42643413362). The local Windows environment blocks asyncio's socket-pair setup, so two HTTP transport tests cannot run here; core inference, schema validation, model parity and dashboards were checked separately. CI retains the HTTP tests for a normal networking environment.

The real dashboard shows reference backtests, supplied-label results, review queues, calibration and evidence. Offer effects require a randomized retention experiment. A production real-data service would additionally require authentication, TLS and operational monitoring. The hosted demo below is synthetic only.

The user-started local dashboard has also been reviewed in a live browser: all four tabs, March metrics, cohort selection and the capacity slider were checked. See [the live aggregate-results screenshot](docs/screenshots/live-march-evaluation.png) and [review record](docs/DASHBOARD_REVIEW.md). The live API subsequently passed seven health/prediction/validation/batch-boundary checks, with exact offline-model prediction parity; see [the API review](docs/API_REVIEW.md). The synthetic public dashboard is deployed and browser-verified; local Docker Desktop remains unverified.

For public hosting, use the separate **synthetic-only** `streamlit_app.py` entrypoint with the root `requirements.txt`. It does not read the real-data artifact path. `Dockerfile.demo` and a Docker CI job are also prepared. See [deployment instructions and current verification limits](docs/DEPLOYMENT.md). Source is published at [rishabhghosh54-spec/retainiq](https://github.com/rishabhghosh54-spec/retainiq). The [live public demo](https://retainiq-rishabh.streamlit.app/) is deployed and browser-verified; it uses synthetic data only.

[Current evidence](docs/REFERENCE_RELEASE.md) · [Data card](docs/DATA_CARD.md) · [Model card](docs/MODEL_CARD.md) · [Interview preparation](docs/INTERVIEW.md) · [Earlier pilot, superseded](docs/REAL_DATA_RUN.md)
