@echo off
setlocal
cd /d "%~dp0"
set "OMP_NUM_THREADS=2"
set "OPENBLAS_NUM_THREADS=2"
set "RETAINIQ_ARTIFACTS=artifacts/reference"
set "RETAINIQ_MODEL=artifacts/reference/model.joblib"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
set "RETAINIQ_PYTHON=python"
if exist "%USERPROFILE%\anaconda3\python.exe" set "RETAINIQ_PYTHON=%USERPROFILE%\anaconda3\python.exe"
if exist ".venv\Scripts\python.exe" set "RETAINIQ_PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "artifacts\reference\report.json" (
  echo The real-data model is missing. See README.md for the data pipeline.
  pause
  exit /b 1
)
"%RETAINIQ_PYTHON%" -c "import pandas,streamlit" >nul 2>&1
if errorlevel 1 (
  "%RETAINIQ_PYTHON%" -c "import sys; sys.exit(0 if sys.version_info[:2]==(3,14) else 1)" >nul 2>&1
  if not errorlevel 1 if exist "..\..\work\runtime\streamlit" set "PYTHONPATH=%CD%\..\..\work\runtime;%PYTHONPATH%"
)
"%RETAINIQ_PYTHON%" -c "import pandas,streamlit" >nul 2>&1
if errorlevel 1 (
  echo Required libraries are missing. Run: python -m pip install -e .
  pause
  exit /b 1
)
echo RetainIQ - real-data dashboard
echo The browser should open after the server starts.
echo If needed, open http://localhost:8501 yourself.
echo Keep this window open while reviewing. Press Ctrl+C to stop.
"%RETAINIQ_PYTHON%" -m streamlit run src/retainiq/dashboard.py --server.address=127.0.0.1 --server.headless=false --browser.gatherUsageStats=false
if errorlevel 1 pause
endlocal
