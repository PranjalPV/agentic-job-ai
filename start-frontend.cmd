@echo off
rem Starts the website on http://localhost:5173
setlocal
cd /d "%~dp0supabase-react"

if not exist ".env.local" (
    echo supabase-react\.env.local is missing. Copy .env.example to .env.local and fill it in.
    exit /b 1
)

if not exist "node_modules" (
    echo Installing frontend packages ^(first run only^)...
    call npm install
)

echo Starting website on http://localhost:5173
echo The API must be running too ^(start-backend.cmd in another terminal^).
echo Press Ctrl+C to stop.
call npm run dev
