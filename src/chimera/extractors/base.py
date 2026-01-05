"""Base extractor interface.

All extractors inherit from BaseExtractor and implement
the extract() method.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExtractionResult:
    """Result of content extraction."""
    file_path: Path
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    chunks: list[str] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    code_elements: list[dict[str, Any]] = field(default_factory=list)
    success: bool = True
    error: str | None = None
    
    # Stats
    word_count: int = 0
    page_count: int = 0
    language: str | None = None


class BaseExtractor(ABC):
    """Base class for content extractors."""
    
    # File extensions this extractor handles
    extensions: list[str] = []
    
    # MIME types this extractor handles
    mime_types: list[str] = []
    
    # Extractor name
    name: str = "base"
    
    @abstractmethod
    async def extract(self, file_path: Path) -> ExtractionResult:
        """Extract content from a file.
        
        Args:
            file_path: Path to the file to extract
            
        Returns:
            ExtractionResult with content and metadata
        """
        pass
    
    async def can_handle(self, file_path: Path) -> bool:
        """Check if this extractor can handle the given file.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if this extractor can process the file
        """
        ext = self.get_extension(file_path)
        return ext in self.extensions
    
    def get_extension(self, file_path: Path) -> str:
        """Get file extension without dot, lowercase."""
        return file_path.suffix.lstrip(".").lower()
    
    def count_words(self, text: str) -> int:
        """Count words in text."""
        return len(text.split())
