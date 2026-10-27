@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment. Make sure Python 3.10+ is installed and on PATH.
        pause
        exit /b 1
    )
)

echo [2/3] Installing/checking dependencies...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo [3/3] Starting Housing Redevelopment DSS...
".venv\Scripts\python.exe" -m streamlit run app.py

pause
