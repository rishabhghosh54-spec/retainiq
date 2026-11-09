$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:OMP_NUM_THREADS = '2'
$env:OPENBLAS_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
python -m retainiq.cli demo
if ($LASTEXITCODE -ne 0) { throw 'Demo training failed' }
python -m streamlit run src/retainiq/dashboard.py
