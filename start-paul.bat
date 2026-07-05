@echo off
title PAUL — Starting...
cd /d "%~dp0"

echo.
echo  ====================================
echo   PAUL — Product Attribute Unified Layer
echo   Lakehouse Edition (Iceberg + Trino + OpenMetadata)
echo  ====================================
echo.

REM ── Data Layer (PostgreSQL + FastAPI + React + Lakehouse) ──
echo [1/2] Starting data-layer (incl. MinIO, Iceberg, Trino, OpenMetadata)...
cd /d "%~dp0data-layer"
docker compose --profile openmetadata up -d --build
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

echo Waiting for Trino...
:wait_trino
curl -s http://localhost:8082/v1/info | find "ACTIVE" >nul 2>&1
if errorlevel 1 (
    timeout /t 3 /nobreak >nul
    goto wait_trino
)
echo   Trino OK (http://localhost:8082)

echo Waiting for OpenMetadata (takes ~60s on first start)...
:wait_om
curl -s http://localhost:8585/api/v1/system/version | find "version" >nul 2>&1
if errorlevel 1 (
    timeout /t 5 /nobreak >nul
    goto wait_om
)
echo   OpenMetadata OK (http://localhost:8585)

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
echo   PAUL UI:           http://localhost:3000
echo   PAUL API:          http://localhost:8000/docs
echo   Product Layer:     http://localhost:8080
echo   Trino UI:          http://localhost:8082
echo   MinIO Console:     http://localhost:9001  (admin / password)
echo   OpenMetadata:      http://localhost:8585  (admin / admin)
echo   Lakehouse Health:  http://localhost:8000/api/v1/lakehouse/health
echo   Iceberg Products:  http://localhost:8000/api/v1/lakehouse/products
echo.

start "" http://localhost:3000

title PAUL — Live Logs
echo ==================== LIVE LOGS ====================
echo (Press Ctrl+C to stop viewing logs)
echo.
cd /d "%~dp0data-layer"
docker compose --profile openmetadata logs -f
