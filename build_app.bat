@echo off
cd /d "%~dp0"

echo Installing PyInstaller...
".venv\Scripts\python.exe" -m pip install -q pyinstaller
if errorlevel 1 (
  echo Failed to install PyInstaller. Is .venv set up?
  pause
  exit /b 1
)

echo Building HSR Auto Skip.exe ...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm "HSR_Auto_Skip.spec"
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

REM Ensure writable assets/config sit next to the .exe (not only in _internal)
set "OUT=dist\HSR Auto Skip"
if not exist "%OUT%\assets" (
  xcopy /E /I /Y "assets" "%OUT%\assets" >nul
)
if not exist "%OUT%\config.json" (
  copy /Y "config.json" "%OUT%\config.json" >nul
)

echo.
echo Done. Open the app with:
echo   %OUT%\HSR Auto Skip.exe
echo.
explorer "%OUT%"
pause
