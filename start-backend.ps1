# Starts the API on http://localhost:8000
# Run from anywhere:  .\start-backend.ps1

$ErrorActionPreference = "Stop"

$backend = Join-Path $PSScriptRoot "backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "No virtual environment found in backend\.venv" -ForegroundColor Red
    Write-Host "Create it first:" -ForegroundColor Yellow
    Write-Host "  uv venv --python 3.12 backend\.venv"
    Write-Host "  uv pip install --python backend\.venv -r backend\requirements-dev.txt"
    exit 1
}

if (-not (Test-Path (Join-Path $backend ".env"))) {
    Write-Host "backend\.env is missing. Copy backend\.env.example to backend\.env and add your keys." -ForegroundColor Red
    exit 1
}

Write-Host "Starting API on http://localhost:8000  (health check: http://localhost:8000/health)" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray

Set-Location $backend
& $python -m uvicorn main:app --reload --port 8000
