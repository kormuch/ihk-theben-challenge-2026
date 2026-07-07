@echo off
title PAUL — Starting...
cd /d "%~dp0"

echo.
echo  ====================================
echo   PAUL — Product Attribute Unified Layer
echo  ====================================
echo.

REM ── Kill everything first ──
echo Stopping all previous containers...
cd /d "%~dp0product-layer"
docker compose down --remove-orphans >nul 2>&1
cd /d "%~dp0data-layer"
docker compose down --remove-orphans >nul 2>&1

REM ── Data Layer ──
echo.
echo [1/2] Starting data-layer...
cd /d "%~dp0data-layer"
docker compose up -d --build
if errorlevel 1 (
    echo ERROR: data-layer failed to start.
    pause
    exit /b 1
)

echo Waiting for backend...
:wait_data
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto wait_data
)
echo   backend OK

REM ── Product Layer ──
echo.
echo [2/2] Starting product-layer...
cd /d "%~dp0product-layer"
docker compose up -d --build
if errorlevel 1 (
    echo WARNING: product-layer failed. Continuing without it.
    goto open
)

echo Waiting for product-layer...
set /a tries=0
:wait_product
curl -s http://localhost:8080/health >nul 2>&1
if errorlevel 1 (
    set /a tries+=1
    if %tries% GEQ 30 (
        echo WARNING: product-layer timeout. Continuing without it.
        goto open
    )
    timeout /t 2 /nobreak >nul
    goto wait_product
)
echo   product-layer OK

:open
echo.
echo  ====================================
echo   ALL SERVICES RUNNING
echo  ====================================
echo.
echo   PAUL UI:           http://localhost:3000
echo   PAUL API:          http://localhost:8000/docs
echo   Product Layer:     http://localhost:8080
echo.

start http://localhost:3000
start http://localhost:8080

title PAUL — Live Logs
echo ==================== LIVE LOGS ====================
echo (Press Ctrl+C to stop)
echo.
cd /d "%~dp0data-layer"
docker compose logs -f
