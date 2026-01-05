#!/bin/bash
# CHIMERA Installation Script

set -e

echo "========================================"
echo "  CHIMERA Installation"
echo "========================================"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
if [[ "$PYTHON_VERSION" < "3.11" ]]; then
    echo "Error: Python 3.11+ required (found $PYTHON_VERSION)"
    exit 1
fi
echo "✓ Python $PYTHON_VERSION"

# Install from PyPI or source
if [[ -f "pyproject.toml" ]]; then
    echo "Installing from source..."
    pip install -e ".[dev]"
else
    echo "Installing from PyPI..."
    pip install chimera-daemon
fi
echo "✓ Package installed"

# Initialize config
echo "Initializing configuration..."
chimera init
echo "✓ Configuration initialized"

# Download spaCy model
echo "Downloading spaCy model..."
python -m spacy download en_core_web_sm
echo "✓ spaCy model installed"

# Install systemd service (optional)
if [[ -d "/etc/systemd/system" ]]; then
    read -p "Install systemd service? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo cp deploy/chimera.service /etc/systemd/system/chimera@.service
        sudo systemctl daemon-reload
        echo "✓ Systemd service installed"
        echo "  Enable with: sudo systemctl enable chimera@$USER"
        echo "  Start with:  sudo systemctl start chimera@$USER"
    fi
fi

echo ""
echo "========================================"
echo "  Installation Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Edit ~/.chimera/chimera.yaml"
echo "  2. Run: chimera serve"
echo "  3. Test: curl http://localhost:7777/api/v1/health"
echo ""
