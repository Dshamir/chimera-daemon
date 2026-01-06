# CHIMERA Unified Launcher for Windows
# Usage: .\chimera.ps1

$ErrorActionPreference = "Stop"

$CHIMERA_DIR = $PSScriptRoot
if (-not $CHIMERA_DIR) { $CHIMERA_DIR = Get-Location }

$VENV_PATH = Join-Path $CHIMERA_DIR "venv"
$ACTIVATE_SCRIPT = Join-Path $VENV_PATH "Scripts\Activate.ps1"

# Check venv exists
if (-not (Test-Path $ACTIVATE_SCRIPT)) {
    Write-Host "[ERROR] Virtual environment not found at $VENV_PATH" -ForegroundColor Red
    Write-Host "Run: python -m venv venv && .\venv\Scripts\Activate.ps1 && pip install -e '.[dev]'" -ForegroundColor Yellow
    exit 1
}

# Activate and launch
& $ACTIVATE_SCRIPT
python -m chimera.shell
