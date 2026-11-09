@echo off
setlocal
cd /d "%~dp0"
set "OMP_NUM_THREADS=2"
set "OPENBLAS_NUM_THREADS=2"
set "RETAINIQ_MODEL=artifacts/reference/model.joblib"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
set "RETAINIQ_PYTHON=python"
if exist "%USERPROFILE%\anaconda3\python.exe" set "RETAINIQ_PYTHON=%USERPROFILE%\anaconda3\python.exe"
if exist ".venv\Scripts\python.exe" set "RETAINIQ_PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "artifacts\reference\model.joblib" (
  echo The real-data model is missing. See README.md for the data pipeline.
  pause
  exit /b 1
)
"%RETAINIQ_PYTHON%" -c "import fastapi,uvicorn,duckdb,sklearn" >nul 2>&1
if errorlevel 1 (
  "%RETAINIQ_PYTHON%" -c "import sys; sys.exit(0 if sys.version_info[:2]==(3,14) else 1)" >nul 2>&1
  if not errorlevel 1 if exist "..\..\work\runtime\fastapi" set "PYTHONPATH=%CD%\..\..\work\runtime;%PYTHONPATH%"
)
"%RETAINIQ_PYTHON%" -c "import fastapi,uvicorn,duckdb,sklearn" >nul 2>&1
if errorlevel 1 (
  echo Required libraries are missing. Run: python -m pip install -e .
  pause
  exit /b 1
)
echo RetainIQ - local inference API
echo Open http://localhost:8000/docs after the server starts.
echo Keep this window open while reviewing. Press Ctrl+C to stop.
"%RETAINIQ_PYTHON%" -m uvicorn retainiq.api:app --host 127.0.0.1 --port 8000
if errorlevel 1 pause
endlocal
