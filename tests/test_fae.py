"""Tests for FAE extractors."""

import json
import pytest

from chimera.extractors.fae import (
    ClaudeParser,
    ChatGPTParser,
    FAEProcessor,
)


def test_claude_parser_detect(sample_claude_export):
    """Test Claude export detection."""
    with open(sample_claude_export) as f:
        data = json.load(f)
    
    parser = ClaudeParser()
    assert parser.detect(data)


def test_claude_parser_parse(sample_claude_export):
    """Test Claude export parsing."""
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


def test_chatgpt_parser_detect(temp_dir):
    """Test ChatGPT export detection."""
    # Create ChatGPT format export
    chatgpt_file = temp_dir / "chatgpt.json"
    data = [
        {
            "id": "conv-123",
            "title": "Test Chat",
            "create_time": 1704067200.0,
            "update_time": 1704070800.0,
            "mapping": {
                "node-1": {
                    "message": {
                        "id": "msg-1",
                        "author": {"role": "user"},
                        "content": {"parts": ["Hello!"]},
                        "create_time": 1704067200.0,
                    }
                },
                "node-2": {
                    "message": {
                        "id": "msg-2",
                        "author": {"role": "assistant"},
                        "content": {"parts": ["Hi there!"]},
                        "create_time": 1704067230.0,
                    }
                },
            },
        }
    ]
    chatgpt_file.write_text(json.dumps(data))
    
    parser = ChatGPTParser()
    assert parser.detect(data)
    
    # Parse it
    conversations = parser.parse(data)
    assert len(conversations) == 1
    assert conversations[0].title == "Test Chat"
    assert len(conversations[0].messages) == 2


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


def test_fae_processor_invalid_file(temp_dir):
    """Test FAE processor with invalid file."""
    invalid_file = temp_dir / "invalid.json"
    invalid_file.write_text("not valid json")
    
    processor = FAEProcessor()
    result = processor.process(invalid_file)
    
    assert not result.success
    assert "Invalid JSON" in result.error


def test_fae_processor_unknown_format(temp_dir):
    """Test FAE processor with unknown format."""
    unknown_file = temp_dir / "unknown.json"
    unknown_file.write_text(json.dumps({"random": "data"}))
    
    processor = FAEProcessor()
    result = processor.process(unknown_file)
    
    assert not result.success
    assert "Could not detect" in result.error
