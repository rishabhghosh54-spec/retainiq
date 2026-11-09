$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:OMP_NUM_THREADS = '2'
$env:OPENBLAS_NUM_THREADS = '2'
$env:RETAINIQ_ARTIFACTS = 'artifacts/reference'
$env:RETAINIQ_MODEL = 'artifacts/reference/model.joblib'
if (-not (Test-Path -LiteralPath 'artifacts/reference/report.json')) { throw 'Run the reference pipeline first; see docs/REFERENCE_RELEASE.md' }
python -m streamlit run src/retainiq/dashboard.py
