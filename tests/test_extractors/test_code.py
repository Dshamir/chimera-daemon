"""Tests for code extractors."""

import pytest

from chimera.extractors.code import PythonExtractor


@pytest.mark.asyncio
async def test_python_extractor(sample_python_file):
    """Test Python file extraction."""
    extractor = PythonExtractor()
    
    assert await extractor.can_handle(sample_python_file)
    
    result = await extractor.extract(sample_python_file)
    
    assert result.success
    assert result.metadata["language"] == "python"
    
    # Check function extraction
    functions = result.metadata["functions"]
    assert len(functions) >= 1
    assert any(f["name"] == "hello" for f in functions)
    
    # Check class extraction
    classes = result.metadata["classes"]
    assert len(classes) >= 1
    assert any(c["name"] == "Greeter" for c in classes)
