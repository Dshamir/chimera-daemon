"""Extractor registry - maps file types to extractors."""

from pathlib import Path
from typing import Type

from chimera.extractors.base import BaseExtractor
from chimera.utils.logging import get_logger

logger = get_logger(__name__)


class ExtractorRegistry:
    """Registry of available extractors."""
    
    def __init__(self) -> None:
        self._extractors: dict[str, BaseExtractor] = {}
        self._extension_map: dict[str, str] = {}
        self._initialized = False
    
    def _ensure_initialized(self) -> None:
        """Lazy initialization of extractors."""
        if self._initialized:
            return
        
        # Import and register all extractors
        from chimera.extractors.document import (
            PDFExtractor,
            DOCXExtractor,
            MarkdownExtractor,
            TextExtractor,
            HTMLExtractor,
        )
        from chimera.extractors.code import (
            PythonExtractor,
            JavaScriptExtractor,
            YAMLExtractor,
            JSONExtractor,
        )
        from chimera.extractors.image import ImageExtractor
        from chimera.extractors.audio import AudioExtractor

        extractors = [
            PDFExtractor(),
            DOCXExtractor(),
            MarkdownExtractor(),
            TextExtractor(),
            HTMLExtractor(),
            PythonExtractor(),
            JavaScriptExtractor(),
            YAMLExtractor(),
            JSONExtractor(),
            ImageExtractor(),
            AudioExtractor(),
        ]
        
        for extractor in extractors:
            self.register(extractor)
        
        self._initialized = True
        logger.debug(f"Extractor registry initialized with {len(self._extractors)} extractors")
    
    def register(self, extractor: BaseExtractor) -> None:
        """Register an extractor."""
        self._extractors[extractor.name] = extractor
        
        for ext in extractor.extensions:
            self._extension_map[ext.lower()] = extractor.name
    
    def get_for_extension(self, extension: str) -> BaseExtractor | None:
        """Get extractor for file extension."""
        self._ensure_initialized()
        
        ext = extension.lower().lstrip(".")
        extractor_name = self._extension_map.get(ext)
        
        if extractor_name:
            return self._extractors.get(extractor_name)
        return None
    
    def get_for_file(self, file_path: Path) -> BaseExtractor | None:
        """Get extractor for a file."""
        ext = file_path.suffix.lstrip(".").lower()
        return self.get_for_extension(ext)
    
    def list_supported_extensions(self) -> list[str]:
        """List all supported file extensions."""
        self._ensure_initialized()
        return list(self._extension_map.keys())
    
    def list_extractors(self) -> list[str]:
        """List all registered extractors."""
        self._ensure_initialized()
        return list(self._extractors.keys())


# Global registry instance
_registry = ExtractorRegistry()


def get_extractor(file_path: Path) -> BaseExtractor | None:
    """Get the appropriate extractor for a file."""
    return _registry.get_for_file(file_path)


def get_registry() -> ExtractorRegistry:
    """Get the global extractor registry."""
    return _registry
