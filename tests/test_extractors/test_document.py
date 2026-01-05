"""Tests for document extractors."""

import pytest

from chimera.extractors.document import (
    MarkdownExtractor,
    TextExtractor,
)


@pytest.mark.asyncio
async def test_text_extractor(sample_text_file):
    """Test text file extraction."""
    extractor = TextExtractor()
    
    assert await extractor.can_handle(sample_text_file)
    
    result = await extractor.extract(sample_text_file)
    
    assert result.success
    assert "Hello, CHIMERA" in result.content
    assert result.metadata["format"] == "text"


@pytest.mark.asyncio
async def test_markdown_extractor(temp_dir):
    """Test markdown file extraction."""
    md_file = temp_dir / "test.md"
    md_file.write_text("# Title\n\nSome content.")
    
    extractor = MarkdownExtractor()
    
    assert await extractor.can_handle(md_file)
    
    result = await extractor.extract(md_file)
    
    assert result.success
    assert "# Title" in result.content
    assert result.metadata["format"] == "markdown"
