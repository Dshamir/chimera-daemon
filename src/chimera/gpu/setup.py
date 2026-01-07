"""GPU setup utilities.

Helps users configure GPU acceleration for CHIMERA.
"""

import subprocess
import sys
from typing import Optional


def check_nvidia_driver() -> Optional[str]:
    """Check if NVIDIA driver is installed."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def check_cuda_version() -> Optional[str]:
    """Check CUDA version."""
    try:
        result = subprocess.run(
            ["nvcc", "--version"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            # Parse version from output
            for line in result.stdout.split("\n"):
                if "release" in line.lower():
                    parts = line.split("release")
                    if len(parts) > 1:
                        version = parts[1].split(",")[0].strip()
                        return version
    except FileNotFoundError:
        pass
    return None


def install_gpu_packages(cuda_version: str = "12.1"):
    """Install GPU-accelerated packages."""
    print(f"Installing GPU packages for CUDA {cuda_version}...")
    
    packages = [
        f"torch --index-url https://download.pytorch.org/whl/cu{cuda_version.replace('.', '')}",
        "faiss-gpu",
    ]
    
    for pkg in packages:
        print(f"Installing {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + pkg.split())
    
    # cuML requires conda or special handling
    print("\nNote: For cuML (GPU-accelerated ML), use conda:")
    print("  conda install -c rapidsai -c conda-forge -c nvidia cuml")


def setup_gpu():
    """Interactive GPU setup."""
    print("CHIMERA GPU Setup")
    print("=" * 40)
    
    # Check driver
    driver = check_nvidia_driver()
    if driver:
        print(f"✓ NVIDIA Driver: {driver}")
    else:
        print("✗ NVIDIA Driver not found")
        print("  Install from: https://www.nvidia.com/drivers")
        return
    
    # Check CUDA
    cuda = check_cuda_version()
    if cuda:
        print(f"✓ CUDA: {cuda}")
    else:
        print("✗ CUDA toolkit not found (nvcc)")
        print("  Install from: https://developer.nvidia.com/cuda-downloads")
    
    # Check PyTorch
    try:
        import torch
        if torch.cuda.is_available():
            print(f"✓ PyTorch CUDA: {torch.version.cuda}")
            print(f"  Device: {torch.cuda.get_device_name(0)}")
        else:
            print("✗ PyTorch installed but CUDA not available")
    except ImportError:
        print("✗ PyTorch not installed")
    
    # Check FAISS
    try:
        import faiss
        if hasattr(faiss, 'StandardGpuResources'):
            print("✓ FAISS-GPU available")
        else:
            print("○ FAISS-CPU only (install faiss-gpu for acceleration)")
    except ImportError:
        print("✗ FAISS not installed")
    
    # Check cuML
    try:
        import cuml
        print("✓ cuML available")
    except ImportError:
        print("○ cuML not installed (optional, for advanced ML)")
    
    print("\n" + "=" * 40)
    print("To install GPU packages:")
    print("  python -m chimera.gpu.setup install")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "install":
        cuda = sys.argv[2] if len(sys.argv) > 2 else "12.1"
        install_gpu_packages(cuda)
    else:
        setup_gpu()
