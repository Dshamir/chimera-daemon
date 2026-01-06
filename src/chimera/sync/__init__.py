"""CHIMERA Cross-Machine Sync Module.

Handles merging excavations from multiple machines into a unified catalog.
"""

from chimera.sync.merger import CatalogMerger, MergeResult
from chimera.sync.discovery import CrossMachineDiscovery

__all__ = ["CatalogMerger", "MergeResult", "CrossMachineDiscovery"]
