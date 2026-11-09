# Verified build record — 2026-11-08

This is the initial synthetic build record. The current 0.2 reference-label implementation, full transaction audit, independent oracle and separate supplied-label evaluation are documented in [the current release record](REFERENCE_RELEASE.md). The earlier [extension-only pilot](REAL_DATA_RUN.md) is retained as superseded history.

## Executed successfully

- Deterministic synthetic raw-data generation: 600 subscribers per snapshot, three snapshots, 1,800 labeled feature rows total.
- Chunked CSV ingestion into DuckDB with file hashing and duplicate/conflict reporting.
- Point-in-time SQL feature/label generation and chronological training, model serialization, held-out scores, JSON metrics, bootstrap intervals, and permutation importance.
- Separate CLI `build` route against synthetic database: 600 matured rows per cutoff, no censored rows in this fixture; audit JSON produced.
- Python wheel packaging (`retainiq-0.1.0-py3-none-any.whl`).
- Final automated suite: **9 passed, 1 warning in 17.04 seconds**. This runtime is for small synthetic tests, not KKBOX processing.

Tests cover future-event feature invariance (including future conflicting revisions), exact cutoff exclusion, censoring, malformed values, conflicting pre-cutoff transaction exclusion, inclusive renewal deadline, duplicate removal and failed-import rollback, chronological embargo rejection, API/offline prediction parity, invalid API requests, missing model behavior, dashboard rendering, synthetic disclosure, and review-capacity interaction.

The warning is a Starlette deprecation notice about using the installed httpx test client. Tests pass; a future dependency update may require adapting that test client. Windows restricted execution blocked temporary files and stalled the in-process API check; the final suite passed with normal process access. Training was limited to two OpenMP/BLAS threads in the final run. No system-wide library installation was needed: missing packages were downloaded into the workspace runtime.

`examples/synthetic-report.json` contains actual metrics from the executed demo. They demonstrate functionality only. The dashboard marks them SYNTHETIC and the API returns synthetic provenance. The exact verified top-level library versions are in `requirements-verified.txt`; this machine used Python 3.14.6. The recommended Python 3.12 and CI/Linux environments have not been executed here.

## Access inspection

The starting workspace contained only empty work/output folders. No KKBOX dataset or Kaggle credentials were supplied. The access command confirmed no raw folder, Kaggle CLI, credential file, or credential environment variables. Kaggle authorization was therefore **not verified**, and no competition files were downloaded.

Connected GitHub inspection succeeded and found existing portfolio repositories under rishabhghosh54-spec, including wealth-management-portfolio-analytics and financial-data-quality-reporting. Searching connected repositories for RetainIQ returned none. The deliverable is a new local Git repository; no remote repository was created and no existing repository was changed.

## Not verified / remaining gates

- Real KKBOX ingestion, schema compatibility, source completeness, revision adjudication, cohort sizes, and official label agreement.
- Real chronological model performance, calibration, segment reliability, or business outcomes.
- Full-data memory/disk/CPU requirements. Only raw ingestion is chunked; aggregate training data must fit memory.
- Docker execution: Docker is not installed on the build machine.
- GitHub Actions execution, public hosting, TLS/authentication, or deployed service behavior. Configuration is provided, not deployed infrastructure.

To resume real-data work, obtain authorized original/v2 transaction and listening history, inspect the generated manifest, attest a complete observation end date, and choose three supported cutoffs with sufficient maturity gaps. If available data cannot support that design, document the reduced scope rather than claim a random split is out-of-time evaluation.
