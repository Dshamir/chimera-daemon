"""Build portable USB package.

Creates a standalone USB-deployable excavator.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def build_usb_package(output_dir: Path):
    """Build complete USB package."""
    print("Building CHIMERA USB Package...")
    print("=" * 40)
    
    # Get project root
    project_root = Path(__file__).parent.parent.parent.parent
    
    # Create output structure
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy source files
    print("\nCopying source files...")
    src_dir = output_dir / "src" / "chimera"
    src_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy chimera package
    shutil.copytree(
        project_root / "src" / "chimera",
        src_dir,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git")
    )
    
    # Copy USB package files
    print("Copying launcher files...")
    usb_pkg_dir = project_root / "usb-package"
    if usb_pkg_dir.exists():
        for f in usb_pkg_dir.iterdir():
            if f.is_file():
                shutil.copy(f, output_dir)
    
    # Create __init__.py for src
    (output_dir / "src" / "__init__.py").touch()
    
    # Create excavations directory
    (output_dir / "excavations").mkdir(exist_ok=True)
    
    # Create requirements.txt
    requirements = [
        "rich>=13.0.0",
    ]
    
    with open(output_dir / "requirements.txt", "w") as f:
        f.write("\n".join(requirements))
    
    # Create simple runner script
    runner = '''
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from chimera.usb.excavator import main
main()
'''
    
    with open(output_dir / "run_excavator.py", "w") as f:
        f.write(runner.strip())
    
    print("\n" + "=" * 40)
    print(f"USB Package built: {output_dir}")
    print("\nTo use:")
    print("  1. Copy folder to USB drive")
    print("  2. Run launch.bat (Windows) or launch.sh (Linux/Mac)")
    print("  3. Or: python run_excavator.py")


def build_exe(output_dir: Path):
    """Build single-file executable with PyInstaller."""
    print("Building CHIMERA Executable...")
    print("=" * 40)
    
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    project_root = Path(__file__).parent.parent.parent.parent
    
    # PyInstaller spec
    subprocess.run([
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "chimera-excavator",
        "--distpath", str(output_dir),
        "--workpath", str(output_dir / "build"),
        "--specpath", str(output_dir),
        str(project_root / "src" / "chimera" / "usb" / "excavator.py"),
    ])
    
    print(f"\nExecutable built: {output_dir / 'chimera-excavator'}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build CHIMERA USB Package")
    parser.add_argument("output", help="Output directory")
    parser.add_argument("--exe", action="store_true", help="Build single executable")
    
    args = parser.parse_args()
    
    if args.exe:
        build_exe(Path(args.output))
    else:
        build_usb_package(Path(args.output))
