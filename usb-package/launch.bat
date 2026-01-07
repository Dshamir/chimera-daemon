@echo off
REM CHIMERA USB Excavator Launcher (Windows)
REM Run as Administrator for full drive access

echo.
echo   CHIMERA USB EXCAVATOR
echo   ======================
echo.

REM Check for Python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found!
    echo Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

REM Check Python version
python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python 3.10+ required!
    pause
    exit /b 1
)

REM Get script directory
set SCRIPT_DIR=%~dp0

REM Run excavator
cd /d "%SCRIPT_DIR%"
python -m chimera.usb.excavator

pause
