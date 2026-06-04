@echo off
set "PYTHONUTF8=1"
set "CODEX_TRAFFIC_LIGHT_STATUS=D:\codex红绿灯提示灯\state\status.json"
cd /d "%~dp0"
start "" pythonw "%~dp0traffic_light_window.py"
