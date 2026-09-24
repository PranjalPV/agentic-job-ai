# Starts the website on http://localhost:5173
# Run from anywhere:  .\start-frontend.ps1

$ErrorActionPreference = "Stop"

$frontend = Join-Path $PSScriptRoot "supabase-react"

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "Installing frontend packages (first run only)..." -ForegroundColor Yellow
    Set-Location $frontend
    npm install
}

if (-not (Test-Path (Join-Path $frontend ".env.local"))) {
    Write-Host "supabase-react\.env.local is missing. Copy .env.example to .env.local and fill it in." -ForegroundColor Red
    exit 1
}

Write-Host "Starting website on http://localhost:5173" -ForegroundColor Green
Write-Host "The API must be running too (.\start-backend.ps1 in another terminal)." -ForegroundColor DarkGray
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray

Set-Location $frontend
npm run dev
