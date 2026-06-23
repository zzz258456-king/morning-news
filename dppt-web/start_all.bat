@echo off
chcp 65001 > nul
echo 正在启动 DPPT Web ...
echo.

REM 启动后端（新窗口）
start "DPPT Web 后端" cmd /k "cd /d C:\Users\Administrator\Desktop\_Projects\try\dppt-web\backend && .venv\Scripts\python run.py"

REM 等待后端启动
timeout /t 4 /nobreak > nul

REM 启动前端（新窗口）
start "DPPT Web 前端" cmd /k "cd /d C:\Users\Administrator\Desktop\_Projects\try\dppt-web\frontend && npm run dev"

REM 等待前端启动
timeout /t 6 /nobreak > nul

REM 打开浏览器
echo 正在打开浏览器...
start http://localhost:5173

echo.
echo DPPT Web 已启动，请使用浏览器访问 http://localhost:5173
