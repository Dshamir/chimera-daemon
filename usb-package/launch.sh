#!/bin/bash
# CHIMERA USB Excavator Launcher (Linux/Mac)
# Run with sudo for full drive access

echo ""
echo "   CHIMERA USB EXCAVATOR"
echo "   ======================"
echo ""

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found!"
    echo "Please install Python 3.10+"
    exit 1
fi

# Check Python version
python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "ERROR: Python 3.10+ required!"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo "Note: Run with sudo for full drive access"
    echo ""
fi

# Run excavator
cd "$SCRIPT_DIR"
python3 -m chimera.usb.excavator
