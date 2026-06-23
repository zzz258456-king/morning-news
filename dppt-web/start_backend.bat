@echo off
chcp 65001 > nul
echo 启动 DPPT Web 后端...
cd /d "C:\Users\Administrator\Desktop\_Projects\try\dppt-web\backend"
.venv\Scripts\python run.py
