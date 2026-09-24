@echo off
rem Starts the API on http://localhost:8000
setlocal
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
    echo No virtual environment found in backend\.venv
    echo Create it first:
    echo   uv venv --python 3.12 backend\.venv
    echo   uv pip install --python backend\.venv -r backend\requirements-dev.txt
    exit /b 1
)

if not exist ".env" (
    echo backend\.env is missing. Copy backend\.env.example to backend\.env and add your keys.
    exit /b 1
)

echo Starting API on http://localhost:8000   (health check: http://localhost:8000/health)
echo Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m uvicorn main:app --reload --port 8000
