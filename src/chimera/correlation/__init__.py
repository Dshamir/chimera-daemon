"""CHIMERA Correlation Engine.

Analyzes extracted content to discover:
- Entity relationships
- Expertise patterns
- Workflow patterns
- Unknown knowns (discoveries)
"""

from chimera.correlation.engine import CorrelationEngine
from chimera.correlation.discovery import DiscoverySurfacer, Discovery
from chimera.correlation.entities import EntityConsolidator
from chimera.correlation.patterns import PatternDetector

__all__ = [
    "CorrelationEngine",
    "DiscoverySurfacer",
    "Discovery",
    "EntityConsolidator",
    "PatternDetector",
]
