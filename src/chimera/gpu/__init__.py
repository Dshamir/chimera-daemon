"""CHIMERA GPU Acceleration Module.

Provides CUDA-accelerated operations for:
- Vector similarity search (FAISS-GPU)
- Correlation computation (cuML)
- Embedding generation (when supported)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Check for GPU availability
GPU_AVAILABLE = False
CUDA_VERSION = None
GPU_NAME = None
GPU_MEMORY = None

try:
    import torch
    if torch.cuda.is_available():
        GPU_AVAILABLE = True
        CUDA_VERSION = torch.version.cuda
        GPU_NAME = torch.cuda.get_device_name(0)
        GPU_MEMORY = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # GB
        logger.info(f"GPU detected: {GPU_NAME} ({GPU_MEMORY:.1f}GB) CUDA {CUDA_VERSION}")
except ImportError:
    pass

# Try FAISS-GPU
FAISS_GPU_AVAILABLE = False
try:
    import faiss
    if hasattr(faiss, 'StandardGpuResources'):
        FAISS_GPU_AVAILABLE = True
        logger.info("FAISS-GPU available")
except ImportError:
    pass

# Try cuML
CUML_AVAILABLE = False
try:
    import cuml
    CUML_AVAILABLE = True
    logger.info("cuML available")
except ImportError:
    pass


def get_gpu_info() -> dict:
    """Get GPU information."""
    return {
        "available": GPU_AVAILABLE,
        "cuda_version": CUDA_VERSION,
        "name": GPU_NAME,
        "memory_gb": GPU_MEMORY,
        "faiss_gpu": FAISS_GPU_AVAILABLE,
        "cuml": CUML_AVAILABLE,
    }


def ensure_gpu():
    """Raise error if GPU not available."""
    if not GPU_AVAILABLE:
        raise RuntimeError(
            "GPU not available. Install PyTorch with CUDA support:\n"
            "pip install torch --index-url https://download.pytorch.org/whl/cu121"
        )
