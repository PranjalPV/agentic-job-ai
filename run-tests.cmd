@echo off
rem Runs the backend test suite (no API keys or internet needed)
setlocal
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
    echo No virtual environment found in backend\.venv
    exit /b 1
)

".venv\Scripts\python.exe" -m pytest
