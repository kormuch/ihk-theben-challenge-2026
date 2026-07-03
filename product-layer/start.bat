@echo off
cd /d "%~dp0"
start "" /b cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8080"
python -m app.app --host 127.0.0.1 --port 8080
pause
