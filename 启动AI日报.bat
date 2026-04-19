@echo off
title AI 日报
cd /d "%~dp0"

REM 如果有虚拟环境则激活
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo 正在启动 AI 日报...
echo 浏览器访问: http://127.0.0.1:8080
echo 关闭此窗口即停止服务
echo.
python main.py
pause
