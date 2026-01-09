@echo off
REM CHIMERA WSL Launcher
REM Runs CHIMERA commands through WSL with the WSL-specific venv
REM
REM Usage:
REM   chimera-wsl serve --dev
REM   chimera-wsl shell
REM   chimera-wsl status
REM   chimera-wsl dashboard

setlocal enabledelayedexpansion

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

REM Get project root (parent of scripts directory)
for %%I in ("%SCRIPT_DIR%\..") do set "PROJECT_ROOT=%%~fI"

REM Convert Windows path to WSL path
set "WSL_PROJECT_ROOT=%PROJECT_ROOT:\=/%"
set "WSL_PROJECT_ROOT=%WSL_PROJECT_ROOT:C:=/mnt/c%"
set "WSL_PROJECT_ROOT=%WSL_PROJECT_ROOT:D:=/mnt/d%"
set "WSL_PROJECT_ROOT=%WSL_PROJECT_ROOT:E:=/mnt/e%"
set "WSL_PROJECT_ROOT=%WSL_PROJECT_ROOT:F:=/mnt/f%"

REM Build the command with all arguments
set "CHIMERA_ARGS="
:args_loop
if "%~1"=="" goto args_done
set "CHIMERA_ARGS=%CHIMERA_ARGS% %1"
shift
goto args_loop
:args_done

REM Check if WSL venv exists
wsl -e test -d "%WSL_PROJECT_ROOT%/venv-wsl"
if errorlevel 1 (
    echo WSL environment not set up. Running setup...
    wsl -e bash -c "cd '%WSL_PROJECT_ROOT%' && chmod +x scripts/wsl-setup.sh && ./scripts/wsl-setup.sh"
)

REM Run chimera command in WSL
echo Running CHIMERA in WSL...
wsl -e bash -c "cd '%WSL_PROJECT_ROOT%' && source venv-wsl/bin/activate && chimera%CHIMERA_ARGS%"

endlocal
