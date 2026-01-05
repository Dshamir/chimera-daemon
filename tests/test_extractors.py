"""Tests for extractors."""

import pytest
from pathlib import Path

from chimera.extractors.document import (
    MarkdownExtractor,
    TextExtractor,
)
from chimera.extractors.code import PythonExtractor
from chimera.extractors.registry import get_extractor, get_registry
from chimera.extractors.chunker import TextChunker, CodeChunker


@pytest.mark.asyncio
async def test_text_extractor(sample_text_file):
    """Test text file extraction."""
    extractor = TextExtractor()
    
    assert await extractor.can_handle(sample_text_file)
    
    result = await extractor.extract(sample_text_file)
    
    assert result.success
    assert "Hello, CHIMERA" in result.content
    assert result.metadata["format"] == "text"
    assert result.word_count > 0


@pytest.mark.asyncio
async def test_markdown_extractor(temp_dir):
    """Test markdown file extraction."""
    md_file = temp_dir / "test.md"
    md_file.write_text("# Title\n\nSome content with **bold** text.")
    
    extractor = MarkdownExtractor()
    
    assert await extractor.can_handle(md_file)
    
    result = await extractor.extract(md_file)
    
    assert result.success
    assert "# Title" in result.content
    assert result.metadata["format"] == "markdown"
    assert len(result.metadata["headers"]) == 1


@pytest.mark.asyncio
async def test_python_extractor(sample_python_file):
    """Test Python file extraction."""
    extractor = PythonExtractor()
    
    assert await extractor.can_handle(sample_python_file)
    
    result = await extractor.extract(sample_python_file)
    
    assert result.success
    assert result.metadata["language"] == "python"
    
    # Check code element extraction
    assert len(result.code_elements) >= 1
    
    # Find hello function
    functions = [e for e in result.code_elements if e["element_type"] == "function"]
    assert any(f["name"] == "hello" for f in functions)
    
    # Find Greeter class
    classes = [e for e in result.code_elements if e["element_type"] == "class"]
    assert any(c["name"] == "Greeter" for c in classes)


def test_extractor_registry():
    """Test extractor registry."""
    registry = get_registry()
    
    # Check supported extensions
    extensions = registry.list_supported_extensions()
    assert "txt" in extensions
    assert "md" in extensions
    assert "py" in extensions
    assert "pdf" in extensions
    
    # Get extractor for file
    extractor = get_extractor(Path("test.py"))
    assert extractor is not None
    assert extractor.name == "python"


def test_text_chunker():
    """Test text chunking."""
    chunker = TextChunker(target_tokens=100, max_tokens=200)
    
    # Test with short text
    text = "This is a short paragraph. It should become one chunk."
    chunks = chunker.chunk(text)
    assert len(chunks) >= 1
    
    # Test with longer text
    long_text = "\n\n".join([f"Paragraph {i}. " * 20 for i in range(10)])
    chunks = chunker.chunk(long_text)
    assert len(chunks) > 1
    
    # Check chunk properties
    for chunk in chunks:
        assert chunk.content
        assert chunk.chunk_type
        assert chunk.token_count > 0


def test_code_chunker(sample_python_file):
    """Test code chunking."""
    chunker = CodeChunker()
    
    content = sample_python_file.read_text()
    
    # Chunk with code elements
    code_elements = [
        {"element_type": "function", "name": "hello", "line_start": 4, "line_end": 6},
        {"element_type": "class", "name": "Greeter", "line_start": 8, "line_end": 12},
    ]
    
    chunks = chunker.chunk(content, code_elements)
    assert len(chunks) == 2
    assert "code_function" in chunks[0].chunk_type
    assert "code_class" in chunks[1].chunk_type
