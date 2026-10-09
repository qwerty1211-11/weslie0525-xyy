@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "" pythonw "校园跑自动刷步数程序.py"
if errorlevel 1 (
    echo.
    echo 启动失败, 尝试用 python 启动...
    python "校园跑自动刷步数程序.py"
    pause
)