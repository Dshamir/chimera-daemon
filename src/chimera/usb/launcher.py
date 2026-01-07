"""Cross-platform launcher for USB excavator."""

import os
import platform
import subprocess
import sys
from pathlib import Path


def get_python():
    """Find Python executable."""
    # Check if we have bundled Python
    usb_root = Path(__file__).parent.parent.parent.parent
    
    if platform.system() == "Windows":
        bundled = usb_root / "python" / "python.exe"
        if bundled.exists():
            return str(bundled)
    else:
        bundled = usb_root / "python" / "bin" / "python3"
        if bundled.exists():
            return str(bundled)
    
    # Use system Python
    return sys.executable


def check_dependencies():
    """Check and install required packages."""
    required = ["rich"]
    
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            print(f"Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])


def main():
    """Launch the excavator."""
    print("CHIMERA USB Excavator")
    print("=" * 40)
    
    # Check Python version
    if sys.version_info < (3, 10):
        print(f"Error: Python 3.10+ required (found {sys.version})")
        input("Press Enter to exit...")
        sys.exit(1)
    
    # Check dependencies
    check_dependencies()
    
    # Launch excavator
    from chimera.usb.excavator import main as excavator_main
    excavator_main()


if __name__ == "__main__":
    main()
