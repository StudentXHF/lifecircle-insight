@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"

echo [1/4] Preparing virtual environment...
if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>nul
    if %errorlevel%==0 (
        py -3.11 -m venv .venv 2>nul || py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Failed to create .venv. Please install Python 3.11+.
    pause
    exit /b 1
)

echo [2/4] Installing/updating dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

echo [3/4] Checking configuration...
if not exist ".env" (
    echo [NOTE] .env not found. Offline demo mode is still fully available.
    echo [NOTE] For real Baidu Map API analysis, copy .env.example to .env and fill BAIDU_MAP_AK.
)

echo [4/4] Starting LifeCircle Insight at http://127.0.0.1:8015
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8015
endlocal
