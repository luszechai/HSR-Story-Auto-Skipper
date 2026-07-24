@echo off
cd /d "%~dp0"

echo Installing verified runtime and build dependencies...
".venv\Scripts\python.exe" -m pip install -q -r requirements-lock.txt
if errorlevel 1 (
  echo Failed to install dependencies. Is .venv set up?
  pause
  exit /b 1
)

echo Building HSR Auto Skip.exe ...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean "HSR_Auto_Skip.spec"
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

set "OUT=dist\HSR Auto Skip"

echo.
echo Done. Open the app with:
echo   %OUT%\HSR Auto Skip.exe
echo.
explorer "%OUT%"
pause
