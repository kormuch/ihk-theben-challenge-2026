@echo off
title PAUL — Starting...
cd /d "%~dp0"

echo.
echo  ====================================
echo   PAUL — Product Attribute Unified Layer
echo  ====================================
echo.

REM ── Data Layer (PostgreSQL + FastAPI + React) ──
echo [1/2] Starting data-layer...
cd /d "%~dp0data-layer"
docker compose up -d --build
if errorlevel 1 (
    echo ERROR: data-layer failed to start.
    pause
    exit /b 1
)

echo Waiting for data-layer backend...
:wait_data
curl -s http://localhost:8000/health | find "ok" >nul 2>&1
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto wait_data
)
echo   data-layer OK (http://localhost:3000)

REM ── Product Layer (Christian's governance layer) ──
echo.
echo [2/2] Starting product-layer...
cd /d "%~dp0product-layer"
docker compose up -d --build product-layer
if errorlevel 1 (
    echo WARNING: product-layer failed to start. Continuing without it.
    goto open
)

echo Waiting for product-layer...
:wait_product
curl -s http://localhost:8080/health | find "ok" >nul 2>&1
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto wait_product
)
echo   product-layer OK (http://localhost:8080)

:open
echo.
echo  ====================================
echo   ALL SERVICES RUNNING
echo  ====================================
echo.
echo   PAUL UI:          http://localhost:3000
echo   PAUL API:         http://localhost:8000/docs
echo   Product Layer:    http://localhost:8080
echo   Product Layer API: http://localhost:8080/docs
echo.

start "" http://localhost:3000

title PAUL — Live Logs
echo ==================== LIVE LOGS ====================
echo (Press Ctrl+C to stop viewing logs)
echo.
cd /d "%~dp0data-layer"
docker compose logs -f
