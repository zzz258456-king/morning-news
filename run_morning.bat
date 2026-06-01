@REM ============================================
@REM 新闻晨报 — Windows 定时任务启动脚本
@REM 运行方式：双击 或 由计划任务调用
@REM ============================================
@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [%date% %time%] 新闻晨报系统启动...
set PYTHONIOENCODING=utf-8

:: 激活虚拟环境（如果有）
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

python run_morning.py >> morning_log.txt 2>&1

echo [%date% %time%] 执行完成 >> morning_log.txt
