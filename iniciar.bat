@echo off
cd /d "%~dp0"
if not exist runtime\python\python.exe (
  echo Execute instalar.bat primeiro.
  pause
  exit /b 1
)
set PYTHONUTF8=1
runtime\python\python.exe -X utf8 server.py
pause
