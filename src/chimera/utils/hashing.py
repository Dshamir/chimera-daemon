"""Hashing utilities for CHIMERA."""

import hashlib
from pathlib import Path


def hash_file(file_path: Path, algorithm: str = "sha256") -> str:
    """Calculate hash of a file.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (sha256, md5, sha1)
        
    Returns:
        Hex digest of the hash
    """
    hasher = hashlib.new(algorithm)
    
    with open(file_path, "rb") as f:
        # Read in chunks for large files
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    
    return hasher.hexdigest()


def hash_content(content: str | bytes, algorithm: str = "sha256") -> str:
    """Calculate hash of content.
    
    Args:
        content: String or bytes to hash
        algorithm: Hash algorithm
        
    Returns:
        Hex digest of the hash
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    
    hasher = hashlib.new(algorithm)
    hasher.update(content)
    return hasher.hexdigest()


def generate_id(prefix: str, content: str) -> str:
    """Generate a unique ID based on content.
    
    Args:
        prefix: ID prefix (e.g., 'file', 'conv', 'disc')
        content: Content to hash for uniqueness
        
    Returns:
        ID in format: prefix_shortHash
    """
    full_hash = hash_content(content)
    short_hash = full_hash[:12]
    return f"{prefix}_{short_hash}"
