#!/bin/bash
# CHIMERA WSL Setup Script
# Creates and configures a WSL-specific Python environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo ""
echo "  ██████╗██╗  ██╗██╗███╗   ███╗███████╗██████╗  █████╗"
echo " ██╔════╝██║  ██║██║████╗ ████║██╔════╝██╔══██╗██╔══██╗"
echo " ██║     ███████║██║██╔████╔██║█████╗  ██████╔╝███████║"
echo " ██║     ██╔══██║██║██║╚██╔╝██║██╔══╝  ██╔══██╗██╔══██║"
echo " ╚██████╗██║  ██║██║██║ ╚═╝ ██║███████╗██║  ██║██║  ██║"
echo "  ╚═════╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝"
echo ""
echo "  WSL Environment Setup"
echo ""

cd "$PROJECT_ROOT"
echo "[1/5] Project root: $PROJECT_ROOT"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "[2/5] Python version: $PYTHON_VERSION"

if [[ $(echo "$PYTHON_VERSION < 3.10" | bc -l) -eq 1 ]]; then
    echo "ERROR: Python 3.10+ required, found $PYTHON_VERSION"
    exit 1
fi

# Create venv if it doesn't exist
VENV_DIR="$PROJECT_ROOT/venv-wsl"
if [ -d "$VENV_DIR" ]; then
    echo "[3/5] WSL venv exists at: $VENV_DIR"
else
    echo "[3/5] Creating WSL venv at: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

# Activate venv
echo "[4/5] Activating venv..."
source "$VENV_DIR/bin/activate"

# Install dependencies
echo "[5/5] Installing dependencies..."
pip install --upgrade pip -q
pip install -e ".[dev]" -q

echo ""
echo "Setup complete!"
echo ""

# Check for existing Windows data and create symlink
WINDOWS_USER=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')
WINDOWS_DATA="/mnt/c/Users/$WINDOWS_USER/.chimera"

if [ -d "$WINDOWS_DATA" ]; then
    WINDOWS_SIZE=$(du -s "$WINDOWS_DATA" 2>/dev/null | cut -f1 || echo "0")

    if [ -L "$HOME/.chimera" ]; then
        # Already a symlink
        echo "[*] Symlink already exists: ~/.chimera -> $(readlink $HOME/.chimera)"
        echo ""
    elif [ -d "$HOME/.chimera" ]; then
        # Directory exists - check if it's small/empty compared to Windows
        WSL_SIZE=$(du -s "$HOME/.chimera" 2>/dev/null | cut -f1 || echo "0")

        # If Windows data is > 100MB and WSL is < 10MB, offer to replace
        if [ "$WINDOWS_SIZE" -gt 100000 ] && [ "$WSL_SIZE" -lt 10000 ]; then
            echo "[!] Found large Windows data ($(($WINDOWS_SIZE/1024))MB) but small WSL data ($(($WSL_SIZE/1024))MB)"
            echo "[*] Replacing WSL directory with symlink to Windows data..."
            rm -rf "$HOME/.chimera"
            ln -s "$WINDOWS_DATA" "$HOME/.chimera"
            echo "[*] Symlink created! Your Windows data will be used."
            echo ""
        else
            echo "[*] Using existing WSL data at: ~/.chimera"
            echo "[*] Windows data also exists at: $WINDOWS_DATA"
            echo "[*] To use Windows data instead, run:"
            echo "      rm -rf ~/.chimera && ln -s $WINDOWS_DATA ~/.chimera"
            echo ""
        fi
    elif [ ! -e "$HOME/.chimera" ]; then
        # Nothing exists - create symlink
        echo "[*] Found existing CHIMERA data at: $WINDOWS_DATA"
        echo "[*] Creating symlink: ~/.chimera -> $WINDOWS_DATA"
        ln -s "$WINDOWS_DATA" "$HOME/.chimera"
        echo "[*] Symlink created! Your existing data will be used."
        echo ""
    fi
else
    if [ -d "$HOME/.chimera" ]; then
        echo "[*] Using existing WSL data at: ~/.chimera"
    else
        echo "[*] No existing data found. Fresh installation."
        echo "[*] Data will be stored at: ~/.chimera"
    fi
    echo ""
fi

echo "To activate the environment:"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "To start CHIMERA daemon:"
echo "  chimera serve --dev"
echo ""
echo "To start CHIMERA shell:"
echo "  chimera shell"
echo ""

# Download spaCy model if not present
if ! python -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null; then
    echo "Downloading spaCy model..."
    python -m spacy download en_core_web_sm -q
fi

echo "All dependencies ready!"
