# Runs the backend test suite (no API keys or internet needed)
# Run from anywhere:  .\run-tests.ps1

$ErrorActionPreference = "Stop"

$backend = Join-Path $PSScriptRoot "backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "No virtual environment found in backend\.venv" -ForegroundColor Red
    exit 1
}

Set-Location $backend
& $python -m pytest
