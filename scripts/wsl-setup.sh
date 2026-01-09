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
