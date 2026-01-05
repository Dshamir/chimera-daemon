"""Tests for file watcher."""

import pytest

from chimera.config import ChimeraConfig, SourceConfig
from chimera.watcher import ChimeraEventHandler, FileWatcher


def test_event_handler_should_ignore():
    """Test file ignore patterns."""
    source = SourceConfig(path="/test", file_types=["txt", "md"])
    
    changes = []
    def on_change(path, event_type):
        changes.append((path, event_type))
    
    handler = ChimeraEventHandler(
        source=source,
        on_change=on_change,
        exclude_patterns=["*.tmp", "**/.git/**"],
    )
    
    assert handler._should_ignore("test.tmp")
    assert handler._should_ignore("/path/.git/config")
    assert not handler._should_ignore("document.txt")


def test_event_handler_should_process():
    """Test file type filtering."""
    source = SourceConfig(path="/test", file_types=["txt", "md"])
    
    changes = []
    def on_change(path, event_type):
        changes.append((path, event_type))
    
    handler = ChimeraEventHandler(
        source=source,
        on_change=on_change,
        exclude_patterns=[],
    )
    
    assert handler._should_process("document.txt")
    assert handler._should_process("readme.md")
    assert not handler._should_process("image.png")
    assert not handler._should_process("code.py")


def test_fae_trigger_detection():
    """Test FAE trigger file detection."""
    config = ChimeraConfig(sources=[SourceConfig(path="/test")])
    watcher = FileWatcher(config)
    
    from pathlib import Path
    
    assert watcher._is_fae_trigger(Path("conversations.json"))
    assert watcher._is_fae_trigger(Path("claude_export.json"))
    assert watcher._is_fae_trigger(Path("chat_history.json"))
    assert not watcher._is_fae_trigger(Path("config.yaml"))
    assert not watcher._is_fae_trigger(Path("document.pdf"))
