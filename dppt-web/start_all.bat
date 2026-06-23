@echo off
chcp 65001 > nul
echo Starting DPPT Web...
echo.

REM Start backend
start "DPPT Backend" cmd /k "cd /d C:\Users\Administrator\Desktop\_Projects\try\dppt-web\backend && .venv\Scripts\python run.py"

REM Wait for backend (4 seconds)
ping -n 5 127.0.0.1 > nul

REM Start frontend
start "DPPT Frontend" cmd /k "cd /d C:\Users\Administrator\Desktop\_Projects\try\dppt-web\frontend && npm run dev"

REM Wait for frontend (6 seconds)
ping -n 7 127.0.0.1 > nul

REM Open browser
echo Opening browser...
start http://localhost:5173

echo.
echo DPPT Web started. Please visit http://localhost:5173