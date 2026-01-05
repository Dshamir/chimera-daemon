"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_text_file(temp_dir):
    """Create a sample text file."""
    file_path = temp_dir / "sample.txt"
    file_path.write_text("Hello, CHIMERA! This is a test file.")
    return file_path


@pytest.fixture
def sample_python_file(temp_dir):
    """Create a sample Python file."""
    file_path = temp_dir / "sample.py"
    file_path.write_text('''
"""Sample module."""

def hello(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"

class Greeter:
    """A greeter class."""
    
    def greet(self, name: str) -> str:
        return hello(name)
''')
    return file_path


@pytest.fixture
def sample_claude_export(temp_dir):
    """Create a sample Claude export file."""
    import json
    
    file_path = temp_dir / "conversations.json"
    data = [
        {
            "uuid": "conv-001",
            "name": "Test Conversation",
            "created_at": "2026-01-01T10:00:00Z",
            "updated_at": "2026-01-01T11:00:00Z",
            "chat_messages": [
                {
                    "uuid": "msg-001",
                    "sender": "human",
                    "text": "Hello Claude!",
                    "created_at": "2026-01-01T10:00:00Z",
                },
                {
                    "uuid": "msg-002",
                    "sender": "assistant",
                    "text": "Hello! How can I help you today?",
                    "created_at": "2026-01-01T10:00:30Z",
                },
            ],
        },
    ]
    file_path.write_text(json.dumps(data))
    return file_path
