"""Tests for FAE extractors."""

import pytest

from chimera.extractors.fae import (
    ClaudeParser,
    FAEProcessor,
)


def test_claude_parser_detect(sample_claude_export):
    """Test Claude export detection."""
    import json
    
    with open(sample_claude_export) as f:
        data = json.load(f)
    
    parser = ClaudeParser()
    assert parser.detect(data)


def test_claude_parser_parse(sample_claude_export):
    """Test Claude export parsing."""
    import json
    
    with open(sample_claude_export) as f:
        data = json.load(f)
    
    parser = ClaudeParser()
    conversations = parser.parse(data)
    
    assert len(conversations) == 1
    assert conversations[0].title == "Test Conversation"
    assert conversations[0].provider == "claude"
    assert len(conversations[0].messages) == 2
    assert conversations[0].messages[0].role == "human"
    assert conversations[0].messages[1].role == "assistant"


def test_fae_processor_detect(sample_claude_export):
    """Test FAE processor provider detection."""
    processor = FAEProcessor()
    provider = processor.detect_provider(sample_claude_export)
    
    assert provider == "claude"


def test_fae_processor_process(sample_claude_export):
    """Test FAE processor full processing."""
    processor = FAEProcessor()
    result = processor.process(sample_claude_export)
    
    assert result.success
    assert result.provider == "claude"
    assert len(result.conversations) == 1
