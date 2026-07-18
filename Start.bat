@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Virtual env not found. Run: python -m venv .venv
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "main.py"
