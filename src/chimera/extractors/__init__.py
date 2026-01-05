"""CHIMERA content extractors.

Extractors handle different file types and extract:
- Text content
- Metadata
- Entities
- Embeddings
"""

from chimera.extractors.base import BaseExtractor, ExtractionResult
from chimera.extractors.registry import ExtractorRegistry, get_extractor

__all__ = ["BaseExtractor", "ExtractionResult", "ExtractorRegistry", "get_extractor"]
