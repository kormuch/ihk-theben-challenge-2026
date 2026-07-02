@echo off
title PAUL — Starting...
cd /d "%~dp0data-layer"

echo Starting PAUL...
docker compose up -d --build

echo Waiting for backend...
:wait
curl -s http://localhost:8000/health | find "ok" >nul 2>&1
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto wait
)

echo Opening browser...
start "" http://localhost:3000

title PAUL — Live Logs
echo.
echo ==================== PAUL LIVE LOGS ====================
docker compose logs -f
